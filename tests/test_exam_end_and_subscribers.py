import pytest
from fastapi.testclient import TestClient
from main import app
from database import db, Exam, Question, AllowlistEntry

client = TestClient(app)

def test_end_exam_and_subscribed_candidates():
    # 1. Create ACTIVE exam
    exam = Exam(
        title="High Throughput Distributed Databases",
        topic="Database Engine Internals",
        status="ACTIVE",
        price_cents=1500,
        questions=[Question(id="q1", prompt="What is WAL?", type="short_answer", correct_answer="Write Ahead Log")]
    )
    db.create_exam(exam)

    # 2. Register candidates
    reg_resp = client.post(f"/api/exams/{exam.id}/register", json={
        "email": "db_engineer_1@tech.com",
        "phone_number": "+15550199"
    })
    assert reg_resp.status_code == 200

    # 3. Get Subscribed Candidates (/api/exams/{exam_id}/candidates)
    cand_resp = client.get(f"/api/exams/{exam.id}/candidates")
    assert cand_resp.status_code == 200
    cand_data = cand_resp.json()
    assert cand_data["subscribed_count"] >= 1
    assert cand_data["candidates"][0]["candidate_email"] == "db_engineer_1@tech.com"

    # 4. End Exam (/api/exams/{exam_id}/end)
    end_resp = client.post(f"/api/exams/{exam.id}/end")
    assert end_resp.status_code == 200
    end_data = end_resp.json()
    assert end_data["status"] == "completed"
    assert end_data["exam_status"] == "COMPLETED"

    # 5. Release Results (/api/exams/{exam_id}/release-results)
    rel_resp = client.post(f"/api/exams/{exam.id}/release-results")
    assert rel_resp.status_code == 200
    assert rel_resp.json()["results_released"] is True
