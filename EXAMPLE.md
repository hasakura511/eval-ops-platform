# Example: Maps Search Quality Evaluation Workflow

This demonstrates how to use the Eval Ops Platform for your Maps Search Quality evaluation tasks.

## Scenario

You're evaluating map search results and need to ensure evaluators:
1. Take screenshots at correct zoom levels
2. Record what they can/cannot verify
3. Don't make claims without evidence
4. Rate accuracy based only on observed facts

## Step 1: Compile Workflow from Guidelines

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/workflows/compile \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws-default",
    "guideline_text": "Map Search Quality Evaluation Guidelines\n\n1. Zoom to satellite view at 18z\n2. Take screenshot showing the pin location\n3. Confirm rooftop is visible in the satellite imagery\n4. Verify building number matches the query address\n5. Record observations: what you can verify vs. what you cannot verify\n6. Do not use phrases like \"looks like\" or \"probably\" - only state what you can confirm\n7. Rate pin placement accuracy based on your observations\n8. Your rating must reference specific observations from the screenshot\n\nRequired Evidence:\n- Screenshot at 18z zoom showing pin and rooftop\n- Observation ledger with verified facts and cannot-verify items\n- Rating decision that cites specific screenshot artifacts",
    "workflow_name": "Maps Pin Verification",
    "task_type": "verify"
  }'
```

**Response:**
```json
{
  "workflow": {
    "id": "wf-maps-pin-001",
    "name": "Maps Pin Verification",
    "steps": [
      {
        "step_id": "step-capture",
        "type": "capture",
        "produces": "screenshot",
        "verifiers": ["screenshot_required", "screenshot_hash_valid"]
      },
      {
        "step_id": "step-extract",
        "type": "extract",
        "requires": ["step-capture"],
        "produces": "observation_ledger",
        "verifiers": ["ledger_complete"]
      },
      {
        "step_id": "step-rate",
        "type": "rate",
        "requires": ["step-extract"],
        "produces": "decision",
        "verifiers": ["evidence_gated_decision", "banned_phrases"]
      }
    ]
  },
  "compiler_notes": {
    "verifier_rules": {
      "required_artifacts": [
        "screenshot at 18z zoom showing pin and rooftop",
        "observation ledger with verified facts"
      ],
      "field_requirements": ["building number", "rooftop visible"]
    },
    "banned_phrases": ["looks like", "probably"]
  }
}
```

## Step 2: Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "wf-maps-pin-001",
    "rubric_id": "rubric-maps-001",
    "task_type": "verify",
    "inputs": {
      "query": "1600 Amphitheatre Parkway, Mountain View, CA",
      "map_url": "https://www.google.com/maps/...",
      "expected_coordinates": [37.4220, -122.0841]
    },
    "instructions": "Verify the pin placement accuracy for the Google headquarters address. Check if the pin is placed on the correct building.",
    "required_artifacts": ["screenshot", "observation_ledger", "decision"]
  }'
```

**Response:**
```json
{
  "id": "task-001",
  "workflow_id": "wf-maps-pin-001",
  "status": "pending",
  "instructions": "Verify the pin placement accuracy...",
  "required_artifacts": ["screenshot", "observation_ledger", "decision"]
}
```

## Step 3: Start Execution

```bash
curl -X POST http://localhost:8000/api/v1/executions \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-001",
    "executor_id": "evaluator-jay",
    "executor_type": "human"
  }'
```

**Response:**
```json
{
  "id": "exec-001",
  "task_id": "task-001",
  "executor_id": "evaluator-jay",
  "started_at": "2024-01-03T10:00:00Z"
}
```

## Step 4: Upload Screenshot (Evidence Gate)

```bash
# Take screenshot at 18z zoom, save as screenshot.png
curl -X POST http://localhost:8000/api/v1/artifacts/upload \
  -F "task_id=task-001" \
  -F "artifact_type=screenshot" \
  -F "file=@screenshot.png"
```

**Response:**
```json
{
  "id": "artifact-screenshot-001",
  "task_id": "task-001",
  "artifact_type": "screenshot",
  "content_hash": "a1b2c3d4e5f6...",
  "size_bytes": 245678,
  "metadata": {
    "filename": "screenshot.png",
    "zoom_level": 18
  }
}
```

## Step 5: Create Observation Ledger

```bash
curl -X POST http://localhost:8000/api/v1/artifacts \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-001",
    "artifact_type": "observation_ledger",
    "data": {
      "observations": [
        {
          "fact": "Rooftop clearly visible in satellite view",
          "source": "artifact-screenshot-001",
          "verified": true
        },
        {
          "fact": "Building has distinctive oval shape",
          "source": "artifact-screenshot-001",
          "verified": true
        },
        {
          "fact": "Pin placed on center of main building",
          "source": "artifact-screenshot-001",
          "verified": true
        }
      ],
      "cannot_verify": [
        {
          "claim": "Building number not visible in satellite imagery",
          "reason": "Text too small at 18z zoom"
        }
      ]
    }
  }'
```

**Response:**
```json
{
  "id": "artifact-ledger-001",
  "task_id": "task-001",
  "artifact_type": "observation_ledger",
  "data": {
    "observations": [...],
    "cannot_verify": [...]
  }
}
```

## Step 6: Submit Execution (Verification Gate)

### ✅ GOOD SUBMISSION (Passes All Verifiers)

```bash
curl -X POST http://localhost:8000/api/v1/executions/exec-001/submit \
  -H "Content-Type: application/json" \
  -d '{
    "decision": {
      "rating": "accurate",
      "rationale": "Pin placement is accurate. In screenshot artifact-screenshot-001, the rooftop is clearly visible and matches the distinctive oval shape of Google'\''s main building. The pin is placed on the center of the main building structure. While I cannot verify the building number from the satellite imagery, the building shape and location match the expected coordinates.",
      "confidence": 0.9,
      "rating_scale": {
        "accurate": "Pin placed on correct building",
        "approximate": "Pin near correct building",
        "inaccurate": "Pin on wrong building"
      }
    },
    "trace": {
      "zoom_level_verified": 18,
      "screenshot_timestamp": "2024-01-03T10:15:00Z",
      "verification_steps": [
        "Zoomed to 18z satellite view",
        "Captured screenshot artifact-screenshot-001",
        "Verified rooftop visible",
        "Confirmed pin placement on main building"
      ]
    }
  }'
```

**Response:**
```json
{
  "id": "exec-001",
  "task_id": "task-001",
  "decision": {...},
  "completed_at": "2024-01-03T10:20:00Z",
  "status": "verified"
}
```

### ❌ BAD SUBMISSION (Fails Verification)

```bash
curl -X POST http://localhost:8000/api/v1/executions/exec-002/submit \
  -H "Content-Type: application/json" \
  -d '{
    "decision": {
      "rating": "accurate",
      "rationale": "The pin looks like it'\''s probably on the right building. It appears to match the address.",
      "confidence": 0.7
    }
  }'
```

**Response:**
```json
{
  "error": "Verification failed",
  "verification_results": {
    "all_passed": false,
    "results": [
      {
        "verifier": "banned_phrases",
        "passed": false,
        "violations": [
          {
            "rule": "banned_phrases",
            "field": "rationale",
            "reason": "Banned phrase found: \"looks like\"",
            "evidence": {"phrase": "looks like"}
          },
          {
            "rule": "banned_phrases",
            "field": "rationale",
            "reason": "Banned phrase found: \"probably\"",
            "evidence": {"phrase": "probably"}
          }
        ]
      },
      {
        "verifier": "evidence_gated_decision",
        "passed": false,
        "violations": [
          {
            "rule": "evidence_gated_decision",
            "field": "rationale",
            "reason": "Rationale does not reference artifacts or evidence"
          }
        ]
      }
    ]
  }
}
```

## Step 7: Adjudication (If Needed)

If you have multiple evaluators and need to resolve disagreements:

```bash
curl -X POST http://localhost:8000/api/v1/adjudications \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-001",
    "executions_compared": ["exec-001", "exec-003"],
    "winner_id": "exec-001",
    "reason_tags": ["better_evidence", "clearer_rationale"],
    "notes": "exec-001 provided specific artifact references and avoided speculative language",
    "adjudicator_id": "senior-evaluator"
  }'
```

## Benefits Demonstrated

1. **No Simulated Verification**: Can't submit without screenshot artifact
2. **Evidence-Gated**: Decision must reference specific artifacts
3. **Language Enforcement**: Banned phrases like "probably" are caught
4. **Full Audit Trail**: Every step logged with timestamps and hashes
5. **Reproducible**: Another evaluator can verify by examining artifacts
6. **Scalable**: Same workflow can run for thousands of tasks

## Integration with Your Haiku Prompts

You can integrate this with your Haiku evaluation system:

```python
# In your Haiku prompt evaluation loop
from app.services.verifier_engine import VerifierEngine

verifier = VerifierEngine()

# After Haiku generates a rating
haiku_output = {
    "decision": haiku_response,
    "trace": {"model": "haiku", "timestamp": ...}
}

# Verify the output before accepting
passed, violations = verifier.verify(
    "evidence_gated_decision",
    artifacts=task_artifacts,
    execution=haiku_output
)

if not passed:
    # Regenerate with stronger constraints
    prompt += "\nYour previous response failed verification: " + str(violations)
    haiku_response = anthropic_client.messages.create(...)
```

This ensures Haiku actually checks the evidence instead of taking shortcuts.
