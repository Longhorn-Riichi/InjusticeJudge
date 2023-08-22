from .constants import Kyoku, SHANTEN_NAMES
from enum import Enum
from typing import *
from .utils import ph, pt, relative_seat_name, round_name, shanten_name, sorted_hand
from pprint import pprint

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " FIVE_SHANTEN_START"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " LAST_DISCARD_STOPPED_NAGASHI"
    " LAST_NAGASHI_TILE_CALLED"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " SOMEONE_REACHED_TENPAI"
    " WINNER"
    " WINNER_GOT_BAIMAN"
    " WINNER_GOT_HANEMAN"
    " WINNER_GOT_MANGAN"
    " WINNER_GOT_SANBAIMAN"
    " WINNER_GOT_YAKUMAN"
    " WINNER_HAD_BAD_WAIT"
    " WINNER_IPPATSU_TSUMO"
    " YOU_ARE_DEALER"
    " YOU_DEALT_IN_BEFORE_NOTEN_PAYMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
    " YOU_FOLDED_FROM_TENPAI"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_TENPAI_FIRST"
    " YOUR_TENPAI_TILE_DEALT_IN"


    # unused:
    " CHASER_LOST_POINTS"
    " FIRST_ROW_TENPAI"
    " GAME_ENDED_WITH_TSUMO"
    " YOU_ACHIEVED_NAGASHI"
    " YOU_DECLARED_RIICHI"

    # TODO:
    " HAITEI_HAPPENED_WHILE_YOU_ARE_TENPAI"
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
    flags: List[Flags] = []
    data: List[Any] = []
    other_player = None
    other_chases = False
    other_hand = None
    other_wait = None
    other_ukeire = None
    draws_since_shanten_change = 0
    starting_player_shanten = None
    player_shanten: Tuple[float, List[int]] = (99, [])
    player_past_waits = []
    someone_is_tenpai = False
    turn_number = 1
    num_players = kyoku["num_players"]
    opened_hand: List[bool] = [False]*num_players
    in_riichi: List[bool] = [False]*num_players
    nagashi: List[bool] = [True]*num_players
    last_draw_event_ix: List[int] = [-1]*num_players
    last_discard_event_ix: List[int] = [-1]*num_players
    tiles_in_wall = 70 if num_players == 4 else 55
    assert num_players in {3,4}, f"somehow we have {num_players} players"

    # First, get some basic data about the game.
    # - whether you're dealer
    # - game ended with ron or tsumo
    # - when was each player's last draw and discard

    if (player + kyoku["round"] % 4) == 0:
        flags.append(Flags.YOU_ARE_DEALER)
        data.append({})
    if kyoku["result"][0] == "和了":
        is_tsumo = kyoku["result"][2][0] == kyoku["result"][2][1]
        if is_tsumo:
            flags.append(Flags.GAME_ENDED_WITH_TSUMO)
            data.append({})
        else:
            flags.append(Flags.GAME_ENDED_WITH_RON)
            data.append({})
    # Figure out the index of each player's last draw event by going through the events backwards
    # (-1 if the player never got to draw)
    for i, event in enumerate(kyoku["events"][::-1]):
        seat, event_type, *event_data = event
        if last_draw_event_ix[seat] == -1 and event_type in {"draw", "minkan"}:
            last_draw_event_ix[seat] = len(kyoku["events"]) - 1 - i
        elif last_discard_event_ix[seat] == -1 and event_type == "discard":
            last_discard_event_ix[seat] = len(kyoku["events"]) - 1 - i
        if all(ix != -1 for ix in last_draw_event_ix + last_discard_event_ix):
            break

    # Next, go through the events of the game in order. This determines flags related to:
    # - starting shanten
    # - tenpais/riichis and chases/folds
    # - slow shanten changes
    for i, event in enumerate(kyoku["events"]):
        seat, event_type, *event_data = event
        if event_type in {"draw", "minkan"}:
            tiles_in_wall -= 1
        if seat == player:
            if event_type == "start_shanten":
                starting_player_shanten = event_data[0]
                player_shanten = event_data[0]
                if player_shanten[0] >= 5:
                    flags.append(Flags.FIVE_SHANTEN_START)
                    data.append({"shanten": player_shanten})
            elif event_type == "shanten_change":
                assert starting_player_shanten is not None
                prev_shanten = event_data[0]
                new_shanten = event_data[1]
                draws_since_shanten_change = 0
                if prev_shanten[0] == 0:
                    player_past_waits.append(prev_shanten[1])
                    if new_shanten[0] > 0:
                        flags.append(Flags.YOU_FOLDED_FROM_TENPAI)
                        data.append({})
                player_shanten = new_shanten
            elif event_type in {"draw", "minkan"}:
                if event_type == "draw":
                    # check if draw would have completed a past wait
                    for wait in player_past_waits:
                        if event_data[0] in wait:
                            flags.append(Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE)
                            data.append({"tile": event_data[0], "wait": wait, "shanten": player_shanten})
                draws_since_shanten_change += 1
                if player_shanten[0] > 0 and draws_since_shanten_change >= 9:
                    flags.append(Flags.NINE_DRAWS_NO_IMPROVEMENT)
                    data.append({"shanten": player_shanten,
                                 "turns": draws_since_shanten_change})
        if event_type == "riichi":
            in_riichi[seat] = True
            if seat == player:
                flags.append(Flags.YOU_DECLARED_RIICHI)
                data.append({})
        elif event_type in {"chii", "pon", "minkan"}:
            opened_hand[seat] = True
        elif event_type == "discard":
            dealt_in = i == max(last_discard_event_ix) and kyoku["result"][0] == "和了" and not is_tsumo
            already_tenpai = Flags.YOU_REACHED_TENPAI in flags
            just_reached_tenpai = not already_tenpai and any(e[0] == seat and e[1] == "tenpai" for e in kyoku["events"][i:])
            if dealt_in:
                if seat == player and just_reached_tenpai:
                    flags.append(Flags.YOUR_TENPAI_TILE_DEALT_IN)
                    data.append({"tile": event_data[0]})
                if already_tenpai and tiles_in_wall <= 3:
                    flags.append(Flags.YOU_DEALT_IN_BEFORE_NOTEN_PAYMENT)
                    data.append({"tile": event_data[0]})

        elif event_type == "tenpai":
            flags.append(Flags.SOMEONE_REACHED_TENPAI)
            data.append({"seat": seat,
                         "hand": event_data[0],
                         "wait": event_data[1],
                         "ukeire": event_data[2]})
            if seat == player:
                if Flags.YOU_FOLDED_FROM_TENPAI in flags: # folded no longer
                    ix = flags.index(Flags.YOU_FOLDED_FROM_TENPAI)
                    del flags[ix]
                    del data[ix]
                flags.append(Flags.YOU_REACHED_TENPAI)
                data.append({"seat": seat,
                             "hand": event_data[0],
                             "wait": event_data[1],
                             "ukeire": event_data[2]})
                if not someone_is_tenpai:
                    flags.append(Flags.YOU_TENPAI_FIRST)
                    data.append({})
            elif Flags.YOU_REACHED_TENPAI in flags:
                player_data = data[len(flags) - 1 - flags[::-1].index(Flags.YOU_REACHED_TENPAI)]
                flags.append(Flags.YOU_GOT_CHASED)
                data.append({"seat": seat,
                             "hand": event_data[0],
                             "wait": event_data[1],
                             "ukeire": event_data[2],
                             "your_seat": player_data["seat"],
                             "your_hand": player_data["hand"],
                             "your_wait": player_data["wait"],
                             "your_ukeire": player_data["ukeire"]})
            if turn_number <= 6:
                flags.append(Flags.FIRST_ROW_TENPAI)
                data.append({"seat": seat, "turn": turn_number})
            someone_is_tenpai = True
        elif event_type == "end_nagashi":
            nagashi[seat] = False
            tile = event_data[2]
            # if the game ended in ryuukyoku, mark if this happened after our final draw
            if kyoku["result"][0] == "流局" and i > last_draw_event_ix[seat]:
                if event_data[1] == "discard":
                    flags.append(Flags.LAST_DISCARD_STOPPED_NAGASHI)
                    data.append({"seat": seat, "tile": tile})
                elif event_data[1] in {"minkan", "pon", "chii"}:
                    flags.append(Flags.LAST_NAGASHI_TILE_CALLED)
                    data.append({"seat": event_data[0], "tile": tile, "caller": seat})
        if seat == kyoku["round"] % kyoku["num_players"]: # dealer turn
            turn_number += 1

    # Finally, look at the game as a whole. This determines flags related to:
    # - deal-ins
    # - chases
    # - scoring
    if kyoku["result"][0] == "和了":
        # get final waits
        final_waits: List[List[int]] = list(map(lambda _: [], [()]*num_players))
        final_ukeire: List[int] = [0]*num_players
        for ix in (ix for ix, flag in enumerate(flags) if flag == Flags.SOMEONE_REACHED_TENPAI):
            seat = data[ix]["seat"]
            final_waits[seat] = data[ix]["wait"]
            final_ukeire[seat] = data[ix]["ukeire"]

        # check winners
        winners = [t for t in range(kyoku["num_players"]) if kyoku["result"][1][t] > 0]
        for w in winners:
            assert len(final_waits[w]) > 0, f"in {round_name(kyoku['round'], kyoku['honba'])}, seat {w} won with hand {ph(sorted_hand(kyoku['hands'][w]))}, but has no waits saved from SOMEONE_REACHED_TENPAI"
            if kyoku["result"][1][player] < 0 and not is_tsumo:
                if not opened_hand[w] and not in_riichi[w]:
                    flags.append(Flags.YOU_DEALT_INTO_DAMA)
                    data.append({"seat": w,
                                 "score": -kyoku["result"][1][player]})
                if "一発(1飜)" in kyoku["result"][2]:
                    flags.append(Flags.YOU_DEALT_INTO_IPPATSU)
                    data.append({"seat": w,
                                 "score": -kyoku["result"][1][player]})

            limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                                Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                                Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
            if kyoku["result"][2][3].startswith("満貫"):
                limit_hand_flags = limit_hand_flags[0:1]
            elif kyoku["result"][2][3].startswith("跳満"):
                limit_hand_flags = limit_hand_flags[0:2]
            elif kyoku["result"][2][3].startswith("倍満"):
                limit_hand_flags = limit_hand_flags[0:3]
            elif kyoku["result"][2][3].startswith("三倍満"):
                limit_hand_flags = limit_hand_flags[0:4]
            elif kyoku["result"][2][3].startswith("役満"):
                pass
            else:
                limit_hand_flags = []
            for flag in limit_hand_flags:
                flags.append(flag)
                data.append({"seat": w,
                             "wait": final_waits[w],
                             "ukeire": final_ukeire[w]})

            if final_ukeire[w] <= 4:
                flags.append(Flags.WINNER_HAD_BAD_WAIT)
                data.append({"seat": w,
                             "wait": final_waits[w],
                             "ukeire": final_ukeire[w]})
            if "一発(1飜)" in kyoku["result"][2] and is_tsumo:
                flags.append(Flags.WINNER_IPPATSU_TSUMO)
                data.append({"seat": w})
        if Flags.YOU_GOT_CHASED in flags:
            assert Flags.YOU_REACHED_TENPAI in flags, "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
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
                player_data = data[flags.index(Flags.YOU_REACHED_TENPAI)]
    elif kyoku["result"][0] in {"流局", "全員聴牌", "流し満貫"}:
        assert tiles_in_wall == 0, f"somehow ryuukyoku with {tiles_in_wall} tiles left in wall"
        flags.append(Flags.GAME_ENDED_WITH_RYUUKYOKU)
        data.append({})
        for seat in (seat for seat, achieved in enumerate(nagashi) if achieved):
            if seat == player:
                flags.append(Flags.YOU_ACHIEVED_NAGASHI)
                data.append({"seat": seat})

    if kyoku["result"][0] in {"和了", "流局"} and len(kyoku["result"][1]) > 0:
        if kyoku["result"][1][player] < 0:
            flags.append(Flags.YOU_LOST_POINTS)
            data.append({"amount": kyoku["result"][1][player]})
            if turn_number <= 6:
                flags.append(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)
                data.append({"seat": seat, "turn": turn_number, "amount": kyoku["result"][1][player]})
        elif kyoku["result"][1][player] > 0:
            "(1飜)"
            flags.append(Flags.YOU_GAINED_POINTS)
            data.append({"amount": kyoku["result"][1][player]})


    assert len(flags) == len(data), f"somehow got a different amount of flags ({len(flags)}) than data ({len(data)})"
    return flags, data

def evaluate_injustices(kyoku: Kyoku, player: int) -> List[str]:
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

# each injustice function takes two lists of flags: `require` and `forbid`
# the main `evaluate_injustices` function above calls an injustice function
#   only if all require flags exist and no forbid flags exist

injustices: List[Dict[str, Any]] = []
InjusticeFunc = Callable[[List[Flags], List[Dict[str, Any]], int, int, int], List[str]]
def injustice(require: List[Flags] = [], forbid: List[Flags] = []) -> Callable[[InjusticeFunc], InjusticeFunc] :
    """Decorator for DIY injustices, see below for usage"""
    global injustices
    def decorator(callback):
        injustices.append({"callback": callback, "required_flags": require, "forbidden_flags": forbid})
        return lambda f: f
    return decorator

# Print if your tenpai got chased by a worse wait, and they won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.YOU_TENPAI_FIRST,
                    Flags.YOU_GOT_CHASED, Flags.CHASER_GAINED_POINTS],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.GAME_ENDED_WITH_RYUUKYOKU,
                    Flags.YOU_GAINED_POINTS])
def chaser_won_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    chasers = {}
    for i in [i for i, f in enumerate(flags) if f == Flags.YOU_GOT_CHASED]:
        chase_data = data[i]
        chasers[chase_data["seat"]] = chase_data
    ret = []
    for chase_data in chasers.values():
        chaser_seat = chase_data["seat"]
        chaser_wait = chase_data["wait"]
        chaser_ukeire = chase_data["ukeire"]
        your_seat = chase_data["your_seat"]
        your_wait = chase_data["your_wait"]
        your_ukeire = chase_data["your_ukeire"]
        try:
            winner_seat = data[i+flags[i:].index(Flags.CHASER_GAINED_POINTS)]["seat"]
        except ValueError:
            continue
        if chaser_seat == winner_seat and chaser_ukeire < your_ukeire:
            if Flags.YOU_LOST_POINTS in flags and Flags.GAME_ENDED_WITH_RON in flags:
                ret.append(f"Major injustice detected in {round_name(round_number, honba)}:"
                           f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and you dealt into it")
            else:
                ret.append(f"Injustice detected in {round_name(round_number, honba)}:"
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
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you were stuck at {shanten_name(shanten)} for {turns} turns, and never reached tenpai"]

# Print if you started with atrocious shanten and never got to tenpai
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_REACHED_TENPAI])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["shanten"]
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you started at {shanten_name(shanten)}"]

# Print if you lost points to a first row ron/tsumo
@injustice(require=[Flags.LOST_POINTS_TO_FIRST_ROW_WIN])
def lost_points_to_first_row_win(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)]
    winner = win_data["seat"]
    turn = win_data["turn"]
    if Flags.YOU_DECLARED_RIICHI in flags:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you lost points to an early win by {relative_seat_name(player, winner)} on turn {turn}, while in riichi (goodbye riichi stick)"]
    elif Flags.YOU_REACHED_TENPAI in flags:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you lost points to an early win by {relative_seat_name(player, winner)} on turn {turn}, while tenpai"]
    else:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you lost points to an early win by {relative_seat_name(player, winner)} on turn {turn}"]

def tenpai_status_string(flags: List[Flags]) -> str:
    status = ""
    if Flags.YOU_DECLARED_RIICHI in flags and not Flags.YOUR_TENPAI_TILE_DEALT_IN in flags:
        status = ", while in riichi (goodbye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        status = ", while tenpai"
    return status

# Print if you dealt into dama
@injustice(require=[Flags.YOU_DEALT_INTO_DAMA])
def dealt_into_dama(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_DAMA)]
    winner = win_data["seat"]
    score = win_data["score"]
    extra_text = ""
    if Flags.YOU_DECLARED_RIICHI in flags:
        extra_text = ", while in riichi"
        if not Flags.YOUR_TENPAI_TILE_DEALT_IN in flags:
            extra_text += " (goodbye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        extra_text = ", while tenpai"
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point dama{tenpai_status_string(flags)}"]

# Print if you dealt into ippatsu
@injustice(require=[Flags.YOU_DEALT_INTO_IPPATSU])
def dealt_into_ippatsu(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_IPPATSU)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point ippatsu{tenpai_status_string(flags)}"]

# Print if someone else won with bad wait ippatsu tsumo
@injustice(require=[Flags.WINNER_HAD_BAD_WAIT, Flags.WINNER_IPPATSU_TSUMO],
           forbid=[Flags.YOU_GAINED_POINTS])
def someone_got_bad_wait_ippatsu_tsumo(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.WINNER_HAD_BAD_WAIT)]
    winner = win_data["seat"]
    wait = win_data["wait"]
    ukeire = win_data["ukeire"]
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" {relative_seat_name(player, winner)} got ippatsu tsumo with a bad wait {ph(wait)} ({ukeire} ukeire)"]

# Print if you just barely failed nagashi
@injustice(require=[Flags.LAST_DISCARD_STOPPED_NAGASHI],
           forbid=[Flags.LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_draw(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    nagashi_data = data[flags.index(Flags.LAST_DISCARD_STOPPED_NAGASHI)]
    seat = nagashi_data["seat"]
    tile = nagashi_data["tile"]
    if seat == player:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you lost nagashi on your last discard ({pt(tile)})"]
    else:
        return []

# Print if someone calls your last tile for nagashi (not ron)
@injustice(require=[Flags.LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_call(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    nagashi_data = data[flags.index(Flags.LAST_NAGASHI_TILE_CALLED)]
    seat = nagashi_data["seat"]
    tile = nagashi_data["tile"]
    caller = nagashi_data["caller"]
    if seat == player:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you lost nagashi on your last discard {pt(tile)} because {relative_seat_name(player, caller)} called it"]
    else:
        return []

# Print if you are dealer and lost to baiman+ tsumo
@injustice(require=[Flags.YOU_ARE_DEALER, Flags.GAME_ENDED_WITH_TSUMO, Flags.YOU_LOST_POINTS, Flags.WINNER_GOT_BAIMAN])
def baiman_oyakaburi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    win_data = data[flags.index(Flags.WINNER)]
    winner = win_data["seat"]
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you were dealer and {relative_seat_name(player, winner)} got a baiman tsumo"]

# Print if your riichi/tenpai tile dealt in
@injustice(require=[Flags.YOUR_TENPAI_TILE_DEALT_IN])
def your_tenpai_tile_dealt_in(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    tile = data[flags.index(Flags.YOUR_TENPAI_TILE_DEALT_IN)]["tile"]
    if Flags.YOU_DECLARED_RIICHI in flags:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you declared riichi with {pt(tile)} and immediately dealt in"]
    else:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you reached tenpai by discarding {pt(tile)} and immediately dealt in"]

# Print if you drew a tile that would have completed a past wait
@injustice(require=[Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE])
def drew_tile_completing_past_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    tile_data = data[flags.index(Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE)]
    tile = tile_data["tile"]
    wait = tile_data["wait"]
    shanten = tile_data["shanten"]
    return [f"Injustice detected in {round_name(round_number, honba)}:"
            f" you drew a tile {pt(tile)} that would have completed your past wait on {ph(wait)}"
            f" if you didn't change to {shanten_name(shanten)}"]

# Print if you dealt in while tenpai, right before you would have received tenpai payments
@injustice(require=[Flags.YOU_DEALT_IN_BEFORE_NOTEN_PAYMENT])
def you_dealt_in_before_noten_payment(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[str]:
    tile = data[flags.index(Flags.YOU_DEALT_IN_BEFORE_NOTEN_PAYMENT)]["tile"]
    if Flags.YOU_DECLARED_RIICHI in flags:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you were in riichi and about to get noten payments, but then dealt in with {pt(tile)}"]
    else:
        return [f"Injustice detected in {round_name(round_number, honba)}:"
                f" you were tenpai and about to get noten payments, but then dealt in with {pt(tile)}"]

# TODO: head bump, furiten
