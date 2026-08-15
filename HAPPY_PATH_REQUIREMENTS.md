# Requirements Document: End-to-End Happy Path Workflow

This document outlines the **Happy Path Requirements** for the **Autonomous Assessment & Competition Agent (Zero-Human Architecture)**. It traces the zero-human lifecycle from initial topic input to final candidate evaluation and leaderboard publishing.

---

## 1. Zero-Human Lifecycle Overview

```
 [Organizer Input]
        │
        ▼
 ┌──────────────┐      ┌─────────────────────────┐      ┌──────────────────────────┐
 │ 1. Pioneer   │ ───> │ 2. Terac Expert Review  │ ───> │ 3. Lovable UI Builder    │
 │ AI Schema    │      │ & Diff Generation       │      │ & Dynamic Frontend Sync  │
 └──────────────┘      └─────────────────────────┘      └────────────┬─────────────┘
                                                                     │
                                                               Stripe Paywall
                                                                     │
                                                                     ▼
 ┌──────────────┐      ┌─────────────────────────┐      ┌──────────────────────────┐
 │ 6. Live      │ <─── │ 5. Evaluation Engine    │ <─── │ 4. Linq SMS Dispatch &   │
 │ Leaderboard  │      │ (Conditional Sandbox)   │      │ Candidate SPA Access     │
 └──────────────┘      └─────────────────────────┘      └──────────────────────────┘
```

---

## 2. Step-by-Step Happy Path Requirements

### Step 1: Exam Generation via Pioneer AI
- **Trigger**: Organizer inputs a topic (e.g., `"Python Async & Concurrency"`), target difficulty (`"Senior"`), and time limit (`45 mins`).
- **Process**:
  - API calls `POST /api/exams/create`.
  - System invokes `PioneerClient.generate_exam(topic, level, time_limit)`.
  - Pioneer returns a structured schema (`exam_id`, `title`, `questions` with deterministic test cases and rubrics).
- **State Transition**: Exam created in state `DRAFT`.

### Step 2: Mandatory Expert Validation via Terac
- **Trigger**: Upon receiving draft exam from Pioneer.
- **Process**:
  - System automatically dispatches the unverified Q&A batch to Terac via `TeracClient.submit_for_review()`.
  - Exam state transitions to `IN_REVIEW`.
  - When Terac reviewer completes validation, Terac posts to `POST /api/exams/terac-callback`.
  - System computes a visual line-by-line diff between original Pioneer JSON vs. Terac-corrected JSON, storing `terac_diff` and rubric improvement metrics.
- **State Transition**: Exam state transitions to `VERIFIED`.

### Step 3: Dynamic UI Customization via Lovable (`services/lovable_client.py`)
- **Trigger**: Exam status transitions to `VERIFIED`.
- **Process**:
  - System invokes `PresentationAdapterFactory.get_adapter()`.
  - Communicates with Lovable MCP Server (`https://mcp.lovable.dev/`) or native browser HTML adapter to generate dynamic, responsive visual exam layouts and styling templates tailored to the exam subject.
  - Generates embeddable component configurations for candidate SPAs.

### Step 4: Monetization & Stripe Allowlist Automation
- **Trigger**: Exam interface generated.
- **Process**:
  - System calls `StripeManager.create_payment_link(exam_id)` to generate a Stripe checkout URL.
  - Exam state transitions to `ACTIVE`.
  - Candidate navigates to registration / payment link.
  - Upon successful payment, Stripe fires `checkout.session.completed` webhook to `POST /webhooks/stripe`.
  - System validates payload, generates a cryptographically secure `candidate_token`, and inserts `{ candidate_email, candidate_token, exam_id }` into the `allowlist` table.

### Step 5: Candidate Access Dispatch via Linq (SMS / iMessage)
- **Trigger**: Successful candidate allowlist insertion.
- **Process**:
  - System invokes `LinqClient.send_exam_access(phone, candidate_token, exam_url)`.
  - Candidate receives an SMS/iMessage with their personalized exam URL: `https://<domain>/take/<exam_id>?token=<candidate_token>`.
  - Candidate clicks link and lands on Candidate Exam SPA (`public/exam.html`).
  - System validates `candidate_token` against `allowlist` before granting exam entry.
  - If candidate replies `"STATUS"` via SMS, `POST /webhooks/linq` responds automatically with remaining time and submission status.

### Step 6: Candidate Execution & Smart Evaluation Routing

> **Conditional Execution Routing**:
> - **MCQ & Short Answer Questions**: Does **NOT** require container provisioning. Evaluated instantly in-memory in $O(1)$ time against the Terac-verified answer key/rubric.
> - **Code Questions**: Ephemeral container runner is provisioned via Superserve API (`https://superserve.ai/`) to execute code safely against test cases.

- **Process**:
  - Dynamic timer starts counting down.
  - For MCQ / Short Answer questions: UI renders option choices or text input; answers are graded immediately against the answer key without server container overhead.
  - For Code questions: UI renders Monaco Editor. Candidate can click **"Run Code"**, which sends the payload to `services/sandbox_runner.py` to provision an ephemeral VM container via Superserve API (`https://superserve.ai/`).
  - Sandbox container executes candidate solution against Terac-verified test suite under strict memory/timeout limits and returns `{ passed_count, total_tests, stdout, stderr, execution_time_ms }`.

### Step 7: Submission, Evaluation & Live Leaderboard
- **Trigger**: Candidate clicks **"Submit Assessment"** or timer expires.
- **Process**:
  - Frontend posts payload to `POST /api/exams/{id}/submit`.
  - System combines in-memory MCQ scores + Sandbox code scores weighted by Terac rubric.
  - Submission score and timestamp stored in `submissions` table.
  - Live Leaderboard (`GET /api/exams/{id}/leaderboard`) updates instantly, ranking candidates by verified test score and completion speed.
  - Organizer Dashboard displays updated active revenue, completion rates, and leaderboard.

---

## 3. Workflow State Machine

| State | Trigger | Output / Artifact |
|---|---|---|
| `DRAFT` | `POST /api/exams/create` called | Initial Pioneer JSON schema |
| `IN_REVIEW` | Dispatched to Terac API / MCP | Pending Terac task/opportunity ID |
| `VERIFIED` | Terac webhook callback received | Visual quality diff & refined rubric stored |
| `ACTIVE` | Lovable UI generated & Stripe Payment Link created | Active payment URL & registered allowlist |
| `COMPLETED` | Exam time window expires | Final published leaderboard & revenue metrics |

---

## 4. Requirement Traceability Matrix to Implementation Plan

| Happy Path Step | Module / Service File | Primary API / Endpoint | Evaluation / Output | Verification Mechanism |
|---|---|---|---|---|
| Step 1: Pioneer Generation | `services/pioneer_client.py` | `POST /api/exams/create` | Schema Validation | `tests/test_pioneer.py` |
| Step 2: Terac Validation | `services/terac_client.py` | `POST /api/exams/terac-callback` | Quality Diff & Rubric | `tests/test_terac.py` |
| Step 3: Lovable / Adapter | `services/presentation_adapter.py` | `GET /api/exams/{id}/presentation` | Dynamic UI Template | `tests/test_presentation_adapter.py` |
| Step 4: Stripe Paywall | `services/stripe_manager.py` | `POST /webhooks/stripe` | Allowlist Token Generation | `tests/test_stripe.py` |
| Step 5: Linq Messaging | `services/linq_client.py` | `POST /webhooks/linq` | SMS Access Dispatch | `tests/test_linq.py` |
| Step 6a: MCQ Evaluation | `main.py` & `database.py` | `POST /api/exams/{id}/submit` | In-Memory Answer Key ($O(1)$) | `tests/test_api_flow.py` |
| Step 6b: Code Sandbox | `services/sandbox_runner.py` | `POST /api/exams/{id}/run-test` | Ephemeral Container (Superserve) | `tests/test_sandbox.py` |
| Step 7: Leaderboard | `main.py` | `GET /api/exams/{id}/leaderboard` | Score & Speed Ranking | `tests/test_api_flow.py` |
