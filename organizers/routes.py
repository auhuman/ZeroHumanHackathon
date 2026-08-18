import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from database import db, Exam
from clients.pioneer_client import PioneerClient
from clients.terac_client import TeracClient
from clients.lovable_client import LovableClient
from clients.stripe_manager import StripeManager
from clients.presentation_adapter import PresentationAdapterFactory

router = APIRouter()

organizer_dir = os.path.dirname(__file__)
pioneer_client = PioneerClient()
terac_client = TeracClient()
lovable_client = LovableClient()
stripe_manager = StripeManager()

class CreateExamRequest(BaseModel):
    topic: str
    level: str = "Intermediate"
    time_limit: int = 45
    price_dollars: float = 15.0

class TeracCallbackRequest(BaseModel):
    exam_id: str
    terac_task_id: str
    verified_rubric: Optional[Dict[str, Any]] = None

@router.get("/", response_class=HTMLResponse)
@router.get("/organizer", response_class=HTMLResponse)
@router.get("/orgnizer", response_class=HTMLResponse)
async def serve_organizer_dashboard():
    """Serves the Organizer Dashboard SPA under /organizer."""
    index_path = os.path.join(organizer_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
@router.post("/api/exams/clear")
async def clear_database():
    """Clears all exams, submissions, and allowlists from memory and storage."""
    db.clear_all()
    return {"status": "success", "message": "Database reset to empty state."}

@router.get("/api/exams/{exam_id}/presentation")
async def get_exam_presentation(exam_id: str):
    """Returns dynamic theme & layout config for the presentation adapter."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    adapter = PresentationAdapterFactory.get_adapter(lovable_client)
    layout = await adapter.render_exam_theme_and_layout(exam)
    return {
        "exam_id": exam_id,
        "presentation_adapter": adapter.get_adapter_type(),
        "layout_config": layout
    }

async def _process_terac_and_stripe_pipeline(exam: Exam):
    """Background task to launch Terac opportunity live, sync Lovable UI, and create Stripe Payment Link."""
    try:
        terac_task_id = await terac_client.submit_for_review(exam)
        exam, diff_summary = terac_client.process_review_result(exam)
        
        ui_config = await lovable_client.generate_ui_config(exam)
        exam.lovable_ui_config = ui_config
        
        payment_url = stripe_manager.create_payment_link(exam)
        exam.stripe_payment_link = payment_url
        exam.status = "VERIFIED"
        db.update_exam(exam)
    except Exception as e:
        print(f"[Main Pipeline Exception]: {e}")

@router.post("/api/exams/create")
async def create_exam(req: CreateExamRequest, background_tasks: BackgroundTasks):
    """Ingests topic -> calls Pioneer AI -> dispatches Terac MCP & Stripe pipeline."""
    price_cents = int(req.price_dollars * 100) if req.price_dollars else 1500
    exam = await pioneer_client.generate_exam(req.topic, req.level, req.time_limit, price_cents=price_cents)
    exam.status = "IN_REVIEW"
    db.create_exam(exam)

    background_tasks.add_task(_process_terac_and_stripe_pipeline, exam)

    return {
        "status": "success",
        "exam_id": exam.id,
        "terac_task_id": f"terac_opp_{exam.id[:8]}",
        "exam": exam.model_dump()
    }

@router.post("/api/exams/terac-callback")
async def terac_callback(req: TeracCallbackRequest):
    """Receives Terac verified rubric -> syncs Lovable UI -> generates Stripe link -> state VERIFIED."""
    exam = db.get_exam(req.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    exam, diff_summary = terac_client.process_review_result(exam, req.verified_rubric)
    
    ui_config = await lovable_client.generate_ui_config(exam)
    exam.lovable_ui_config = ui_config
    
    payment_url = stripe_manager.create_payment_link(exam)
    exam.stripe_payment_link = payment_url
    exam.status = "VERIFIED"
    db.update_exam(exam)

    return {
        "status": "verified",
        "exam_id": exam.id,
        "payment_link": payment_url,
        "terac_diff": diff_summary
    }

@router.post("/api/exams/{exam_id}/start")
async def start_exam(exam_id: str):
    """Organizer starts the exam: transitions status from VERIFIED to ACTIVE and dispatches Linq SMS notifications to candidates."""
    from clients.linq_client import LinqClient
    linq_client = LinqClient()

    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    exam.status = "ACTIVE"
    db.update_exam(exam)

    dispatched = []
    for entry in db.allowlist:
        if entry.exam_id == exam_id:
            res = await linq_client.send_exam_access(
                phone_number=entry.phone_number or "+15550199",
                exam_id=exam_id,
                candidate_token=entry.candidate_token
            )
            dispatched.append({"email": entry.candidate_email, "phone": entry.phone_number, "sms_result": res})

    return {
        "status": "started",
        "exam_id": exam_id,
        "exam_status": exam.status,
        "sms_dispatched_count": len(dispatched),
        "dispatches": dispatched
    }

@router.post("/api/exams/{exam_id}/end")
async def end_exam(exam_id: str):
    """Organizer ends active exam: transitions status from ACTIVE to COMPLETED."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    exam.status = "COMPLETED"
    db.update_exam(exam)

    return {
        "status": "completed",
        "exam_id": exam_id,
        "exam_status": exam.status
    }

@router.get("/api/exams/{exam_id}/candidates")
async def get_subscribed_candidates(exam_id: str):
    """Returns list of subscribed/registered candidates for an exam."""
    candidates = [
        entry.model_dump() for entry in db.allowlist
        if entry.exam_id == exam_id
    ]
    return {
        "exam_id": exam_id,
        "subscribed_count": len(candidates),
        "candidates": candidates
    }

@router.post("/api/exams/{exam_id}/release-results")
async def release_exam_results(exam_id: str):
    """Releases official assessment scores and dispatches Linq SMS notifications to candidates."""
    from clients.linq_client import LinqClient
    linq_client = LinqClient()

    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    exam.results_released = True
    exam.status = "RESULTS_RELEASED"
    db.update_exam(exam)

    leaderboard = db.get_leaderboard(exam_id)
    rank_map = {item["candidate_email"]: item for item in leaderboard}

    dispatched = []
    for entry in db.allowlist:
        if entry.exam_id == exam_id:
            score_info = rank_map.get(entry.candidate_email)
            score_text = f"{score_info['score']:.1f}% (Rank #{score_info['rank']})" if score_info else "Completed"
            
            res = await linq_client.send_exam_access(
                phone_number=entry.phone_number or "+15550199",
                exam_id=exam_id,
                candidate_token=entry.candidate_token
            )
            dispatched.append({"email": entry.candidate_email, "phone": entry.phone_number, "score_info": score_text, "sms_result": res})

    return {
        "status": "results_released",
        "exam_id": exam_id,
        "results_released": True,
        "sms_dispatched_count": len(dispatched),
        "dispatches": dispatched
    }

@router.post("/api/exams/{exam_id}/mock-terac-review")
async def mock_terac_review(exam_id: str):
    """Simulates an expert completing review on Terac."""
    exam = db.get_exam(exam_id)
    if not exam:
        exams = db.list_exams()
        if exams:
            exam = exams[0]
        else:
            raise HTTPException(status_code=404, detail="Exam not found")

    mock_payload = terac_client.generate_mock_submission(exam)
    
    from clients.terac_poller import log_terac_submission_to_file
    log_terac_submission_to_file(exam.terac_opportunity_id or "pvvwd034orh6rf7bhm2hecjw", mock_payload)

    exam, diff_summary = terac_client.process_review_result(exam, mock_payload)
    ui_config = await lovable_client.generate_ui_config(exam)
    exam.lovable_ui_config = ui_config
    payment_url = stripe_manager.create_payment_link(exam)
    exam.stripe_payment_link = payment_url
    exam.status = "VERIFIED"
    db.update_exam(exam)

    return {
        "status": "mock_review_completed",
        "event": "opportunity.submission.completed",
        "exam_id": exam.id,
        "terac_submission": mock_payload,
        "terac_diff": diff_summary,
        "stripe_payment_link": payment_url
    }
