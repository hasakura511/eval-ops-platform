import copy
import os
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from .extract import extract_task
from .schemas import Features, LabeledFeature
from .score import score_features
from .utils import dump_yaml, load_yaml, read_jsonl, safe_filename


def _load_labeled(path: str) -> List[LabeledFeature]:
    rows = read_jsonl(path)
    labeled = []
    for row in rows:
        entry = LabeledFeature.model_validate(row)
        labeled.append(entry)
    return labeled


def _label_of(entry: LabeledFeature) -> str:
    return entry.label or entry.rating or ""


def _compute_metrics(preds: List[str], labels: List[str]) -> Dict[str, object]:
    total = len(labels)
    correct = sum(1 for p, l in zip(preds, labels) if p == l)
    accuracy = correct / total if total else 0.0

    counts = Counter(labels)
    confusion = defaultdict(lambda: Counter())
    for pred, label in zip(preds, labels):
        confusion[label][pred] += 1

    labels_set = sorted(set(labels) | set(preds))
    f1_scores = []
    for label in labels_set:
        tp = confusion[label][label]
        fp = sum(confusion[other].get(label, 0) for other in labels_set if other != label)
        fn = sum(confusion[label].get(other, 0) for other in labels_set if other != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        f1_scores.append(f1)
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "macro_f1": macro_f1,
        "counts": dict(counts),
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def _format_metrics(metrics: Dict[str, object]) -> str:
    lines = []
    lines.append(f"Accuracy: {metrics['accuracy']:.3f} ({metrics['correct']}/{metrics['total']})")
    lines.append(f"Macro-F1: {metrics['macro_f1']:.3f}")
    lines.append("Label counts:")
    for label, count in sorted(metrics["counts"].items()):
        lines.append(f"  {label}: {count}")
    lines.append("Confusion matrix:")
    labels = sorted(metrics["counts"].keys())
    header = "true\\pred," + ",".join(labels)
    lines.append(header)
    for label in labels:
        row = [label]
        for pred in labels:
            row.append(str(metrics["confusion"].get(label, {}).get(pred, 0)))
        lines.append(",".join(row))
    return "\n".join(lines)


def _features_from_labeled(labeled: List[LabeledFeature], cache_dir: Optional[str]) -> Tuple[List[Features], List[str]]:
    features_list = []
    labels = []
    for entry in labeled:
        label = _label_of(entry)
        labels.append(label)
        if entry.features:
            features_list.append(entry.features)
            continue
        if not cache_dir:
            raise ValueError("cache_dir is required when labeled entries do not include features")
        task_dir = os.path.join(cache_dir, safe_filename(entry.task_id))
        features = extract_task(task_dir)
        if not features:
            raise ValueError(f"missing cached features for task_id={entry.task_id}")
        features_list.append(features)
    return features_list, labels


def fit_thresholds(train_path: str, config_in: str, config_out: str,
                   cache_dir: Optional[str] = None) -> Tuple[Dict[str, object], str]:
    config = load_yaml(config_in)
    grid = config.get("fit", {}).get("grid", {})

    thresholds_grid = grid.get("thresholds", {})
    dominance_grid = grid.get("dominance_cutoffs", {})
    weights_grid = grid.get("weights", {})

    perfect_grid = thresholds_grid.get("perfect", [config.get("thresholds", {}).get("perfect", 0.85)])
    good_grid = thresholds_grid.get("good", [config.get("thresholds", {}).get("good", 0.7)])
    acceptable_grid = thresholds_grid.get("acceptable", [config.get("thresholds", {}).get("acceptable", 0.55)])

    dom_perfect_grid = dominance_grid.get("perfect", [config.get("dominance_cutoffs", {}).get("perfect", 0.85)])
    dom_good_grid = dominance_grid.get("good", [config.get("dominance_cutoffs", {}).get("good", 0.7)])
    dom_acceptable_grid = dominance_grid.get("acceptable", [config.get("dominance_cutoffs", {}).get("acceptable", 0.55)])

    match_grid = weights_grid.get("match", [config.get("weights", {}).get("match", 0.5)])
    popularity_grid = weights_grid.get("popularity", [config.get("weights", {}).get("popularity", 0.3)])
    dominance_weight_grid = weights_grid.get("dominance", [config.get("weights", {}).get("dominance", 0.2)])

    labeled = _load_labeled(train_path)
    features_list, labels = _features_from_labeled(labeled, cache_dir)

    best = {"accuracy": -1.0, "config": None}

    for perfect in perfect_grid:
        for good in good_grid:
            for acceptable in acceptable_grid:
                if not (perfect >= good >= acceptable):
                    continue
                for dom_perfect in dom_perfect_grid:
                    for dom_good in dom_good_grid:
                        for dom_acceptable in dom_acceptable_grid:
                            if not (dom_perfect >= dom_good >= dom_acceptable):
                                continue
                            for match in match_grid:
                                for popularity in popularity_grid:
                                    for dominance in dominance_weight_grid:
                                        if abs((match + popularity + dominance) - 1.0) > 0.05:
                                            continue
                                        trial_config = copy.deepcopy(config)
                                        trial_config["thresholds"] = {
                                            "perfect": float(perfect),
                                            "good": float(good),
                                            "acceptable": float(acceptable),
                                        }
                                        trial_config["dominance_cutoffs"] = {
                                            "perfect": float(dom_perfect),
                                            "good": float(dom_good),
                                            "acceptable": float(dom_acceptable),
                                        }
                                        trial_config["weights"] = {
                                            "match": float(match),
                                            "popularity": float(popularity),
                                            "dominance": float(dominance),
                                        }
                                        preds = [score_features(f, trial_config).rating for f in features_list]
                                        metrics = _compute_metrics(preds, labels)
                                        if metrics["accuracy"] > best["accuracy"]:
                                            best = {"accuracy": metrics["accuracy"], "config": trial_config}

    if best["config"]:
        config = best["config"]
        config["fit"] = config.get("fit", {})
        config["fit"]["last_accuracy"] = best["accuracy"]

    preds = [score_features(f, config).rating for f in features_list]
    metrics = _compute_metrics(preds, labels)
    dump_yaml(config_out, config)
    return config, _format_metrics(metrics)
