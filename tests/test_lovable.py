import pytest
from database import Exam, Question
from clients.lovable_client import LovableClient

@pytest.mark.asyncio
async def test_lovable_ui_sync():
    client = LovableClient(api_key="mock_lovable_key")
    exam = Exam(title="React Architecture", topic="Frontend React", questions=[Question(prompt="Q1", type="mcq")])
    
    config = await client.generate_ui_config(exam)
    assert "theme" in config
    assert config["theme"]["variant"] == "glassmorphic-dark"
    assert "monaco_theme" in config["components"]
