import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class TestCase(BaseModel):
    input: str
    expected_output: str

class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    prompt: str
    type: str  # "mcq" | "code" | "short_answer"
    options: Optional[List[str]] = None  # For MCQ questions
    test_cases: List[TestCase] = Field(default_factory=list)
    rubric: str = ""
    correct_answer: Optional[str] = None  # For MCQ or short_answer grading

class Exam(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    topic: str
    level: str = "Intermediate"
    time_limit: int = 45  # in minutes
    status: str = "DRAFT"  # "DRAFT" | "IN_REVIEW" | "VERIFIED" | "ACTIVE" | "COMPLETED"
    questions: List[Question] = Field(default_factory=list)
    terac_diff: Optional[Dict] = None
    terac_submission: Optional[Dict] = None
    terac_opportunity_id: Optional[str] = None
    terac_callback_received_at: Optional[str] = None
    lovable_ui_config: Optional[Dict] = None
    stripe_payment_link: Optional[str] = None
    price_cents: int = 1500  # $15.00 default exam entry fee
    results_released: bool = False  # Set to True when organizer releases official exam scores
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AllowlistEntry(BaseModel):
    exam_id: str
    candidate_email: str
    candidate_token: str = Field(default_factory=lambda: f"tok_{uuid.uuid4().hex[:12]}")
    phone_number: Optional[str] = None
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Submission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exam_id: str
    candidate_token: str
    candidate_email: str = ""
    answers: Dict[str, str] = Field(default_factory=dict)  # question_id -> answer/code
    score: float = 0.0
    passed_questions: int = 0
    total_questions: int = 0
    sandbox_results: Dict[str, Dict] = Field(default_factory=dict)
    submitted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_time_ms: int = 0

import json
import os

class Database:
    def __init__(self):
        self.storage_file = os.path.join(os.path.dirname(__file__), "db_storage.json")
        self.exams: Dict[str, Exam] = {}
        self.allowlist: List[AllowlistEntry] = []
        self.submissions: Dict[str, List[Submission]] = {}  # exam_id -> list of Submissions
        self.total_revenue_cents: int = 0
        self._load()

    def _save(self):
        try:
            data = {
                "exams": {k: v.model_dump() for k, v in self.exams.items()},
                "allowlist": [e.model_dump() for e in self.allowlist],
                "submissions": {k: [s.model_dump() for s in v] for k, v in self.submissions.items()},
                "total_revenue_cents": self.total_revenue_cents
            }
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Database Save Exception]: {e}")

    def _load(self):
        if not os.path.exists(self.storage_file):
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "exams" in data:
                self.exams = {k: Exam(**v) for k, v in data["exams"].items()}
            if "allowlist" in data:
                self.allowlist = [AllowlistEntry(**e) for e in data["allowlist"]]
            if "submissions" in data:
                self.submissions = {k: [Submission(**s) for s in v] for k, v in data["submissions"].items()}
            if "total_revenue_cents" in data:
                self.total_revenue_cents = data["total_revenue_cents"]
        except Exception as e:
            print(f"[Database Load Exception]: {e}")

    def clear_all(self):
        self.exams = {}
        self.allowlist = []
        self.submissions = {}
        self.total_revenue_cents = 0
        if os.path.exists(self.storage_file):
            try:
                os.remove(self.storage_file)
            except Exception:
                pass

    def create_exam(self, exam: Exam) -> Exam:
        self.exams[exam.id] = exam
        self._save()
        return exam

    def get_exam(self, exam_id: str) -> Optional[Exam]:
        if exam_id not in self.exams:
            self._load()
        return self.exams.get(exam_id)

    def list_exams(self) -> List[Exam]:
        self._load()
        return list(self.exams.values())

    def update_exam(self, exam: Exam) -> Exam:
        self.exams[exam.id] = exam
        self._save()
        return exam

    def add_to_allowlist(self, entry: AllowlistEntry) -> AllowlistEntry:
        self.allowlist.append(entry)
        self.total_revenue_cents += 1500
        self._save()
        return entry

    def is_allowlisted(self, exam_id: str, candidate_token: str) -> Optional[AllowlistEntry]:
        self._load()
        for entry in self.allowlist:
            if entry.exam_id == exam_id and entry.candidate_token == candidate_token:
                return entry
        return None

    def add_submission(self, submission: Submission) -> Submission:
        if submission.exam_id not in self.submissions:
            self.submissions[submission.exam_id] = []
        self.submissions[submission.exam_id].append(submission)
        self._save()
        return submission

    def get_leaderboard(self, exam_id: str) -> List[Dict]:
        self._load()
        subs = self.submissions.get(exam_id, [])
        best_subs = {}
        for s in subs:
            key = s.candidate_email or s.candidate_token
            if key not in best_subs or s.score > best_subs[key].score:
                best_subs[key] = s

        sorted_subs = sorted(
            best_subs.values(),
            key=lambda x: (x.score, -x.execution_time_ms),
            reverse=True
        )

        leaderboard = []
        for rank, s in enumerate(sorted_subs, start=1):
            leaderboard.append({
                "rank": rank,
                "candidate_email": s.candidate_email or "Anonymous Candidate",
                "candidate_token": s.candidate_token[:8] + "...",
                "score": s.score,
                "passed_questions": s.passed_questions,
                "total_questions": s.total_questions,
                "submitted_at": s.submitted_at,
                "execution_time_ms": s.execution_time_ms
            })
        return leaderboard

db = Database()
