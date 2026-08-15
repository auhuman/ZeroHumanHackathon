import os
import sys
import time
import subprocess
import tempfile
import httpx
from typing import List, Dict, Any
from database import TestCase
from clients.logger import log_integration

class SandboxRunner:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SUPERSERVE_API_KEY", "")
        self.base_url = "https://api.superserve.ai"

    def execute_code(self, code: str, test_cases: List[Any], timeout_sec: float = 3.0) -> Dict[str, Any]:
        """Convenience method accepting list of TestCase objects or dicts."""
        tc_objs = [
            TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", "")) if isinstance(tc, dict) else tc
            for tc in test_cases
        ]
        return self._execute_local_isolated_subprocess(code, tc_objs, timeout_sec)

    async def execute_code_against_test_suite(
        self, code: str, test_cases: List[TestCase], timeout_sec: float = 3.0
    ) -> Dict[str, Any]:
        """
        Executes candidate Python code against verified test suite.
        Uses Superserve API when valid key present, or local isolated subprocess runner fallback.
        """
        if not test_cases:
            return {
                "passed_count": 0,
                "total_tests": 0,
                "stdout": "",
                "stderr": "No test cases specified for this question.",
                "execution_time_ms": 0,
                "passed_all": True
            }

        url = f"{self.base_url}/v1/sandbox/execute"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "language": "python",
            "code": code,
            "test_cases": [{"input": tc.input, "expected_output": tc.expected_output} for tc in test_cases],
            "timeout_seconds": timeout_sec,
            "memory_limit_mb": 64
        }

        if self.api_key and not self.api_key.startswith("mock_"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = resp.text

                    log_integration("Superserve Sandbox API", "POST", url, headers, payload, resp.status_code, resp.headers, resp_json)
                    if resp.status_code == 200 and isinstance(resp_json, dict):
                        return resp_json
            except Exception as e:
                print(f"[SandboxRunner] Superserve API exception: {e}")
                log_integration("Superserve Sandbox API", "POST", url, headers, payload, 500, {}, str(e))

        res = self._execute_local_isolated_subprocess(code, test_cases, timeout_sec)
        log_integration("Superserve Sandbox [LOCAL SUBPROCESS]", "POST", url, headers, payload, 200, {"content-type": "application/json"}, res)
        return res

    def _execute_local_isolated_subprocess(
        self, code: str, test_cases: List[TestCase], timeout_sec: float
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        passed_count = 0
        all_stdout = []
        all_stderr = []

        for idx, tc in enumerate(test_cases, start=1):
            harness_code = f"""
{code}

# Test Harness Injection
if __name__ == "__main__":
    import sys
    try:
        res = {tc.input}
        print(f"OUTPUT:{{res}}")
    except Exception as err:
        print(f"ERROR:{{err}}", file=sys.stderr)
        sys.exit(1)
"""
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
                tmp.write(harness_code)
                tmp_path = tmp.name

            try:
                proc = subprocess.run(
                    [sys.executable, tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                
                stdout = proc.stdout.strip()
                stderr = proc.stderr.strip()

                output_val = ""
                for line in stdout.splitlines():
                    if line.startswith("OUTPUT:"):
                        output_val = line[len("OUTPUT:"):].strip()

                if output_val == tc.expected_output.strip() and proc.returncode == 0:
                    passed_count += 1
                    all_stdout.append(f"Test {idx} PASSED (Input: `{tc.input}` -> `{output_val}`)")
                else:
                    all_stdout.append(f"Test {idx} FAILED (Input: `{tc.input}` | Got: `{output_val}` | Expected: `{tc.expected_output}`)")
                    if stderr:
                        all_stderr.append(f"Test {idx} error: {stderr}")

            except subprocess.TimeoutExpired:
                all_stderr.append(f"Test {idx} FAILED: Execution timed out after {timeout_sec}s.")
            except Exception as ex:
                all_stderr.append(f"Test {idx} FAILED with exception: {ex}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        exec_time_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "passed_count": passed_count,
            "total_tests": len(test_cases),
            "stdout": "\n".join(all_stdout),
            "stderr": "\n".join(all_stderr),
            "execution_time_ms": exec_time_ms,
            "passed_all": passed_count == len(test_cases)
        }
