import json
import pytest
from database import db, Exam
from clients.stripe_manager import StripeManager

def test_stripe_payment_link_and_webhook():
    manager = StripeManager(secret_key="mock_stripe_key")
    exam = Exam(title="Stripe Test Exam", topic="Payments")
    db.create_exam(exam)

    payment_url = manager.create_payment_link(exam)
    assert "pay_exam=" in payment_url or "buy.stripe.com" in payment_url

    # Simulate webhook event
    event_payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_details": {"email": "test_candidate@domain.com", "phone": "+15550199"},
                "metadata": {"exam_id": exam.id}
            }
        }
    }).encode("utf-8")

    entry = manager.process_webhook_event(event_payload)
    assert entry is not None
    assert entry.candidate_email == "test_candidate@domain.com"
    assert entry.candidate_token.startswith("tok_")
    assert db.is_allowlisted(exam.id, entry.candidate_token) is not None
