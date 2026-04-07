# context.md §3 — Hexagonal Architecture: zero framework imports in domain layer.
# Pure Python frozen dataclasses. stdlib only.

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.shared.domain.base_value_object import BaseValueObject
from src.shared.domain.exceptions import ValidationError

_VALID_CURRENCIES = {"INR", "USDC"}
_VALID_ACTIONS = {"OFFER", "ACCEPT", "REJECT", "COUNTER", "PAUSE"}
_VALID_AUTOMATION = {"FULL", "SUPERVISED", "MANUAL"}
_VALID_RISK_APPETITES = {"LOW", "MEDIUM", "HIGH"}


@dataclass(frozen=True)
class OfferValue(BaseValueObject):
    """Monetary offer amount with currency."""

    amount: Decimal = Decimal("0")
    currency: str = "INR"

    def __post_init__(self) -> None:
        if self.amount <= Decimal("0"):
            raise ValidationError(
                f"OfferValue amount must be > 0, got {self.amount}.",
                field="amount",
            )
        if self.currency not in _VALID_CURRENCIES:
            raise ValidationError(
                f"Currency must be one of {_VALID_CURRENCIES}, got '{self.currency}'.",
                field="currency",
            )


@dataclass(frozen=True)
class Confidence(BaseValueObject):
    """LLM-generated confidence score in [0.0, 1.0]."""

    value: float = 0.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValidationError(
                f"Confidence must be in [0.0, 1.0], got {self.value}.",
                field="value",
            )


@dataclass(frozen=True)
class AgentAction(BaseValueObject):
    """Agent action token returned by LLM."""

    value: str = ""

    def __post_init__(self) -> None:
        upper = self.value.upper()
        object.__setattr__(self, "value", upper)
        if upper not in _VALID_ACTIONS:
            raise ValidationError(
                f"AgentAction must be one of {_VALID_ACTIONS}, got '{self.value}'.",
                field="value",
            )


@dataclass(frozen=True)
class RoundNumber(BaseValueObject):
    """Non-negative monotonically increasing round counter."""

    value: int = 0

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValidationError(
                f"RoundNumber must be >= 0, got {self.value}.",
                field="value",
            )


@dataclass(frozen=True)
class AutomationLevel(BaseValueObject):
    """Agent automation level controlling human-in-the-loop behaviour."""

    value: str = "FULL"

    def __post_init__(self) -> None:
        upper = self.value.upper()
        object.__setattr__(self, "value", upper)
        if upper not in _VALID_AUTOMATION:
            raise ValidationError(
                f"AutomationLevel must be one of {_VALID_AUTOMATION}, got '{self.value}'.",
                field="value",
            )


@dataclass(frozen=True)
class StrategyWeights(BaseValueObject):
    """
    LLM agent strategy configuration derived from historical session data.

    Persisted per AgentProfile; updated after each session (rolling average).
    """

    concession_rate: float = 0.05       # 0.0–1.0: how aggressively to concede
    acceptance_threshold: float = 0.02  # 0.0–1.0: ZOPA auto-accept gap
    avg_deviation: float = 0.0          # historical avg price deviation %
    avg_rounds: float = 5.0             # historical avg rounds to agreement
    win_rate: float = 0.5               # historical % sessions agreed
    stall_threshold: int = 10           # rounds before HUMAN_REVIEW escalation

    def __post_init__(self) -> None:
        if not (0.0 <= self.concession_rate <= 1.0):
            raise ValidationError(
                f"concession_rate must be in [0.0, 1.0], got {self.concession_rate}.",
                field="concession_rate",
            )
        if not (0.0 <= self.acceptance_threshold <= 1.0):
            raise ValidationError(
                f"acceptance_threshold must be in [0.0, 1.0], got {self.acceptance_threshold}.",
                field="acceptance_threshold",
            )
        if self.stall_threshold < 1:
            raise ValidationError(
                f"stall_threshold must be >= 1, got {self.stall_threshold}.",
                field="stall_threshold",
            )


@dataclass(frozen=True)
class RiskProfile(BaseValueObject):
    """
    Enterprise risk constraints injected into LLM context (REDACTED before send).

    SECURITY: budget_ceiling exact value NEVER sent to LLM.
    Redacted to HIGH/MEDIUM/LOW bucket in PersonalizationBuilder.
    """

    budget_ceiling: Decimal = Decimal("1000000")  # Max price buyer will pay (INR)
    margin_floor: Decimal = Decimal("10")         # Min margin seller accepts (%)
    liquidity_buffer: Decimal = Decimal("50000")  # Reserved liquidity (INR)
    risk_appetite: str = "MEDIUM"

    def __post_init__(self) -> None:
        if self.margin_floor < Decimal("0") or self.margin_floor > Decimal("100"):
            raise ValidationError(
                f"margin_floor must be in [0, 100], got {self.margin_floor}.",
                field="margin_floor",
            )
        if self.risk_appetite not in _VALID_RISK_APPETITES:
            raise ValidationError(
                f"risk_appetite must be one of {_VALID_RISK_APPETITES}, "
                f"got '{self.risk_appetite}'.",
                field="risk_appetite",
            )
