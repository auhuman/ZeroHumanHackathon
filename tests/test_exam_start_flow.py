import pytest
from fastapi.testclient import TestClient
from main import app
from database import db, Exam, Question, AllowlistEntry

client = TestClient(app)

def test_exam_start_gate_and_candidate_sms_notification():
    # 1. Create an Exam that reaches VERIFIED state (Review Completed)
    exam = Exam(
        title="Distributed Systems & Consensus",
        topic="Raft & Paxos",
        status="VERIFIED",
        price_cents=2000,
        questions=[Question(id="q1", prompt="What is leader election in Raft?", type="mcq", options=["A", "B"], correct_answer="A")]
    )
    db.create_exam(exam)

    # 2. Verify exam is listed in Candidate Catalog (/api/candidate/catalog)
    cat_resp = client.get("/api/candidate/catalog")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    listed_ids = [e["id"] for e in cat_data["exams"]]
    assert exam.id in listed_ids

    # 3. Candidate registers with Email & Phone Number
    reg_resp = client.post(f"/api/exams/{exam.id}/register", json={
        "email": "distributed_candidate@example.com",
        "phone_number": "+15550199"
    })
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    token = reg_data["candidate_token"]
    assert token.startswith("tok_")

    # 4. Candidate fetches exam before Organizer clicks Start (Exam status == VERIFIED)
    get_before = client.get(f"/api/exams/{exam.id}?token={token}")
    assert get_before.status_code == 200
    assert get_before.json()["status"] == "VERIFIED"

    # 5. Organizer clicks "Start Exam" -> POST /api/exams/{exam_id}/start
    start_resp = client.post(f"/api/exams/{exam.id}/start")
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] == "started"
    assert start_data["exam_status"] == "ACTIVE"
    assert start_data["sms_dispatched_count"] >= 1

    # 6. Verify Exam state transitioned to ACTIVE in DB and candidate can start answering
    get_after = client.get(f"/api/exams/{exam.id}?token={token}")
    assert get_after.status_code == 200
    assert get_after.json()["status"] == "ACTIVE"
