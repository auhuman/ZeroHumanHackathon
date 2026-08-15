import pytest
from fastapi.testclient import TestClient
from main import app
from database import db, Exam, Question, AllowlistEntry

client = TestClient(app)

def test_google_auth_integration():
    # Test POST /api/auth/google profile payload
    resp = client.post("/api/auth/google", json={
        "email": "alex.google@example.com",
        "name": "Alex Google",
        "picture": "https://lh3.googleusercontent.com/a/default-user"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "authenticated"
    assert data["user"]["email"] == "alex.google@example.com"
    assert data["user"]["google_id"].startswith("g_")

def test_strict_payment_token_access_gate():
    # 1. Create active exam
    exam = Exam(
        title="Payment Gate Test Exam",
        topic="Security & OAuth",
        status="ACTIVE",
        price_cents=1000,
        questions=[Question(id="q1", prompt="What is OAuth?", type="mcq", options=["A", "B"], correct_answer="A")]
    )
    db.create_exam(exam)

    # 2. Candidate attempts to access exam WITHOUT token -> expect HTTP 402
    no_token_resp = client.get(f"/api/exams/{exam.id}")
    assert no_token_resp.status_code == 402
    assert "Payment Required" in no_token_resp.json()["detail"]

    # 3. Candidate attempts to access exam with INVALID / dummy token -> expect HTTP 402
    invalid_token_resp = client.get(f"/api/exams/{exam.id}?token=demo_token")
    assert invalid_token_resp.status_code == 402
    assert "Payment Required" in invalid_token_resp.json()["detail"]

    # 4. Candidate registers and receives valid token
    reg_resp = client.post(f"/api/exams/{exam.id}/register", json={
        "email": "paid_candidate@example.com",
        "phone_number": "+15550199"
    })
    assert reg_resp.status_code == 200
    valid_token = reg_resp.json()["candidate_token"]

    # 5. Candidate accesses exam with VALID token -> expect HTTP 200 OK
    valid_resp = client.get(f"/api/exams/{exam.id}?token={valid_token}")
    assert valid_resp.status_code == 200
    assert valid_resp.json()["id"] == exam.id

    # 6. Organizer request with is_organizer=True -> expect HTTP 200 OK
    org_resp = client.get(f"/api/exams/{exam.id}?is_organizer=true")
    assert org_resp.status_code == 200
    assert org_resp.json()["id"] == exam.id
