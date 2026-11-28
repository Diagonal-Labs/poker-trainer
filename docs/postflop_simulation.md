# Postflop simulation (slice 4)

Six starter personas at a six-handed table, 100 big blind stacks, 30,000 hands, each persona using its own
`chartAdherence`. Run with `python tools/simulate_preflop.py --hands 30000 --adherence preset`.

```
30000 hands, 6 seats, 80s (375 hands/s)

persona            hands    VPIP    target     PFR    target  ok
dave_station       30000   52.2%     50-70    4.0%       2-8  yes
fit_or_fold        30000   16.0%     20-28    4.2%       4-9  NO
lag_regular        30000   36.1%     30-38   29.4%     24-30  yes
maniac             30000   52.5%     50-70   31.4%     30-45  yes
nit                30000   10.8%     10-14    8.2%      8-11  yes
solid_regular      30000   23.1%     20-26   17.7%     15-20  yes

Postflop (the full decision pipeline)
persona             AF   WTSD%   cbet%  fold to bet%  saw flop%  outside target
dave_station      0.81    32.6    60.2          26.1       46.5  -
fit_or_fold       2.05    33.7    60.2          37.2       13.5  wtsd, foldToBet
lag_regular       1.79    29.4    43.6          50.9       26.2  cbet
maniac            6.28    23.2    73.3          58.0       40.8  foldToBet
nit               2.43    24.5    51.5          51.3       10.2  cbet
solid_regular     1.03    33.7    32.1          47.0       18.5  af, wtsd, cbet
```

AF is bets and raises divided by calls. WTSD is the share of flops seen that reached showdown. C-bet is a flop
bet by the preflop aggressor when checked to. Fold to bet is a fold when facing a flop bet. The target ranges
for these four stats in `data/personas/*.json` are my estimates of plausible $1/$2 behavior, not measured data.
Review them.

## Where the bots miss their (estimated) targets

- **Solid regular** c-bets only about 32% and has AF 1.0. It is the Level 3 bot, which reads true equity against
  range buckets, and often checks medium equity on dry boards. A thin-value / protection bonus for Level 3 is
  the likely fix.
- **Fit-or-fold** goes to showdown more and folds less than its target, and its VPIP is below target because the
  chart-adherence fallback is still check-or-fold (see DECISIONS).
- **Maniac** folds to flop bets 58% of the time against a target of 35-55%. Its all-in-heavy raise menu makes
  opponents' bets look strong to it.
- **Nit and LAG** c-bet a little less than target.

## What was tuned, and how

The pipeline first produced bots that almost never called (fold to a flop bet 61%) and had AF of 4 to 200. I
tuned the preset values in `data/presets.json` with a parameter grid over 20,000-hand runs. The values that mattered
most were `callBonus` (0.2, a stand-in for implied odds the baseline ignores), `maxFoldPerOpponent`,
`raiseFoldFactor` and `raiseCalledPenalty` (these keep raises from looking like free money), and the
aggression and stickiness scales in `data/bias_scales.json`. All are guesses to calibrate further.
