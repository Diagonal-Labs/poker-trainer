"""Build a BotSeat from a persona and the data it needs. Takes plain data, reads no files."""

from __future__ import annotations

from typing import Any

from pokersim.decision_engine.bot_seat import BotSeat
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.preflop import ChartPolicy, validate_chart
from pokersim.decision_engine.presets import Tuning, resolve_profile
from pokersim.schemas.persona import Persona


def make_bot(
    persona: Persona,
    chart: dict[str, Any],
    ranking: list[str],
    presets: dict[str, Any],
    looseness_classes_per_unit: float,
    tuning: Tuning,
    model: EquityModel,
) -> BotSeat:
    problems = validate_chart(chart)
    if problems:
        raise ValueError(f"chart {persona.preflop.chart}: {problems[0]}")
    shift = round(persona.biases.looseness * looseness_classes_per_unit)
    profile = resolve_profile(persona, presets)
    return BotSeat(persona, ChartPolicy(chart, ranking, shift), profile, tuning, model)
