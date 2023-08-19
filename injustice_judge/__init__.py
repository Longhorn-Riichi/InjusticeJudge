import asyncio
from typing import *
from .fetch import fetch_tenhou, parse_tenhou, fetch_majsoul, parse_majsoul
from .injustices import evaluate_unluckiness

def analyze_game(link: str, specified_player = None) -> List[str]:
    """Given a game link, fetch and parse the game into kyokus, then evaluate each kyoku"""
    print(f"Analyzing game {link}:")
    kyokus = []
    if link.startswith("https://tenhou.net/0/?log="):
        tenhou_log, player = fetch_tenhou(link)
        for raw_kyoku in tenhou_log:
            kyoku = parse_tenhou(raw_kyoku)
            kyokus.append(kyoku)
    elif link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="):
        majsoul_log, player = asyncio.run(fetch_majsoul(link))
        kyokus = parse_majsoul(majsoul_log)
    else:
        raise Exception("expected tenhou link starting with https://tenhou.net/0/?log="
                        "or mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu=")
    if specified_player is not None:
        player = specified_player
    return [injustice for kyoku in kyokus for injustice in evaluate_unluckiness(kyoku, player)]
