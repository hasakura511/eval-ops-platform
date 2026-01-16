import argparse
import os
from collections import Counter, defaultdict

from .extract import extract_cache
from .fetch import collect
from .fit import fit_thresholds
from .schemas import Features, LabeledFeature
from .score import score_features
from .utils import load_yaml, read_jsonl, safe_filename, write_jsonl


def _load_features(path: str):
    rows = read_jsonl(path)
    return [Features.model_validate(row) for row in rows]


def _load_labeled(path: str):
    rows = read_jsonl(path)
    labeled = []
    for row in rows:
        labeled.append(LabeledFeature.model_validate(row))
    return labeled


def _label_of(entry: LabeledFeature) -> str:
    return entry.label or entry.rating or ""


def _compute_metrics(preds, labels):
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
        "macro_f1": macro_f1,
        "total": total,
        "counts": dict(counts),
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


def _format_metrics(metrics):
    lines = []
    correct = 0
    for label, counts in metrics["confusion"].items():
        correct += counts.get(label, 0)
    lines.append(f"Accuracy: {metrics['accuracy']:.3f} ({correct}/{metrics['total']})")
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


def cmd_collect(args):
    collect(
        input_path=args.input,
        cache_dir=args.cache_dir,
        screenshot=args.screenshot,
        force=args.force,
        collect_alternatives=args.collect_alternatives,
        timeout_ms=args.timeout_ms,
        retries=args.retries,
        user_agent=args.user_agent,
    )


def cmd_extract(args):
    extract_cache(cache_dir=args.cache_dir, out_path=args.out)


def cmd_score(args):
    features_list = _load_features(args.features)
    config = load_yaml(args.config)
    outputs = [score_features(features, config).model_dump() for features in features_list]
    write_jsonl(args.out, outputs)


def cmd_fit(args):
    _, report = fit_thresholds(args.train, args.config_in, args.config_out, cache_dir=args.cache_dir)
    print(report)


def cmd_eval(args):
    labeled = _load_labeled(args.labeled)
    config = load_yaml(args.config)

    preds = []
    labels = []
    for entry in labeled:
        label = _label_of(entry)
        labels.append(label)
        if entry.features:
            features = entry.features
        else:
            if not args.cache_dir:
                raise ValueError("cache_dir is required when labeled entries do not include features")
            task_dir = os.path.join(args.cache_dir, safe_filename(entry.task_id))
            from .extract import extract_task
            features = extract_task(task_dir)
            if not features:
                raise ValueError(f"missing cached features for task_id={entry.task_id}")
        preds.append(score_features(features, config).rating)

    metrics = _compute_metrics(preds, labels)
    print(_format_metrics(metrics))


def build_parser():
    parser = argparse.ArgumentParser(prog="hint_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect", help="Collect HTML for tasks")
    collect_parser.add_argument("--input", required=True)
    collect_parser.add_argument("--cache-dir", required=True)
    collect_parser.add_argument("--screenshot", action="store_true")
    collect_parser.add_argument("--force", action="store_true")
    collect_parser.add_argument("--collect-alternatives", action="store_true",
                                help="Fetch IMDb pages for top query candidates")
    collect_parser.add_argument("--timeout-ms", type=int, default=30000)
    collect_parser.add_argument("--retries", type=int, default=2)
    collect_parser.add_argument("--user-agent", default=None)
    collect_parser.set_defaults(func=cmd_collect)

    extract_parser = sub.add_parser("extract", help="Extract features from cached HTML")
    extract_parser.add_argument("--cache-dir", required=True)
    extract_parser.add_argument("--out", required=True)
    extract_parser.set_defaults(func=cmd_extract)

    score_parser = sub.add_parser("score", help="Score features and output labels")
    score_parser.add_argument("--features", required=True)
    score_parser.add_argument("--config", required=True)
    score_parser.add_argument("--out", required=True)
    score_parser.set_defaults(func=cmd_score)

    fit_parser = sub.add_parser("fit", help="Fit thresholds on labeled data")
    fit_parser.add_argument("--train", required=True)
    fit_parser.add_argument("--config-in", required=True)
    fit_parser.add_argument("--config-out", required=True)
    fit_parser.add_argument("--cache-dir", default=None,
                            help="Cache directory for labeled tasks without features")
    fit_parser.set_defaults(func=cmd_fit)

    eval_parser = sub.add_parser("eval", help="Evaluate labeled data")
    eval_parser.add_argument("--labeled", required=True)
    eval_parser.add_argument("--config", required=True)
    eval_parser.add_argument("--cache-dir", default=None,
                             help="Cache directory for labeled tasks without features")
    eval_parser.set_defaults(func=cmd_eval)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
