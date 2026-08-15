import pytest
from database import Exam, Question, TestCase
from clients.terac_client import TeracClient

@pytest.mark.asyncio
async def test_terac_review_and_diff_generation():
    client = TeracClient(api_key="mock_terac_key")
    exam = Exam(
        title="Test Exam",
        topic="Database Systems",
        questions=[
            Question(
                id="q1",
                prompt="Write a query",
                type="code",
                test_cases=[TestCase(input="solution(5)", expected_output="120")],
                rubric="Basic rubric"
            )
        ]
    )

    task_id = await client.submit_for_review(exam)
    assert task_id.startswith("terac_")

    verified_exam, diff = client.process_review_result(exam)
    assert verified_exam.status == "VERIFIED"
    assert "quality_score_improvement" in diff
    assert len(diff["diff_details"]) == 1
    assert "Terac Expert Verified" in verified_exam.questions[0].rubric
