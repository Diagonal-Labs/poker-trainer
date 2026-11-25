"""The engine: poker rules, table play and bot decisions.

A functional core. Data goes in, a result comes out. No web, storage, file or network access, and
no global random calls: the random generator is always passed in (see docs/DECISIONS.md).

Planned modules, added slice by slice:
    rules, game, seats, table_state, decision_state, equity, chart, preflop, perception,
    sizing, scoring, decision, memory, presets.
Only ``rules`` may import PokerKit.
"""
