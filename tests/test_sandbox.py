import pytest
from database import TestCase
from clients.sandbox_runner import SandboxRunner

@pytest.mark.asyncio
async def test_sandbox_local_execution_passing():
    runner = SandboxRunner(api_key="mock_superserve_key")
    code = "def solution(n):\n    return n * 2\n"
    test_cases = [
        TestCase(input="solution(5)", expected_output="10"),
        TestCase(input="solution(0)", expected_output="0")
    ]

    res = await runner.execute_code_against_test_suite(code, test_cases)
    assert res["passed_count"] == 2
    assert res["total_tests"] == 2
    assert res["passed_all"] is True
    assert "PASSED" in res["stdout"]

@pytest.mark.asyncio
async def test_sandbox_local_execution_failing():
    runner = SandboxRunner(api_key="mock_superserve_key")
    code = "def solution(n):\n    return n + 1\n"
    test_cases = [
        TestCase(input="solution(5)", expected_output="10")
    ]

    res = await runner.execute_code_against_test_suite(code, test_cases)
    assert res["passed_count"] == 0
    assert res["passed_all"] is False
    assert "FAILED" in res["stdout"]
