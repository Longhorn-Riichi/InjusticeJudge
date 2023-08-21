from typing import *
from .fetch import parse_game_link
from .injustices import evaluate_injustices

async def analyze_game(link: str, specified_player = None) -> List[str]:
    """Given a game link, fetch and parse the game into kyokus, then evaluate each kyoku"""
    # print(f"Analyzing game {link}:")
    kyokus, game_metadata, player = await parse_game_link(link, specified_player)
    return [injustice for kyoku in kyokus for injustice in evaluate_injustices(kyoku, player)]
