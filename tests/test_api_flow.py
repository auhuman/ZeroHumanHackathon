import pytest
from fastapi.testclient import TestClient
from main import app
from database import db

client = TestClient(app)

def test_full_zero_human_happy_path():
    # 1. Create Exam (Pioneer -> Terac Review)
    create_resp = client.post("/api/exams/create", json={
        "topic": "FastAPI Microservices",
        "level": "Intermediate",
        "time_limit": 30
    })
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    exam_id = create_data["exam_id"]
    assert exam_id is not None

    # 2. Terac Review Callback
    cb_resp = client.post("/api/exams/terac-callback", json={
        "exam_id": exam_id,
        "terac_task_id": create_data["terac_task_id"]
    })
    assert cb_resp.status_code == 200
    cb_data = cb_resp.json()
    assert cb_data["status"] == "verified"
    assert "payment_link" in cb_data

    # 3. Candidate Register (Stripe & Linq SMS)
    reg_resp = client.post(f"/api/exams/{exam_id}/register", json={
        "email": "zero_human_candidate@example.com",
        "phone_number": "+15550199"
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    token = reg_data["candidate_token"]
    assert token.startswith("tok_")

    # 4. Fetch Exam as Candidate
    get_resp = client.get(f"/api/exams/{exam_id}?token={token}")
    assert get_resp.status_code == 200
    exam_data = get_resp.json()
    assert exam_data["id"] == exam_id

    # 5. Candidate Answer Submission
    answers = {}
    for q in exam_data["questions"]:
        if q["type"] == "mcq":
            answers[q["id"]] = "A"
        elif q["type"] == "short_answer":
            answers[q["id"]] = q.get("correct_answer", "O(1)")
        elif q["type"] == "code":
            answers[q["id"]] = "def solution(n):\n    if n <= 1:\n        return 1\n    return n * solution(n - 1)\n"

    sub_resp = client.post(f"/api/exams/{exam_id}/submit", json={
        "candidate_token": token,
        "answers": answers
    })
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["status"] == "evaluated"
    assert sub_data["score"] > 0

    # 6. Leaderboard Verification
    lb_resp = client.get(f"/api/exams/{exam_id}/leaderboard")
    assert lb_resp.status_code == 200
    lb_data = lb_resp.json()
    assert len(lb_data["leaderboard"]) >= 1
    assert lb_data["leaderboard"][0]["candidate_email"] == "zero_human_candidate@example.com"
