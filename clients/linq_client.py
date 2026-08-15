import os
import httpx
from typing import Dict, Any, Optional
from database import db, AllowlistEntry
from clients.logger import log_integration

class LinqClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("LINQ_API_KEY", "")
        self.base_url = "https://api.linq.ai"

    async def send_exam_access(self, phone_number: str, exam_id: str, candidate_token: str, domain: str = None) -> Dict[str, Any]:
        """
        Sends SMS/iMessage via Linq API containing the candidate tokenized access link.
        """
        base_domain = domain or os.getenv("DOMAIN") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
        access_url = f"{base_domain}/candidate/{exam_id}?token={candidate_token}"
        message_body = (
            f"🚀 [Zero-Human Exam Pass] You are authorized! "
            f"Click to start your assessment: {access_url} "
            f"Reply 'STATUS' anytime to view your live score and remaining time."
        )

        url = f"{self.base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": phone_number,
            "body": message_body,
            "type": "imessage_or_sms"
        }

        if self.api_key and not self.api_key.startswith("mock_"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = resp.text

                    log_integration("Linq SMS API", "POST", url, headers, payload, resp.status_code, resp.headers, resp_json)
                    if resp.status_code in (200, 201) and isinstance(resp_json, dict):
                        return resp_json
            except Exception as e:
                print(f"[LinqClient] API exception: {e}")
                log_integration("Linq SMS API", "POST", url, headers, payload, 500, {}, str(e))
        else:
            mock_res = {
                "status": "sent",
                "message_id": f"msg_linq_mock_{candidate_token[:8]}",
                "to": phone_number,
                "body": message_body,
                "channel": "iMessage"
            }
            log_integration("Linq SMS API [MOCK]", "POST", url, headers, payload, 200, {"content-type": "application/json"}, mock_res)
            return mock_res

        return {"status": "dispatched", "body": message_body}

    def process_incoming_sms(self, payload: Dict[str, Any]) -> str:
        """
        Processes incoming SMS messages via Linq webhook (e.g. candidate texting 'STATUS').
        """
        log_integration("Linq Webhook [INCOMING SMS]", "POST", "/webhooks/linq", {}, payload, 200, {}, {"status": "processing"})
        from_phone = payload.get("from", "")
        text_body = payload.get("body", "").strip().upper()

        if "STATUS" in text_body:
            entry = None
            for e in db.allowlist:
                if e.phone_number == from_phone:
                    entry = e
                    break
            
            if entry:
                subs = db.submissions.get(entry.exam_id, [])
                candidate_sub = next((s for s in subs if s.candidate_token == entry.candidate_token), None)
                if candidate_sub:
                    return f"📊 Exam Status: COMPLETED. Your Score: {candidate_sub.score:.1f}%. Passed {candidate_sub.passed_questions}/{candidate_sub.total_questions} questions."
                else:
                    return f"⏳ Exam Status: REGISTERED & ACTIVE. Access link: http://localhost:8000/candidate/{entry.exam_id}?token={entry.candidate_token}"
            
            return "⚠️ No active exam registration found for this phone number."

        return "🤖 Linq Bot: Send 'STATUS' to retrieve your active assessment progress."
