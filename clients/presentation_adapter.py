import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from database import Exam
from clients.lovable_client import LovableClient

class BasePresentationAdapter(ABC):
    """
    Abstract Presentation Layer Adapter Interface.
    Decouples UI rendering logic from core business endpoints, supporting pluggable engines
    (Browser Native HTML/CSS/JS vs. Lovable MCP Server UI Builder).
    """

    @abstractmethod
    async def render_exam_theme_and_layout(self, exam: Exam) -> Dict[str, Any]:
        """Returns theme tokens, layout structure, and component styling configs for candidate SPA."""
        pass

    @abstractmethod
    def get_adapter_type(self) -> str:
        """Returns name of active presentation adapter engine."""
        pass


class StandardHTMLPresentationAdapter(BasePresentationAdapter):
    """
    Native Browser HTML/Tailwind/Glassmorphism Presentation Adapter.
    Renders high-performance, dark-mode responsive layouts directly in-browser.
    """

    def get_adapter_type(self) -> str:
        return "Browser Native HTML/Tailwind Adapter"

    async def render_exam_theme_and_layout(self, exam: Exam) -> Dict[str, Any]:
        return {
            "adapter_type": self.get_adapter_type(),
            "theme": {
                "variant": "glassmorphic-dark",
                "background_color": "#090d16",
                "card_background": "rgba(23, 31, 48, 0.75)",
                "primary_accent": "#06b6d4",   # Cyan-500
                "secondary_accent": "#8b5cf6", # Purple-500
                "text_primary": "#f3f4f6"
            },
            "components": {
                "timer_badge": "cyan-pill-glow",
                "code_editor": {
                    "engine": "Monaco",
                    "theme": "vs-dark",
                    "font_size": 13
                },
                "question_card": {
                    "border": "1px solid rgba(255, 255, 255, 0.08)",
                    "border_radius": "16px"
                },
                "submit_button": "gradient-emerald-teal"
            }
        }


class LovableMCPPresentationAdapter(BasePresentationAdapter):
    """
    Lovable MCP Server Presentation Adapter.
    Queries Lovable MCP Server (https://mcp.lovable.dev/) to build dynamic AI UI layouts
    and component tokens when Lovable credentials are present.
    """

    def __init__(self, lovable_client: LovableClient):
        self.lovable_client = lovable_client

    def get_adapter_type(self) -> str:
        return "Lovable MCP Server AI Presentation Adapter (https://mcp.lovable.dev/)"

    async def render_exam_theme_and_layout(self, exam: Exam) -> Dict[str, Any]:
        lovable_ui = await self.lovable_client.generate_ui_config(exam)
        return {
            "adapter_type": self.get_adapter_type(),
            "lovable_project_id": lovable_ui.get("project_id"),
            "theme": lovable_ui.get("theme", {}),
            "components": lovable_ui.get("components", {}),
            "lovable_raw_config": lovable_ui
        }


class PresentationAdapterFactory:
    """
    Presentation Adapter Factory.
    Defaults to StandardHTMLPresentationAdapter (Browser Native HTML/CSS/JS hosted directly on server).
    """

    @staticmethod
    def get_adapter(lovable_client: LovableClient = None) -> BasePresentationAdapter:
        # Default unconditionally to Server Hosted Browser Native HTML
        return StandardHTMLPresentationAdapter()
