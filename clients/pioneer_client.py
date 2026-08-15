import os
import json
import uuid
import httpx
from typing import Dict, List, Any
from database import Question, TestCase, Exam
from clients.logger import log_integration

class PioneerClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("PIONEER_API_KEY", "")
        self.base_url = "https://api.pioneer.ai"

    def _extract_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        return json.loads(text)

    def _get_cache_file(self) -> str:
        return os.path.join(os.path.dirname(__file__), "pioneer_cache.json")

    def _load_cache(self) -> Dict[str, Any]:
        cache_file = self._get_cache_file()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self, cache: Dict[str, Any]):
        try:
            with open(self._get_cache_file(), "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"[PioneerClient] Failed to save cache: {e}")

    async def generate_exam(self, topic: str, level: str = "Intermediate", time_limit: int = 45, price_cents: int = 1500) -> Exam:
        """
        Query Pioneer API (https://api.pioneer.ai/v1/chat/completions) using model slug 'pioneer/auto'.
        Caches responses to pioneer_cache.json for fast testing of downstream integrations (Terac, Stripe, Lovable).
        """
        cache_key = f"{topic.lower().strip()}_{level.lower().strip()}_{time_limit}"
        cache_data = self._load_cache()

        if cache_key in cache_data:
            print(f"[PioneerClient] Returning cached Pioneer AI response for key '{cache_key}'")
            log_integration("Pioneer AI [CACHED]", "POST", f"{self.base_url}/v1/chat/completions", {}, {"topic": topic, "level": level}, 200, {"content-type": "application/json"}, cache_data[cache_key])
            return self._parse_pioneer_response(cache_data[cache_key], topic, level, time_limit, price_cents=price_cents)

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            f"Generate a technical exam for topic: '{topic}', difficulty: '{level}', time limit: {time_limit} minutes. "
            f"Return ONLY valid JSON matching this exact structure (no markdown formatting, no commentary):\n"
            f'{{"title": "...", "questions": [{{"id": "q1", "prompt": "...", "type": "mcq|code|short_answer", '
            f'"options": ["A)..."], "correct_answer": "...", "rubric": "...", "test_cases": [{{"input": "...", "expected_output": "..."}}]}}]}}'
        )
        payload = {
            "model": "pioneer/auto",
            "messages": [
                {"role": "system", "content": "You are an automated exam generator. Output ONLY raw JSON matching the requested schema without any markdown formatting or surrounding conversational text."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        if self.api_key and not self.api_key.startswith("mock_"):
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        
                        try:
                            resp_json = resp.json()
                        except Exception:
                            resp_json = resp.text

                        log_integration("Pioneer AI", "POST", url, headers, payload, resp.status_code, resp.headers, resp_json)

                        if resp.status_code == 200 and isinstance(resp_json, dict):
                            content = resp_json["choices"][0]["message"]["content"]
                            parsed_json = self._extract_json(content)
                            cache_data[cache_key] = parsed_json
                            self._save_cache(cache_data)
                            return self._parse_pioneer_response(parsed_json, topic, level, time_limit, price_cents=price_cents)
                except Exception as e:
                    print(f"[PioneerClient] Pioneer API attempt {attempt+1} exception: {e}")
                    log_integration("Pioneer AI", "POST", url, headers, payload, 500, {}, str(e))
        else:
            log_integration("Pioneer AI [MOCK]", "POST", url, headers, payload, 200, {"content-type": "application/json"}, {"status": "mock_generated"})

        return self._generate_fallback(topic, level, time_limit, price_cents=price_cents)

    def _parse_pioneer_response(self, data: Dict[str, Any], topic: str, level: str, time_limit: int, price_cents: int = 1500) -> Exam:
        questions = []
        for q_data in data.get("questions", []):
            test_cases = [
                TestCase(input=tc.get("input", ""), expected_output=tc.get("expected_output", ""))
                for tc in q_data.get("test_cases", [])
            ]
            questions.append(Question(
                id=q_data.get("id", str(uuid.uuid4())[:8]),
                prompt=q_data.get("prompt", ""),
                type=q_data.get("type", "mcq"),
                options=q_data.get("options"),
                test_cases=test_cases,
                rubric=q_data.get("rubric", ""),
                correct_answer=q_data.get("correct_answer")
            ))
        
        return Exam(
            id=data.get("exam_id", str(uuid.uuid4())),
            title=data.get("title", f"Autonomous Assessment: {topic}"),
            topic=topic,
            level=level,
            time_limit=time_limit,
            price_cents=price_cents,
            status="DRAFT",
            questions=questions
        )

    def _generate_fallback(self, topic: str, level: str, time_limit: int, price_cents: int = 1500) -> Exam:
        questions = [
            Question(
                id="q1_mcq",
                prompt=f"Which of the following best describes the core principle of {topic}?",
                type="mcq",
                options=[
                    f"A) Parallel asynchronous non-blocking event loops",
                    f"B) Synchronous blocking execution on a single thread",
                    f"C) Pure functional side-effect free state mutation",
                    f"D) Distributed disk-based swapping memory"
                ],
                correct_answer="A",
                rubric="Evaluates fundamental conceptual understanding of topic."
            ),
            Question(
                id="q2_short",
                prompt=f"What is the standard time complexity for basic operations when using optimized structures in {topic}?",
                type="short_answer",
                correct_answer="O(1)",
                rubric="Evaluates theoretical algorithmic complexity precision."
            ),
            Question(
                id="q3_code",
                prompt=f"Write a Python function `solution(n)` that computes the factorial of `n` for {topic} benchmark validation.",
                type="code",
                test_cases=[
                    TestCase(input="solution(5)", expected_output="120"),
                    TestCase(input="solution(0)", expected_output="1"),
                    TestCase(input="solution(3)", expected_output="6")
                ],
                rubric="Must handle edge case solution(0) = 1, recursion/loop correctness, and speed under 100ms."
            )
        ]

        return Exam(
            id=str(uuid.uuid4()),
            title=f"Autonomous Technical Exam: {topic}",
            topic=topic,
            level=level,
            time_limit=time_limit,
            price_cents=price_cents,
            status="DRAFT",
            questions=questions
        )
