import pytest
from database import db, AllowlistEntry
from clients.linq_client import LinqClient

@pytest.mark.asyncio
async def test_linq_sms_dispatch_and_status_bot():
    client = LinqClient(api_key="mock_linq_key")
    res = await client.send_exam_access("+15550199", "exam_123", "tok_abc")
    assert res["status"] == "sent"
    assert "tok_abc" in res["body"]

    # Test incoming status query for unregistered vs registered
    reply_unknown = client.process_incoming_sms({"from": "+19999999", "body": "STATUS"})
    assert "No active exam registration" in reply_unknown

    db.add_to_allowlist(AllowlistEntry(exam_id="exam_linq_test", candidate_email="c@d.com", candidate_token="tok_linq_fresh", phone_number="+15559999"))
    reply_known = client.process_incoming_sms({"from": "+15559999", "body": "STATUS"})
    assert "REGISTERED & ACTIVE" in reply_known
