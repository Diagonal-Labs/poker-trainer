from pathlib import Path

import pytest
from pydantic import ValidationError

from pokersim.decision_engine.preflop import validate_chart
from pokersim.schemas.persona import Persona
from pokersim.storage.persona_library import PersonaLibrary

DATA = Path(__file__).resolve().parent.parent / "data"
LIB = PersonaLibrary(DATA)
MINIMAL = {"id": "x", "name": "X", "skillLevel": 2, "preflop": {"chart": "l2_nit"}}


def test_six_starter_personas_load() -> None:
    assert LIB.persona_ids() == [
        "dave_station",
        "fit_or_fold",
        "lag_regular",
        "maniac",
        "nit",
        "solid_regular",
    ]
    for persona_id in LIB.persona_ids():
        assert LIB.persona(persona_id).id == persona_id


def test_every_persona_points_at_a_valid_chart_of_its_level() -> None:
    for persona_id in LIB.persona_ids():
        persona = LIB.persona(persona_id)
        chart = LIB.chart(persona.preflop.chart)
        assert validate_chart(chart) == []
        assert chart["skillLevel"] == persona.skillLevel


def test_target_stats_are_ordered_ranges() -> None:
    for persona_id in LIB.persona_ids():
        for lo, hi in LIB.persona(persona_id).targetStats.values():
            assert 0 <= lo < hi <= 100


def test_hand_ranking_lists_all_169_classes_strongest_first() -> None:
    ranking = LIB.hand_ranking()
    assert len(ranking) == len(set(ranking)) == 169
    assert ranking[0] == "AA"


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="speling"):
        Persona.model_validate({**MINIMAL, "speling": 1})
    with pytest.raises(ValidationError, match="chartAdhernce"):
        Persona.model_validate({**MINIMAL, "preflop": {"chart": "l2_nit", "chartAdhernce": 1}})


def test_out_of_range_values_name_the_field() -> None:
    bad = {**MINIMAL, "preflop": {"chart": "l2_nit", "chartAdherence": 1.5}}
    with pytest.raises(ValidationError, match=r"preflop\.chartAdherence"):
        Persona.model_validate(bad)
    with pytest.raises(ValidationError, match=r"biases\.looseness"):
        Persona.model_validate({**MINIMAL, "biases": {"looseness": 2}})
    with pytest.raises(ValidationError, match="skillLevel"):
        Persona.model_validate({**MINIMAL, "skillLevel": 4})


def test_level_presets_fill_in_adherence_and_mix_fidelity() -> None:
    expected = {1: (0.60, 0.0), 2: (0.85, 0.3), 3: (0.97, 0.9)}
    for level, (adherence, fidelity) in expected.items():
        persona = Persona.model_validate({**MINIMAL, "skillLevel": level})
        assert (persona.chart_adherence(), persona.mix_fidelity()) == (adherence, fidelity)


def test_explicit_settings_beat_the_preset() -> None:
    persona = Persona.model_validate(
        {**MINIMAL, "preflop": {"chart": "l2_nit", "chartAdherence": 0.5, "mixFidelity": 1}}
    )
    assert (persona.chart_adherence(), persona.mix_fidelity()) == (0.5, 1.0)


def test_a_persona_file_must_match_its_name(tmp_path: Path) -> None:
    (tmp_path / "personas").mkdir()
    (tmp_path / "personas" / "other.json").write_text(
        '{"id": "x", "name": "X", "skillLevel": 1, "preflop": {"chart": "l1_basic"}}'
    )
    with pytest.raises(ValueError, match="has id"):
        PersonaLibrary(tmp_path).persona("other")
