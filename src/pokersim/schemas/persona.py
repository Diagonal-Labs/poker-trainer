"""Persona file model. Field names match the design doc's "Persona" section one to one.

Slice 3 models the preflop part of a persona. Perception, habits, selector and the other bias
sliders are added with the slices that use them; unknown fields are rejected until then, so a
setting that nothing reads cannot sit in a file unnoticed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Level presets from the design doc: chartAdherence 0.60 / 0.85 / 0.97, mixFidelity 0.0 / 0.3 / 0.9.
LEVEL_CHART_ADHERENCE = {1: 0.60, 2: 0.85, 3: 0.97}
LEVEL_MIX_FIDELITY = {1: 0.0, 2: 0.3, 3: 0.9}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflopSettings(_Strict):
    chart: str  # id of a chart file in data/charts
    chartAdherence: float | None = Field(default=None, ge=0, le=1)  # None: the level preset
    mixFidelity: float | None = Field(default=None, ge=0, le=1)  # None: the level preset


class Biases(_Strict):
    looseness: float = Field(default=0.0, ge=-1, le=1)


class Persona(_Strict):
    schemaVersion: int = 1
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=40)
    description: str = ""
    version: int = Field(default=1, ge=1)
    skillLevel: Literal[1, 2, 3]
    preflop: PreflopSettings
    biases: Biases = Biases()
    targetStats: dict[str, tuple[float, float]] = {}  # stat -> [min, max] percent, for calibration

    def chart_adherence(self) -> float:
        value = self.preflop.chartAdherence
        return LEVEL_CHART_ADHERENCE[self.skillLevel] if value is None else value

    def mix_fidelity(self) -> float:
        value = self.preflop.mixFidelity
        return LEVEL_MIX_FIDELITY[self.skillLevel] if value is None else value
