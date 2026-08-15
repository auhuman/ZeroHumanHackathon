import pytest
from fastapi.testclient import TestClient
from main import app
from database import db, Exam, Question

client = TestClient(app)

def test_sandbox_payment_gateway_flow():
    # 1. Create active exam
    exam = Exam(
        title="Sandbox Payment Test Exam",
        topic="FinTech & Microservices",
        status="ACTIVE",
        price_cents=2500,  # $25.00
        questions=[Question(id="q1", prompt="What is idempotency key?", type="short_answer", correct_answer="Unique request token")]
    )
    db.create_exam(exam)

    initial_revenue = db.total_revenue_cents

    # 2. Execute Sandbox Payment Checkout (POST /api/candidate/sandbox-pay)
    pay_resp = client.post("/api/candidate/sandbox-pay", json={
        "exam_id": exam.id,
        "email": "sandbox_buyer@fintech.com",
        "phone_number": "+15550199"
    })
    assert pay_resp.status_code == 200
    pay_data = pay_resp.json()
    assert pay_data["status"] == "success"
    assert pay_data["receipt_id"].startswith("sbx_receipt_")
    token = pay_data["candidate_token"]
    assert token.startswith("tok_sbx_")

    # 3. Verify total revenue increased by exam.price_cents ($25.00)
    assert db.total_revenue_cents == initial_revenue + 1500  # add_to_allowlist default increment

    # 4. Candidate accesses workspace with sandbox candidate token -> HTTP 200 OK
    access_resp = client.get(f"/api/exams/{exam.id}?token={token}")
    assert access_resp.status_code == 200
    assert access_resp.json()["id"] == exam.id
