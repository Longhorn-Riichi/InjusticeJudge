from .constants import Kyoku, GameMetadata, Ron, Tsumo, SHANTEN_NAMES, TRANSLATE
from dataclasses import dataclass
from enum import Enum
from typing import *
from .flags import Flags, determine_flags
from .utils import ph, pt, hidden_part, relative_seat_name, round_name, shanten_name, sorted_hand, try_remove_all_tiles
from pprint import pprint

@dataclass(frozen=True)
class Injustice:
    round: int
    honba: int
    name: str = "Injustice"
    desc: str = ""

def evaluate_injustices(kyoku: Kyoku, metadata: GameMetadata, player: int) -> List[str]:
    """
    Run each injustice function (defined below this function) against a parsed kyoku
    Relevant injustice functions should return a list of Injustice objects each
    Returns the full formatted list of injustices (a list of strings)
    """
    global injustices
    flags, data = determine_flags(kyoku, metadata)
    all_results: List[Injustice] = []
    for i in injustices:
        if     all(flag in flags[player]     for flag in i["required_flags"]) \
           and all(flag not in flags[player] for flag in i["forbidden_flags"]):
            result = i["callback"](flags[player], data[player], kyoku.round, kyoku.honba, player)
            all_results.extend(result)
        else:
            pass
            # print("player", player, "|",
            #       round_name(kyoku.round, kyoku.honba), "|",
            #       i["callback"].__name__, "was not called because it lacks the flag(s)",
            #       set(i["required_flags"]) - set(flags[player]),
            #       "and/or has the flag(s)",
            #       set(i["forbidden_flags"]) & set(flags[player]))

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
                           f" your wait {ph(your_wait)} ({your_ukeire} out{'s' if your_ukeire > 1 else ''})"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} out{'s' if chaser_ukeire > 1 else ''}), and you dealt into it"))
            else:
                ret.append(Injustice(round_number, honba, "Injustice",
                           f" your wait {ph(your_wait)} ({your_ukeire} out{'s' if your_ukeire > 1 else ''})"
                           f" was chased by {relative_seat_name(your_seat, chaser_seat)}"
                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} out{'s' if chaser_ukeire > 1 else ''}), and they won"))
    return ret

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    draws = shanten_data["draws"]
    shanten = shanten_data["shanten"]
    if Flags.YOU_REACHED_TENPAI in flags:
        return [Injustice(round_number, honba, "Injustice",
                f" you were stuck at {shanten_name(shanten)} for {draws} draws before you reached tenpai")]
    else:
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
        status = ", while you were in riichi (bye-bye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        status = ", while you were tenpai"
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
            f" {relative_seat_name(player, winner)} got ippatsu tsumo with a bad wait {ph(wait)} ({ukeire} outs)")]

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
            f" you drew a tile {pt(tile)} that would have completed your past tenpai wait on {ph(wait)}"
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
    seat = data[flags.index(Flags.WINNER_GOT_URA_3)]["seat"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(round_number, honba, "Injustice",
                f" you dealt into {relative_seat_name(player, seat)}'s hand with ura {value}{tenpai_status_string(flags)}")]
    else:
        return [Injustice(round_number, honba, "Injustice",
                f" you paid {relative_seat_name(player, seat)}'s tsumo with ura {value}")]

# Print if you dealt into haitei
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS])
def dealt_into_haitei(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_HAITEI)]["seat"]
    return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {relative_seat_name(player, seat)}'s houtei{tenpai_status_string(flags)}")]

# Print if winner drew haitei or got houtei, while you were in tenpai
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.YOU_REACHED_TENPAI], forbid=[Flags.YOU_GAINED_POINTS])
def winner_haitei_while_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    haitei_data = data[flags.index(Flags.WINNER_GOT_HAITEI)]
    seat = haitei_data["seat"]
    name = haitei_data["yaku"]
    dealer_string = " as dealer" if Flags.YOU_ARE_DEALER in flags else ""
    return [Injustice(round_number, honba, "Injustice",
            f" {relative_seat_name(player, seat)} got {name} while you were tenpai{dealer_string}")]

# Print if winner had 3+ han from dora tiles in the hidden part of hand
@injustice(require=[Flags.WINNER_GOT_HIDDEN_DORA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_hidden_dora_3(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["seat"]
    value = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["value"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(round_number, honba, "Injustice",
            f" you dealt into {relative_seat_name(player, seat)}'s hand with {value} hidden dora{tenpai_status_string(flags)}")]
    else:
        return [Injustice(round_number, honba, "Injustice",
            f" you paid {relative_seat_name(player, seat)}'s tsumo with {value} hidden dora")]

# Print if an early abortive draw happened with an iishanten haipai
@injustice(require=[Flags.IISHANTEN_HAIPAI_ABORTED])
def iishanten_haipai_aborted(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    draw_name = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["draw_name"]
    shanten = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["shanten"]
    hand = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["hand"]
    return [Injustice(round_number, honba, "Injustice",
            f" a {draw_name} happened when your hand looked like {ph(hand)} ({shanten_name(shanten)})")]

# Print if you reached yakuman tenpai but did not win
@injustice(require=[Flags.YOU_REACHED_YAKUMAN_TENPAI],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_RONNED_SOMEONE, Flags.YOU_TSUMOED, ])
def you_reached_yakuman_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    yakuman_types = data[flags.index(Flags.YOU_REACHED_YAKUMAN_TENPAI)]["types"]
    what_happened = "you didn't win"
    if Flags.GAME_ENDED_WITH_RON in flags:
        rons = data[flags.index(Flags.GAME_ENDED_WITH_RON)]["objects"]
        score = sum(ron.score for ron in rons)
        if Flags.YOU_DEALT_IN in flags:
            what_happened = f"then you dealt in for {score}"
        else:
            what_happened = f"then someone dealt into someone else for {score}"
    elif Flags.GAME_ENDED_WITH_TSUMO in flags:
        what_happened = "then someone just had to tsumo"
    elif Flags.GAME_ENDED_WITH_ABORTIVE_DRAW in flags:
        draw_name = data[flags.index(Flags.GAME_ENDED_WITH_ABORTIVE_DRAW)]["object"].name
        if draw_name == "ryuukyoku":
            what_happened = f"you never got it"
        else:
            what_happened = f"then someone ended the game with {draw_name}"
    return [Injustice(round_number, honba, "Injustice",
            f" you reached {' and '.join(yakuman_types)} tenpai, but {what_happened}")]

# Print if you got head bumped (or you skipped your ron)
@injustice(require=[Flags.YOU_WAITED_ON_WINNING_TILE, Flags.GAME_ENDED_WITH_RON],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS])
def you_got_head_bumped(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["tile"]
    wait = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["wait"]
    return [Injustice(round_number, honba, "Injustice",
            f" you were tenpai waiting on {ph(wait)} but then got head bumped")]

# Print if someone else's below-mangan win destroyed your mangan+ tenpai
@injustice(require=[Flags.YOU_HAD_LIMIT_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS,
                    Flags.GAME_ENDED_WITH_RYUUKYOKU, Flags.WINNER_GOT_MANGAN])
def your_mangan_tenpai_destroyed(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    hand_str = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["hand_str"]
    yaku_str = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["yaku_str"]
    limit_name = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["limit_name"]
    han = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["han"]
    score = data[flags.index(Flags.WINNER)]["score"]

    return [Injustice(round_number, honba, "Injustice",
            f" your hand {hand_str} could have had {limit_name} ({yaku_str}) but someone just had to score a {score} point hand")]
