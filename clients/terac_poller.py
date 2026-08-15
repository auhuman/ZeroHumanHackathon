import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

import httpx
from database import db, Exam
from clients.terac_client import TeracClient
from clients.lovable_client import LovableClient
from clients.stripe_manager import StripeManager
from clients.logger import log_integration

SUBMISSIONS_LOG_FILE = os.path.join(os.path.dirname(__file__), "terac_expert_submissions.json")

def log_terac_submission_to_file(opp_id: str, submission: Dict[str, Any]):
    """Appends captured completed Terac submission data to terac_expert_submissions.json log file."""
    status = str(submission.get("status", "")).lower()
    event = str(submission.get("event", "")).lower()
    outcome = str(submission.get("screening_outcome", "")).lower()

    # Filter: Only log completed / approved submissions or opportunity.submission.completed events
    is_completed = (
        event == "opportunity.submission.completed" or
        status in ("completed", "approved", "submitted") or
        "verified_rubric" in submission
    )

    if not is_completed or status == "screened_out" or outcome == "failed":
        return

    sub_id = submission.get("submission_id") or submission.get("id")

    logs = []
    if os.path.exists(SUBMISSIONS_LOG_FILE):
        try:
            with open(SUBMISSIONS_LOG_FILE, "r") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    
    # Deduplicate: Avoid appending identical submission ID twice
    if sub_id and any((l.get("submission", {}).get("submission_id") == sub_id or l.get("submission", {}).get("id") == sub_id) for l in logs):
        return

    entry = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "opportunity_id": opp_id,
        "event": event or "opportunity.submission.completed",
        "submission": submission
    }
    logs.append(entry)
    
    with open(SUBMISSIONS_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)
    
    print(f"✅ [TeracPoller] Logged COMPLETED submission {sub_id} for opportunity {opp_id} into {SUBMISSIONS_LOG_FILE}")

class TeracPoller:
    def __init__(self, terac_client: TeracClient = None, lovable_client: LovableClient = None, stripe_manager: StripeManager = None):
        self.terac_client = terac_client or TeracClient()
        self.lovable_client = lovable_client or LovableClient()
        self.stripe_manager = stripe_manager or StripeManager()
        self.running = False

    async def poll_once(self, opp_id: str = "pvvwd034orh6rf7bhm2hecjw") -> List[Dict[str, Any]]:
        """Polls Terac REST API for opportunity submissions, logs to file, and updates exam state."""
        headers = {
            "Authorization": f"Bearer {self.terac_client.api_key}",
            "Accept": "application/json"
        }
        url = f"{self.terac_client.rest_url}/opportunities/{opp_id}/submissions"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    submissions = data.get("data", []) or data.get("submissions", [])
                    if submissions:
                        for sub in submissions:
                            log_terac_submission_to_file(opp_id, sub)
                            
                            # Match exam in database
                            exams = db.list_exams()
                            exam = next((e for e in exams if opp_id in (e.terac_opportunity_id or "") or e.id.startswith(opp_id[:8])), None)
                            
                            if not exam and len(exams) > 0:
                                exam = exams[0]  # Fallback to current exam
                            
                            if exam and exam.status not in ("ACTIVE", "COMPLETED"):
                                exam, diff_summary = self.terac_client.process_review_result(exam, sub)
                                ui_config = await self.lovable_client.generate_ui_config(exam)
                                exam.lovable_ui_config = ui_config
                                payment_url = self.stripe_manager.create_payment_link(exam)
                                exam.stripe_payment_link = payment_url
                                exam.status = "VERIFIED"
                                db.update_exam(exam)
                                print(f"🚀 [TeracPoller] Exam {exam.id} updated to VERIFIED status with expert submission!")
                    return submissions
        except Exception as e:
            print(f"[TeracPoller] Error polling submissions for {opp_id}: {e}")
        return []

    async def start_polling_loop(self, interval_seconds: int = 15, target_opp_id: str = "pvvwd034orh6rf7bhm2hecjw"):
        """Runs background polling loop checking for new expert submissions every interval_seconds."""
        self.running = True
        print(f"🔄 [TeracPoller] Starting background polling for Terac Opportunity {target_opp_id} every {interval_seconds}s...")
        while self.running:
            await self.poll_once(target_opp_id)
            await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    poller = TeracPoller()
    asyncio.run(poller.poll_once("pvvwd034orh6rf7bhm2hecjw"))
