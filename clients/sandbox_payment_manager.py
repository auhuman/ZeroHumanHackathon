import os
import uuid
from typing import Dict, Any, Optional
from database import db, AllowlistEntry, Exam
from clients.logger import log_integration

class SandboxPaymentManager:
    """
    Sandbox Payment Gateway Client replacing external payment dependency.
    Simulates real-time card authorization, instant settlement, and webhook dispatches.
    """
    def __init__(self):
        self.gateway_id = "sandbox_pay_v1"

    def create_payment_link(self, exam: Exam, domain: str = None) -> str:
        """
        Creates a Sandbox Payment Checkout link for an active exam.
        """
        base_domain = domain or os.getenv("DOMAIN") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
        checkout_url = f"{base_domain}/candidate/sandbox-checkout/{exam.id}?price_cents={exam.price_cents}"
        
        log_integration("Sandbox Payment Gateway [PAYMENTLINK.CREATE]", "POST", f"{base_domain}/api/candidate/sandbox-pay", 
                        {"Authorization": "Bearer sbx_key_sandbox_mode"}, 
                        {"exam_id": exam.id, "unit_amount": exam.price_cents, "currency": "usd"}, 
                        200, {"content-type": "application/json"}, 
                        {"payment_link_url": checkout_url, "sandbox_mode": True})
        return checkout_url

    def process_sandbox_payment(self, exam_id: str, candidate_email: str, phone_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes instant sandbox payment authorization, credits exam revenue,
        issues tokenized access, and adds candidate to allowlist.
        """
        exam = db.get_exam(exam_id)
        if not exam:
            return {"status": "error", "message": "Exam not found"}

        token = f"tok_sbx_{uuid.uuid4().hex[:12]}"
        phone = phone_number or "+15550199"

        entry = AllowlistEntry(
            exam_id=exam_id,
            candidate_email=candidate_email,
            candidate_token=token,
            phone_number=phone
        )
        db.add_to_allowlist(entry)
        
        receipt_id = f"sbx_receipt_{uuid.uuid4().hex[:8]}"

        log_integration("Sandbox Payment Gateway [PAYMENT.SUCCESS]", "POST", "/api/candidate/sandbox-pay",
                        {"Content-Type": "application/json"},
                        {
                            "exam_id": exam_id,
                            "candidate_email": candidate_email,
                            "amount_cents": exam.price_cents,
                            "status": "SETTLED"
                        },
                        200,
                        {"content-type": "application/json"},
                        {
                            "status": "APPROVED",
                            "receipt_id": receipt_id,
                            "candidate_token": token,
                            "sandbox_mode": True
                        })

        return {
            "status": "success",
            "receipt_id": receipt_id,
            "candidate_token": token,
            "entry": entry
        }
