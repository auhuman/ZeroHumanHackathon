import pytest
from database import Exam, Question
from clients.lovable_client import LovableClient
from clients.presentation_adapter import PresentationAdapterFactory, StandardHTMLPresentationAdapter, LovableMCPPresentationAdapter

@pytest.mark.asyncio
async def test_presentation_adapter_factory():
    lovable_client = LovableClient(api_key="mock_lovable_key")
    adapter = PresentationAdapterFactory.get_adapter(lovable_client)
    
    assert isinstance(adapter, StandardHTMLPresentationAdapter)
    assert "Browser Native" in adapter.get_adapter_type()

    exam = Exam(title="Test Exam", topic="Testing", questions=[Question(prompt="Q1", type="mcq")])
    layout = await adapter.render_exam_theme_and_layout(exam)
    assert "theme" in layout
    assert "components" in layout
