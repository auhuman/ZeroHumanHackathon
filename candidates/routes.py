import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from database import db, AllowlistEntry, Submission
from clients.stripe_manager import StripeManager
from clients.linq_client import LinqClient
from clients.sandbox_runner import SandboxRunner

router = APIRouter()

candidate_dir = os.path.dirname(__file__)
stripe_manager = StripeManager()
linq_client = LinqClient()
sandbox_runner = SandboxRunner()

class RegisterCandidateRequest(BaseModel):
    email: str
    phone_number: Optional[str] = None

class SandboxPayRequest(BaseModel):
    exam_id: str
    email: str
    phone_number: Optional[str] = None

class RunTestRequest(BaseModel):
    question_id: str
    code: str

class SubmitExamRequest(BaseModel):
    candidate_token: str
    answers: Dict[str, str]

class GoogleLoginRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None

@router.post("/api/auth/google")
async def google_login(req: GoogleLoginRequest):
    """Processes Google OAuth Sign-in credential token or user profile payload."""
    from clients.auth import parse_google_jwt, GoogleUser
    
    user = None
    if req.credential:
        user = parse_google_jwt(req.credential)

    if not user and req.email:
        user = GoogleUser(
            google_id=f"g_{req.email}",
            email=req.email,
            name=req.name or req.email.split("@")[0],
            picture=req.picture or f"https://api.dicebear.com/7.x/avataaars/svg?seed={req.email}"
        )

    if not user:
        raise HTTPException(status_code=400, detail="Invalid Google authentication credential")

    return {
        "status": "authenticated",
        "provider": "google",
        "user": user.model_dump()
    }

@router.post("/api/candidate/sandbox-pay")
async def process_sandbox_payment(req: SandboxPayRequest):
    """Processes candidate sandbox payment checkout, issues tokenized access pass, and dispatches SMS notification."""
    from clients.sandbox_payment_manager import SandboxPaymentManager
    sandbox_pm = SandboxPaymentManager()

    exam = db.get_exam(req.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    pay_res = sandbox_pm.process_sandbox_payment(
        exam_id=req.exam_id,
        candidate_email=req.email,
        phone_number=req.phone_number or "+15550199"
    )

    if pay_res.get("status") != "success":
        raise HTTPException(status_code=400, detail="Sandbox Payment processing failed")

    token = pay_res["candidate_token"]

    linq_res = await linq_client.send_exam_access(
        phone_number=req.phone_number or "+15550199",
        exam_id=req.exam_id,
        candidate_token=token
    )

    domain = os.getenv("DOMAIN") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
    access_url = f"{domain}/candidate/{req.exam_id}?token={token}"

    return {
        "status": "success",
        "message": "Sandbox Payment Authorized & Settled",
        "receipt_id": pay_res["receipt_id"],
        "candidate_token": token,
        "access_url": access_url,
        "linq_dispatch": linq_res
    }

@router.get("/candidate", response_class=HTMLResponse)
async def serve_candidate_catalog():
    """Serves the Candidate Assessment Catalog SPA under /candidate."""
    catalog_path = os.path.join(candidate_dir, "candidate_catalog.html")
    if os.path.exists(catalog_path):
        return FileResponse(catalog_path)
    return HTMLResponse("<h1>Candidate Portal loading...</h1>")

@router.get("/api/candidate/catalog")
async def get_candidate_catalog():
    """Returns only exams whose Terac review is completed (VERIFIED, ACTIVE, COMPLETED, RESULTS_RELEASED)."""
    all_exams = db.list_exams()
    available_exams = [
        e.model_dump() for e in all_exams
        if e.status in ("VERIFIED", "ACTIVE", "COMPLETED", "RESULTS_RELEASED")
    ]
    return {
        "status": "success",
        "total_available": len(available_exams),
        "exams": available_exams
    }

@router.get("/candidate/{exam_id}", response_class=HTMLResponse)
@router.get("/candidate/take/{exam_id}", response_class=HTMLResponse)
@router.get("/take/{exam_id}", response_class=HTMLResponse)
async def serve_candidate_exam_view(exam_id: str, token: Optional[str] = Query(None)):
    """Serves the Candidate Exam Workspace SPA under /candidate/{exam_id}."""
    exam_path = os.path.join(candidate_dir, "exam.html")
    if os.path.exists(exam_path):
        return FileResponse(exam_path)
    return HTMLResponse("<h1>Candidate Exam View loading...</h1>")

@router.post("/api/exams/{exam_id}/register")
async def register_candidate(exam_id: str, req: RegisterCandidateRequest):
    """Registers candidate, issues tokenized access, and dispatches Linq SMS pass."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    entry = AllowlistEntry(
        exam_id=exam_id,
        candidate_email=req.email,
        phone_number=req.phone_number or "+15550199"
    )
    db.add_to_allowlist(entry)

    linq_res = await linq_client.send_exam_access(
        phone_number=entry.phone_number,
        exam_id=exam_id,
        candidate_token=entry.candidate_token
    )

    domain = os.getenv("DOMAIN") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
    access_url = f"{domain}/candidate/{exam_id}?token={entry.candidate_token}"

    return {
        "status": "registered",
        "candidate_token": entry.candidate_token,
        "access_url": access_url,
        "stripe_payment_link": exam.stripe_payment_link,
        "linq_dispatch": linq_res
    }

@router.post("/api/exams/{exam_id}/run-test")
async def run_test_code(exam_id: str, req: RunTestRequest):
    """Runs candidate code against a question's test cases in Superserve sandbox."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    question = next((q for q in exam.questions if q.id == req.question_id), None)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    test_cases_dicts = [tc.model_dump() for tc in question.test_cases]
    sandbox_result = sandbox_runner.execute_code(req.code, test_cases_dicts)
    return sandbox_result

@router.post("/api/exams/{exam_id}/submit")
async def submit_exam(exam_id: str, req: SubmitExamRequest):
    """Evaluates MCQ in-memory + Code in Superserve sandbox and publishes leaderboard rank."""
    exam = db.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    allowlist_entry = db.is_allowlisted(exam_id, req.candidate_token)
    if not allowlist_entry:
        raise HTTPException(status_code=403, detail="Unauthorized candidate token")

    total_questions = len(exam.questions)
    passed_questions = 0
    total_score_weight = 0.0
    sandbox_details = {}

    for question in exam.questions:
        cand_answer = req.answers.get(question.id, "").strip()

        if question.type == "mcq":
            if question.correct_answer and cand_answer.upper() == question.correct_answer.strip().upper():
                passed_questions += 1
                total_score_weight += 1.0

        elif question.type == "short_answer":
            if question.correct_answer and cand_answer.lower() == question.correct_answer.strip().lower():
                passed_questions += 1
                total_score_weight += 1.0

        elif question.type == "code":
            if cand_answer:
                test_cases_dicts = [tc.model_dump() for tc in question.test_cases]
                res = sandbox_runner.execute_code(cand_answer, test_cases_dicts)
                sandbox_details[question.id] = res

                if res.get("passed_all"):
                    passed_questions += 1
                    total_score_weight += 1.0
                elif res.get("total_tests", 0) > 0:
                    fraction = res.get("passed_count", 0) / res.get("total_tests", 1)
                    total_score_weight += fraction

    final_score = round((total_score_weight / total_questions) * 100.0, 2) if total_questions > 0 else 0.0

    submission = Submission(
        exam_id=exam_id,
        candidate_token=req.candidate_token,
        candidate_email=allowlist_entry.candidate_email,
        answers=req.answers,
        score=final_score,
        passed_questions=passed_questions,
        total_questions=total_questions,
        sandbox_results=sandbox_details
    )
    db.add_submission(submission)

    leaderboard = db.get_leaderboard(exam_id)

    return {
        "status": "evaluated",
        "exam_id": exam_id,
        "score": final_score,
        "passed_questions": passed_questions,
        "total_questions": total_questions,
        "leaderboard": leaderboard
    }

@router.get("/api/exams/{exam_id}/leaderboard")
async def get_leaderboard(exam_id: str):
    """Retrieves live leaderboard for an exam."""
    leaderboard = db.get_leaderboard(exam_id)
    return {"exam_id": exam_id, "leaderboard": leaderboard}
