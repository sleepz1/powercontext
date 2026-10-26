from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class PcPingTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        note = str(tool_parameters.get("note") or "").strip()
        message = "PowerContext Dify plugin skeleton. No Server request was sent."
        yield self.create_json_message(
            {
                "ok": True,
                "operation": "ping",
                "status": "skeleton",
                "result": {"message": message, "note": note},
            }
        )
        if note:
            message = f"{message} Note: {note}"
        yield self.create_text_message(message)
