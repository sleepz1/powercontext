from __future__ import annotations

from urllib.parse import urlparse

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class PowerContextProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        server_url = str(credentials.get("server_url") or "").strip()
        api_token = str(credentials.get("api_token") or "").strip()
        parsed = urlparse(server_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ToolProviderCredentialValidationError(
                "server_url must be an http or https URL reachable by the plugin daemon."
            )
        if not api_token:
            raise ToolProviderCredentialValidationError("api_token is required.")
