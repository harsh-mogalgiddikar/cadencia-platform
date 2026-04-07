# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.shared.domain.base_entity import BaseEntity


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class IndustryPlaybook(BaseEntity):
    """
    Industry-specific negotiation context injected into LLM system prompt.

    context.md §6.2: playbook merged into agent context per vertical.
    to_prompt_context() returns only data safe for LLM consumption.
    """

    vertical: str = ""                 # e.g. "steel", "textiles", "chemicals"
    playbook_config: dict = field(default_factory=dict)

    def to_prompt_context(self) -> dict:
        """
        Return dict safe for LLM prompt injection.

        Include: pricing_norms, payment_schedules, typical_discount_ranges,
                 seasonal_factors, standard_slas.
        Exclude: internal config keys not intended for agent consumption.
        """
        allowed_keys = {
            "pricing_norms",
            "payment_schedules",
            "typical_discount_ranges",
            "seasonal_factors",
            "standard_slas",
            "common_terms",
        }
        return {
            "vertical": self.vertical,
            **{k: v for k, v in self.playbook_config.items() if k in allowed_keys},
        }
