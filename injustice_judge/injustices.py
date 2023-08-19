from .constants import Kyoku, SHANTEN_NAMES
from enum import Enum
from typing import *
from .utils import ph, relative_seat_name, round_name

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " FIVE_SHANTEN_START"
    " YOU_FOLDED_FROM_TENPAI"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_TENPAI_FIRST"

    # unused:
    " CHASER_LOST_POINTS"
    " GAME_ENDED_WITH_TSUMO"
    " FIRST_ROW_TENPAI"
    " YOU_DECLARED_RIICHI"
    " YOU_WON_BIG_HAND"
    " OTHER_WON_BIG_HAND"

    # TODO:
    " HAITEI_HAPPENED_WHILE_YOU_ARE_TENPAI"
    " OPPONENT_RIICHI_IPPATSU_TSUMO"
    " YOU_HAVE_FIRST_ROW_DISCARDS"
    " YOU_HAVE_SECOND_ROW_DISCARDS"
    " YOU_HAVE_THIRD_ROW_DISCARDS"
    " YOU_PAID_TSUMO_AS_DEALER"
    " YOUR_HAND_RUINED_BY_TANYAO"
    )

def determine_flags(kyoku, player: int) -> Tuple[List[Flags], List[Dict[str, Any]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag in `flags`
    """
    flags = []
    data = []
    other_player = None
    other_chases = False
    other_hand = None
    other_wait = None
    other_ukeire = None
    draws_since_shanten_change = 0
    starting_player_shanten = None
    player_shanten: Tuple[float, List[int]] = (99, [])
    someone_is_tenpai = False
    turn_number = 1
    opened_hand = [False]*4
    in_riichi = [False]*4
    for event in kyoku["events"]:
        if event[0] == player:
            if event[1] == "shanten":
                starting_player_shanten = event[2]
                player_shanten = event[2]
                if player_shanten[0] >= 5:
                    flags.append(Flags.FIVE_SHANTEN_START)
                    data.append({"shanten": player_shanten[0]})
            elif event[1] == "shanten_change":
                assert starting_player_shanten is not None
                player_shanten = event[3]
                draws_since_shanten_change = 0
                if event[2][0] == 0 and event[3][0] > 0:
                    flags.append(Flags.YOU_FOLDED_FROM_TENPAI)
                    data.append({})
            elif event[1] in ["draw", "minkan"]:
                draws_since_shanten_change += 1
                if player_shanten[0] > 0 and draws_since_shanten_change >= 9:
                    flags.append(Flags.NINE_DRAWS_NO_IMPROVEMENT)
                    data.append({"shanten": player_shanten[0],
                                 "iishanten_tiles": player_shanten[1],  # type: ignore[dict-item]
                                 "turns": draws_since_shanten_change})
        if event[1] == "riichi":
            in_riichi[event[0]] = True
            if event[0] == player:
                flags.append(Flags.YOU_DECLARED_RIICHI)
                data.append({})
        elif event[1] in ["chii", "pon", "minkan"]:
            opened_hand[event[0]] = True
        elif event[1] == "tenpai":
            if event[0] == player:
                if Flags.YOU_FOLDED_FROM_TENPAI in flags:
                    ix = flags.index(Flags.YOU_FOLDED_FROM_TENPAI)
                    del flags[ix]
                    del data[ix]
                flags.append(Flags.YOU_REACHED_TENPAI)
                data.append({"seat": event[0],
                             "hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})
                if not someone_is_tenpai:
                    flags.append(Flags.YOU_TENPAI_FIRST)
                    data.append({})
            elif Flags.YOU_TENPAI_FIRST in flags:
                flags.append(Flags.YOU_GOT_CHASED)
                data.append({"seat": event[0],
                             "hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})
            if turn_number <= 6:
                flags.append(Flags.FIRST_ROW_TENPAI)
                data.append({"seat": event[0], "turn": turn_number})
            someone_is_tenpai = True
        if event[0] == kyoku["round"] % kyoku["num_players"]: # dealer turn
            turn_number += 1

    if kyoku["result"][0] == "和了":
        is_tsumo = kyoku["result"][2][0] == kyoku["result"][2][1]
        if is_tsumo:
            flags.append(Flags.GAME_ENDED_WITH_TSUMO)
            data.append({})
        else:
            flags.append(Flags.GAME_ENDED_WITH_RON)
            data.append({})
        winners = [t for t in range(kyoku["num_players"]) if kyoku["result"][1][t] > 0]
        for w in winners:
            if kyoku["result"][1][player] < 0 and not is_tsumo:
                if not opened_hand[w] and not in_riichi[w]:
                    flags.append(Flags.YOU_DEALT_INTO_DAMA)
                    data.append({"seat": w,
                                 "score": kyoku["result"][1][w]})
                if "一発(1飜)" in kyoku["result"][2]:
                    flags.append(Flags.YOU_DEALT_INTO_IPPATSU)
                    data.append({"seat": w,
                                 "score": kyoku["result"][1][w]})
            if kyoku["result"][1][w] >= 7700:
                if w == player:
                    flags.append(Flags.YOU_WON_BIG_HAND)
                else:
                    flags.append(Flags.OTHER_WON_BIG_HAND)
        if Flags.YOU_GOT_CHASED in flags:
            assert Flags.YOU_TENPAI_FIRST in flags, "somehow got YOU_GOT_CHASED without YOU_TENPAI_FIRST"
            for i in [i for i, f in enumerate(flags) if f == Flags.YOU_GOT_CHASED]:
                # for every chaser, check if they gained or lost points
                chaser_data = data[i]
                chaser = chaser_data["seat"]
                assert player != chaser, "Player should not be chaser for Flags.YOU_GOT_CHASED"
                if kyoku["result"][1][chaser] < 0:
                    flags.append(Flags.CHASER_LOST_POINTS)
                    data.append({"seat": chaser,
                                 "amount": kyoku["result"][1][chaser]})
                if kyoku["result"][1][chaser] > 0:
                    flags.append(Flags.CHASER_GAINED_POINTS)
                    data.append({"seat": chaser,
                                 "amount": kyoku["result"][1][chaser]})
                # for every chaser, check if their wait is worse than yours
                player_data = data[flags.index(Flags.YOU_REACHED_TENPAI)]
    elif kyoku["result"][0] in ["流局", "全員聴牌"] :
        flags.append(Flags.GAME_ENDED_WITH_RYUUKYOKU)
        data.append({})

    if kyoku["result"][0] in ["和了", "流局"] and len(kyoku["result"][1]) > 0:
        if kyoku["result"][1][player] < 0:
            flags.append(Flags.YOU_LOST_POINTS)
            data.append({"amount": kyoku["result"][1][player]})
            if turn_number <= 6:
                flags.append(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)
                data.append({"seat": event[0], "turn": turn_number, "amount": kyoku["result"][1][player]})
        elif kyoku["result"][1][player] > 0:
            "(1飜)"
            flags.append(Flags.YOU_GAINED_POINTS)
            data.append({"amount": kyoku["result"][1][player]})



    # TODO: other results?

    return flags, data

def evaluate_unluckiness(kyoku: Kyoku, player: int) -> List[str]:
    """
    Run each injustice function (defined below this function) against a parsed kyoku
    Relevant injustice functions should return a list of strings each
    Returns the full list of injustices (a list of strings)
    """
    global injustices
    flags, data = determine_flags(kyoku, player)
    ret = []
    for i in injustices:
        if all(flag in flags for flag in i["required_flags"]) and all(flag not in flags for flag in i["forbidden_flags"]):
            if "" != (strs := i["callback"](flags, data, kyoku['round'], kyoku['honba'], player)):
                ret.extend(strs)
    return ret

###
### injustice definitions
###

injustices: List[Dict[str, Any]] = []
InjusticeFunc = Callable[[List[Flags], List[Dict[str, Any]], int, int, int], List[str]]
def injustice(require: List[Flags] = [], forbid: List[Flags] = []) -> Callable[[InjusticeFunc], InjusticeFunc] :
    """Decorator for DIY injustices, see below for usage"""
    global injustices
    def decorator(callback):
        injustices.append({"callback": callback, "required_flags": require, "forbidden_flags": forbid})
        return lambda f: f
    return decorator

# each injustice function takes two lists of flags: require and forbid
# `evaluate_unluckiness` calls an injustice function if all require flags and no forbid flags are satisfied

# Print if your tenpai got chased by a worse wait, and they won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.YOU_TENPAI_FIRST,
                    Flags.YOU_GOT_CHASED, Flags.CHASER_GAINED_POINTS],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.GAME_ENDED_WITH_RYUUKYOKU,
                    Flags.YOU_GAINED_POINTS])
def chaser_won_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    player_data = data[flags.index(Flags.YOU_REACHED_TENPAI)]
    your_seat = player_data["seat"]
    your_wait = player_data["wait"]
    your_ukeire = player_data["ukeire"]
    chasers = {}
    for i in [i for i, f in enumerate(flags) if f == Flags.YOU_GOT_CHASED]:
        chaser_data = data[i]
        chasers[chaser_data["seat"]] = chaser_data
    ret = []
    for chaser_data in chasers.values():
        chaser_seat = chaser_data["seat"]
        chaser_wait = chaser_data["wait"]
        chaser_ukeire = chaser_data["ukeire"]
        try:
            winner_seat = data[i+flags[i:].index(Flags.CHASER_GAINED_POINTS)]["seat"]
        except ValueError:
            continue
        if chaser_seat == winner_seat and chaser_ukeire < your_ukeire:
            if Flags.YOU_LOST_POINTS in flags:
                ret.append(f"Major unluckiness detected in {round_name(round_number, honba)}:"
                           f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
                           f" was chased by a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and you dealt into it")
            else:
                ret.append(f"Unluckiness detected in {round_name(round_number, honba)}:"
                           f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and they won")
    return ret

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT],
            forbid=[Flags.YOU_REACHED_TENPAI])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    turns = shanten_data["turns"]
    shanten = shanten_data["shanten"]
    iishanten_tiles = shanten_data["iishanten_tiles"]
    if len(iishanten_tiles) > 0:
        return [f"Unluckiness detected in {round_name(round_number, honba)}:"
                f" you were stuck at {SHANTEN_NAMES[shanten]} ({ph(iishanten_tiles)}) for {turns} turns, and never reached tenpai"]
    else:
        return [f"Unluckiness detected in {round_name(round_number, honba)}:"
                f" you were stuck at {SHANTEN_NAMES[shanten]} for {turns} turns, and never reached tenpai"]

# Print if you started with atrocious shanten and never got to tenpai
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_REACHED_TENPAI])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["shanten"]
    return [f"Unluckiness detected in {round_name(round_number, honba)}:"
            f" you started at {SHANTEN_NAMES[shanten]}"]

# Print if you lost points to a first row ron/tsumo
@injustice(require=[Flags.LOST_POINTS_TO_FIRST_ROW_WIN])
def lost_points_to_first_row_win(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)]
    winner = win_data["seat"]
    turn = win_data["turn"]
    return [f"Unluckiness detected in {round_name(round_number, honba)}:"
            f" you lost points to an early win by {relative_seat_name(player, winner)} on turn {turn}"]

# Print if you dealt into dama
@injustice(require=[Flags.YOU_DEALT_INTO_DAMA])
def dealt_into_dama(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_DAMA)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [f"Unluckiness detected in {round_name(round_number, honba)}:"
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point dama"]

# Print if you dealt into ippatsu
@injustice(require=[Flags.YOU_DEALT_INTO_IPPATSU])
def dealt_into_ippatsu(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_IPPATSU)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [f"Unluckiness detected in {round_name(round_number, honba)}:"
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point ippatsu"]