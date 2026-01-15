# README.v0 (Archived)

Archived: This README describes the pre-v1 backend-first Eval Ops Platform. See README.md for the current UI-first explainable prototype.

# Eval Ops Platform

**AI-First Evaluation Operations Platform** — Turn evaluation work into compiled workflows with evidence-gated decisions.

## 🎯 What This Is

This platform eliminates "simulated verification" in LLM evaluation tasks by:

1. **Compiling guidelines into workflows** — Parses evaluation docs into structured, executable workflows
2. **Enforcing evidence gates** — Cannot submit decisions without required artifacts (screenshots, citations, ledgers)
3. **Automated verification** — Pluggable verifiers check every submission before acceptance
4. **Full audit trails** — Every action is logged with evidence, timestamps, and rationale

## 🏗️ Architecture

### Core Primitives

- **Task** — A unit of work with explicit inputs, instructions, and required artifacts
- **Workflow** — A DAG of steps that execute with verifiers at each gate
- **Artifact** — Evidence (screenshots, ledgers, citations, diffs) that backs every decision
- **Verifier** — Deterministic rules that prevent "simulated verification"

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Workflow   │  │   Verifier   │  │   Artifact   │      │
│  │   Compiler   │  │    Engine    │  │    Store     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              REST API Endpoints                       │   │
│  │  /workflows  /tasks  /artifacts  /executions         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  Organizations  Workspaces  Rubrics  Workflows  Tasks       │
│  Artifacts  Executions  Verifications  Adjudications        │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)

### Setup

1. **Clone and navigate**
   ```bash
   cd eval-ops-platform
   ```

2. **Create environment file**
   ```bash
   cp backend/.env.example backend/.env
   ```

3. **Start the stack**
   ```bash
   docker-compose up -d
   ```

4. **Run migrations**
   ```bash
   docker-compose exec backend python -m app.db.migrations.001_initial
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Database: postgresql://postgres:postgres@localhost:5432/evalops
   - Ingestion UI: http://localhost:8000/ingest

## 📖 API Usage

### 1. Compile a Workflow from Guidelines

```bash
curl -X POST http://localhost:8000/api/v1/workflows/compile \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws-001",
    "guideline_text": "1. Take screenshot at 18z zoom\n2. Verify building number matches\n3. Rate accuracy",
    "workflow_name": "Map Verification",
    "task_type": "verify"
  }'
```

**Response:**
```json
{
  "workflow": {
    "id": "wf-123",
    "name": "Map Verification",
    "steps": [
      {
        "step_id": "step-1",
        "type": "capture",
        "produces": "screenshot",
        "verifiers": ["screenshot_required", "screenshot_hash_valid"]
      },
      {
        "step_id": "step-2",
        "type": "extract",
        "produces": "observation_ledger",
        "verifiers": ["ledger_complete"]
      },
      {
        "step_id": "step-3",
        "type": "rate",
        "produces": "decision",
        "verifiers": ["evidence_gated_decision", "banned_phrases"]
      }
    ]
  },
  "compiler_notes": {
    "verifier_rules": {
      "required_artifacts": ["screenshot at 18z zoom"],
      "citation_requirements": {},
      "field_requirements": ["building number"]
    },
    "banned_phrases": []
  }
}
```

### 2. Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "wf-123",
    "rubric_id": "rubric-001",
    "task_type": "verify",
    "inputs": {
      "query": "123 Main St",
      "map_url": "https://maps.example.com/..."
    },
    "instructions": "Verify the pin placement for this address",
    "required_artifacts": ["screenshot", "observation_ledger", "decision"]
  }'
```

### 3. Upload Artifact (Evidence Gate)

```bash
curl -X POST http://localhost:8000/api/v1/artifacts/upload \
  -F "task_id=task-456" \
  -F "artifact_type=screenshot" \
  -F "file=@screenshot.png"
```

### 4. Submit Execution (Verification Gate)

```bash
curl -X POST http://localhost:8000/api/v1/executions/exec-789/submit \
  -H "Content-Type: application/json" \
  -d '{
    "decision": {
      "rating": "accurate",
      "rationale": "Building number verified in screenshot artifact-123. Pin placement matches observed rooftop.",
      "confidence": 0.95
    },
    "trace": {
      "zoom_level": 18,
      "screenshot_timestamp": "2024-01-03T10:30:00Z"
    }
  }'
```

**Success (all verifiers pass):**
```json
{
  "id": "exec-789",
  "task_id": "task-456",
  "decision": { ... },
  "completed_at": "2024-01-03T10:31:00Z"
}
```

**Failure (verification failed):**
```json
{
  "error": "Verification failed",
  "verification_results": {
    "all_passed": false,
    "results": [
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

### 5. Ingest raw Haiku output

Use the minimal UI at `/ingest` or call the API directly:

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{ "raw_text": "DEBUG INFO: query=Coffee\nRATINGS TABLE: Pin Accuracy | Correct | Clear storefront\nERRORS: 1 | field: Pin Accuracy | to: Incorrect | rationale: different business"}'
```

**Response**
```json
{
  "submission_id": "6f8c1c4e-b4ad-4f4a-bd4b-64c0957d0123",
  "parsed": {
    "debug_info": { ... },
    "ratings_table": [{ "field": "Pin Accuracy", "answer": "Correct", "details": "Clear storefront" }],
    "errors": [{ "field": "Pin Accuracy", "rationale_text": "different business" }],
    "artifact_refs": []
  },
  "patch_preview": "--- /app/rubrics/maps_evaluation.md\n+++ /app/rubrics/maps_evaluation.md (patched)\n@@\n ## Additional Rules\n- If visible label on satellite conflicts with result name \u2192 Pin Accuracy = Wrong",
  "verifier_violations": [
    {
      "verifier": "observation_specificity",
      "passed": false,
      "violations": [
        { "reason": "Rationale too short (8 words, expected at least 10)", "rule": "observation_specificity", "field": "rationale" }
      ]
    }
  ]
}
```

## 🔧 Core Services

### Workflow Compiler

**Purpose:** Parse evaluation guidelines into structured workflows

**Location:** `app/services/workflow_compiler.py`

**Example:**
```python
from app.services.workflow_compiler import compile_workflow_from_guideline

workflow_data = compile_workflow_from_guideline(
    workspace_id="ws-001",
    guideline_text="""
    1. Zoom to satellite view at 18z
    2. Confirm rooftop visible
    3. Verify building number matches query
    4. Rate pin accuracy (must cite screenshot)
    """,
    workflow_name="Pin Verification",
    task_type=TaskType.VERIFY
)
```

### Verifier Engine

**Purpose:** Enforce evidence-gated decisions

**Location:** `app/services/verifier_engine.py`

**Built-in Verifiers:**
- `screenshot_required` — Screenshot artifact must exist
- `ledger_complete` — Observation ledger has required structure
- `evidence_required` — Evidence pack contains citations
- `citations_required` — Minimum citation count, valid source refs
- `evidence_gated_decision` — Decision references only observed facts
- `banned_phrases` — No prohibited language in rationale
- `required_fields` — All required decision fields present
- `diff_complete` — Diff artifact has before/after/changes
- `screenshot_hash_valid` — Screenshot has valid content hash

**Example:**
```python
from app.services.verifier_engine import verify_execution

result = verify_execution(
    execution_id="exec-123",
    artifacts=[...],
    execution={"decision": {...}},
    verifier_names=["screenshot_required", "evidence_gated_decision"]
)

if not result['all_passed']:
    # Reject submission
    raise ValidationError(result)
```

### Artifact Store

**Purpose:** Manage artifact storage (local or S3)

**Location:** `app/services/artifact_store.py`

**Supports:**
- Local filesystem storage
- S3-compatible object storage (AWS S3, MinIO)
- Content hashing (SHA-256)
- Metadata management

## 🎯 Use Cases

### 1. LLM Evaluation Ops

Turn evaluation guidelines into workflows with automatic verification:
- Map search quality evaluation
- Content moderation scoring
- Preference ranking tasks
- Code review annotation

### 2. Rubric Evolution

Track which rubric clauses generate disputes:
```bash
curl http://localhost:8000/api/v1/verifications/failed/summary
```

### 3. Inter-Rater Reliability

Measure agreement across human evaluators:
```bash
curl http://localhost:8000/api/v1/adjudications/analytics/agreement-rate
```

### 4. Model Evaluation Regression

Run the same task suite across model versions:
- Create gold set tasks with locked answers
- Execute against multiple models
- Compare verification pass rates

## 📊 Database Schema

```
organizations
├── workspaces
    ├── rubrics (versioned evaluation criteria)
    └── workflows (compiled from guidelines)
        └── tasks
            ├── artifacts (evidence: screenshots, ledgers, etc.)
            └── task_executions
                ├── verification_results
                └── adjudication_sessions
```

## 🛠️ Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
cd backend
pip install -r requirements.txt

# Set up environment
cp .env.example .env

# Run database (requires Docker)
docker-compose up -d db

# Run migrations
python -m app.db.migrations.001_initial

# Start server
uvicorn app.main:app --reload
```

### Project Structure

```
eval-ops-platform/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   │   ├── workflows.py
│   │   │   ├── tasks.py
│   │   │   ├── artifacts.py
│   │   │   ├── executions.py
│   │   │   ├── verifications.py
│   │   │   └── adjudications.py
│   │   ├── core/             # Config, database, auth
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── workflow_compiler.py
│   │   │   ├── verifier_engine.py
│   │   │   └── artifact_store.py
│   │   └── db/               # Migrations
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## 🚦 Roadmap

### MVP (Current)
- ✅ Workflow compilation from guidelines
- ✅ Evidence-gated task execution
- ✅ Pluggable verifier system
- ✅ Artifact storage (local + S3)
- ✅ Adjudication support

### Post-MVP
- [ ] Regression harness (run tasks across model versions)
- [ ] Gold set management (curated tasks with locked answers)
- [ ] Active learning (sample high-uncertainty tasks)
- [ ] Rubric evolution tracking (which clauses cause disputes)
- [ ] Model-run integration (AI-generated outputs for human verification)
- [ ] Frontend task runner UI
- [ ] Langfuse/OpenTelemetry trace integration

## 📝 License

MIT

## 🤝 Contributing

Built for LLM evaluation teams. PRs welcome.

---

**Key Innovation:** This platform turns "trust me, I verified it" into "here's the screenshot hash and observation ledger" — making evaluation work auditable, reproducible, and free from simulated verification.
