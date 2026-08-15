import os
import time
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load live environment variables from .env
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import db, Exam
from clients.pioneer_client import PioneerClient
from clients.terac_client import TeracClient
from clients.lovable_client import LovableClient
from clients.stripe_manager import StripeManager
from clients.linq_client import LinqClient
from clients.sandbox_runner import SandboxRunner
from clients.presentation_adapter import PresentationAdapterFactory
from clients.logger import get_logs, log_integration
from clients.terac_poller import TeracPoller, log_terac_submission_to_file

from organizers.routes import router as organizer_router
from candidates.routes import router as candidate_router

app = FastAPI(
    title="Zero-Human Autonomous Assessment Platform",
    description="End-to-end autonomous technical exam creation, validation, monetization, and sandbox execution.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Clients
pioneer_client = PioneerClient()
terac_client = TeracClient()
lovable_client = LovableClient()
stripe_manager = StripeManager()
linq_client = LinqClient()
sandbox_runner = SandboxRunner()
terac_poller = TeracPoller(terac_client, lovable_client, stripe_manager)

# Include Modular Feature Routers
app.include_router(organizer_router)
app.include_router(candidate_router)

@app.on_event("startup")
async def start_background_poller():
    print("🚀 [Main] Launching Terac expert submission background listener...")
    asyncio.create_task(terac_poller.start_polling_loop(interval_seconds=10, target_opp_id="pvvwd034orh6rf7bhm2hecjw"))

# Mount Static Files
public_dir = os.path.join(os.path.dirname(__file__), "public")
if not os.path.exists(public_dir):
    os.makedirs(public_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=public_dir), name="static")

@app.get("/api/logs")
async def get_integration_logs():
    """Returns recent external integration HTTP request/response log stream."""
    return {"logs": get_logs()}

@app.get("/api/exams")
async def list_exams():
    """Returns all exams and organizer overview stats."""
    exams = db.list_exams()
    adapter = PresentationAdapterFactory.get_adapter(lovable_client)
    return {
        "presentation_adapter": adapter.get_adapter_type(),
        "total_revenue_dollars": db.total_revenue_cents / 100.0,
        "active_exams_count": sum(1 for e in exams if e.status in ("ACTIVE", "VERIFIED")),
        "verified_rubrics_count": sum(1 for e in exams if e.status in ("VERIFIED", "ACTIVE", "COMPLETED", "RESULTS_RELEASED")),
        "exams": [e.model_dump() for e in exams]
    }

@app.get("/api/exams/{exam_id}")
async def get_exam(exam_id: str, token: Optional[str] = Query(None), is_organizer: Optional[bool] = Query(False)):
    """Retrieves single exam by ID, strictly validating candidate payment token."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    if not is_organizer:
        if not token:
            raise HTTPException(status_code=402, detail="Stripe Payment Required: Missing candidate access token. Please complete signup and Stripe payment.")
        
        entry = db.is_allowlisted(exam_id, token)
        if not entry:
            raise HTTPException(status_code=402, detail="Stripe Payment Required: Invalid or unpaid candidate token.")

    return exam.model_dump()

# ==================== WEBHOOK ROUTERS ====================

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Processes Stripe checkout.session.completed webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    entry = stripe_manager.process_webhook_event(payload, sig_header)
    if entry:
        await linq_client.send_exam_access(
            phone_number=entry.phone_number,
            exam_id=entry.exam_id,
            candidate_token=entry.candidate_token
        )
        return {"status": "success", "candidate_token": entry.candidate_token}

    return {"status": "ignored"}

@app.post("/webhooks/linq")
async def linq_webhook(request: Request):
    """Processes incoming candidate SMS via Linq webhook."""
    payload = await request.json()
    reply_msg = linq_client.process_incoming_sms(payload)
    return {"status": "replied", "message": reply_msg}

@app.post("/webhooks/terac")
async def terac_webhook(request: Request):
    """Processes Terac opportunity.submission.completed webhooks."""
    payload = await request.json()
    event = payload.get("event")
    data = payload.get("data", {})
    sub_data = data if data else payload

    status = sub_data.get("status") or payload.get("status")
    if status and status != "COMPLETED":
        return {"status": "ignored", "reason": f"Non-completed status '{status}'"}

    opp_id = payload.get("opportunity_id") or sub_data.get("opportunity_id") or "pvvwd034orh6rf7bhm2hecjw"
    log_terac_submission_to_file(opp_id, sub_data)

    exams = db.list_exams()
    exam = next((e for e in exams if opp_id in (e.terac_opportunity_id or "") or e.id.startswith(opp_id[:8])), None)
    if not exam and len(exams) > 0:
        exam = exams[0]

    if exam:
        exam, diff_summary = terac_client.process_review_result(exam, sub_data)
        ui_config = await lovable_client.generate_ui_config(exam)
        exam.lovable_ui_config = ui_config
        payment_url = stripe_manager.create_payment_link(exam)
        exam.stripe_payment_link = payment_url
        exam.status = "ACTIVE"
        db.update_exam(exam)
        return {
            "status": "success",
            "event": event or "opportunity.submission.completed",
            "exam_id": exam.id,
            "opportunity_id": opp_id,
            "terac_diff": diff_summary,
            "stripe_payment_link": payment_url
        }

    return {"status": "ignored", "reason": "exam not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
