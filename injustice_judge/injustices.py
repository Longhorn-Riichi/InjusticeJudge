from .constants import Kyoku, Ron, Tsumo, SHANTEN_NAMES, TRANSLATE
from dataclasses import dataclass
from enum import Enum
from typing import *
from .utils import ph, pt, hidden_part, relative_seat_name, round_name, shanten_name, sorted_hand, try_remove_all_tiles
from pprint import pprint

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " FIVE_SHANTEN_START"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " YOUR_LAST_DISCARD_ENDED_NAGASHI"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " SOMEONE_REACHED_TENPAI"
    " WINNER"
    " WINNER_GOT_BAIMAN"
    " WINNER_GOT_HANEMAN"
    " WINNER_GOT_MANGAN"
    " WINNER_GOT_SANBAIMAN"
    " WINNER_GOT_YAKUMAN"
    " WINNER_GOT_DORA_BOMB"
    " WINNER_GOT_URA_3"
    " WINNER_GOT_HAITEI"
    " WINNER_HAD_BAD_WAIT"
    " WINNER_IPPATSU_TSUMO"
    " WINNER_WAS_FURITEN"
    " YOU_ARE_DEALER"
    " YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_DOUBLE_RON"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
    " YOU_FOLDED_FROM_TENPAI"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_TENPAI_FIRST"
    " YOUR_LAST_NAGASHI_TILE_CALLED"
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

def determine_flags(kyoku) -> Tuple[List[List[Flags]], List[List[Dict[str, Any]]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag in `flags`
    """
    num_players = kyoku.num_players
    flags: List[List[Flags]] = [list() for i in range(num_players)]
    data: List[List[Any]] = [list() for i in range(num_players)]
    global_flags: List[Flags] = []
    global_data: List[Any] = []
    assert num_players in {3,4}, f"somehow we have {num_players} players"
    def add_flag(p, f, d = None):
        nonlocal flags
        nonlocal data
        flags[p].append(f)
        data[p].append(d)
    def add_global_flag(f, d = None):
        nonlocal global_flags
        nonlocal global_data
        global_flags.append(f)
        global_data.append(d)

    # First, get some basic data about the game.
    # - whether you're dealer
    # - game ending type
    # - when was each player's last draw and discard

    add_flag(kyoku.round % 4, Flags.YOU_ARE_DEALER)
    if kyoku.result[0] == "ron":
        add_global_flag(Flags.GAME_ENDED_WITH_RON)
    elif kyoku.result[0] == "tsumo":
        add_global_flag(Flags.GAME_ENDED_WITH_TSUMO)
    elif kyoku.result[0] == "ryuukyoku":
        add_global_flag(Flags.GAME_ENDED_WITH_RYUUKYOKU) # TODO abortive draws

    # Next, go through kyoku.events. This determines flags related to:
    # - starting shanten
    # - tenpais/riichis and chases/folds
    # - slow shanten changes

    shanten: List[Tuple[float, List[int]]] = [(99, [])]*4
    draws_since_shanten_change: List[int] = [0]*num_players
    tiles_in_wall = 70 if num_players == 4 else 55
    past_waits: List[List[List[int]]] = [list() for player in range(num_players)]
    num_discards: List[int] = [0]*num_players
    opened_hand: List[bool] = [False]*num_players
    in_riichi: List[bool] = [False]*num_players
    nagashi: List[bool] = [True]*num_players
    for i, event in enumerate(kyoku.events):
        # print(round_name(kyoku.round, kyoku.honba), ":", tiles_in_wall, seat, event)
        seat, event_type, *event_data = event
        if event_type in {"draw", "minkan"}:
            tiles_in_wall -= 1
            tile = event_data[0]
            # check if draw would have completed a past wait
            for wait in past_waits[seat]:
                if tile in wait:
                    add_flag(seat, Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE, {"tile": event_data[0], "wait": wait, "shanten": shanten[seat]})
            # check if it's been more than 9 draws since we changed shanten
            if shanten[seat][0] > 0 and draws_since_shanten_change[seat] >= 9:
                add_flag(seat, Flags.NINE_DRAWS_NO_IMPROVEMENT, {"shanten": shanten[seat], "draws": draws_since_shanten_change[seat]})
            draws_since_shanten_change[seat] += 1
        elif event_type == "riichi":
            in_riichi[seat] = True
            add_flag(seat, Flags.YOU_DECLARED_RIICHI)
        elif event_type in {"chii", "pon", "minkan"}:
            opened_hand[seat] = True
        elif event_type == "discard":
            num_discards[seat] += 1
            is_last_discard_of_the_game = i == max(kyoku.final_discard_event_index)
            # check if this is the deal-in tile
            if is_last_discard_of_the_game and kyoku.result[0] == "ron":
                # check if we just reached tenpai
                already_tenpai = Flags.YOU_REACHED_TENPAI in flags[seat]
                if not already_tenpai and any(e[0] == seat and e[1] == "tenpai" for e in kyoku.events[i:]):
                    add_flag(seat, Flags.YOUR_TENPAI_TILE_DEALT_IN, {"tile": event_data[0]})
                # check if we're tenpai and this would have been our last discard before noten payments
                if already_tenpai and tiles_in_wall <= 3:
                    add_flag(seat, Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT, {"tile": event_data[0]})
        elif event_type == "tenpai":
            # check if we're tenpai first
            if Flags.SOMEONE_REACHED_TENPAI not in global_flags:
                add_flag(seat, Flags.YOU_TENPAI_FIRST)
            # otherwise, this is a chase
            else:
                for other in range(num_players):
                    if other == seat:
                        continue
                    if Flags.YOU_REACHED_TENPAI in flags[other]:
                        other_data = data[other][len(flags[other]) - 1 - flags[other][::-1].index(Flags.YOU_REACHED_TENPAI)]
                        add_flag(other, Flags.YOU_GOT_CHASED,
                                       {"seat": seat,
                                        "hand": event_data[0],
                                        "wait": event_data[1],
                                        "ukeire": event_data[2],
                                        "furiten": kyoku.furiten[seat],
                                        "your_seat": other,
                                        "your_hand": other_data["hand"],
                                        "your_wait": other_data["wait"],
                                        "your_ukeire": other_data["ukeire"],
                                        "furiten": other_data["furiten"]})
            add_global_flag(Flags.SOMEONE_REACHED_TENPAI,
                            {"seat": seat,
                             "hand": event_data[0],
                             "wait": event_data[1],
                             "ukeire": event_data[2],
                             "furiten": kyoku.furiten[seat]})
            add_flag(seat, Flags.YOU_REACHED_TENPAI,
                           {"hand": event_data[0],
                            "wait": event_data[1],
                            "ukeire": event_data[2],
                            "furiten": kyoku.furiten[seat]})
            # check for first row tenpai
            if num_discards[seat] <= 6:
                add_flag(seat, Flags.FIRST_ROW_TENPAI, {"seat": seat, "turn": num_discards[seat]})
            # remove YOU_FOLDED_FROM_TENPAI flag if any
            if Flags.YOU_FOLDED_FROM_TENPAI in flags[seat]:
                ix = flags[seat].index(Flags.YOU_FOLDED_FROM_TENPAI)
                del flags[seat][ix]
                del data[seat][ix]
        elif event_type == "end_nagashi":
            who, reason, tile = event_data
            nagashi[who] = False
            # check if this happened after our final draw (if the game ended in ryuukyoku)
            if kyoku.result[0] == "ryuukyoku" and i > kyoku.final_draw_event_index[seat]:
                if reason == "discard":
                    add_flag(who, Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI, {"tile": tile})
                elif reason in {"minkan", "pon", "chii"}:
                    add_flag(who, Flags.YOUR_LAST_NAGASHI_TILE_CALLED, {"tile": tile, "caller": seat})
        elif event_type == "haipai_shanten":
            shanten[seat] = event_data[0]
            if shanten[seat][0] >= 5:
                add_flag(seat, Flags.FIVE_SHANTEN_START, {"shanten": shanten[seat]})
        elif event_type == "shanten_change":
            prev_shanten, new_shanten = event_data
            assert shanten[seat][0] != 99, f"missing haipai_shanten event before a shanten_change event"
            assert prev_shanten == shanten[seat], f"somehow shanten changed from {shanten[seat]} to {prev_shanten} outside a shanten_change event"
            shanten[seat] = new_shanten
            draws_since_shanten_change[seat] = 0
            # record past waits if we've changed from tenpai
            if prev_shanten[0] == 0:
                past_waits[seat].append(prev_shanten[1])
                if new_shanten[0] > 0:
                    add_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)

    # Finally, look at kyoku.result. This determines flags related to:
    # - deal-ins
    # - chases
    # - results
    result_type, *results = kyoku.result

    for result in results:
        for seat in range(num_players):
            # check for points won or lost
            if result.score_delta[seat] > 0:
                add_flag(seat, Flags.YOU_GAINED_POINTS, {"amount": result.score_delta[seat]})
            elif result.score_delta[seat] < 0:
                add_flag(seat, Flags.YOU_LOST_POINTS, {"amount": -result.score_delta[seat]})
                # check for first row win
                if result_type in {"ron", "tsumo"}:
                    num_winner_discards = len(kyoku.pond[result.winner])
                    if num_winner_discards <= 6:
                        add_flag(seat, Flags.LOST_POINTS_TO_FIRST_ROW_WIN, {"seat": result.winner, "turn": num_winner_discards})

    if result_type in {"ron", "tsumo"}:
        for result in results:
            # Add potentially several WINNER flags depending on the limit hand
            # e.g. haneman wins will get WINNER_GOT_HANEMAN plus all the flags before that
            assert len(kyoku.final_waits) > 0, "forgot to set kyoku.final_waits after processing event list"
            limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                                Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                                Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
            limit_hand_names = ["", "", "満貫", "跳満", "倍満", "三倍満", "役満"]
            assert result.limit_name in limit_hand_names, f"unknown limit hand name {result.limit_name}"
            limit_hand_flags = limit_hand_flags[0:limit_hand_names.index(result.limit_name)]
            for flag in limit_hand_flags:
                add_global_flag(flag, {"seat": result.winner,
                                       "wait": kyoku.final_waits[result.winner],
                                       "ukeire": kyoku.final_ukeire[result.winner]})
            if kyoku.final_ukeire[result.winner] <= 4:
                add_global_flag(Flags.WINNER_HAD_BAD_WAIT,
                                {"seat": result.winner,
                                 "wait": kyoku.final_waits[result.winner],
                                 "ukeire": kyoku.final_ukeire[result.winner]})
            # check for 3+ hidden dora
            if result.yaku.dora >= 3:
                hidden_hand = hidden_part(tuple(kyoku.hands[result.winner]), tuple(kyoku.calls[result.winner]))
                hidden_dora = sum((Counter(hidden_hand) & Counter(kyoku.doras*4)).values())
                if hidden_dora >= 3:
                    add_global_flag(Flags.WINNER_GOT_DORA_BOMB, {"seat": result.winner, "value": result.yaku.dora})
            # check for 3+ ura
            elif result.yaku.ura >= 3:
                add_global_flag(Flags.WINNER_GOT_URA_3, {"seat": result.winner, "value": result.yaku.ura})
            # check for haitei/houtei
            if result.yaku.haitei:
                haitei_type = "haitei" if "海底摸月(1飜)" in result.yaku.yaku_strs \
                         else "houtei" if "河底撈魚(1飜)" in result.yaku.yaku_strs \
                         else ""
                assert haitei_type != "", f"unknown haitei type for yaku {result.yaku.yaku_strs}"
                add_global_flag(Flags.WINNER_GOT_HAITEI, {"seat": result.winner, "yaku": haitei_type})

    if result_type == "ron":
        # check winners
        for ron in results:
            assert isinstance(ron, Ron), f"result tagged ron got non-Ron object: {ron}"
            # check deal-ins
            assert len(kyoku.final_waits[ron.winner]) > 0, f"in {round_name(kyoku.round, kyoku.honba)}, seat {ron.winner} won with hand {ph(sorted_hand(kyoku.hands[ron.winner]))}, but has no waits saved in kyoku.final_waits"
            for seat in range(num_players):
                if ron.score_delta[seat] < 0:
                    if not opened_hand[ron.winner] and not in_riichi[ron.winner]:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DAMA, {"seat": ron.winner, "score": -ron.score_delta[seat]})
                    if ron.yaku.ippatsu:
                        add_flag(seat, Flags.YOU_DEALT_INTO_IPPATSU, {"seat": ron.winner, "score": -ron.score_delta[seat]})
                    if len(results) > 1:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DOUBLE_RON, {"number": len(results)})
        if Flags.YOU_GOT_CHASED in flags[ron.won_from]:
            assert Flags.YOU_REACHED_TENPAI in flags[ron.won_from], "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
            add_flag(ron.won_from, Flags.CHASER_GAINED_POINTS, {"seat": ron.winner, "amount": ron.score})
    elif result_type == "tsumo":
        tsumo = results[0]
        assert isinstance(tsumo, Tsumo), f"result tagged tsumo got non-Tsumo object: {tsumo}"
        # check furiten
        if kyoku.furiten[tsumo.winner]:
            add_flag(Flags.WINNER_WAS_FURITEN,
                     {"seat": tsumo.winner,
                      "wait": kyoku.final_waits[tsumo.winner],
                      "ukeire": kyoku.final_ukeire[tsumo.winner]})
        # check ippatsu tsumo
        if tsumo.yaku.ippatsu:
            add_flag(seat, Flags.WINNER_IPPATSU_TSUMO, {"seat": tsumo.winner})
    elif result_type == "draw":
        name = results[0].name
        if name in {"ryuukyoku", "nagashi mangan"}:
            assert tiles_in_wall == 0, f"somehow ryuukyoku with {tiles_in_wall} tiles left in wall"
            for seat in (seat for seat, achieved in enumerate(nagashi) if achieved):
                add_flag(seat, Flags.YOU_ACHIEVED_NAGASHI, {"seat": seat})

    assert len(global_flags) == len(global_data), f"somehow got a different amount of global flags ({len(global_flags)}) than data ({len(global_data)})"
    for seat in range(num_players):
        assert len(flags[seat]) == len(data[seat]), f"somehow got a different amount of flags ({len(flags[seat])}) than data ({len(data[seat])})"
        flags[seat] = global_flags + flags[seat]
        data[seat] = global_data + data[seat]
    return flags, data

@dataclass(frozen=True)
class Injustice:
    round: int
    honba: int
    name: str = "Injustice"
    desc: str = ""

def evaluate_injustices(kyoku: Kyoku, player: int) -> List[str]:
    """
    Run each injustice function (defined below this function) against a parsed kyoku
    Relevant injustice functions should return a list of Injustice objects each
    Returns the full formatted list of injustices (a list of strings)
    """
    global injustices
    flags, data = determine_flags(kyoku)
    all_results: List[Injustice] = []
    for i in injustices:
        if     all(flag in flags[player]     for flag in i["required_flags"]) \
           and all(flag not in flags[player] for flag in i["forbidden_flags"]):
            result = i["callback"](flags[player], data[player], kyoku.round, kyoku.honba, player)
            all_results.extend(result)

    # `all_results` contains a list of injustices for this kyoku,
    #   but we need to group them up before we printing.
    # This outputs a header like "- Injustice detected in **East 1**:"
    #   followed by `injustice.desc` joined by ", and"
    #   for every injustice in all_results
    if len(all_results) > 0:
        # get the name of the longest name out of all the injustices
        longest_name_length = max(len(r.name) for r in all_results)
        longest_name = next(r.name for r in all_results if len(r.name) == longest_name_length)
        # assemble the header
        header = f"- {longest_name} detected in **{round_name(all_results[0].round, all_results[0].honba)}**:"
        # return a list containing a single string:
        #   the header + each injustice separated by ", and"
        return [header + ", and".join(r.desc for r in all_results)]
    else:
        return []

###
### injustice definitions
###

# each injustice function takes two lists of flags: `require` and `forbid`
# the main `evaluate_injustices` function above calls an injustice function
#   only if all `require` flags exist and no `forbid` flags exist, for each kyoku

injustices: List[Dict[str, Any]] = []
InjusticeFunc = Callable[[List[Flags], List[Dict[str, Any]], int, int, int], List[Injustice]]
def injustice(require: List[Flags] = [], forbid: List[Flags] = []) -> Callable[[InjusticeFunc], InjusticeFunc] :
    """Decorator for DIY injustices, see below for usage"""
    global injustices
    def decorator(callback):
        injustices.append({"callback": callback, "required_flags": require, "forbidden_flags": forbid})
        return lambda f: f
    return decorator

# Print if your tenpai got chased by a worse wait, and they won
@injustice(require=[Flags.YOU_REACHED_TENPAI,
                    Flags.YOU_GOT_CHASED, Flags.CHASER_GAINED_POINTS],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.GAME_ENDED_WITH_RYUUKYOKU,
                    Flags.YOU_GAINED_POINTS])
def chaser_won_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    chasers: Dict[int, Dict[str, Any]] = {}
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
                ret.append(Injustice(round_number, honba, "Major injustice",
                           f" your wait {ph(your_wait)} ({your_ukeire} outs)"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} outs), and you dealt into it"))
            else:
                ret.append(Injustice(round_number, honba, "Injustice",
                           f" your wait {ph(your_wait)} ({your_ukeire} outs)"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} outs), and they won"))
    return ret

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT],
            forbid=[Flags.YOU_REACHED_TENPAI])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    draws = shanten_data["draws"]
    shanten = shanten_data["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            f" you were stuck at {shanten_name(shanten)} for {draws} draws, and never reached tenpai")]

# Print if you started with atrocious shanten and never got to tenpai
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_REACHED_TENPAI])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            f" you started at {shanten_name(shanten)} and never reached tenpai")]

def tenpai_status_string(flags: List[Flags]) -> str:
    status = ""
    if Flags.YOU_DECLARED_RIICHI in flags and not Flags.YOUR_TENPAI_TILE_DEALT_IN in flags:
        status = ", while in riichi (goodbye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        status = ", while tenpai"
    return status

# Print if you lost points to a first row ron/tsumo
@injustice(require=[Flags.LOST_POINTS_TO_FIRST_ROW_WIN])
def lost_points_to_first_row_win(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)]
    winner = win_data["seat"]
    turn = win_data["turn"]
    prefix = f"you dealt into an early ron" if Flags.GAME_ENDED_WITH_RON in flags else "you got hit by an early tsumo"
    return [Injustice(round_number, honba, "Injustice",
            f" {prefix} by {relative_seat_name(player, winner)} on turn {turn}{tenpai_status_string(flags)}")]

# Print if you dealt into dama
@injustice(require=[Flags.YOU_DEALT_INTO_DAMA])
def dealt_into_dama(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_DAMA)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point dama{tenpai_status_string(flags)}")]

# Print if you dealt into ippatsu
@injustice(require=[Flags.YOU_DEALT_INTO_IPPATSU])
def dealt_into_ippatsu(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_IPPATSU)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {relative_seat_name(player, winner)}'s {score} point ippatsu{tenpai_status_string(flags)}")]

# Print if someone else won with bad wait ippatsu tsumo
@injustice(require=[Flags.WINNER_HAD_BAD_WAIT, Flags.WINNER_IPPATSU_TSUMO],
           forbid=[Flags.YOU_GAINED_POINTS])
def someone_got_bad_wait_ippatsu_tsumo(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.WINNER_HAD_BAD_WAIT)]
    winner = win_data["seat"]
    wait = win_data["wait"]
    ukeire = win_data["ukeire"]
    return [Injustice(round_number, honba, "Injustice",
            f" {relative_seat_name(player, winner)} got ippatsu tsumo with a bad wait {ph(wait)} ({ukeire} ukeire)")]

# Print if you just barely failed nagashi
@injustice(require=[Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI],
           forbid=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_draw(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI)]["tile"]
    return [Injustice(round_number, honba, "Injustice",
            f" you lost nagashi on your last discard ({pt(tile)})")]

# Print if someone calls your last tile for nagashi (not ron)
@injustice(require=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_call(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    nagashi_data = data[flags.index(Flags.YOUR_LAST_NAGASHI_TILE_CALLED)]
    tile = nagashi_data["tile"]
    caller = nagashi_data["caller"]
    return [Injustice(round_number, honba, "Injustice",
            f" you lost nagashi on your last discard {pt(tile)} because {relative_seat_name(player, caller)} called it")]

# Print if you are dealer and lost to baiman+ tsumo
@injustice(require=[Flags.YOU_ARE_DEALER, Flags.GAME_ENDED_WITH_TSUMO, Flags.YOU_LOST_POINTS, Flags.WINNER_GOT_BAIMAN])
def baiman_oyakaburi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.WINNER)]
    winner = win_data["seat"]
    furiten_string = ", while in furiten" if Flags.WINNER_WAS_FURITEN else ""
    return [Injustice(round_number, honba, "Injustice",
            f" you were dealer and {relative_seat_name(player, winner)} got a baiman tsumo{furiten_string}")]

# Print if your riichi/tenpai tile dealt in
@injustice(require=[Flags.YOUR_TENPAI_TILE_DEALT_IN])
def your_tenpai_tile_dealt_in(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOUR_TENPAI_TILE_DEALT_IN)]["tile"]
    tenpai_string = "declared riichi with" if Flags.YOU_DECLARED_RIICHI in flags else "reached tenpai by discarding"
    return [Injustice(round_number, honba, "Injustice",
            f" you {tenpai_string} {pt(tile)} and immediately dealt in")]

# Print if you drew a tile that would have completed a past wait
@injustice(require=[Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE])
def drew_tile_completing_past_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile_data = data[flags.index(Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE)]
    tile = tile_data["tile"]
    wait = tile_data["wait"]
    shanten = tile_data["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            f" you drew a tile {pt(tile)} that would have completed your past wait on {ph(wait)}"
            f" if you didn't change to {shanten_name(shanten)}")]

# Print if you dealt in while tenpai, right before you would have received tenpai payments
@injustice(require=[Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT])
def you_JUST_dealt_in_before_noten_payment(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT)]["tile"]
    tenpai_string = "in riichi" if Flags.YOU_DECLARED_RIICHI in flags else "tenpai"
    return [Injustice(round_number, honba, "Injustice",
            f" you were {tenpai_string} and about to get noten payments, but then dealt in with {pt(tile)}")]

# Print if you dealt in while tenpai, right before you would have received tenpai payments
@injustice(require=[Flags.YOU_DEALT_INTO_DOUBLE_RON])
def you_dealt_into_double_ron(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    number = data[flags.index(Flags.YOU_DEALT_INTO_DOUBLE_RON)]["number"]
    return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {'double' if number == 2 else 'triple'} ron")]

# Print if you dealt into ura 3 OR if someone else tsumoed and got ura 3
@injustice(require=[Flags.WINNER_GOT_URA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_ura_3(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    value = data[flags.index(Flags.WINNER_GOT_URA_3)]["value"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(round_number, honba, "Injustice",
                f" you dealt into a hand with ura {value}{tenpai_status_string(flags)}")]
    else:
        return [Injustice(round_number, honba, "Injustice",
                f" someone tsumoed and got ura {value}")]

# Print if you dealt into haitei
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS])
def dealt_into_haitei(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_HAITEI)]["seat"]
    return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {relative_seat_name(player, seat)}'s houtei{tenpai_status_string(flags)}")]

# Print if winner drew haitei or got houtei, while you were in tenpai
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.YOU_REACHED_TENPAI])
def winner_haitei_while_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    haitei_data = data[flags.index(Flags.WINNER_GOT_HAITEI)]
    seat = haitei_data["seat"]
    name = haitei_data["yaku"]
    dealer_string = " as dealer" if Flags.YOU_ARE_DEALER in flags else ""
    return [Injustice(round_number, honba, "Injustice",
            f" {relative_seat_name(player, seat)} got {name} while you were tenpai{dealer_string}")]

# Print if winner had 3+ dora in closed part of hand
@injustice(require=[Flags.WINNER_GOT_DORA_BOMB], forbid=[Flags.YOU_GAINED_POINTS])
def dora_bomb(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_DORA_BOMB)]["seat"]
    value = data[flags.index(Flags.WINNER_GOT_DORA_BOMB)]["value"]
    return [Injustice(round_number, honba, "Injustice",
            f" {relative_seat_name(player, seat)} won with dora {value} hidden in hand")]

# TODO: head bump
