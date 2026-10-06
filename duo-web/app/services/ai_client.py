"""OpenAI-compatible AI client with three-slot automatic failover."""
from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        OpenAI,
        RateLimitError,
    )
    OPENAI_SDK_AVAILABLE = True
except ImportError:  # The core tracker can still boot without AI installed.
    OpenAI = None
    APIConnectionError = APITimeoutError = APIStatusError = AuthenticationError = RateLimitError = Exception
    OPENAI_SDK_AVAILABLE = False

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AIKeySlot
from .security import decrypt_secret, encrypt_secret, mask_secret

logger = logging.getLogger(__name__)


@dataclass
class ProviderSlot:
    slot: int
    provider: str
    base_url: str
    model: str
    api_key: str
    masked_key: str


class AIClientManager:
    """Loads provider slots from SQLite and tries them in priority order."""

    def __init__(self, db: Session):
        self.db = db

    def slots(self) -> list[ProviderSlot]:
        rows = self.db.scalars(select(AIKeySlot).order_by(AIKeySlot.slot)).all()
        result: list[ProviderSlot] = []
        for row in rows:
            key = decrypt_secret(row.encrypted_key)
            if row.enabled and key:
                result.append(ProviderSlot(row.slot, row.provider, row.base_url, row.model, key, mask_secret(key)))
        return result

    def save_slot(
        self,
        slot_number: int,
        provider: str,
        base_url: str,
        model: str,
        key: str | None,
        enabled: bool,
    ) -> AIKeySlot:
        row = self.db.scalar(select(AIKeySlot).where(AIKeySlot.slot == slot_number))
        if row is None:
            row = AIKeySlot(slot=slot_number)
            self.db.add(row)
        row.provider = provider
        row.base_url = base_url
        row.model = model
        row.enabled = enabled
        if key is not None:
            row.encrypted_key = encrypt_secret(key) if key else None
        row.last_status = "untested"
        row.last_error = None
        self.db.flush()
        return row

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if not OPENAI_SDK_AVAILABLE:
            return False
        if isinstance(exc, (RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError)):
            return True
        if isinstance(exc, APIStatusError):
            return exc.status_code in {401, 403, 408, 429, 500, 502, 503, 504}
        return False

    def _call_slot(self, slot: ProviderSlot, prompt: str, temperature: float = 0.7) -> str:
        if not OPENAI_SDK_AVAILABLE:
            raise RuntimeError("OpenAI-compatible SDK is not installed. Run: pip install -r requirements.txt")
        client = OpenAI(api_key=slot.api_key, base_url=slot.base_url, timeout=12.0, max_retries=0)
        response = client.chat.completions.create(
            model=slot.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are the AI companion inside Duo Tracker. Be concise, practical, friendly, and playful.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise RuntimeError("The AI provider returned an empty response.")
        return content.strip()

    def generate(self, prompt: str, temperature: float = 0.7, simulate_first_failure: bool = False) -> tuple[str, int]:
        slots = self.slots()
        if not slots:
            raise RuntimeError("No enabled AI key is configured.")
        last_error: Exception | None = None
        for index, slot in enumerate(slots):
            try:
                if simulate_first_failure and index == 0:
                    raise RuntimeError("Simulated 429")
                text = self._call_slot(slot, prompt, temperature)
                self._mark(slot.slot, "ok", None)
                logger.info("AI request succeeded using slot %s (%s).", slot.slot, slot.provider)
                return text, slot.slot
            except Exception as exc:
                last_error = exc
                self._mark(slot.slot, "failed", type(exc).__name__)
                logger.warning("AI slot %s failed with %s; trying next slot if available.", slot.slot, type(exc).__name__)
                if simulate_first_failure and index == 0:
                    continue
                if not self._is_retryable(exc):
                    raise
        raise RuntimeError(f"All configured AI providers failed. Last error: {last_error}")

    def test_slot(self, slot_number: int) -> tuple[bool, str]:
        row = self.db.scalar(select(AIKeySlot).where(AIKeySlot.slot == slot_number))
        if row is None:
            return False, "Slot not configured."
        key = decrypt_secret(row.encrypted_key)
        if not key or not row.enabled:
            return False, "Slot is disabled or has no key."
        slot = ProviderSlot(row.slot, row.provider, row.base_url, row.model, key, mask_secret(key))
        try:
            self._call_slot(slot, "Reply with exactly: Duo Tracker connection OK", 0)
            self._mark(slot_number, "ok", None)
            return True, "Connection OK."
        except Exception as exc:
            self._mark(slot_number, "failed", type(exc).__name__)
            return False, f"Connection failed: {type(exc).__name__}."

    def test_failover(self) -> tuple[bool, str, int | None]:
        try:
            text, used_slot = self.generate(
                "This is a failover test. Reply with exactly: Failover path OK",
                temperature=0,
                simulate_first_failure=True,
            )
            return True, text, used_slot
        except Exception as exc:
            return False, str(exc), None

    def _mark(self, slot_number: int, status: str, error: str | None) -> None:
        row = self.db.scalar(select(AIKeySlot).where(AIKeySlot.slot == slot_number))
        if row:
            row.last_status = status
            row.last_error = error
            self.db.flush()
