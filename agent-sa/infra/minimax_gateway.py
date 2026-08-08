"""MiniMax-backed implementation of domain.ports.LlmGateway.

A second adapter behind the same LlmGateway port as AnthropicGateway — swap
providers via LLM_PROVIDER in .env, nothing else in the codebase changes
(handlers only ever depend on the port, see domain/ports.py).

Uses MiniMax's OpenAI-compatible chat-completions endpoint over plain HTTP
(httpx is already a dependency — no MiniMax SDK needed). Endpoint path and
payload shape are correct as of this repo's last check against MiniMax's
docs; if MiniMax changes their API, this is the one place to fix it — verify
against https://www.minimax.io/platform/document before relying on it in
production, since it hasn't been exercised against a live key here.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via is_available()
    HTTPX_AVAILABLE = False

_DEFAULT_BASE_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"


class MinimaxGateway:
    """Implements domain.ports.LlmGateway using the MiniMax chat-completions API.

    Config precedence: explicit constructor arg > env var > hardcoded default.
    See .env.example for MINIMAX_API_KEY / MINIMAX_MODEL / MINIMAX_BASE_URL / MINIMAX_GROUP_ID.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        group_id: Optional[str] = None,
    ):
        self.model = model or os.getenv("MINIMAX_MODEL")
        self.max_tokens = max_tokens or int(os.getenv("MINIMAX_MAX_TOKENS", "4000"))
        self._api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self._base_url = base_url or os.getenv("MINIMAX_BASE_URL", _DEFAULT_BASE_URL)
        self._group_id = group_id or os.getenv("MINIMAX_GROUP_ID")

    def is_available(self) -> bool:
        return HTTPX_AVAILABLE and bool(self._api_key) and bool(self.model)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx package not installed. Install with: pip install httpx")
        if not self._api_key:
            raise RuntimeError("MINIMAX_API_KEY not set. export MINIMAX_API_KEY=...")
        if not self.model:
            raise RuntimeError("MINIMAX_MODEL not set. export MINIMAX_MODEL=... (e.g. abab6.5s-chat)")

        params = {"GroupId": self._group_id} if self._group_id else None

        response = httpx.post(
            self._base_url,
            params=params,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()

        # MiniMax reports application-level errors with HTTP 200 + a non-zero
        # base_resp.status_code (auth failures, quota, bad model id, ...).
        base_resp = payload.get("base_resp") or {}
        if base_resp.get("status_code", 0) != 0:
            raise RuntimeError(
                f"MiniMax API error {base_resp.get('status_code')}: {base_resp.get('status_msg')}"
            )

        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected MiniMax response shape: {payload}") from e
