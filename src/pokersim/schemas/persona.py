"""Persona file model. Field names match the design doc's "Persona" section one to one.

Slices 3 and 4 model the preflop part, four perception dials, the four bias sliders, sizing style,
the selector temperatures and tell leakage. Habits, tells and the other dials are added with the
slices that use them. Unknown fields are rejected until then, so a setting that nothing reads
cannot sit in a file unnoticed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Level presets from the design doc: chartAdherence 0.60 / 0.85 / 0.97, mixFidelity 0.0 / 0.3 / 0.9.
LEVEL_CHART_ADHERENCE = {1: 0.60, 2: 0.85, 3: 0.97}
LEVEL_MIX_FIDELITY = {1: 0.0, 2: 0.3, 3: 0.9}


# Registries. A name that is not listed here is rejected, so a typo cannot silently do nothing.
SIZE_IDS = (
    "bet_33", "bet_66", "bet_100", "bet_150", "bet_allin",
    "raise_min", "raise_3x", "raise_35x", "raise_allin",
)  # fmt: skip
HAND_CATEGORIES = ("monster", "strong", "medium", "weak", "strong_draw", "weak_draw", "air")
MISREADS = ("pairOvervalue", "aceHighOvervalue")
# Every flag has exactly one consumer (the design doc's "Flag rule").
FLAG_CONSUMERS = {"scary_board": "perception", "big_bet": "perception", "protect": "sizing"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflopSettings(_Strict):
    chart: str  # id of a chart file in data/charts
    chartAdherence: float | None = Field(default=None, ge=0, le=1)  # None: the level preset
    mixFidelity: float | None = Field(default=None, ge=0, le=1)  # None: the level preset


class PerceptionSettings(_Strict):
    """The four dials implemented so far (0 to 3; None means the skill level). The rest of the
    doc's seven dials (position, stackDepth, opponentModeling) are added with the slices that use
    them. A dial of 0 reads like 1."""

    handStrength: int | None = Field(default=None, ge=0, le=3)
    boardTexture: int | None = Field(default=None, ge=0, le=3)
    money: int | None = Field(default=None, ge=0, le=3)
    multiway: int | None = Field(default=None, ge=0, le=3)
    categoryTable: dict[str, float] | None = None  # hand category -> equity, levels 1 and 2
    misreads: dict[str, float] | None = None  # named misread -> equity points, 0 to 0.15
    noise: float = Field(default=0.0, ge=0, le=0.1)
    flags: dict[str, float] | None = None  # flag name -> strength, 0 to 2

    @model_validator(mode="after")
    def _check_registries(self) -> PerceptionSettings:
        for name in self.categoryTable or {}:
            if name not in HAND_CATEGORIES:
                raise ValueError(f"perception.categoryTable: unknown category {name!r}")
        for name, value in (self.categoryTable or {}).items():
            if not 0 <= value <= 1:
                raise ValueError(f"perception.categoryTable.{name} must be between 0 and 1")
        for name, value in (self.misreads or {}).items():
            if name not in MISREADS:
                raise ValueError(f"perception.misreads: unknown misread {name!r}")
            if not 0 <= value <= 0.15:
                raise ValueError(f"perception.misreads.{name} must be between 0 and 0.15")
        for name, value in (self.flags or {}).items():
            if FLAG_CONSUMERS.get(name) != "perception":
                raise ValueError(f"perception.flags: {name!r} is not a perception flag")
            if not 0 <= value <= 2:
                raise ValueError(f"perception.flags.{name} must be between 0 and 2")
        return self


class SizingStyle(_Strict):
    favoredSizes: list[str] | None = None
    strength: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _check_sizes(self) -> SizingStyle:
        for size in self.favoredSizes or []:
            if size not in SIZE_IDS:
                raise ValueError(f"biases.sizingStyle.favoredSizes: unknown size {size!r}")
        return self


class Biases(_Strict):
    looseness: float = Field(default=0.0, ge=-1, le=1)
    aggression: float = Field(default=0.0, ge=-1, le=1)
    stickiness: float = Field(default=0.0, ge=-1, le=1)
    riskAversion: float = Field(default=0.0, ge=-1, le=1)
    sizingStyle: SizingStyle = SizingStyle()
    tellLeakage: float | None = Field(default=None, ge=0, le=1)


class Selector(_Strict):
    temperature: float | None = Field(default=None, ge=0.02, le=0.25)
    sizeTemperature: float | None = Field(default=None, ge=0.02, le=0.25)


class Persona(_Strict):
    schemaVersion: int = 1
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=40)
    description: str = ""
    version: int = Field(default=1, ge=1)
    skillLevel: Literal[1, 2, 3]
    perception: PerceptionSettings = PerceptionSettings()
    preflop: PreflopSettings
    biases: Biases = Biases()
    selector: Selector = Selector()
    targetStats: dict[str, tuple[float, float]] = {}  # stat -> [min, max] percent, for calibration

    def chart_adherence(self) -> float:
        value = self.preflop.chartAdherence
        return LEVEL_CHART_ADHERENCE[self.skillLevel] if value is None else value

    def mix_fidelity(self) -> float:
        value = self.preflop.mixFidelity
        return LEVEL_MIX_FIDELITY[self.skillLevel] if value is None else value
