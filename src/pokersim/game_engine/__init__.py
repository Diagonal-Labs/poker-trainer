"""The Game engine: plays a hand forward. Poker rules, seats and table state.

Design doc: "Module structure". Knows how poker works and nothing about how anyone plays.
A functional core: no web, storage, file or network access, and no global random calls (the random
generator is always passed in).

Modules: rules (the only PokerKit importer), game (the hand loop), seats, positions.
Planned: table_state.
Imports only schemas and the standard library, plus PokerKit in rules. It never imports the
Decision engine: bot seats live in decision_engine, so the loop sees only the Seat interface.
"""
