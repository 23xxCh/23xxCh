"""OpenAI-compatible API client for LLM calls."""

from __future__ import annotations

import json
import re
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"https"}
BLOCKED_HOSTS = {
    "169.254.169.254",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "metadata.google.internal",
}


def validate_base_url(base_url: str) -> str:
    """Validate base_url to prevent SSRF attacks.

    Args:
        base_url: The URL to validate.

    Returns:
        The validated URL.

    Raises:
        ValueError: If the URL scheme is not allowed or the host is blocked.
    """
    parsed = urlparse(base_url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme must be https, got: {parsed.scheme}")
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError(f"Access to blocked host is not allowed: {parsed.hostname}")
    if parsed.hostname and (
        parsed.hostname.startswith("10.")
        or parsed.hostname.startswith("192.168.")
        or parsed.hostname.startswith("172.")
    ):
        raise ValueError(f"Access to private networks is not allowed: {parsed.hostname}")
    return base_url


class OpenAICompatClient:
    """Client for OpenAI-compatible LLM APIs.

    Supports multiple API protocols:
    - chat: OpenAI chat completions API (/v1/chat/completions)
    - responses: OpenAI responses API (/v1/responses)
    - dual: Try responses first, fall back to chat

    The client handles:
    - Endpoint URL construction
    - HTTP request with authentication
    - Response parsing for different formats
    - Protocol fallback for dual mode
    """

    def _endpoint_for(self, base_url: str, protocol: str) -> str:
        """Construct the API endpoint URL.

        Args:
            base_url: The base URL of the API (e.g., "https://api.openai.com").
            protocol: The protocol type ("chat" or "responses").

        Returns:
            The full endpoint URL.

        Raises:
            ValueError: If the protocol is not supported or URL is invalid.
        """
        validate_base_url(base_url)
        root = base_url.rstrip("/")
        versioned = bool(re.search(r"/v[0-9]+$", root))
        if protocol == "chat":
            if versioned:
                return f"{root}/chat/completions"
            return f"{root}/v1/chat/completions"
        if protocol == "responses":
            if versioned:
                return f"{root}/responses"
            return f"{root}/v1/responses"
        raise ValueError(f"unsupported protocol: {protocol}")

    def _post_json(
        self,
        *,
        url: str,
        api_key: str,
        timeout_sec: float,
        payload: dict[str, Any],
        extra_headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a JSON POST request to the API.

        Args:
            url: The endpoint URL.
            api_key: The API key for authentication.
            timeout_sec: Request timeout in seconds.
            payload: The JSON payload to send.
            extra_headers: Optional additional headers.

        Returns:
            The parsed JSON response.

        Raises:
            RuntimeError: If the HTTP request fails.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            for k, v in extra_headers.items():
                headers[str(k)] = str(v)
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=max(1.0, timeout_sec)) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"http {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"network error: {exc}") from exc

    def _extract_chat_text(self, payload: dict[str, Any]) -> str:
        """Extract text content from a chat completions response.

        Args:
            payload: The raw API response.

        Returns:
            The extracted text content, or empty string if not found.
        """
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts: list[str] = []
                for row in content:
                    if isinstance(row, dict):
                        if isinstance(row.get("text"), str):
                            texts.append(row["text"])
                        elif row.get("type") == "text" and isinstance(row.get("text"), str):
                            texts.append(row["text"])
                return "\n".join(texts).strip()
        return ""

    def _extract_responses_text(self, payload: dict[str, Any]) -> str:
        """Extract text content from a responses API response.

        Args:
            payload: The raw API response.

        Returns:
            The extracted text content, or empty string if not found.
        """
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        output = payload.get("output")
        if isinstance(output, list):
            texts: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str):
                            texts.append(text)
            return "\n".join(texts).strip()
        return ""

    def call(
        self,
        *,
        profile: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call the LLM API with the given profile and messages.

        Args:
            profile: The LLM profile containing:
                - base_url: Required API base URL.
                - api_key: Required API key.
                - model: Required model name.
                - protocol: Protocol type ("chat", "responses", "dual").
                - timeout_sec: Optional timeout in seconds.
                - headers: Optional extra headers dict.
            messages: List of message dicts with "role" and "content".

        Returns:
            A dictionary containing:
                - text: The extracted text response.
                - raw: The raw API response.
                - protocol_used: The protocol that was used.

        Raises:
            RuntimeError: If the profile is incomplete or API call fails.
        """
        protocol = str(profile.get("protocol") or "chat").lower()
        base_url = str(profile.get("base_url") or "")
        api_key = str(profile.get("api_key") or "")
        model = str(profile.get("model") or "")
        timeout_sec = float(profile.get("timeout_sec") or 60.0)
        headers = profile.get("headers") if isinstance(profile.get("headers"), dict) else {}
        if not base_url or not api_key or not model:
            raise RuntimeError("incomplete llm profile: base_url/api_key/model required")

        def _call_chat() -> tuple[str, dict[str, Any]]:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
            }
            raw = self._post_json(
                url=self._endpoint_for(base_url, "chat"),
                api_key=api_key,
                timeout_sec=timeout_sec,
                payload=payload,
                extra_headers=headers,
            )
            return self._extract_chat_text(raw), raw

        def _call_responses() -> tuple[str, dict[str, Any]]:
            input_payload = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
            payload = {
                "model": model,
                "input": input_payload,
                "temperature": 0.2,
            }
            raw = self._post_json(
                url=self._endpoint_for(base_url, "responses"),
                api_key=api_key,
                timeout_sec=timeout_sec,
                payload=payload,
                extra_headers=headers,
            )
            return self._extract_responses_text(raw), raw

        if protocol == "chat":
            text, raw = _call_chat()
            return {"text": text, "raw": raw, "protocol_used": "chat"}
        if protocol == "responses":
            text, raw = _call_responses()
            return {"text": text, "raw": raw, "protocol_used": "responses"}
        if protocol == "dual":
            try:
                text, raw = _call_responses()
                if text.strip():
                    return {"text": text, "raw": raw, "protocol_used": "responses"}
            except Exception:
                pass
            text, raw = _call_chat()
            return {"text": text, "raw": raw, "protocol_used": "chat"}
        raise RuntimeError(f"unsupported profile protocol: {protocol}")
