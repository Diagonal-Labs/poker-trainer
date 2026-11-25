"""Generate the six starter charts from the hand ranking and per-persona profiles.
Each persona has base frequencies per spot, a ranking distortion (bonuses and noise), and two scale knobs
(raise-type kr, call-type kc) that are fitted so the chart's implied PFR and VPIP hit the persona's target midpoints."""

import hashlib
import json
from pathlib import Path
from typing import Any

from pokersim.engine.chart import RANKS as R
from pokersim.engine.chart import combos, implied_stats, validate_chart

ROOT = Path(__file__).resolve().parent.parent
MIX = json.loads((ROOT / "data" / "spot_mix.json").read_text())
rk = json.loads((ROOT / "data" / "hand_ranking.json").read_text())["classes"]
EQ = {c["hand"]: c["equity"] for c in rk}
CL = list(EQ)
PF = {
    "early": 0.6,
    "middle": 0.8,
    "cutoff": 1.1,
    "button": 1.5,
    "sb": 1.2,
}  # open-spot position factor


def noise(persona, hand, tag):
    h = hashlib.sha256(f"{persona}:{tag}:{hand}".encode()).digest()[0] / 255
    return h * 2 - 1


def is_conn(h):
    return len(h) == 3 and 0 < R.index(h[0]) - R.index(h[1]) <= 2


def score(persona, hand, tag, p):
    e = EQ[hand]
    b = p["bonus"]
    pair = len(hand) == 2
    suited = len(hand) == 3 and hand[2] == "s"
    hi, lo = R.index(hand[0]), R.index(hand[1])
    if pair:
        e += b.get("pair", 0)
    if suited:
        e += b.get("suited", 0)
    if is_conn(hand) and suited:
        e += b.get("connector", 0)
    if hand[0] == "A" and not pair and not suited:
        e += b.get("offsuit_ace", 0)
    if hi >= 8 and lo >= 8:
        e += b.get("broadway", 0)
    return e + p["noise"].get(tag, 0) * noise(persona, hand, tag)


# base profile: r0 open raise, l0 open limp, a0 vs_limp raise, b0 vs_limp call, c0 3bet, d0 call vs raise,
# e0 4bet, f0 call vs 3bet, g0 5bet, h0 call vs 4bet (fractions of all hands, before scaling)
P = {
    "l2_nit": dict(
        id="l2_nit",
        name="Nit (Level 2)",
        level=2,
        target=(12, 9.5),
        base=dict(
            r0=0.13, l0=0.0, a0=0.06, b0=0.04, c0=0.05, d0=0.04, e0=0.04, f0=0.03, g0=0.03, h0=0.02
        ),
        bonus={"pair": 0.01},
        noise={},
    ),
    "l2_loose_passive": dict(
        id="l2_loose_passive",
        name="Loose passive (Level 2)",
        level=2,
        target=(60, 5),
        base=dict(
            r0=0.03,
            l0=0.30,
            a0=0.03,
            b0=0.45,
            c0=0.015,
            d0=0.35,
            e0=0.01,
            f0=0.15,
            g0=0.01,
            h0=0.06,
        ),
        bonus={"offsuit_ace": 0.045, "suited": 0.03, "pair": 0.02},
        noise={"call": 0.015},
    ),
    "l2_wide_aggressive": dict(
        id="l2_wide_aggressive",
        name="Wide aggressive (Level 2)",
        level=2,
        target=(60, 37.5),
        base=dict(
            r0=0.30, l0=0.08, a0=0.30, b0=0.20, c0=0.15, d0=0.30, e0=0.08, f0=0.25, g0=0.05, h0=0.15
        ),
        bonus={"suited": 0.02, "connector": 0.02, "broadway": 0.02, "offsuit_ace": 0.02},
        noise={"raise": 0.04, "call": 0.03},
    ),
    "l1_basic": dict(
        id="l1_basic",
        name="Basic beginner (Level 1)",
        level=1,
        target=(24, 6.5),
        base=dict(
            r0=0.05, l0=0.12, a0=0.04, b0=0.18, c0=0.02, d0=0.12, e0=0.01, f0=0.04, g0=0.01, h0=0.02
        ),
        bonus={"pair": 0.03, "broadway": 0.03, "connector": -0.02},
        noise={"raise": 0.02, "call": 0.02},
    ),
    "l3_solid": dict(
        id="l3_solid",
        name="Solid regular (Level 3)",
        level=3,
        target=(23, 17.5),
        base=dict(
            r0=0.14,
            l0=0.03,
            a0=0.08,
            b0=0.12,
            c0=0.045,
            d0=0.12,
            e0=0.03,
            f0=0.06,
            g0=0.02,
            h0=0.03,
        ),
        bonus={},
        noise={},
    ),
    "l3_lag": dict(
        id="l3_lag",
        name="Loose-aggressive regular (Level 3)",
        level=3,
        target=(34, 27),
        base=dict(
            r0=0.22, l0=0.04, a0=0.15, b0=0.12, c0=0.08, d0=0.14, e0=0.05, f0=0.08, g0=0.03, h0=0.04
        ),
        bonus={"suited": 0.015, "connector": 0.015},
        noise={"raise": 0.01, "call": 0.01},
    ),
}


def fill(order, frac, used):
    """take classes in order until `frac` of 1326 combos is allocated; returns {hand: weight} (weights in 0.05 steps)"""
    need = min(frac, 1.0) * 1326
    out = {}
    for h in order:
        if need <= 0.5:
            break
        room = 1 - used.get(h, 0)
        if room <= 1e-9:
            continue
        w = min(room, need / combos(h))
        w = int(w * 20 + 0.5) / 20
        if w <= 0:
            continue
        out[h] = w
        used[h] = used.get(h, 0) + w
        need -= w * combos(h)
    return out


def write(rng):
    """{hand: weight} -> compact range string"""
    by = {}
    for h, w in rng.items():
        by.setdefault(w, []).append(h)
    parts = []
    for w in sorted(by, reverse=True):
        hs = set(by[w])
        suf = "" if w == 1 else f":{w:g}"
        pairs = sorted(R.index(h[0]) for h in hs if len(h) == 2)
        for run in runs(pairs):
            lo, hi = run[0], run[-1]
            parts.append(
                (
                    R[lo] * 2 + ("+" if hi == 12 and lo != 12 else "")
                    if hi == 12
                    else (R[hi] * 2 + "-" + R[lo] * 2 if hi != lo else R[lo] * 2)
                )
                + suf
            )
        for sx in "so":
            for top in range(12, 0, -1):
                sec = sorted(
                    R.index(h[1]) for h in hs if len(h) == 3 and h[2] == sx and R.index(h[0]) == top
                )
                for run in runs(sec):
                    lo, hi = run[0], run[-1]
                    if lo == hi:
                        parts.append(f"{R[top]}{R[lo]}{sx}{suf}")
                    elif hi == top - 1:
                        parts.append(f"{R[top]}{R[lo]}{sx}+{suf}")
                    else:
                        parts.append(f"{R[top]}{R[hi]}{sx}-{R[top]}{R[lo]}{sx}{suf}")
    return ",".join(parts)


def runs(xs):
    out = []
    for x in xs:
        if out and out[-1][-1] == x - 1:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def build(p, kr, kc):
    b = p["base"]
    pid = p["id"]
    sr = sorted(CL, key=lambda h: -score(pid, h, "raise", p))
    sc = sorted(CL, key=lambda h: -score(pid, h, "call", p))

    def rule(raise_act, rf, call_act, cf, when=None, free_check=False):
        used = {}
        rr = fill(sr, rf * kr, used)
        if free_check:
            cc = {
                h: round(1 - used.get(h, 0), 2) for h in CL if 1 - used.get(h, 0) > 0.001
            }  # check with everything not raised
        else:
            cc = fill(sc, cf * kc, used)
        d = {"ranges": {raise_act: write(rr)}}
        if cc:
            d["ranges"][call_act] = write(cc)
        if not rr:
            del d["ranges"][raise_act]
        return ({"when": {"pos": when}} if when else {}) | d

    sp = {}
    op: list[dict[str, Any]] = [
        rule("raise", b["r0"] * PF[pos], "limp", b["l0"] * PF[pos], [pos])
        for pos in ["early", "middle", "cutoff", "button"]
    ]
    op.append(rule("raise", b["r0"] * PF["sb"], "limp", b["l0"] * PF["sb"]))
    sp["open"] = {"rules": op}
    sp["vs_limp"] = {
        "rules": [
            rule("raise", b["a0"], "call", 0, ["bb"], free_check=True),
            rule("raise", b["a0"], "call", b["b0"]),
        ]
    }
    sp["vs_raise"] = {
        "rules": [
            rule("3bet", b["c0"] * 0.7, "call", b["d0"] * 0.7, ["early"]),
            rule("3bet", b["c0"], "call", b["d0"] * 1.5, ["bb"]),
            rule("3bet", b["c0"], "call", b["d0"]),
        ]
    }
    sp["vs_3bet"] = {"rules": [rule("4bet", b["e0"], "call", b["f0"])]}
    sp["vs_4bet"] = {"rules": [rule("5bet", b["g0"], "call", b["h0"])]}
    return {"schemaVersion": 1, "id": pid, "name": p["name"], "skillLevel": p["level"], "spots": sp}


def bisect(f, target, lo=0.0, hi=4.0, it=26):
    for _ in range(it):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fit(p: dict) -> tuple[float, float]:
    """Alternate fits: PFR via the raise scale kr, then VPIP via the call scale kc."""
    tv, tp = p["target"]
    kr = kc = 1.0
    for _ in range(3):
        kr = bisect(lambda k, kc=kc: implied_stats(build(p, k, kc), MIX).pfr * 100, tp)
        kc = bisect(lambda k, kr=kr: implied_stats(build(p, kr, k), MIX).vpip * 100, tv, 0, 6)
    return kr, kc


def main() -> None:
    for pid, p in P.items():
        tv, tp = p["target"]
        kr, kc = fit(p)
        ch = build(p, kr, kc)
        errs = validate_chart(ch)
        assert not errs, errs
        (ROOT / "data" / "charts" / f"{pid}.json").write_text(json.dumps(ch, indent=1))
        st = implied_stats(ch, MIX)
        print(
            f"{pid:20s} target {tv:>4}/{tp:<5} "
            f"implied {st.vpip * 100:5.1f}/{st.pfr * 100:5.1f}  kr={kr:.2f} kc={kc:.2f}"
        )


if __name__ == "__main__":
    main()
