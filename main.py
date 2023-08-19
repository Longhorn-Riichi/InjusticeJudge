import asyncio
from pprint import pprint
from injustices import evaluate_unluckiness
from fetch import fetch_tenhou, parse_tenhou, fetch_majsoul, parse_majsoul
from typing import *

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
        

import sys
if __name__ == "__main__":
    assert len(sys.argv) >= 2, "expected one or two arguments, the tenhou/majsoul url, and then seat [0-3] (optional)"
    link = sys.argv[1]
    player = int(sys.argv[2]) if len(sys.argv) == 3 else None
    assert link != "", "expected one or two arguments, the tenhou/majsoul url, and then seat [0-3] (optional)"
    assert player in [0,1,2,3,None], "expected second argument to be 0,1,2,3"
    print("\n".join(analyze_game(link, player)))

    # # shanten tests
    # from shanten import calculate_shanten
    # hand = [12,13,14,22,23,52,27,28,28,34,35,38,38]
    # print(ph(hand), calculate_shanten(hand))

    # from shanten import calculate_shanten
    # print("tenpai:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,37,37])[0] == 0   # 11123m123567p77s  tenpai
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36])[0] == 0
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36])[1] == [32,35]
    # print("kutsuki iishanten:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,28,38])[0] == 1.1 # 11123m1235678p8s  kutsuki iishanten
    # assert calculate_shanten([11,12,13,23,24,25,52,33,37,38,39,42,42])[0] == 1.1
    # assert calculate_shanten([24,24,52,27,28,29,33,34,35,53,37,38,39])[0] == 1.1
    # assert calculate_shanten([24,24,52,27,28,29,33,34,35,53,37,38,39])[1] == [52,53]
    # assert calculate_shanten([11,11,12,12,13,13,15,16,16,17,18,18,19])[0] == 1.1 # 1122335667889m
    # assert calculate_shanten([11,11,12,12,13,13,15,16,16,17,18,18,19])[1] == [15,16,18,19]
    # print("headless iishanten:")
    # assert calculate_shanten([11,11,12,13,13,21,22,23,25,26,27,37,38])[0] == 1.2 # 11223m123567p78s  headless iishanten
    # print("complete iishanten:")
    # assert calculate_shanten([11,11,11,12,13,13,21,22,23,25,26,37,37])[0] == 1.3 # 111233m12356p77s  complete iishanten
    # assert calculate_shanten([11,12,13,17,18,19,23,23,25,27,27,32,33])[0] == 1.3
    # assert calculate_shanten([11,12,13,17,18,19,23,23,25,27,27,32,33])[1] == [23,23,25,27,27]
    # print("floating tile iishanten:")
    # assert calculate_shanten([11,11,11,12,13,17,21,22,23,25,26,37,37])[0] == 1.4 # 111237m12356p77s  floating tile iishanten
    # assert calculate_shanten([11,11,11,12,13,17,21,22,23,25,26,37,37])[1] == [17]
    # print("chiitoitsu iishanten:")
    # assert calculate_shanten([15,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 0   # 5566m44577p5077s  chiitoitsu tenpai
    # assert calculate_shanten([11,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 1.5 # 1566m44577p5077s  chiitoitsu iishanten
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,37,37])[0] == 1.5
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,36,39])[0] == 2
    # print("kokushi musou iishanten:")
    # assert calculate_shanten([11,11,19,21,29,31,39,41,42,43,44,45,46])[0] == 0 # kokushi musou tenpai
    # assert calculate_shanten([11,11,19,21,29,31,39,41,42,43,44,45,46])[1] == [47]
    # assert calculate_shanten([11,19,21,29,31,39,41,42,43,44,45,46,47])[0] == 0 # kokushi musou 13-sided tenpai
    # assert calculate_shanten([11,19,21,29,31,39,41,42,43,44,45,46,47])[1] == [11,19,21,29,31,39,41,42,43,44,45,46,47]
    # assert calculate_shanten([14,19,21,29,29,31,39,41,42,44,45,46,47])[0] == 1.6 # kokushi musou iishanten
    # assert calculate_shanten([19,19,21,29,29,31,39,41,42,44,46,46,47])[0] == 3
    # print("2+ shanten:")
    # assert calculate_shanten([12,13,14,22,23,52,27,28,28,34,35,38,38])[0] == 2   # 234m230788p4588s  2-shanten
    # assert calculate_shanten([11,19,23,24,25,31,32,35,36,37,38,43,43])[0] == 2   # 19m345p125678s33z  2-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,43])[0] == 3   # 19m245p125678s33z  3-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,47])[0] == 4   # 19m245p125678s37z  4-shanten
    # assert calculate_shanten([11,12,16,18,22,26,27,34,41,42,44,45,46])[0] == 5   # 1268m267p4s12456z  5-shanten
    # assert calculate_shanten([13,16,18,19,27,28,31,35,38,42,44,45,46])[0] == 6   # 3689m78p158s2456z  6-shanten
    # assert calculate_shanten([12,15,51,23,25,33,39,41,42,44,45,45,46])[0] == 4   # 150m25p39s124556z  4-shanten for chiitoitsu
