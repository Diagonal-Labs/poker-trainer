"""Rank the 169 preflop hand classes by equity against a random hand (Monte Carlo, eval7).
Usage: python rank_hands.py OUT.json [iterations]"""

import json
import random
import sys
from multiprocessing import Pool

import eval7

R = "23456789TJQKA"


def classes():
    out = []
    for i in range(12, -1, -1):
        for j in range(i, -1, -1):
            if i == j:
                out.append(R[i] * 2)
            else:
                out.append(R[i] + R[j] + "s")
                out.append(R[i] + R[j] + "o")
    return out


def combo_count(c):
    return 6 if len(c) == 2 else (4 if c[2] == "s" else 12)


def hero(c):
    if len(c) == 2:
        return [eval7.Card(c[0] + "s"), eval7.Card(c[1] + "h")]
    return [eval7.Card(c[0] + "s"), eval7.Card(c[1] + ("s" if c[2] == "s" else "h"))]


def equity(args):
    c, n, seed = args
    rng = random.Random(seed)
    h = hero(c)
    deck = [x for x in eval7.Deck().cards if x not in h]
    win = 0.0
    for _ in range(n):
        s = rng.sample(deck, 7)
        a = eval7.evaluate(h + s[2:])
        b = eval7.evaluate(s[:2] + s[2:])
        win += 1 if a > b else (0.5 if a == b else 0)
    return c, win / n


if __name__ == "__main__":
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    cl = classes()
    with Pool() as p:
        res = p.map(equity, [(c, n, 1000 + i) for i, c in enumerate(cl)])
    res.sort(key=lambda t: -t[1])
    method = f"Monte Carlo equity vs one random hand, {n} samples per class, eval7, seed 1000+index"
    classes_out = [{"hand": c, "equity": round(e, 4), "combos": combo_count(c)} for c, e in res]
    with open(out, "w") as f:
        json.dump({"method": method, "classes": classes_out}, f, indent=1)
    for c, e in res[:12]:
        print(c, round(e, 3))
    print("...", [(c, round(e, 3)) for c, e in res[-3:]])
