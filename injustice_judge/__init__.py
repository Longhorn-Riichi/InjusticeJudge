from typing import *
from .fetch import parse_game_link
from .injustices import evaluate_game

# This file is the entry point for InjusticeJudge.
# Essentially calls `parse_game_link` from `fetch.py`
# and gives the result to `evaluate_injustices` from `injustices.py`.

async def analyze_game(link: str, specified_players: Set[int] = set(), look_for: Set[str] = {"injustice"}) -> List[str]:
    """Given a game link, fetch and parse the game into kyokus, then evaluate each kyoku"""
    # print(f"Analyzing game {link}:")
    kyokus, game_metadata, players = await parse_game_link(link, specified_players)

    return [result for kyoku in kyokus for result in evaluate_game(kyoku, players, game_metadata.name, look_for)]
