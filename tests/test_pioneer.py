import pytest
from clients.pioneer_client import PioneerClient

@pytest.mark.asyncio
async def test_pioneer_fallback_schema_validation():
    client = PioneerClient(api_key="mock_pioneer_key")
    exam = await client.generate_exam("Python AsyncIO", "Senior", 45)
    
    assert exam.id is not None
    assert exam.topic == "Python AsyncIO"
    assert exam.level == "Senior"
    assert exam.time_limit == 45
    assert exam.status == "DRAFT"
    assert len(exam.questions) >= 3

    # Check question types
    types = [q.type for q in exam.questions]
    assert "mcq" in types
    assert "code" in types

    # Check code test cases
    code_q = next(q for q in exam.questions if q.type == "code")
    assert len(code_q.test_cases) > 0
    assert code_q.test_cases[0].input is not None
    assert code_q.test_cases[0].expected_output is not None
