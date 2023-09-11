from .classes import Kyoku, Ron, Score, Tsumo
from .constants import PLACEMENTS, SHANTEN_NAMES, TRANSLATE
from dataclasses import dataclass
from enum import Enum
from typing import *
from .flags import Flags, determine_flags
from .utils import apply_delta_scores, calculate_delta_scores, is_mangan, ph, pt, relative_seat_name, round_name, shanten_name, sorted_hand, to_placement, try_remove_all_tiles, calculate_delta_scores, apply_delta_scores
from pprint import pprint

# This file provides `evaluate_injustices`, which is called by `__init__.py`
#   after it fetches a list of kyoku. It first generates facts about the kyoku
#   via `determine_flags` from `flags.py`. It then calls every injustice
#   function (defined at the end of the file) that satisfies said flags,
#   generating a list of `Injustice` objects. These `Injustice`s are then
#   formatted as a string and returned to `__init__.py`.
#   
# See `evaluate_injustices` and `injustice` for more info.

# ad-hoc object used for joining two injustices with better grammar
# extremely subject to change

@dataclass(frozen=True)
class InjusticeClause:
    subject: str
    verb: str
    object: Optional[str] = None
    content: Optional[str] = None
    subject_description: Optional[str] = None
    last_subject: Optional[str] = None

# main injustice object used for printing
@dataclass(frozen=True)
class Injustice:
    round: int
    honba: int
    name: str
    clause: InjusticeClause

def evaluate_injustices(kyoku: Kyoku, player: int) -> List[str]:
    """
    Run each injustice function (defined below this function) against a parsed kyoku.
    Relevant injustice functions should return a list of Injustice objects each.
    The return value is either a single-element list containing the final formatted
        injustice string, or an empty list if there were no injustices.
    """
    global injustices
    flags, data = determine_flags(kyoku)
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
        # now print the subject of the first injustice clause followed by content
        # whenever the subject of the next clause is the same as the subject of the previous clause,
        # we omit the subject and just write ", and <content>"
        # return a list containing a single string
        ret = header
        last_clause = None
        seen_results: Set[Tuple[str, str, str]] = set() # (subject, content)
        for result in all_results:
            clause = result.clause
            # skip things we've already said
            if (clause.subject, clause.object, clause.content) in seen_results:
                continue
            seen_results.add((clause.subject, clause.verb, clause.object))

            # add ", and" unless it's the first clause
            if last_clause is not None:
                ret += ", and"
            else:
                last_clause = InjusticeClause(subject="",verb="")

            # print subject if subject changed
            if clause.subject != last_clause.subject:
                ret += " " + clause.subject
                # print subject description
                # this is basically part of the subject,
                # but we don't want it to be used for comparing subjects
                if clause.subject_description is not None:
                    ret += " " + clause.subject_description
                current_subject = clause.subject

            # print verb if verb changed or if subject changed
            if clause.verb != last_clause.verb or clause.subject != last_clause.subject:
                ret += " " + clause.verb

            # print object always (if any)
            if clause.object is not None:
                ret += " " + clause.object
            # print content always (if any)
            if clause.content is not None:
                ret += " " + clause.content

            # if the clause ends on another subject, change current subject to that
            if clause.last_subject is not None:
                current_subject = clause.last_subject
            last_clause = clause
        return [ret]
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
        return callback
    return decorator



###
### early game injustices
###

# Print if you started with atrocious shanten and couldn't gain points as a result
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_GAINED_POINTS])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="started with",
                            object=shanten_name(shanten)))]

# Print if you started with 7-8 types of terminals and couldn't gain points as a result
@injustice(require=[Flags.SEVEN_TERMINAL_START],
            forbid=[Flags.YOU_GAINED_POINTS])
def seven_terminal_start(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    num_types = data[flags.index(Flags.SEVEN_TERMINAL_START)]["num_types"]
    if num_types in {8,9}:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject="you",
                                verb="started with",
                                content=f"{num_types} types of terminal/honor tiles"))]
    return []

@injustice(require=[Flags.STARTED_WITH_TWO_147_SHAPES],
            forbid=[])
def started_with_two_147_shapes(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    hand = data[flags.index(Flags.STARTED_WITH_TWO_147_SHAPES)]["hand"]
    num = data[flags.index(Flags.STARTED_WITH_TWO_147_SHAPES)]["num"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="started with",
                            object=f"{num} 1-4-7 shapes",
                            content=f"in your hand ({ph(hand)})"))]

# Print if you were still at bad shanten after the first row of discards and couldn't gain points as a result
@injustice(require=[Flags.FOUR_SHANTEN_AFTER_FIRST_ROW],
            forbid=[Flags.YOU_GAINED_POINTS])
def four_shanten_after_first_row(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten = data[flags.index(Flags.FOUR_SHANTEN_AFTER_FIRST_ROW)]["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were still",
                            object=shanten_name(shanten),
                            content="after the first row of discards"))]

@injustice(require=[Flags.DREW_WORST_HAIPAI_SHANTEN],
            forbid=[])
def drew_worst_shanten_by_far(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten: Tuple[int, List[int]] = data[flags.index(Flags.DREW_WORST_HAIPAI_SHANTEN)]["shanten"]
    second_worst_shanten: int = data[flags.index(Flags.DREW_WORST_HAIPAI_SHANTEN)]["second_worst_shanten"]
    difference = (shanten[0]//1) - second_worst_shanten
    if difference >= 2:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject=f"your {shanten_name(shanten)} start",
                                verb=f"was {difference} worse than",
                                object=f"everyone else's starting shanten",
                                content=f"(their worst was {SHANTEN_NAMES[second_worst_shanten]})"))]
    else:
        return []

###
### mid game injustices
###

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
        if chaser_seat != winner_seat or chaser_ukeire >= your_ukeire:
            continue
        ret.append(Injustice(round_number, honba, "Injustice",
                   InjusticeClause(subject="your wait",
                                   subject_description=f"{ph(your_wait)} ({your_ukeire} out{'s' if your_ukeire > 1 else ''})",
                                   verb="was chased by",
                                   object=f"{relative_seat_name(your_seat, chaser_seat)}"
                                           f" with a worse wait {ph(chaser_wait)} ({chaser_ukeire} out{'s' if chaser_ukeire > 1 else ''})")))
        if Flags.YOU_LOST_POINTS in flags and Flags.GAME_ENDED_WITH_RON in flags:
            ret.append(Injustice(round_number, honba, "Major injustice",
                       InjusticeClause(subject="you", verb="dealt into", object="it")))
        else:
            ret.append(Injustice(round_number, honba, "Injustice",
                       InjusticeClause(subject="they", verb="won")))
    return ret

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    draws = shanten_data["draws"]
    shanten = shanten_data["shanten"]
    ret = []
    reached_tenpai_str = " before you finally reached tenpai" if Flags.YOU_REACHED_TENPAI in flags else ", and never reached tenpai"
    if Flags.YOU_REACHED_TENPAI in flags:
        ret.append(Injustice(round_number, honba, "Injustice",
                   InjusticeClause(subject="you",
                                   verb="were stuck at",
                                   content=f"{shanten_name(shanten)} for {draws} draws before you finally reached tenpai")))
    else:
        ret.append(Injustice(round_number, honba, "Injustice",
                   InjusticeClause(subject="you",
                                   verb="were stuck at",
                                   content=f"{shanten_name(shanten)} for {draws} draws")))
        ret.append(Injustice(round_number, honba, "Injustice",
                   InjusticeClause(subject="you", verb="never reached", object="tenpai")))
    return ret

# Print if you drew a dora tile you had discarded a turn prior
@injustice(require=[Flags.IMMEDIATELY_DREW_DISCARDED_DORA],
            forbid=[])
def drew_dora_you_just_discarded(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.IMMEDIATELY_DREW_DISCARDED_DORA)]["tile"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="immediately drew",
                            content=f"a dora {pt(tile+100)} that you just discarded"))]

# Print if your turn was skipped 3 times due to pon/kan
@injustice(require=[Flags.TURN_SKIPPED_BY_PON],
            forbid=[])
def turn_was_skipped_3_times(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    times = flags.count(Flags.TURN_SKIPPED_BY_PON)
    if times >= 3:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject="your turn",
                                verb="was skipped",
                                content=f"{times} times by pon/kan"))]
    else:
        return []

# Print if you just barely failed nagashi
@injustice(require=[Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI],
            forbid=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_draw(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI)]["tile"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="lost",
                            content=f"nagashi on your last discard ({pt(tile)})"))]

# Print if someone calls your last tile for nagashi (not ron)
@injustice(require=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_call(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    nagashi_data = data[flags.index(Flags.YOUR_LAST_NAGASHI_TILE_CALLED)]
    tile = nagashi_data["tile"]
    caller = nagashi_data["caller"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="lost",
                            content=f"nagashi on your last discard {pt(tile)} because {relative_seat_name(player, caller)} called it"))]

# Print if ankan removed (part of) your tenpai wait
@injustice(require=[Flags.ANKAN_ERASED_TENPAI_WAIT])
def ankan_erased_tenpai_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["tile"]
    wait = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["wait"]
    ukeire = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["ukeire"]
    caller = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["caller"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject=f"{relative_seat_name(player, caller)}'s ankan",
                            subject_description=ph((50,tile,tile,50)),
                            verb="erased",
                            content=f"{'your entire' if ukeire <= 4 else 'part of your'} wait {ph(wait)}"))]

# Print if you drew at least 6 off-suit tiles in a row for honitsu
@injustice(require=[Flags.BAD_HONITSU_DRAWS])
def consecutive_bad_honitsu_draws(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tiles = data[flags.index(Flags.BAD_HONITSU_DRAWS)]["tiles"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were going for",
                            content=f"honitsu, but drew {len(tiles)} off-suit tiles ({ph(tiles)}) in a row"))]

# Print if you had to deal with triple riichi
@injustice(require=[Flags.AGAINST_TRIPLE_RIICHI, Flags.YOU_DEALT_IN])
def against_triple_riichi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were against",
                            object="a triple riichi, and dealt in"))]

# Print if your 3-shanten start was slower than someone else's 5-shanten start
@injustice(require=[Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN],
           forbid=[Flags.YOU_REACHED_TENPAI])
def your_3_shanten_slower_than_5_shanten(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    their_seat = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["seat"]
    their_shanten = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["their_shanten"]
    your_shanten = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["your_shanten"]

    if Flags.YOU_REACHED_TENPAI in flags:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject=f"your {SHANTEN_NAMES[your_shanten]} starting hand",
                                verb="reached tenpai after",
                                content=f"{relative_seat_name(player, their_seat)} who started from {SHANTEN_NAMES[their_shanten]}"))]
    else:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject=f"your {SHANTEN_NAMES[your_shanten]} starting hand",
                                verb="couldn't reach tenpai,",
                                content=f"yet {relative_seat_name(player, their_seat)}'s {SHANTEN_NAMES[their_shanten]} starting hand did"))]

# Print if you were ever iishanten with zero tiles left
@injustice(require=[Flags.IISHANTEN_WITH_0_TILES])
def iishanten_with_0_tiles(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    shanten = data[flags.index(Flags.IISHANTEN_WITH_0_TILES)]["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject=f"your {shanten_name(shanten)}",
                            verb="had",
                            content="zero outs at some point"))]

# Print if everyone immediately threw a dangerous tile after your riichi
@injustice(require=[Flags.EVERYONE_DISRESPECTED_YOUR_RIICHI])
def everyone_disrespected_your_riichi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="your riichi",
                            verb="was disrespected by",
                            content="everyone (they all immediately threw dangerous tiles against you)"))]

# Print if you drew a dangerous tile and had no safe tiles at least four times
@injustice(require=[Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI])
def four_dangerous_draws_after_riichi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    num = data[len(data) - 1 - flags[::-1].index(Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI)]["num"]
    opponent = data[len(data) - 1 - flags[::-1].index(Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI)]["opponent"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="kept drawing",
                            content=f"dangerous tile after dangerous tile ({num} times) after {relative_seat_name(player, opponent)}'s riichi"))]

###
### end game injustices
###

def tenpai_status_string(flags: List[Flags]) -> str:
    status = ""
    if Flags.YOU_DECLARED_RIICHI in flags and not Flags.YOUR_TENPAI_TILE_DEALT_IN in flags:
        status = ", while you were in riichi (bye-bye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        status = ", while you were tenpai"
    return status

# Print if your riichi discard passed, but someone stole your riichi stick before your next draw
@injustice(require=[Flags.LAST_DISCARD_WAS_RIICHI, Flags.WINNER],
            forbid=[Flags.YOUR_TENPAI_TILE_DEALT_IN])
def riichi_stick_robbed(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    winner = data[flags.index(Flags.WINNER)]["seat"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="your riichi discard",
                            verb="passed",
                            content=f"but {relative_seat_name(player, winner)} won before your next draw, stealing your riichi stick",
                            last_subject=relative_seat_name(player, winner)))]

# Print if you lost points to a first row ron/tsumo
@injustice(require=[Flags.LOST_POINTS_TO_FIRST_ROW_WIN])
def lost_points_to_first_row_win(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)]
    winner = win_data["seat"]
    turn = win_data["turn"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into" if Flags.GAME_ENDED_WITH_RON in flags else "got hit by",
                            object="an early ron" if Flags.GAME_ENDED_WITH_RON in flags else "an early tsumo",
                            content=f"by {relative_seat_name(player, winner)} on turn {turn}{tenpai_status_string(flags)}"))]

# Print if you dealt into a double ron
@injustice(require=[Flags.YOU_DEALT_INTO_DOUBLE_RON])
def you_dealt_into_double_ron(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    number = data[flags.index(Flags.YOU_DEALT_INTO_DOUBLE_RON)]["number"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            content=f"{'double' if number == 2 else 'triple'} ron"))]

# Print if you dealt into dama
@injustice(require=[Flags.YOU_DEALT_INTO_DAMA])
def dealt_into_dama(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_DAMA)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            object=f"{relative_seat_name(player, winner)}'s {score} point dama{tenpai_status_string(flags)}"))]

# Print if you dealt into ippatsu
@injustice(require=[Flags.YOU_DEALT_INTO_IPPATSU])
def dealt_into_ippatsu(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.YOU_DEALT_INTO_IPPATSU)]
    winner = win_data["seat"]
    score = win_data["score"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            object=f"{relative_seat_name(player, winner)}'s {score} point ippatsu{tenpai_status_string(flags)}"))]

# Print if someone else won with bad wait ippatsu tsumo
@injustice(require=[Flags.WINNER_HAD_BAD_WAIT, Flags.WINNER_IPPATSU_TSUMO],
            forbid=[Flags.YOU_GAINED_POINTS])
def someone_got_bad_wait_ippatsu_tsumo(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.WINNER_HAD_BAD_WAIT)]
    winner = win_data["seat"]
    wait = win_data["wait"]
    ukeire = win_data["ukeire"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject=relative_seat_name(player, winner),
                            verb="got",
                            object=f"ippatsu tsumo with a bad wait {ph(wait)} ({ukeire} outs)"))]

# Print if you are dealer and lost to baiman+ tsumo
@injustice(require=[Flags.YOU_ARE_DEALER, Flags.GAME_ENDED_WITH_TSUMO, Flags.YOU_LOST_POINTS, Flags.WINNER_GOT_BAIMAN])
def baiman_oyakaburi(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    win_data = data[flags.index(Flags.WINNER)]
    winner = win_data["seat"]
    furiten_string = ", while in furiten" if Flags.WINNER_WAS_FURITEN else ""
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you", verb="were", object="dealer")),
            Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject=relative_seat_name(player, winner),
                            verb="got",
                            object="a baiman tsumo{furiten_string}"))]

# Print if your riichi/tenpai tile dealt in
@injustice(require=[Flags.YOUR_TENPAI_TILE_DEALT_IN])
def your_tenpai_tile_dealt_in(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOUR_TENPAI_TILE_DEALT_IN)]["tile"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="declared riichi with" if Flags.YOU_DECLARED_RIICHI in flags else "reached tenpai by discarding",
                            content=f"{pt(tile)}")),
            Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you", verb="immediately dealt in"))]

# Print if you drew a tile that would have completed a past wait
@injustice(require=[Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE])
def drew_tile_completing_past_wait(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile_data = data[flags.index(Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE)]
    tile = tile_data["tile"]
    wait = tile_data["wait"]
    shanten = tile_data["shanten"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="drew",
                            content=f"a tile {pt(tile)} that would have completed your past tenpai wait on {ph(wait)}"
                                    f" if you didn't decide to switch to a {shanten_name(shanten)}"))]

# Print if you dealt in while tenpai, right before you would have received tenpai payments
@injustice(require=[Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT])
def you_JUST_dealt_in_before_noten_payment(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT)]["tile"]
    tenpai_string = "in riichi" if Flags.YOU_DECLARED_RIICHI in flags else "tenpai"
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were",
                            content=f"{tenpai_string} and about to get noten payments, but then dealt in with {pt(tile)}"))]

# Print if you dealt into ura 3 OR if someone else tsumoed and got ura 3
@injustice(require=[Flags.WINNER_GOT_URA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_ura_3(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    value = data[flags.index(Flags.WINNER_GOT_URA_3)]["value"]
    seat = data[flags.index(Flags.WINNER_GOT_URA_3)]["seat"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            object=f"{relative_seat_name(player, seat)}'s hand with ura {value}{tenpai_status_string(flags)}"))]
    else:
        return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="got hit by",
                            object=f"{relative_seat_name(player, seat)}'s tsumo with ura {value}"))]

# Print if you dealt into haitei/houtei
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS])
def dealt_into_haitei(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_HAITEI)]["seat"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            object=f"{relative_seat_name(player, seat)}'s houtei{tenpai_status_string(flags)}"))]

# Print if winner drew haitei or got houtei, while you were in tenpai
@injustice(require=[Flags.WINNER_GOT_HAITEI, Flags.YOU_REACHED_TENPAI], forbid=[Flags.YOU_GAINED_POINTS, Flags.YOU_DEALT_IN])
def winner_haitei_while_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    haitei_data = data[flags.index(Flags.WINNER_GOT_HAITEI)]
    seat = haitei_data["seat"]
    name = haitei_data["yaku"]
    dealer_string = " as dealer" if Flags.YOU_ARE_DEALER in flags else ""
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject=relative_seat_name(player, seat),
                            verb="drew" if name == "haitei" else "got",
                            object=f"{name}, while you were tenpai{dealer_string}"))]

# Print if winner had 3+ han from dora tiles in the hidden part of hand
@injustice(require=[Flags.WINNER_GOT_HIDDEN_DORA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_hidden_dora_3(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    seat = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["seat"]
    value = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["value"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="dealt into",
                            object=f"{relative_seat_name(player, seat)}'s hand with {value} hidden dora{tenpai_status_string(flags)}"))]
    else:
        return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="got hit by",
                            object=f"{relative_seat_name(player, seat)}'s tsumo with {value} hidden dora"))]

# Print if an early abortive draw happened with an iishanten haipai
@injustice(require=[Flags.IISHANTEN_HAIPAI_ABORTED])
def iishanten_haipai_aborted(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    draw_name = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["draw_name"]
    shanten = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["shanten"]
    hand = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["hand"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="a {draw_name}",
                            verb="happened",
                            content=f"when you had a great hand {ph(hand)} ({shanten_name(shanten)})",
                            last_subject="you"))]

# Print if you reached yakuman tenpai but did not win
@injustice(require=[Flags.YOU_REACHED_YAKUMAN_TENPAI],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_RONNED_SOMEONE, Flags.YOU_TSUMOED])
def you_reached_yakuman_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    yakuman_types = data[flags.index(Flags.YOU_REACHED_YAKUMAN_TENPAI)]["types"]
    yakuman_waits = data[flags.index(Flags.YOU_REACHED_YAKUMAN_TENPAI)]["waits"]
    what_happened = "you didn't win"
    last_subject = "you"
    if Flags.GAME_ENDED_WITH_RON in flags:
        rons = data[flags.index(Flags.GAME_ENDED_WITH_RON)]["objects"]
        score = sum(ron.score.to_points() for ron in rons)
        winner = rons[0].winner
        won_from = rons[0].won_from
        if won_from == player:
            what_happened = f"then you dealt into {relative_seat_name(player, winner)} for {score}"
        else:
            what_happened = f"then {relative_seat_name(player, won_from)} dealt into {relative_seat_name(player, winner)} for {score}"
            last_subject = relative_seat_name(player, won_from)
    elif Flags.GAME_ENDED_WITH_TSUMO in flags:
        tsumo = data[flags.index(Flags.GAME_ENDED_WITH_TSUMO)]["object"]
        what_happened = f"then {relative_seat_name(player, tsumo.winner)} just had to tsumo"
        last_subject = relative_seat_name(player, tsumo.winner)
    elif Flags.GAME_ENDED_WITH_ABORTIVE_DRAW in flags:
        draw_name = data[flags.index(Flags.GAME_ENDED_WITH_ABORTIVE_DRAW)]["object"].name
        if draw_name == "ryuukyoku":
            what_happened = f"you never got it"
        else:
            what_happened = f"then someone ended the game with {draw_name}"
            last_subject = "someone"
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="reached",
                            content=f"{' and '.join(yakuman_types)} tenpai, but {what_happened}",
                            last_subject=last_subject))]

# Print if you got head bumped (or you skipped your ron)
@injustice(require=[Flags.YOU_WAITED_ON_WINNING_TILE, Flags.GAME_ENDED_WITH_RON],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS])
def you_got_head_bumped(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    tile = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["tile"]
    wait = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["wait"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were",
                            content=f"tenpai waiting on {ph(wait)} but then got head bumped"))]

# Print if someone else's below-mangan win destroyed your mangan+ tenpai
@injustice(require=[Flags.YOU_HAD_LIMIT_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS,
                    Flags.GAME_ENDED_WITH_RYUUKYOKU, Flags.WINNER_GOT_MANGAN])
def your_mangan_tenpai_destroyed(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    hand_str = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["hand_str"]
    yaku_str = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["yaku_str"]
    limit_name = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["limit_name"]
    han = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["han"]
    fu = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["fu"]
    score = data[flags.index(Flags.WINNER)]["score"]
    winner = data[flags.index(Flags.WINNER)]["seat"]

    # it's injustice if haneman+ OR if your mangan lost to something below 3900
    if han > 5 or score < 3900:
        fu_string = f", {fu} fu" if han < 5 else "" # need to show fu if 3 or 4 han
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject="your hand",
                                subject_description=hand_str,
                                verb="could have had",
                                content=f"{limit_name} ({yaku_str}{fu_string}) but {relative_seat_name(player, winner)} just had to score a {score} point hand",
                                last_subject=relative_seat_name(player, winner)))]
    else:
        return []

# Print if you were fourth started with 3 dora but someone else won
@injustice(require=[Flags.STARTED_WITH_3_DORA, Flags.YOU_WERE_FOURTH, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def couldnt_avoid_last_with_3_dora(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    num_dora = data[flags.index(Flags.STARTED_WITH_3_DORA)]["num"]
    winner = data[flags.index(Flags.WINNER)]["seat"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="were",
                            content=f"in fourth place and had a chance to come back with three dora,"
                                    f" but you couldn't since {relative_seat_name(player, winner)} won"))]

# Print if someone took your points and you dropped placement only because of ura
@injustice(require=[Flags.FINAL_ROUND, Flags.YOU_DEALT_IN, Flags.YOU_DROPPED_PLACEMENT, Flags.WINNER],
            forbid=[])
def dropped_placement_due_to_ura(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    score: Score = data[flags.index(Flags.WINNER)]["score_object"]
    winner: int = data[flags.index(Flags.WINNER)]["seat"]
    prev_scores: List[int] = data[flags.index(Flags.YOU_DROPPED_PLACEMENT)]["prev_scores"]
    old_placement: int = data[flags.index(Flags.YOU_DROPPED_PLACEMENT)]["old"]
    new_placement: int = data[flags.index(Flags.YOU_DROPPED_PLACEMENT)]["new"]
    ura = score.count_ura()
    if ura > 0:
        # check if placement would have stayed constant had there been no ura
        orig_placement = to_placement(prev_scores)
        orig_points = score.to_points()
        score.add_dora("ura", -ura)
        uraless_placement = apply_delta_scores(prev_scores, score.to_score_deltas(round_number, honba, [winner], player))
        uraless_points = score.to_points()
        score.add_dora("ura", ura)
        if orig_placement == uraless_placement:
            return [Injustice(round_number, honba, "Injustice",
                    InjusticeClause(subject="you",
                                    verb="dropped from",
                                    content=f"{PLACEMENTS[old_placement]} to {PLACEMENTS[new_placement]},"
                                            f" which only happened because {relative_seat_name(player, winner)} got ura {ura},"
                                            f" pushing their point gain from {uraless_points} to {orig_points}",
                                    last_subject=relative_seat_name(player, winner)))]
    return []

# Print if your good 4+ sided wait lost to someone else's worse wait
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def four_sided_wait_didnt_win(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    for i, flag in reversed(list(enumerate(flags))):
        if flag == Flags.YOU_REACHED_TENPAI:
            wait = data[i]["wait"]
            ukeire = data[i]["ukeire"]
            winner = data[flags.index(Flags.WINNER)]["seat"]
            winner_wait = data[flags.index(Flags.WINNER)]["wait"]
            winner_ukeire = data[flags.index(Flags.WINNER)]["ukeire"]
            if len(wait) >= 4 and ukeire >= 8 and len(winner_wait) < 4 and winner_ukeire < ukeire:
                return [Injustice(round_number, honba, "Injustice",
                        InjusticeClause(subject=f"your {len(wait)}-sided wait",
                                        subject_description=f"{ph(wait)} ({ukeire} outs)",
                                        verb="lost to",
                                        content=f"{relative_seat_name(player, winner)}'s"
                                                f"{len(winner_wait)}-sided wait"
                                                f"{ph(winner_wait)} ({winner_ukeire} outs)"))]
    return []

# Print if you dealt into chankan while tenpai
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def dealt_into_chankan_while_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    yaku = data[flags.index(Flags.WINNER)]["score_object"].yaku
    if ("chankan", 1) in yaku:
        return [Injustice(round_number, honba, "Injustice",
                InjusticeClause(subject="you",
                                verb="kanned",
                                content="and dealt in while tenpai"))]
    else:
        return []

# Print if you had an early 8 outs ryanmen (or better) and never folded, but never won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.FIRST_ROW_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS, Flags.YOU_FOLDED_FROM_TENPAI])
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.FIRST_ROW_TENPAI, Flags.GAME_ENDED_WITH_RYUUKYOKU],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI])
def your_early_8_outs_wait_never_won(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    for i, flag in enumerate(flags):
        if flag == Flags.YOU_REACHED_TENPAI:
            ukeire = data[i]["ukeire"]
            if ukeire >= 8:
                return [Injustice(round_number, honba, "Injustice",
                        InjusticeClause(subject="you",
                                        verb="had",
                                        object=f"an early {ukeire} outs wait",
                                        content="but never won with it"))]
    return []

@injustice(require=[Flags.SIX_DISCARDS_TSUMOGIRI_HONOR],
            forbid=[])
def you_tsumogiri_honors_6_times(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    num_discards = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_DISCARDS_TSUMOGIRI_HONOR)]["num_discards"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="drew",
                            content=f"and had to discard honors {num_discards} times in a row"))]

@injustice(require=[Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI],
            forbid=[])
def you_tsumogiri_6_times_without_tenpai(flags: List[Flags], data: List[Dict[str, Any]], round_number: int, honba: int, player: int) -> List[Injustice]:
    num_discards = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI)]["num_discards"]
    return [Injustice(round_number, honba, "Injustice",
            InjusticeClause(subject="you",
                            verb="drew",
                            content=f"what you discarded {num_discards} times in a row while not in tenpai"))]
