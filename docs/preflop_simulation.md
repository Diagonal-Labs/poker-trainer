# Preflop simulation (slice 3)

Bot-only hands with stacks reset to 100 big blinds at $1/$2 and the button moving every hand. VPIP
counts a call of a bet or a raise, not a big-blind check. Reproduce with `make simulate` or
`python tools/simulate_preflop.py --help`. Postflop the bots check or fold (placeholder until slice 4).

## Six players, one of each starter persona, bots follow their charts (100,000 hands)

```
100000 hands, 6 seats, 250s (399 hands/s)

persona            hands    VPIP    target     PFR    target  ok
dave_station      100000   61.3%     50-70    4.7%       2-8  yes
fit_or_fold       100000   26.3%     20-28    6.6%       4-9  yes
lag_regular       100000   36.2%     30-38   29.0%     24-30  yes
maniac            100000   62.0%     50-70   36.8%     30-45  yes
nit               100000   12.2%     10-14    8.8%      8-11  yes
solid_regular     100000   23.3%     20-26   17.5%     15-20  yes

VPIP / PFR by position group
  dave_station    early 38/4  middle 54/5  cutoff 68/6  button 75/6  sb 64/4  bb 70/3
  fit_or_fold     early 17/6  middle 27/8  cutoff 31/9  button 33/8  sb 27/5  bb 23/4
  lag_regular     early 28/26  middle 37/33  cutoff 44/36  button 44/34  sb 36/26  bb 29/19
  maniac          early 37/30  middle 55/37  cutoff 67/43  button 75/44  sb 70/36  bb 68/31
  nit             early 10/10  middle 13/11  cutoff 14/10  button 14/10  sb 12/6  bb 12/6
  solid_regular   early 19/17  middle 25/22  cutoff 28/23  button 27/20  sb 21/13  bb 20/10

Measured spot mix of each bot's first decision (percent)
  early   open 100.0  vs_limp   0.0  vs_raise   0.0  vs_3bet   0.0  vs_4bet   0.0  
  middle  open  75.4  vs_limp   9.2  vs_raise  15.4  vs_3bet   0.0  vs_4bet   0.0  
  cutoff  open  49.7  vs_limp  17.3  vs_raise  31.3  vs_3bet   1.7  vs_4bet   0.0  
  button  open  25.3  vs_limp  23.7  vs_raise  46.2  vs_3bet   4.7  vs_4bet   0.1  
  sb      open   8.6  vs_limp  24.8  vs_raise  57.5  vs_3bet   8.8  vs_4bet   0.3  
  bb      open   0.0  vs_limp  21.6  vs_raise  63.4  vs_3bet  14.3  vs_4bet   0.7
```

All six land inside their target ranges. Fit-or-fold sits just under the top of its VPIP range (26.3 of
20-28), and the LAG just under the top of its PFR range (29.0 of 24-30).

## Same table, persona presets for chart adherence (100,000 hands)

The doc's chart adherence presets (0.60 / 0.85 / 0.97) with the stand-in for the missing perception
pipeline (check if free, otherwise fold) on the decisions where the bot "forgets" its chart.

```
100000 hands, 6 seats, 199s (502 hands/s)

persona            hands    VPIP    target     PFR    target  ok
dave_station      100000   52.3%     50-70    4.0%       2-8  yes
fit_or_fold       100000   15.9%     20-28    4.1%       4-9  NO
lag_regular       100000   36.0%     30-38   29.5%     24-30  yes
maniac            100000   52.6%     50-70   31.6%     30-45  yes
nit               100000   10.5%     10-14    7.9%      8-11  NO
solid_regular     100000   23.2%     20-26   17.8%     15-20  yes

Measured spot mix of each bot's first decision (percent)
  early   open 100.0  vs_limp   0.0  vs_raise   0.0  vs_3bet   0.0  vs_4bet   0.0  
  middle  open  78.9  vs_limp   7.4  vs_raise  13.7  vs_3bet   0.0  vs_4bet   0.0  
  cutoff  open  55.8  vs_limp  14.5  vs_raise  28.4  vs_3bet   1.3  vs_4bet   0.0  
  button  open  32.5  vs_limp  20.6  vs_raise  43.2  vs_3bet   3.7  vs_4bet   0.1  
  sb      open  14.3  vs_limp  23.0  vs_raise  55.4  vs_3bet   7.1  vs_4bet   0.2  
  bb      open   0.0  vs_limp  22.3  vs_raise  64.8  vs_3bet  12.4  vs_4bet   0.5
```

The nit (10.5 VPIP, 7.9 PFR) and fit-or-fold (15.9 VPIP, 4.1 PFR) fall at or under the bottom of their
ranges because forgotten decisions are folds. Fit-or-fold has the lowest adherence (0.60). This is
the stand-in's effect, not a chart problem, and it goes away when slice 4 adds the real fallback.

## Nine players (50,000 hands, personas repeated around the table)

```
50000 hands, 9 seats, 177s (283 hands/s)

persona            hands    VPIP    target     PFR    target  ok
dave_station      100000   56.2%     50-70    4.1%       2-8  yes
fit_or_fold       100000   23.6%     20-28    5.3%       4-9  yes
lag_regular       100000   31.7%     30-38   23.8%     24-30  NO
maniac             50000   57.9%     50-70   31.8%     30-45  yes
nit                50000   10.8%     10-14    7.5%      8-11  NO
solid_regular      50000   19.7%     20-26   14.0%     15-20  NO

Measured spot mix of each bot's first decision (percent)
  early   open  76.6  vs_limp   9.8  vs_raise  13.2  vs_3bet   0.3  vs_4bet   0.0  
  middle  open  32.8  vs_limp  22.9  vs_raise  40.4  vs_3bet   3.8  vs_4bet   0.1  
  cutoff  open  15.9  vs_limp  23.4  vs_raise  51.3  vs_3bet   9.0  vs_4bet   0.4  
  button  open   7.3  vs_limp  22.8  vs_raise  56.0  vs_3bet  13.1  vs_4bet   0.7  
  sb      open   2.3  vs_limp  20.3  vs_raise  58.5  vs_3bet  17.7  vs_4bet   1.3  
  bb      open   0.0  vs_limp  16.6  vs_raise  58.8  vs_3bet  22.4  vs_4bet   2.1
```

The charts were fitted for the assumed spot mix, and nine-handed play looks quite different from it:
bots are far more often facing a raise or a 3-bet than first in. The nit, the solid regular and the LAG
drift below their targets (the nit PFR 7.5, solid 19.7 / 14.0, LAG PFR 23.8). Six-handed play matches
the targets, so the charts are fine for six-handed tables. For nine-handed play, re-fit the charts
to a measured spot mix.

## Measured spot mix

The share of each bot's first decision in each spot, by position group, is printed above and can be
written with `--spot-mix-out`. Six-handed, the early group is only the UTG seat, so it is always an
open. The assumed mix in `data/spot_mix.json` is still what the chart generator uses.
