from .tenhou import *
from .majsoul import *
from .riichicity import *
from ..classes import GameMetadata
from ..classes2 import Kyoku
from typing import *

# This directory contains all the logic for fetching and parsing game logs into `Kyoku`s.
# 
# `__init__.py` calls the entry point `parse_game_link`, which takes a game log link
#    and returns a tuple: (kyokus, game metadata, player specified in the link).
#   
# `fetch_majsoul`/`fetch_tenhou` handle requesting and caching game logs, given a link.
# 
# `parse_majsoul`/`parse_tenhou` parse said game logs into a list of `Event`s
#   for each kyoku, as well as a `GameMetadata` object containing information about
#   the game across kyokus. After parsing, `postprocess_events` is called on each event
#   list, turning them into `Kyoku` objects. Returns the resulting list of `Kyoku`s,
#   plus the `GameMetadata` object.
#   
# The sole uses of the resulting `Kyoku` objects are:
# - `determine_flags` in `flags.py`, (used to calculate all the Flags)
# - `evaluate_injustices` in `injustices.py`. (used to fetch data for printing, e.g. dora)
# - in the Ronhorn bot, `parse_game` (used to fetch hand data, ukeire calculations)

async def parse_game_link(link: str, specified_players: Set[int] = set(), nickname: Optional[str]=None) -> Tuple[List[Kyoku], GameMetadata, Set[int]]:
    """Given a game link, fetch and parse the game into kyokus"""
    if "tenhou.net/" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        if metadata["name"][3] == "":
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_tenhou(tenhou_log, metadata, nickname)
    elif "mahjongsoul" in link or "maj-soul" in link or "majsoul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        # Old CN (?): http://majsoul.union-game.com/0/?paipu=190303-335e8b25-7f5c-4bd1-9ac0-249a68529e8d_a93025901
        majsoul_log, metadata, player = await fetch_majsoul(link)
        if len(metadata["accounts"]) == 3:
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_majsoul(majsoul_log, metadata, nickname)
    elif all(c in "0123456789abcdefghijklmnopqrstuv" for c in link[:20]): # riichi city log id
        riichicity_log, metadata, player = await fetch_riichicity(link)
        kyokus, parsed_metadata, parsed_player_seat = parse_riichicity(riichicity_log, metadata, nickname)
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`"
                        " or 20-character riichi city log id like `cjc3unuai08d9qvmstjg`")
    kyokus[-1].is_final_round = True
    if len(specified_players) == 0:
        if parsed_player_seat is not None:
            specified_players = {parsed_player_seat}
        elif player is not None:
            specified_players = {player}
        else:
            specified_players = {0}
    return kyokus, parsed_metadata, specified_players
