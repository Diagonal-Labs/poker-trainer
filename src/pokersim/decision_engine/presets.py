"""Level presets and tuning tables, resolved into one plain Profile per persona.

A persona file only lists what differs from its skill level; ``resolve_profile`` fills in the rest
from data/presets.json. Everything tunable lives in data files, never in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pokersim.schemas.persona import Persona


@dataclass(frozen=True)
class Tuning:
    """Engine constants and bias scales, from data/presets.json and data/bias_scales.json."""

    baseline: dict[str, float]
    money: dict[str, Any]
    multiway: dict[str, Any]
    equity_samples: int
    bias_scales: dict[str, float]  # slider name -> pot units at a slider value of 1

    @classmethod
    def from_data(cls, presets: dict[str, Any], bias_scales: dict[str, Any]) -> Tuning:
        scales = presets["perceptionScales"]
        return cls(
            baseline=presets["baseline"],
            money=scales["money"],
            multiway=scales["multiway"],
            equity_samples=int(scales["equitySamples"]),
            bias_scales={
                name: float(v["potUnits"]) for name, v in bias_scales.items() if "potUnits" in v
            },
        )


@dataclass(frozen=True)
class Profile:
    persona_id: str
    version: int
    level: int
    hand_strength: int
    board_texture: int
    money: int
    multiway: int
    category_table: dict[str, float]
    misreads: dict[str, float]
    flags: dict[str, float]
    noise: float
    looseness: float
    aggression: float
    stickiness: float
    risk_aversion: float
    favored_sizes: tuple[str, ...]
    size_strength: float
    tell_leakage: float
    temperature: float
    size_temperature: float


def resolve_profile(persona: Persona, presets: dict[str, Any]) -> Profile:
    preset = presets["levels"][str(persona.skillLevel)]
    pp = preset["perception"]
    per = persona.perception

    def dial(own: int | None, name: str) -> int:
        return pp[name] if own is None else max(own, 1)  # a dial of 0 reads like 1

    style = persona.biases.sizingStyle
    leakage = persona.biases.tellLeakage
    temperature = persona.selector.temperature
    temperature = preset["temperature"] if temperature is None else temperature
    size_temperature = persona.selector.sizeTemperature
    return Profile(
        persona_id=persona.id,
        version=persona.version,
        level=persona.skillLevel,
        hand_strength=dial(per.handStrength, "handStrength"),
        board_texture=dial(per.boardTexture, "boardTexture"),
        money=dial(per.money, "money"),
        multiway=dial(per.multiway, "multiway"),
        category_table={**pp["categoryTable"], **(per.categoryTable or {})},
        misreads={**pp["misreads"], **(per.misreads or {})},
        flags={**pp["flags"], **(per.flags or {})},
        noise=per.noise,
        looseness=persona.biases.looseness,
        aggression=persona.biases.aggression,
        stickiness=persona.biases.stickiness,
        risk_aversion=persona.biases.riskAversion,
        favored_sizes=tuple(
            preset["sizingStyle"]["favoredSizes"]
            if style.favoredSizes is None
            else style.favoredSizes
        ),
        size_strength=(
            preset["sizingStyle"]["strength"] if style.strength is None else style.strength
        ),
        tell_leakage=preset["tellLeakage"] if leakage is None else leakage,
        temperature=temperature,
        size_temperature=temperature if size_temperature is None else size_temperature,
    )
