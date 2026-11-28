"""Preflop simulation: play bot-only hands and measure VPIP, PFR and how often each spot occurs.

This is the check that the starter charts land where the personas' targets say, and the source of
a measured spot mix to replace the assumed one in data/spot_mix.json.

VPIP is the share of hands in which a bot voluntarily put chips in preflop (a call of a bet or a
raise; checking the big blind does not count). PFR is the share in which it raised. Every hand is
dealt to every seat, so a bot that is folded to still counts as a hand.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from pokersim.decision_engine.bot_factory import make_bot
from pokersim.decision_engine.bot_seat import BotSeat
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.presets import Tuning
from pokersim.game_engine.game import run_until_human_turn, start_hand
from pokersim.game_engine.positions import chart_group
from pokersim.game_engine.rules import HandSetup, SeatEntry
from pokersim.schemas.persona import Persona
from pokersim.storage.persona_library import PersonaLibrary

STACK = 200  # 100 big blinds at $1/$2


@dataclass
class Counts:
    hands: int = 0
    vpip: int = 0
    pfr: int = 0
    # postflop
    flops: int = 0  # hands in which the bot made a decision on the flop
    showdowns: int = 0  # of those, hands it showed down
    bets: int = 0  # postflop bets and raises
    calls: int = 0  # postflop calls
    cbet_chances: int = 0  # first to act or checked to on the flop as the preflop raiser
    cbets: int = 0
    faced_flop_bet: int = 0
    folded_to_flop_bet: int = 0

    def add(self, hands: int, vpip: int, pfr: int) -> None:
        self.hands += hands
        self.vpip += vpip
        self.pfr += pfr

    def merge(self, other: Counts) -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))


def _persona_counts() -> dict[str, Counts]:
    return {}


def _position_counts() -> dict[tuple[str, str], Counts]:
    return {}


def _spot_counts() -> dict[tuple[str, str], int]:
    return {}


@dataclass
class SimResult:
    by_persona: dict[str, Counts] = field(default_factory=_persona_counts)
    by_position: dict[tuple[str, str], Counts] = field(default_factory=_position_counts)
    first_spot: dict[tuple[str, str], int] = field(default_factory=_spot_counts)  # (position, spot)
    hands: int = 0

    def merge(self, other: SimResult) -> None:
        self.hands += other.hands
        for persona, c in other.by_persona.items():
            self.by_persona.setdefault(persona, Counts()).merge(c)
        for key, c in other.by_position.items():
            self.by_position.setdefault(key, Counts()).merge(c)
        for key, n in other.first_spot.items():
            self.first_spot[key] = self.first_spot.get(key, 0) + n


def build_bots(
    library: PersonaLibrary, persona_ids: list[str], chart_adherence: float | None
) -> list[BotSeat]:
    """One BotSeat per entry. ``chart_adherence`` overrides every persona's value when given."""
    ranking = library.hand_ranking()
    presets = library.presets()
    tuning = Tuning.from_data(presets, library.bias_scales())
    model = EquityModel(ranking)
    scale = library.bias_scales()["looseness"]["classesPerUnit"]
    bots: list[BotSeat] = []
    for persona_id in persona_ids:
        persona: Persona = library.persona(persona_id)
        if chart_adherence is not None:
            settings = persona.preflop.model_copy(update={"chartAdherence": chart_adherence})
            persona = persona.model_copy(update={"preflop": settings})
        chart = library.chart(persona.preflop.chart)
        bots.append(make_bot(persona, chart, ranking, presets, scale, tuning, model))
    return bots


def _count_postflop(c: Counts, bot: BotSeat, showed: bool) -> None:
    flop = [r for r in bot.postflop_records if r.street == "flop"]
    if flop:
        c.flops = 1
        c.showdowns = int(showed)
        first = flop[0]
        if first.state.preflop_aggressor and not first.state.facing_bet:
            c.cbet_chances = 1
            c.cbets = int(first.action.kind == "bet")
    for r in bot.postflop_records:
        if r.action.kind in ("bet", "raise"):
            c.bets += 1
        elif r.action.kind == "call":
            c.calls += 1
        if r.street == "flop" and r.state.facing_bet:
            c.faced_flop_bet += 1
            c.folded_to_flop_bet += int(r.action.kind == "fold")


def simulate_range(
    data_dir: Path,
    persona_ids: list[str],
    first_hand: int,
    last_hand: int,
    seed: int,
    chart_adherence: float | None,
) -> SimResult:
    """Play hands ``first_hand`` up to ``last_hand``. The button moves one seat every hand."""
    library = PersonaLibrary(data_dir)
    bots = build_bots(library, persona_ids, chart_adherence)
    n = len(bots)
    seats = dict(enumerate(bots))
    result = SimResult()
    for hand_number in range(first_hand, last_hand):
        setup = HandSetup(tuple(SeatEntry(i, STACK) for i in range(n)), button=hand_number % n)
        for bot in bots:
            bot.records.clear()
            bot.postflop_records.clear()
        hand = start_hand(setup, seed, hand_number)
        positions = {s.seat: s.position for s in hand.snapshot().seats}
        run_until_human_turn(hand, seats, seed, hand_number)
        shown = hand.result().shown
        result.hands += 1
        for seat, bot in seats.items():
            group = chart_group(positions[seat])
            raised = any(r.action.kind in ("bet", "raise") for r in bot.records)
            voluntary = raised or any(
                r.action.kind == "call" and r.to_call > 0 for r in bot.records
            )
            mine = Counts(hands=1, vpip=int(voluntary), pfr=int(raised))
            _count_postflop(mine, bot, seat in shown)
            result.by_persona.setdefault(bot.persona.id, Counts()).merge(mine)
            result.by_position.setdefault((bot.persona.id, group), Counts()).merge(mine)
            if bot.records:
                key = (group, bot.records[0].spot.spot)
                result.first_spot[key] = result.first_spot.get(key, 0) + 1
    return result


def simulate(
    data_dir: Path,
    persona_ids: list[str],
    hands: int,
    seed: int = 1,
    chart_adherence: float | None = None,
    workers: int | None = None,
) -> SimResult:
    """Run ``hands`` hands, split across worker processes. The result does not depend on workers."""
    workers = workers or os.cpu_count() or 1
    step = -(-hands // (workers * 4)) or 1
    ranges = [(a, min(a + step, hands)) for a in range(0, hands, step)]
    total = SimResult()
    if workers == 1 or len(ranges) == 1:
        for a, b in ranges:
            total.merge(simulate_range(data_dir, persona_ids, a, b, seed, chart_adherence))
        return total
    with ProcessPoolExecutor(workers) as pool:
        futures = [
            pool.submit(simulate_range, data_dir, persona_ids, a, b, seed, chart_adherence)
            for a, b in ranges
        ]
        for f in futures:
            total.merge(f.result())
    return total


def pct(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


def report(result: SimResult, library: PersonaLibrary) -> str:
    """A plain-text table of measured VPIP and PFR against each persona's target range."""
    lines = [f"{'persona':<16}{'hands':>8}{'VPIP':>8}{'target':>10}{'PFR':>8}{'target':>10}  ok"]
    for persona_id, c in result.by_persona.items():
        targets = library.persona(persona_id).targetStats
        row = f"{persona_id:<16}{c.hands:>8}"
        ok = True
        for name, count in (("vpip", c.vpip), ("pfr", c.pfr)):
            value = pct(count, c.hands)
            lo, hi = targets.get(name, (0.0, 100.0))
            ok &= lo <= value <= hi
            row += f"{value:>7.1f}%{f'{lo:g}-{hi:g}':>10}"
        lines.append(row + ("  yes" if ok else "  NO"))
    return "\n".join(lines)


def postflop_report(result: SimResult, library: PersonaLibrary | None = None) -> str:
    """Postflop stats: aggression factor, went to showdown, flop c-bet and fold to a flop bet."""
    head = f"{'persona':<16}{'AF':>6}{'WTSD%':>8}{'cbet%':>8}{'fold to bet%':>14}{'saw flop%':>11}"
    lines = [head + "  outside target"]
    for persona_id, c in result.by_persona.items():
        af = c.bets / c.calls if c.calls else float("inf")
        measured = {
            "af": af,
            "wtsd": pct(c.showdowns, c.flops),
            "cbet": pct(c.cbets, c.cbet_chances),
            "foldToBet": pct(c.folded_to_flop_bet, c.faced_flop_bet),
        }
        targets = library.persona(persona_id).targetStats if library else {}
        off = [
            name
            for name, value in measured.items()
            if name in targets and not targets[name][0] <= value <= targets[name][1]
        ]
        lines.append(
            f"{persona_id:<16}{af:>6.2f}{measured['wtsd']:>8.1f}{measured['cbet']:>8.1f}"
            f"{measured['foldToBet']:>14.1f}{pct(c.flops, c.hands):>11.1f}  "
            + (", ".join(off) or "-")
        )
    return "\n".join(lines)
