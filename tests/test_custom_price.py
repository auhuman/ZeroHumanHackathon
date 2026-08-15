import pytest
from fastapi.testclient import TestClient
from main import app
from database import db, Exam
from clients.pioneer_client import PioneerClient

client = TestClient(app)

@pytest.mark.asyncio
async def test_pioneer_client_custom_price_cents():
    pioneer = PioneerClient()
    exam = await pioneer.generate_exam(topic="System Architecture", level="Advanced", time_limit=60, price_cents=100)
    assert exam.price_cents == 100

def test_api_create_exam_custom_price():
    # 1. Test setting 1.00 dollar ($1.00)
    resp1 = client.post("/api/exams/create", json={
        "topic": "Quantum Computing 101",
        "level": "Beginner",
        "time_limit": 15,
        "price_dollars": 1.00
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    exam1_id = data1["exam_id"]
    assert data1["exam"]["price_cents"] == 100

    # Verify fetching exam returns 100 cents
    get_resp1 = client.get(f"/api/exams/{exam1_id}?is_organizer=true")
    assert get_resp1.status_code == 200
    assert get_resp1.json()["price_cents"] == 100

    # 2. Test setting 7.50 dollars ($7.50)
    resp2 = client.post("/api/exams/create", json={
        "topic": "Linear Algebra for ML",
        "level": "Intermediate",
        "time_limit": 30,
        "price_dollars": 7.50
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    exam2_id = data2["exam_id"]
    assert data2["exam"]["price_cents"] == 750

    get_resp2 = client.get(f"/api/exams/{exam2_id}?is_organizer=true")
    assert get_resp2.status_code == 200
    assert get_resp2.json()["price_cents"] == 750
