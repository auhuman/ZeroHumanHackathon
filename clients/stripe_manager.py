import os
import uuid
import json
import stripe
from typing import Dict, Any, Optional
from database import db, AllowlistEntry, Exam
from clients.logger import log_integration

class StripeManager:
    def __init__(self, secret_key: str = None, webhook_secret: str = None):
        self.secret_key = secret_key or os.getenv("STRIPE_SECRET_KEY", "")
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if self.secret_key and not self.secret_key.startswith("mock_"):
            stripe.api_key = self.secret_key

    def create_payment_link(self, exam: Exam, domain: str = None) -> str:
        """
        Creates a Sandbox Payment Gateway link for an active exam.
        """
        base_domain = domain or os.getenv("DOMAIN") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
        sandbox_url = f"{base_domain}/candidate?pay_exam={exam.id}&amount={exam.price_cents}"
        
        log_integration("Sandbox Payment Gateway [PAYMENTLINK.CREATE]", "POST", "/api/candidate/sandbox-pay", 
                        {"Authorization": "Bearer sbx_key_sandbox_mode"}, 
                        {"exam_id": exam.id, "unit_amount": exam.price_cents, "currency": "usd"}, 
                        200, {"content-type": "application/json"}, {"payment_link_url": sandbox_url, "sandbox_mode": True})
        return sandbox_url

    def process_webhook_event(self, payload: bytes, sig_header: Optional[str] = None) -> Optional[AllowlistEntry]:
        """
        Parses checkout.session.completed webhook events, issues candidate_token,
        and adds candidate to allowlist table.
        """
        event_dict = None
        if self.webhook_secret and sig_header and not self.secret_key.startswith("mock_"):
            try:
                event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
                event_dict = event.to_dict()
            except Exception as e:
                print(f"[StripeManager] Webhook signature verification failed: {e}")
                log_integration("Stripe Webhook", "POST", "/webhooks/stripe", {}, {"sig": sig_header}, 400, {}, f"Signature failed: {e}")
                return None
        else:
            try:
                event_dict = json.loads(payload.decode("utf-8"))
            except Exception:
                return None

        if not event_dict:
            return None

        log_integration("Stripe Webhook [RECEIVED]", "POST", "/webhooks/stripe", {}, event_dict, 200, {}, {"status": "parsed"})

        event_type = event_dict.get("type", "")
        if event_type == "checkout.session.completed":
            session = event_dict.get("data", {}).get("object", {})
            customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email") or "candidate@example.com"
            metadata = session.get("metadata", {})
            exam_id = metadata.get("exam_id", "")

            if not exam_id:
                exams = db.list_exams()
                if exams:
                    exam_id = exams[0].id

            token = f"tok_{uuid.uuid4().hex[:12]}"
            phone = session.get("customer_details", {}).get("phone") or "+15550199"
            
            entry = AllowlistEntry(
                exam_id=exam_id,
                candidate_email=customer_email,
                candidate_token=token,
                phone_number=phone
            )
            db.add_to_allowlist(entry)
            return entry

        return None
