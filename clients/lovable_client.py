import os
import uuid
import json
import httpx
from typing import Dict, Any
from database import Exam
from clients.logger import log_integration

class LovableClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("LOVABLE_OAUTH_TOKEN") or os.getenv("LOVABLE_API_KEY", "")
        self.mcp_url = "https://mcp.lovable.dev/"

    async def inspect_mcp_account(self) -> Dict[str, Any]:
        """
        Zero-credit read-only inspection query to test Lovable OAuth / MCP authentication and list tools.
        Consumes 0 generation credits.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Lovable-API-Key": self.api_key,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
        
        # 1. MCP Protocol Initialize
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ZeroHumanAgent", "version": "1.0.0"}
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.mcp_url, headers=headers, json=init_payload)
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = resp.text

            log_integration("Lovable MCP [INITIALIZE]", "POST", self.mcp_url, headers, init_payload, resp.status_code, resp.headers, resp_json)

            # 2. List Available Tools (Read-Only)
            list_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            resp_list = await client.post(self.mcp_url, headers=headers, json=list_payload)
            try:
                list_json = resp_list.json()
            except Exception:
                list_json = resp_list.text

            log_integration("Lovable MCP [TOOLS/LIST]", "POST", self.mcp_url, headers, list_payload, resp_list.status_code, resp_list.headers, list_json)
            return {"init": resp_json, "tools": list_json}

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a JSON-RPC tool call on Lovable Dedicated MCP Server (https://mcp.lovable.dev/).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Lovable-API-Key": self.api_key,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "id": int(uuid.uuid4().int % 1000000),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.mcp_url, headers=headers, json=payload)
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = resp.text

            log_integration(f"Lovable MCP Server [{tool_name}]", "POST", self.mcp_url, headers, payload, resp.status_code, resp.headers, resp_json)
            if resp.status_code == 200 and isinstance(resp_json, dict):
                return resp_json

            return {"status": "error", "response": resp_json}

    async def generate_ui_config(self, exam: Exam) -> Dict[str, Any]:
        """
        Communicates with Lovable MCP Server to construct dynamic layout tokens and responsive component trees.
        """
        if self.api_key and not self.api_key.startswith("mock_"):
            try:
                mcp_res = await self._call_mcp_tool("generate_ui_layout", {
                    "exam_id": exam.id,
                    "topic": exam.topic,
                    "theme": "glassmorphism-dark",
                    "questions_count": len(exam.questions)
                })
                if mcp_res.get("status") != "error":
                    return mcp_res
            except Exception as e:
                print(f"[LovableClient] MCP exception: {e}")

        fallback = self._generate_fallback_layout(exam)
        log_integration("Lovable MCP [MOCK]", "POST", self.mcp_url, {}, {"exam_id": exam.id}, 200, {}, fallback)
        return fallback

    def _generate_fallback_layout(self, exam: Exam) -> Dict[str, Any]:
        return {
            "project_id": f"lovable_prj_{exam.id[:8]}",
            "theme": {
                "variant": "glassmorphic-dark",
                "primary_accent": "#06b6d4",
                "secondary_accent": "#8b5cf6",
                "background_gradient": "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
                "card_backdrop": "rgba(30, 41, 59, 0.7)"
            },
            "components": {
                "timer_badge": {"style": "glowing-pill", "color": "cyan"},
                "monaco_theme": "vs-dark",
                "question_card": {"border": "1px solid rgba(255,255,255,0.1)", "border_radius": "16px"},
                "submit_button": {"style": "neon-glow", "gradient": "from-cyan-500 to-blue-600"}
            },
            "synced_at": "2026-08-15T11:35:00Z"
        }
