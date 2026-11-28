"""The action selector: turns final scores into one action. It changes nothing.

Step 1 picks the action type with a softmax (fold, call or raise; check or bet when no one has
bet). The raise or bet score is a soft maximum of its size scores, T x log(sum of e^(score / T)),
so better sizes count most. Step 2, only for a bet or raise, picks the size with a second softmax
over the size scores. Together this is exactly one softmax over fold, call and every size.
"""

from __future__ import annotations

import math
import random

from pokersim.decision_engine.scoring import Candidate


def softmax(scores: list[float], temperature: float) -> list[float]:
    top = max(scores)
    weights = [math.exp((s - top) / temperature) for s in scores]
    total = sum(weights)
    return [w / total for w in weights]


def _draw(probabilities: list[float], rng: random.Random) -> int:
    roll = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probabilities):
        cumulative += p
        if roll < cumulative:
            return i
    return len(probabilities) - 1


def final_probabilities(
    candidates: list[Candidate], temperature: float, size_temperature: float
) -> dict[str, float]:
    """Probability of each candidate id after both steps."""
    passive = [c for c in candidates if not c.is_aggressive]
    sizes = [c for c in candidates if c.is_aggressive]
    type_scores = [c.score for c in passive]
    if sizes:
        top = max(c.score for c in sizes)
        soft_max = top + temperature * math.log(
            sum(math.exp((c.score - top) / temperature) for c in sizes)
        )
        type_scores.append(soft_max)
    type_probs = softmax(type_scores, temperature)
    out = {c.id: p for c, p in zip(passive, type_probs, strict=False)}
    if sizes:
        size_probs = softmax([c.score for c in sizes], size_temperature)
        for c, p in zip(sizes, size_probs, strict=True):
            out[c.id] = type_probs[-1] * p
    return out


def choose(
    candidates: list[Candidate], temperature: float, size_temperature: float, rng: random.Random
) -> tuple[Candidate, dict[str, float]]:
    """Pick one candidate. Returns it and the probabilities it was drawn from."""
    passive = [c for c in candidates if not c.is_aggressive]
    sizes = [c for c in candidates if c.is_aggressive]
    probs = final_probabilities(candidates, temperature, size_temperature)
    type_probs = [probs[c.id] for c in passive]
    if sizes:
        type_probs.append(sum(probs[c.id] for c in sizes))
    index = _draw(type_probs, rng)
    if index < len(passive):
        return passive[index], probs
    within = [probs[c.id] / type_probs[-1] for c in sizes]
    return sizes[_draw(within, rng)], probs
