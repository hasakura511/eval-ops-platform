# Bottom-Up Office-Work Automation Framework (TODO)

## Goal
Plan a bottom-up automation framework for office work in high-inertia environments, with stable pipeline structure and continuously updated parameters.

## Scope
- Office workflows: evaluation, analysis, compliance, clerical, coordination.
- Focus on Japan-first deployment constraints (process-heavy, documentation-driven roles).

## Pipeline (invariant)
1. Instruction ingestion
2. Guideline interpretation
3. Learning phase (rubric → signals)
4. Do-by-learning execution
5. Decision output (confidence + rationale)
6. Review and verification
7. Feedback incorporation (parameter updates only)

## Translation Layer (context packaging)
- Parse artifacts into minimal, high-signal packets.
- Strip boilerplate and irrelevant metadata.
- Preserve intent, constraints, and preference gradients.
- Emit source handles for traceability.

## Subjectivity Handling
- Model preference gradients explicitly.
- Use rubric-based correctness scoring.
- Support fuzzy classes: better / worse / acceptable / unacceptable.
- Produce confidence intervals per criterion.

## Verification & Accountability
- Trace claims to guideline references.
- Flag unsupported claims and hallucinations.
- Prefer deterministic checks; fallback to reviewer models.
- Keep verification outside the main LLM reasoning loop.

## Bayesian / Evolutionary Updating
- Maintain priors per task and criterion.
- Update weights from outcomes without changing pipeline structure.
- Preserve historical context and decision lineage.

## Deployment (Japan-First)
- Target process-heavy office roles with high documentation load.
- Start with narrow, low-visibility sub-tasks:
  - Document triage
  - Template completion
  - Checklist verification
  - Standardized summary generation

## TODO Plan
- [ ] Draft a textual pipeline diagram with input/output contracts.
- [ ] Define translation layer schema (fields + source handle format).
- [ ] Specify rubric model (weights, thresholds, confidence output).
- [ ] Design verification checks (deterministic + reviewer model gates).
- [ ] Outline Bayesian update algorithm (priors, decay, selection).
- [ ] Enumerate failure modes and mitigations.
- [ ] Map initial target roles and tasks for pilot deployment.
- [ ] Produce component-by-component write-up in final format.
