"""PersonaLibrary: personas, charts and tuning tables as JSON files (the design doc's V1 choice).

Reads files and validates personas with the schemas. Chart contents are plain dicts here; the
Decision engine validates them (``validate_chart``), since storage may import only schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pokersim.schemas.persona import Persona


class PersonaLibrary:
    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir)

    def _read(self, relative: str) -> Any:
        return json.loads((self.root / relative).read_text())

    def persona_ids(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "personas").glob("*.json"))

    def persona(self, persona_id: str) -> Persona:
        persona = Persona.model_validate(self._read(f"personas/{persona_id}.json"))
        if persona.id != persona_id:
            raise ValueError(f"personas/{persona_id}.json has id {persona.id!r}")
        return persona

    def chart_ids(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "charts").glob("*.json"))

    def chart(self, chart_id: str) -> dict[str, Any]:
        chart: dict[str, Any] = self._read(f"charts/{chart_id}.json")
        return chart

    def hand_ranking(self) -> list[str]:
        """All 169 hand classes, strongest first (equity against one random hand)."""
        classes: list[dict[str, Any]] = self._read("hand_ranking.json")["classes"]
        return [c["hand"] for c in classes]

    def bias_scales(self) -> dict[str, Any]:
        scales: dict[str, Any] = self._read("bias_scales.json")
        return scales

    def presets(self) -> dict[str, Any]:
        """Level presets, baseline-engine constants and perception scales (data/presets.json)."""
        presets: dict[str, Any] = self._read("presets.json")
        return presets
