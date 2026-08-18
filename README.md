# Zero-Human Autonomous Assessment Platform

An end-to-end autonomous technical assessment, contest, and exam generation platform powered by multi-agent integrations and MCP tools.

---

## 🌟 Overview

The **Zero-Human Autonomous Assessment Platform** automates the entire lifecycle of technical exams—from initial AI schema generation to human expert rubric validation, UI rendering, automated paywalls, candidate SMS dispatch, sandbox code execution, and real-time leaderboard publishing.

```
 [Organizer Topic Input]
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
 │ 6. Live      │ <─── │ 5. Ephemeral Sandbox    │ <─── │ 4. Linq SMS Dispatch &   │
 │ Leaderboard  │      │ Evaluation Engine       │      │ Candidate Access Link    │
 └──────────────┘      └─────────────────────────┘      └──────────────────────────┘
```

---

## 🚀 Key Integrations & Architecture

| Component | Service / Integration | Description |
|---|---|---|
| **AI Question Paper Generation** | **Pioneer AI** | Generates structured exam questions, distractors, rubrics, and test cases based on topic and difficulty. |
| **Human Expert Verification** | **Terac MCP Server** | Submits draft exams to Terac MCP tools (`terac_create_opportunity`, `terac_launch_draft_opportunity`, `terac_list_opportunities`, `terac_delete_opportunity`) for expert rubric verification and visual diff tracking. |
| **Dynamic Frontend UI** | **Lovable MCP Server** | Generates dynamic, topic-tailored UI layouts and Monaco Editor candidate interfaces. |
| **Monetization & Gate** | **Stripe API** | Automated Stripe Checkout Link creation and candidate allowlist verification upon payment. |
| **Candidate Access Dispatch** | **Linq API** | Sends candidate access tokens and personalized exam URLs via SMS / iMessage. |
| **Execution Sandbox** | **Superserve Ephemeral VM** | Ephemeral container execution runner for safe candidate code execution under memory and time limits. |

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Virtual environment (`venv`)

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/auhuman/ZeroHumanHackathon.git
cd ZeroHumanHackathon
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and set your API keys:

```bash
cp .env.example .env
```

`.env` configuration keys:
- `PIONEER_API_KEY`: Pioneer AI service key
- `TERAC_API_KEY`: Terac account API key (`tk_...`)
- `LOVABLE_API_KEY`: Lovable UI builder API key
- `STRIPE_SECRET_KEY`: Stripe API secret key
- `LINQ_API_KEY`: Linq SMS dispatch key
- `SUPERSERVE_API_KEY`: Ephemeral VM Sandbox runner key

---

## 🏃 Running the Application

Start the FastAPI development server:

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access the Web Portals:
- **Organizer Dashboard**: `http://localhost:8000/organizers/index.html`
- **Candidate Portal**: `http://localhost:8000/public/index.html`
- **API Documentation**: `http://localhost:8000/docs`

---

## 🛠️ Utilities

### Terac Account Cleanup Utility

To clean up all draft or active opportunities in your Terac account via Terac MCP:

```bash
python delete_all_terac_opportunities.py
```

Or programmatically in Python:

```python
from clients.terac_client import TeracClient

client = TeracClient()
summary = await client.delete_all_opportunities()
print(f"Deleted {summary['deleted_count']} opportunities.")
```

---

## 🧪 Testing

Run the unit test suite using `pytest`:

```bash
PYTHONPATH=. pytest
```

---

## 📄 License

MIT License.
