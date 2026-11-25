"""The Decision engine: works out one bot decision, step by step. It never changes the table.

Design doc: "Module structure". Same rules as the Game engine: no I/O, no global random calls.
May import game_engine (table and action types), schemas and eval7. Never PokerKit.

Modules: preflop (charts: range parser, validator, spot and rule lookup).
Planned, added slice by slice: decision (runs the steps in order), decision_state, equity,
perception, sizing, scoring, biases, habits, choose, tells, memory, presets, bot_seat.
"""
