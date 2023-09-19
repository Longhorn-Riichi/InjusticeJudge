from .classes2 import Kyoku, Ron, Score, Tsumo
from .constants import PLACEMENTS, SHANTEN_NAMES
from dataclasses import dataclass
from enum import Enum
from typing import *
from .display import ph, pt, relative_seat_name, round_name, shanten_name
from .flags import Flags, determine_flags
from .utils import apply_delta_scores, to_placement
from pprint import pprint

# This file provides `evaluate_game`, which is called by `__init__.py`
#   after it fetches a list of kyoku. It first generates facts about the kyoku
#   via `determine_flags` from `flags.py`. It then calls every check
#   function (defined at the end of the file) that satisfies said flags,
#   generating a list of `CheckResult` objects. These `CheckResult`s are then
#   formatted as a string and returned to `__init__.py`.
#   
# See `evaluate_game` for more info.

@dataclass(frozen=True)
class CheckClause:
    # ad-hoc object used for joining two injustices with better grammar
    # extremely subject to change
    subject: str
    verb: str
    object: Optional[str] = None
    content: Optional[str] = None
    subject_description: Optional[str] = None
    last_subject: Optional[str] = None

@dataclass(frozen=True)
class CheckResult:
    # superclass of Injustice and Skill
    round: int
    honba: int
    name: str
    clause: CheckClause

@dataclass(frozen=True)
class Injustice(CheckResult):
    pass
@dataclass(frozen=True)
class Skill(CheckResult):
    pass

def evaluate_game(kyoku: Kyoku, players: Set[int], player_names: List[str], look_for: Set[str] = {"injustice"}) -> List[str]:
    """
    Run each injustice function (defined below this function) against a parsed kyoku.
    Relevant injustice functions should return a list of Injustice objects each.
    The return value is either a single-element list containing the final formatted
        injustice string, or an empty list if there were no injustices.
    """
    global checks

    # # skip all checks if we won this round
    # if kyoku.result[0] in {"ron", "tsumo"}:
    #     for result in kyoku.result[1:]:
    #         if result.winner == player:
    #             return []

    # calculate flags for our player this round
    flags, data = determine_flags(kyoku)

    # go through all the injustices and see if they apply
    # collect the resulting CheckResult objects in all_results
    all_results: Dict[int, List[CheckResult]] = {}
    for player in players:
        all_results[player] = []
        for check in checks:
            if check["type"] in look_for:
                if     all(flag in flags[player]     for flag in check["required_flags"]) \
                   and all(flag not in flags[player] for flag in check["forbidden_flags"]):
                    result = check["callback"](flags[player], data[player], kyoku, player)
                    all_results[player].extend(result)
                else:
                    pass
                    # print("player", player, "|",
                    #       round_name(kyoku.round, kyoku.honba), "|",
                    #       i["callback"].__name__, "was not called because it lacks the flag(s)",
                    #       set(i["required_flags"]) - set(flags[player]),
                    #       "and/or has the flag(s)",
                    #       set(i["forbidden_flags"]) & set(flags[player]))

    # `all_results[seat]` contains a list of injustices for this kyoku,
    #   but we need to group them up before we print.
    # This outputs a header like "- Injustice detected in **East 1**:"
    #   followed by `injustice.desc` joined by ", and"
    #   for every injustice in all_results
    rets = []
    for seat, result_list in all_results.items():
        if len(result_list) > 0:
            # get the name of the longest name out of all the injustices
            longest_name_length = max(len(r.name) for r in result_list)
            longest_name = next(r.name for r in result_list if len(r.name) == longest_name_length)
            verb_str = f"shown by **{player_names[seat]}**" \
                       if any(isinstance(r, Skill) for r in result_list) else \
                       f"detected for **{player_names[seat]}**" \
                       if len(all_results) > 1 else \
                       "detected"

            # assemble the header
            header = f"- {longest_name} {verb_str} in **{round_name(result_list[0].round, result_list[0].honba)}**:"
            # now print the subject of the first injustice clause followed by content
            # whenever the subject of the next clause is the same as the subject of the previous clause,
            # we omit the subject and just write ", and <content>"
            # return a list containing a single string
            ret = header
            last_clause = None
            seen_results: Set[Tuple[str, str, str]] = set() # (subject, content)
            for result in result_list:
                clause = result.clause
                # skip things we've already said
                if (clause.subject, clause.object, clause.content) in seen_results:
                    continue
                seen_results.add((clause.subject, clause.verb, clause.object))

                # add ", and" unless it's the first clause
                if last_clause is not None:
                    ret += ", and"
                else:
                    last_clause = CheckClause(subject="",verb="")

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
            rets.append(ret)
    return rets

###
### injustice definitions
###

# each injustice function takes two lists of flags: `require` and `forbid`
# the main `evaluate_injustices` function above calls an injustice function
#   only if all `require` flags exist and no `forbid` flags exist, for each kyoku
# see below for usage

checks: List[Dict[str, Any]] = []
CheckFunc = Callable[[List[Flags], List[Dict[str, Any]], Kyoku, int], List[Injustice]]
def make_check_decorator(check_type: str) -> Callable:
    def check_decorator(require: List[Flags] = [], forbid: List[Flags] = []) -> Callable[[CheckFunc], CheckFunc]:
        global checks
        def decorator(callback):
            checks.append({"type": check_type, "callback": callback, "required_flags": require, "forbidden_flags": forbid})
            return callback
        return decorator
    return check_decorator
injustice = make_check_decorator("injustice")
skill = make_check_decorator("skill")

###
### early game skills
###

@skill(require=[Flags.YOU_WON, Flags.WINNER_GOT_DOUBLE_WIND])
def started_with_double_wind(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.YOU_WON)]["hand"]
    haipai = kyoku.haipai[player]
    wind = [41,42,43,44][player]
    starting_winds = haipai.tiles.count(wind)
    if starting_winds == 2:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="won",
                            content=f"after starting with your double wind {ph((wind,wind), doras=kyoku.starting_doras)} and calling it"))]
    elif starting_winds == 3:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="won",
                            content=f"after starting with a triplet of your double wind {ph((wind,wind,wind), doras=kyoku.starting_doras)}"))]
    elif starting_winds == 4:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="won",
                            content=f"after starting with four of your double winds {ph((wind,wind,wind,wind), doras=kyoku.starting_doras)}"))]
    else:
        return []

@skill(require=[Flags.IISHANTEN_START])
def iishanten_start(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.IISHANTEN_START)]["hand"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="started with",
                        content=f"{shanten_name(hand.shanten)} ({hand.to_str(doras=kyoku.doras)})"))]

@skill(require=[Flags.YOU_WON, Flags.FIVE_SHANTEN_START])
def won_with_five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.FIVE_SHANTEN_START)]["hand"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="won",
                        content=f"despite starting at {shanten_name(hand.shanten)} ({hand.to_str(doras=kyoku.doras)})"))]

# Print if you started with 3 dora and won with 3 dora
@skill(require=[Flags.STARTED_WITH_3_DORA, Flags.YOU_WON])
def won_with_3_starting_dora(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    num_dora = data[flags.index(Flags.YOU_WON)]["score_object"].count_dora()
    starting_dora = sorted(tile for tile in kyoku.haipai[player].tiles if tile in kyoku.starting_doras)
    ending_dora = sorted(tile for tile in kyoku.hands[player].tiles if tile in kyoku.doras)
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="started with",
                        content=f"at least 3 dora ({ph(starting_dora)}), and won with {num_dora} dora ({ph(ending_dora)})"))]

###
### mid game skills
###

@skill(require=[Flags.EVERYONE_RESPECTED_YOUR_RIICHI, Flags.GAME_ENDED_WITH_RYUUKYOKU, Flags.YOU_GAINED_POINTS])
def everyone_respected_your_riichi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    points = data[flags.index(Flags.YOU_GAINED_POINTS)]["amount"]
    if points == 3000: # TODO depends on ruleset?
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="declared",
                            content=f"riichi and everyone respected it and paid you noten payments"))]
    else:
        return []

@skill(require=[Flags.PASSED_FOUR_DANGEROUS_DISCARDS],
        forbid=[Flags.YOU_DEALT_IN])
def you_passed_four_dangerous_discards(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    discards = data[len(flags) - 1 - flags[::-1].index(Flags.PASSED_FOUR_DANGEROUS_DISCARDS)]["discards"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="dealt",
                        content=f"{len(discards)} dangerous discards ({ph(discards, doras=kyoku.doras)}) after riichi without dealing in"))]

@skill(require=[Flags.YOU_REACHED_TENPAI])
def every_draw_helped(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    turn = data[flags.index(Flags.YOU_REACHED_TENPAI)]["turn"]
    haipai = data[flags.index(Flags.YOU_REACHED_TENPAI)]["haipai"]
    if haipai.shanten[0] == turn:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="wasted",
                            content=f"no draws in reaching tenpai (every draw improved your shanten)"))]
    else:
        return []

# Print if you ever called kan and got 4 dora
@skill(require=[Flags.YOU_FLIPPED_DORA_BOMB])
def called_kan_and_got_4_dora(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    doras = data[flags.index(Flags.YOU_FLIPPED_DORA_BOMB)]["doras"]
    call = data[flags.index(Flags.YOU_FLIPPED_DORA_BOMB)]["call"]
    hand = data[flags.index(Flags.YOU_FLIPPED_DORA_BOMB)]["hand"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="your kan call",
                        subject_description=call.to_str(doras=doras),
                        verb="gave you",
                        content=f"four dora {pt(doras[-1]+100)} in hand ({hand.to_str(doras=doras)})"))]

# Print if you melded consecutively 2+ times and then immediately won
@skill(require=[Flags.YOU_WON, Flags.WINNER_WON_WITH_PON_PON_RON])
def won_by_pon_pon_ron(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.WINNER_WON_WITH_PON_PON_RON)]["hand"]
    winning_tile = data[flags.index(Flags.WINNER_WON_WITH_PON_PON_RON)]["winning_tile"]
    num_calls = data[flags.index(Flags.WINNER_WON_WITH_PON_PON_RON)]["num_calls"]
    call_str = "\u2007".join(map(lambda call: call.to_str(doras=kyoku.doras), hand.ordered_calls[-num_calls:]))
    win_str = "tsumo" if Flags.GAME_ENDED_WITH_TSUMO in flags else "ron"
    tile_str = pt(winning_tile + 100 if winning_tile in kyoku.doras else winning_tile)
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="won by",
                        content=f"consecutively calling {call_str} and then immediately calling {win_str} on {tile_str}"))]

###
### end game skills
###

@skill(require=[Flags.YOU_WON, Flags.WINNER, Flags.GAME_ENDED_WITH_RON, Flags.SOMEONE_WAITED_ON_WINNING_TILE],
        forbid=[])
def head_bumped_someone(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    waiters = {data[i]["seat"] for i, flag in enumerate(flags) if flag == Flags.SOMEONE_WAITED_ON_WINNING_TILE}
    winners = {data[i]["seat"] for i, flag in enumerate(flags) if flag == Flags.WINNER}
    folders = {data[i]["seat"] for i, flag in enumerate(flags) if flag == Flags.SOMEONE_FOLDED_FROM_TENPAI}
    yakuless = {data[i]["seat"] for i, flag in enumerate(flags) if flag == Flags.SOMEONES_YAKULESS_HAND_COULD_HAVE_WON}
    furitens = {data[i]["seat"] for i, flag in enumerate(flags) if flag == Flags.SOMEONES_FURITEN_HAND_COULD_HAVE_WON}
    got_head_bumped = waiters - (winners - folders - yakuless - furitens)
    if len(got_head_bumped) >= 1:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="head bumped",
                            content=" and ".join(relative_seat_name(player, seat) for seat in got_head_bumped)))]
    else:
        return []

@skill(require=[Flags.YOU_WON_AFTER_SOMEONES_RIICHI],
        forbid=[Flags.YOU_WON_OFF_TENPAI_TILE])
def robbed_riichi_stick(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    seat = data[flags.index(Flags.YOU_WON_AFTER_SOMEONES_RIICHI)]["seat"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="robbed",
                        content=f"{relative_seat_name(player, seat)}'s riichi stick by winning right after they declared riichi"))]

@skill(require=[Flags.YOU_ACHIEVED_NAGASHI])
def won_nagashi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="got",
                        content="nagashi mangan"))]

@skill(require=[Flags.YOU_WON])
def won_something_silly(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    ukeire = data[flags.index(Flags.YOU_WON)]["ukeire"]
    turn = data[flags.index(Flags.YOU_WON)]["turn"]
    score = data[flags.index(Flags.YOU_WON)]["score_object"]
    winning_tile = data[flags.index(Flags.YOU_WON)]["winning_tile"]

    won_hell_wait = ukeire == 1
    silly_yaku = {("rinshan", 1),
                  ("chankan", 1),
                  ("haitei", 1),
                  ("houtei", 1),
                  ("sankantsu", 2),
                  ("ryanpeikou", 3),
                  ("sanshoku doukou", 2),
                  ("double riichi", 1)}
    win_string = "with a " + " ".join(y[0] for y in silly_yaku if y in score.yaku)
    if win_string == "with a ":
        win_string = "with a"
    for yaku, han in score.yaku:
        if han >= 3 and yaku.startswith("ura"):
            if win_string == "with a":
                win_string = "with an"
            win_string += f" ura {han}"
        elif turn <= 6 and yaku == "chinitsu":
            win_string += " first row chinitsu"
    if ("ippatsu", 1) in score.yaku and ("tsumo", 1) in score.yaku:
        if win_string == "with a":
            win_string = "with an"
        win_string += " ippatsu tsumo"
    if won_hell_wait:
        win_string += f" hell wait on {pt(winning_tile + 100 if winning_tile in kyoku.doras else winning_tile)}"
    else:
        win_string += " hand"

    if win_string != "with a hand":
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="won",
                            content=win_string))]
    else:
        return []

@skill(require=[Flags.YOU_WON, Flags.WINNER_WON_AFTER_CHANGING_WAIT])
def won_after_changing_wait(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.WINNER_WON_AFTER_CHANGING_WAIT)]["hand"]
    winning_tile = data[flags.index(Flags.WINNER_WON_AFTER_CHANGING_WAIT)]["winning_tile"]
    doras = data[flags.index(Flags.WINNER_WON_AFTER_CHANGING_WAIT)]["doras"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
        CheckClause(subject="you",
                    verb="changed your hand's wait from",
                    content=f"{ph(hand.prev_shanten[1], doras=doras)} to {ph(hand.shanten[1], doras=doras)} and immediately won on {pt(winning_tile + 100 if winning_tile in doras else winning_tile)}"))]

@skill(require=[Flags.YOU_WON, Flags.YOU_ARE_DEALER, Flags.YOU_WERE_FIRST])
def won_first_place_3_honba(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    points = data[flags.index(Flags.YOU_WON)]["score_object"].to_points()
    if kyoku.honba >= 3:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="you",
                            verb="won",
                            content=f"a {points} point hand as first place dealer with {kyoku.honba} honba"))]
    else:
        return []

@skill(require=[Flags.YOU_WON, Flags.WINNER_HAD_NAKED_TANKI])
def won_with_naked_tanki(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="won",
                        content=f"with a naked tanki wait"))]

@skill(require=[Flags.LAST_DRAW_TENPAI, Flags.GAME_ENDED_WITH_RYUUKYOKU, Flags.YOU_GAINED_POINTS])
def last_draw_tenpai(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    return [Skill(kyoku.round, kyoku.honba, "Skill",
        CheckClause(subject="your very last draw",
                    verb="gave",
                    content="you tenpai, and you received noten payments for it"))]

@skill(require=[Flags.YOU_CHASED, Flags.YOU_RONNED_SOMEONE, Flags.WINNER_GOT_IPPATSU])
def won_chase_with_ippatsu(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    chased_player = data[flags.index(Flags.YOU_CHASED)]["seat"]
    deal_in_player = data[flags.index(Flags.YOU_RONNED_SOMEONE)]["from"]
    if chased_player == deal_in_player:
        return [Skill(kyoku.round, kyoku.honba, "Major skill",
            CheckClause(subject="you",
                        verb="chased",
                        content=f"{relative_seat_name(player, chased_player)}'s tenpai and they immediately dealt into you with ippatsu"))]
    else:
        return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="got",
                        content=f"ippatsu after chasing {relative_seat_name(player, chased_player)}'s tenpai"))]

@skill(require=[Flags.YOU_GAINED_POINTS, Flags.WINNER_GOT_SANBAIMAN])
def got_sanbaiman_or_yakuman(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    score = data[flags.index(Flags.WINNER_GOT_SANBAIMAN)]["score_object"]
    yaku = score.yaku
    limit_name = score.get_limit_hand_name()
    return [Skill(kyoku.round, kyoku.honba, "Skill",
        CheckClause(subject="you",
                    verb="got",
                    content=f"{limit_name} ({', '.join(y for y, _ in yaku)})"))]

# Print if you gained placement only because of ura
@skill(require=[Flags.YOU_WON, Flags.YOU_GAINED_PLACEMENT],
        forbid=[])
def gained_placement_due_to_ura(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    score: Score = data[flags.index(Flags.YOU_WON)]["score_object"]
    won_from: int = data[flags.index(Flags.YOU_WON)]["won_from"]
    prev_scores: List[int] = data[flags.index(Flags.YOU_GAINED_PLACEMENT)]["prev_scores"]
    old_placement: int = data[flags.index(Flags.YOU_GAINED_PLACEMENT)]["old"]
    new_placement: int = data[flags.index(Flags.YOU_GAINED_PLACEMENT)]["new"]
    ura = score.count_ura()
    if ura > 0:
        # check if placement would have stayed constant had there been no ura
        orig_placement = to_placement(prev_scores)
        orig_points = score.to_points()
        score.add_dora("ura", -ura)
        uraless_placement = apply_delta_scores(prev_scores, score.to_score_deltas(kyoku.round, kyoku.honba, [player], won_from))
        uraless_points = score.to_points()
        score.add_dora("ura", ura)
        if orig_placement == uraless_placement:
            return [Skill(kyoku.round, kyoku.honba, "Injustice",
                    CheckClause(subject="you",
                                verb="went from",
                                content=f"{PLACEMENTS[old_placement]} to {PLACEMENTS[new_placement]},"
                                        f" which only happened because you got ura {ura},"
                                        f" pushing your point gain from {uraless_points} to {orig_points}",
                                last_subject=""))]
    return []

@skill(require=[Flags.SOMEONE_HAS_THREE_DORA_VISIBLE, Flags.YOU_WON])
def won_to_deny_three_dora(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    dora_data = {data[i]["seat"]: data[i] for i, flag in enumerate(flags) if flag == Flags.SOMEONE_HAS_THREE_DORA_VISIBLE}
    if player in dora_data.keys():
        del dora_data[player]
    seats = set(dora_data.keys())
    num_dora_shown = sum(d["amount"] for d in dora_data.values())
    if len(seats) >= 1:
        player_str = " and ".join(map(lambda seat: relative_seat_name(player, seat), seats))
        were_str = "were collectively" if "and" in player_str else "were"
        return [Skill(kyoku.round, kyoku.honba, "Skill",
                CheckClause(subject="your win",
                            verb="denied",
                            content=f"{player_str} from getting the {num_dora_shown} dora they {were_str} showing on the table"))]
    else:
        return []

###
### final round skills
###

# Print if you got out of last place in the final round
@skill(require=[Flags.FINAL_ROUND, Flags.YOU_WERE_FOURTH, Flags.YOU_GAINED_PLACEMENT])
def got_out_of_last_place(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    new = data[flags.index(Flags.YOU_GAINED_PLACEMENT)]["new"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="climbed out of",
                        content=f"4th place (to {PLACEMENTS[new]}) in the final round"))]

@skill(require=[Flags.FINAL_ROUND, Flags.REACHED_DOUBLE_STARTING_POINTS],
        forbid=[Flags.REACHED_TRIPLE_STARTING_POINTS])
def ended_with_double_starting_points(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    points = data[flags.index(Flags.REACHED_DOUBLE_STARTING_POINTS)]["points"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="ended",
                        content=f"the game with double starting points ({points})"))]

@skill(require=[Flags.FINAL_ROUND, Flags.REACHED_TRIPLE_STARTING_POINTS])
def ended_with_triple_starting_points(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    points = data[flags.index(Flags.REACHED_DOUBLE_STARTING_POINTS)]["points"]
    return [Skill(kyoku.round, kyoku.honba, "Skill",
            CheckClause(subject="you",
                        verb="ended",
                        content=f"the game with triple starting points ({points})"))]

###
### early game injustices
###

# Print if you started with atrocious shanten and couldn't gain points as a result
@injustice(require=[Flags.DREW_WORST_HAIPAI_SHANTEN],
            forbid=[Flags.YOU_GAINED_POINTS])
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_GAINED_POINTS, Flags.DREW_WORST_HAIPAI_SHANTEN])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    shanten: Tuple[int, List[int]]
    if Flags.FIVE_SHANTEN_START in flags:
        shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["hand"].shanten
    elif Flags.DREW_WORST_HAIPAI_SHANTEN in flags:
        shanten = data[flags.index(Flags.DREW_WORST_HAIPAI_SHANTEN)]["shanten"]
        second_worst_shanten: int = data[flags.index(Flags.DREW_WORST_HAIPAI_SHANTEN)]["second_worst_shanten"]
        difference = (shanten[0]//1) - second_worst_shanten
        if difference >= 2:
            return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                    CheckClause(subject=f"you",
                                    verb=f"started with",
                                    content=f"{shanten_name(shanten)}, while everyone else started with {SHANTEN_NAMES[second_worst_shanten]} or better"))]
    if shanten[0] >= 5:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                CheckClause(subject="you",
                                verb="started with",
                                object=shanten_name(shanten)))]
    return []

# Print if you started with 7-8 types of terminals and couldn't gain points as a result
@injustice(require=[Flags.SEVEN_TERMINAL_START],
           forbid=[Flags.YOU_GAINED_POINTS])
def seven_terminal_start(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    num_types = data[flags.index(Flags.SEVEN_TERMINAL_START)]["num_types"]
    if num_types in {8,9}:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                CheckClause(subject="you",
                            verb="started with",
                            content=f"{num_types} types of terminal/honor tiles"))]
    return []

# @injustice(require=[Flags.STARTED_WITH_TWO_147_SHAPES],
#             forbid=[])
# def started_with_two_147_shapes(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
#     hand = data[flags.index(Flags.STARTED_WITH_TWO_147_SHAPES)]["hand"]
#     num = data[flags.index(Flags.STARTED_WITH_TWO_147_SHAPES)]["num"]
#     return [Injustice(kyoku.round, kyoku.honba, "Injustice",
#             CheckClause(subject="you",
#                             verb="started with",
#                             object=f"{num} 1-4-7 shapes",
#                             content=f"in your hand ({ph(hand)})"))]

# Print if you were still at bad shanten after the first row of discards and couldn't gain points as a result
@injustice(require=[Flags.FOUR_SHANTEN_AFTER_FIRST_ROW],
            forbid=[Flags.YOU_GAINED_POINTS])
def four_shanten_after_first_row(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    shanten = data[flags.index(Flags.FOUR_SHANTEN_AFTER_FIRST_ROW)]["shanten"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="were still",
                        object=shanten_name(shanten),
                        content="after the first row of discards"))]

###
### mid game injustices
###

# Print if your tenpai got chased by a worse wait, and they won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.WINNER,
                    Flags.YOU_GOT_CHASED, Flags.CHASER_GAINED_POINTS],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS])
def chaser_won_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    chasers: Dict[int, Dict[str, Any]] = {}
    for i in [i for i, f in enumerate(flags) if f == Flags.YOU_GOT_CHASED]:
        chase_data = data[i]
        chasers[chase_data["seat"]] = chase_data
    ret = []
    for chase_data in chasers.values():
        chaser_seat = chase_data["seat"]
        chaser_wait = chase_data["hand"].shanten[1]
        chaser_ukeire = chase_data["ukeire"]
        your_seat = chase_data["your_seat"]
        your_wait = chase_data["your_hand"].shanten[1]
        your_ukeire = chase_data["your_ukeire"]
        try:
            winner_seat = data[i+flags[i:].index(Flags.CHASER_GAINED_POINTS)]["seat"]
        except ValueError:
            continue
        if chaser_seat != winner_seat or chaser_ukeire >= your_ukeire:
            continue
        ret.append(Injustice(kyoku.round, kyoku.honba, "Injustice",
                   CheckClause(subject="your wait",
                               subject_description=f"{ph(your_wait, kyoku.doras)} ({your_ukeire} out{'s' if your_ukeire > 1 else ''})",
                               verb="was chased by",
                               object=f"{relative_seat_name(your_seat, chaser_seat)}"
                                           f" with a worse wait {ph(chaser_wait, kyoku.doras)} ({chaser_ukeire} out{'s' if chaser_ukeire > 1 else ''})")))
        if Flags.YOU_LOST_POINTS in flags and Flags.GAME_ENDED_WITH_RON in flags:
            ret.append(Injustice(kyoku.round, kyoku.honba, "Major injustice",
                       CheckClause(subject="you", verb="dealt into", object="it")))
        else:
            ret.append(Injustice(kyoku.round, kyoku.honba, "Injustice",
                       CheckClause(subject="they", verb="won")))
    return ret

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    draws = shanten_data["draws"]
    shanten = shanten_data["shanten"]
    ret = []
    reached_tenpai_str = " before you finally reached tenpai" if Flags.YOU_REACHED_TENPAI in flags else ", and never reached tenpai"
    if Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI in flags:
        num_discards = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI)]["num_discards"]
        if num_discards >= 9:
            return [] # we'd be repeating the message in `you_tsumogiri_6_times_without_tenpai`
    if Flags.YOU_REACHED_TENPAI in flags:
        ret.append(Injustice(kyoku.round, kyoku.honba, "Injustice",
                   CheckClause(subject="you",
                               verb="were stuck at",
                               content=f"{shanten_name(shanten)} for {draws} draws before you finally reached tenpai")))
    else:
        ret.append(Injustice(kyoku.round, kyoku.honba, "Injustice",
                   CheckClause(subject="you",
                               verb="were stuck at",
                               content=f"{shanten_name(shanten)} for {draws} draws")))
        ret.append(Injustice(kyoku.round, kyoku.honba, "Injustice",
                   CheckClause(subject="you", verb="never reached", object="tenpai")))
    return ret

# Print if you drew a dora tile you had discarded a turn prior
@injustice(require=[Flags.IMMEDIATELY_DREW_DISCARDED_DORA],
            forbid=[])
def drew_dora_you_just_discarded(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile = data[flags.index(Flags.IMMEDIATELY_DREW_DISCARDED_DORA)]["tile"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="immediately drew",
                        content=f"a dora {pt(tile+100)} that you just discarded"))]

# Print if your turn was skipped 3 times due to pon/kan
@injustice(require=[Flags.TURN_SKIPPED_BY_PON],
            forbid=[])
def turn_was_skipped_3_times(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    times = flags.count(Flags.TURN_SKIPPED_BY_PON)
    if times >= 3:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                CheckClause(subject="your turn",
                            verb="was skipped",
                            content=f"{times} times by pon/kan"))]
    else:
        return []

# Print if you just barely failed nagashi
@injustice(require=[Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI],
            forbid=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_draw(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile = data[flags.index(Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI)]["tile"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="lost",
                        content=f"nagashi on your last discard ({pt(tile + 100 if tile in kyoku.doras else tile)})"))]

# Print if someone calls your last tile for nagashi (not ron)
@injustice(require=[Flags.YOUR_LAST_NAGASHI_TILE_CALLED])
def lost_nagashi_to_call(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    nagashi_data = data[flags.index(Flags.YOUR_LAST_NAGASHI_TILE_CALLED)]
    tile = nagashi_data["tile"]
    caller = nagashi_data["caller"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="lost",
                        content=f"nagashi on your last discard {pt(tile + 100 if tile in kyoku.doras else tile)} because {relative_seat_name(player, caller)} called it"))]

# Print if ankan removed (part of) your tenpai wait
@injustice(require=[Flags.ANKAN_ERASED_TENPAI_WAIT])
def ankan_erased_tenpai_wait(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["tile"]
    wait = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["wait"]
    ukeire = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["ukeire"]
    caller = data[flags.index(Flags.ANKAN_ERASED_TENPAI_WAIT)]["caller"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject=f"{relative_seat_name(player, caller)}'s ankan",
                        subject_description=ph((50,tile,tile,50), kyoku.doras),
                        verb="erased",
                        content=f"{'your entire' if ukeire <= 4 else 'part of your'} wait {ph(wait, kyoku.doras)}"))]

# Print if you tsumogiri honors 6 times in a row and are not going for nagashi
@injustice(require=[Flags.SIX_DISCARDS_TSUMOGIRI_HONOR],
            forbid=[Flags.YOU_GAINED_POINTS])
def you_tsumogiri_honors_6_times(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    num_discards = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_DISCARDS_TSUMOGIRI_HONOR)]["num_discards"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="drew",
                        content=f"and had to discard honors {num_discards} times in a row"))]

# Print if you tsumogiri 6 times in a row while not in tenpai
@injustice(require=[Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI],
            forbid=[Flags.YOU_GAINED_POINTS])
def you_tsumogiri_6_times_without_tenpai(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    num_discards = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI)]["num_discards"]
    shanten = data[len(flags) - 1 - flags[::-1].index(Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI)]["shanten"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="discarded",
                        content=f"what you drew {num_discards} times in a row while in {shanten_name(shanten)}"))]

# Print if you drew at least 6 off-suit tiles in a row for honitsu
@injustice(require=[Flags.BAD_HONITSU_DRAWS])
def consecutive_bad_honitsu_draws(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tiles = data[flags.index(Flags.BAD_HONITSU_DRAWS)]["tiles"]
    hand = data[flags.index(Flags.BAD_HONITSU_DRAWS)]["hand"]
    never_tenpai_string = ", and subsequently could not reach tenpai" if Flags.YOU_REACHED_TENPAI not in flags else ""
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="were going for",
                        content=f"honitsu {ph(hand.tiles, kyoku.doras)},"
                                f" but drew {len(tiles)} off-suit tiles ({ph(tiles, kyoku.doras)})"
                                f" in a row{never_tenpai_string}"))]

# Print if you had to deal with triple riichi
@injustice(require=[Flags.AGAINST_TRIPLE_RIICHI, Flags.YOU_DEALT_IN])
def against_triple_riichi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="were against",
                        object="a triple riichi, and dealt in"))]

# # Print if your 3-shanten start was slower than someone else's 5-shanten start
# @injustice(require=[Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN],
#            forbid=[Flags.YOU_REACHED_TENPAI])
# def your_3_shanten_slower_than_5_shanten(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
#     their_seat = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["seat"]
#     their_shanten = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["their_shanten"]
#     your_shanten = data[flags.index(Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN)]["your_shanten"]
#     if Flags.YOU_REACHED_TENPAI in flags:
#         return [Injustice(kyoku.round, kyoku.honba, "Injustice",
#                 CheckClause(subject=f"your {SHANTEN_NAMES[your_shanten]} starting hand",
#                             verb="reached tenpai after",
#                             content=f"{relative_seat_name(player, their_seat)} who started from {SHANTEN_NAMES[their_shanten]}"))]
#     else:
#         return [Injustice(kyoku.round, kyoku.honba, "Injustice",
#                 CheckClause(subject=f"your {SHANTEN_NAMES[your_shanten]} starting hand",
#                             verb="couldn't reach tenpai,",
#                             content=f"yet {relative_seat_name(player, their_seat)}'s {SHANTEN_NAMES[their_shanten]} starting hand did"))]

# Print if you were ever iishanten with zero tiles left
@injustice(require=[Flags.IISHANTEN_WITH_ZERO_TILES])
def iishanten_with_zero_tiles(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    shanten = data[flags.index(Flags.IISHANTEN_WITH_ZERO_TILES)]["shanten"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject=f"your {shanten_name(shanten)}",
                        verb="had",
                        content="zero outs at some point"))]

# Print if everyone immediately threw a dangerous tile after your riichi
@injustice(require=[Flags.EVERYONE_DISRESPECTED_YOUR_RIICHI])
def everyone_disrespected_your_riichi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="your riichi",
                        verb="was disrespected by",
                        content="everyone (they all immediately threw dangerous tiles against you)"))]

# Print if you drew a dangerous tile and had no safe tiles at least four times
@injustice(require=[Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI])
def four_dangerous_draws_after_riichi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tiles = data[len(data) - 1 - flags[::-1].index(Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI)]["tiles"]
    opponent = data[len(data) - 1 - flags[::-1].index(Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI)]["opponent"]
    pond_str = data[len(data) - 1 - flags[::-1].index(Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI)]["pond_str"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="kept drawing",
                        content=f"dangerous tile after dangerous tile ({ph(tiles, kyoku.doras)}) after"
                                    f" {relative_seat_name(player, opponent)}'s riichi"
                                    f" (their discards: {pond_str})"))]

# Print if all tiles in your hand are deal-in tiles
@injustice(require=[Flags.YOUR_TILES_ALL_DEAL_IN, Flags.YOU_DEALT_IN])
def your_tiles_all_deal_in(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand = data[flags.index(Flags.YOUR_TILES_ALL_DEAL_IN)]["hand"]
    waits = data[flags.index(Flags.YOUR_TILES_ALL_DEAL_IN)]["waits"]
    wait_string = " and ".join(f"{relative_seat_name(player, seat)} was waiting on {ph(wait, doras=kyoku.doras)}" for seat, wait in waits.items())
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="your hand",
                        subject_description=ph(hand.hidden_part, doras=kyoku.doras),
                        verb="only had",
                        content=f"tiles that would deal in ({wait_string})"))]

# Print if you had an early 8 outs ryanmen (or better) and never folded, but never won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.FIRST_ROW_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS, Flags.YOU_FOLDED_FROM_TENPAI])
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.FIRST_ROW_TENPAI],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.WINNER])
def your_early_8_outs_wait_never_won(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    for i, flag in enumerate(flags):
        if flag == Flags.YOU_REACHED_TENPAI:
            ukeire = data[i]["ukeire"]
            if ukeire >= 8:
                return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                        CheckClause(subject="you",
                                    verb="had",
                                    object=f"an early {ukeire} outs wait",
                                    content="but never won with it"))]
    return []

###
### end game injustices
###

def tenpai_status_string(flags: List[Flags]) -> str:
    status = ""
    if Flags.YOU_DECLARED_RIICHI in flags and not Flags.YOUR_TENPAI_TILE_DEALT_IN in flags:
        status = ", while you were in riichi (bye-bye riichi stick)"
    elif Flags.YOU_REACHED_TENPAI in flags:
        status = ", while you were tenpai"
    if Flags.YOU_REACHED_TENPAI in flags and Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT in flags:
        status += " and about to get noten payments"
    return status

# Print if your riichi discard passed, but someone stole your riichi stick before your next draw
@injustice(require=[Flags.LAST_DISCARD_WAS_RIICHI, Flags.WINNER],
            forbid=[Flags.YOUR_TENPAI_TILE_DEALT_IN, Flags.YOU_WON])
def riichi_stick_robbed(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    winner = data[flags.index(Flags.WINNER)]["seat"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="your riichi discard",
                        verb="passed",
                        content=f"but {relative_seat_name(player, winner)} won before your next draw, stealing your riichi stick",
                        last_subject=relative_seat_name(player, winner)))]

# Print if you lost points to a first row ron/tsumo
@injustice(require=[Flags.LOST_POINTS_TO_FIRST_ROW_WIN])
def lost_points_to_first_row_win(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    win_data = data[flags.index(Flags.LOST_POINTS_TO_FIRST_ROW_WIN)]
    winner = win_data["seat"]
    turn = win_data["turn"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="dealt into" if Flags.GAME_ENDED_WITH_RON in flags else "got hit by",
                        object="an early ron" if Flags.GAME_ENDED_WITH_RON in flags else "an early tsumo",
                        content=f"by {relative_seat_name(player, winner)} on turn {turn}{tenpai_status_string(flags)}"))]

# Print if you dealt into a double ron, dama, haitei/houtei, or ippatsu
# Or if you dealt in while tenpai, right before you would have received tenpai payments
@injustice(require=[Flags.WINNER, Flags.YOU_DEALT_IN, Flags.WINNER_WAS_DAMA])
@injustice(require=[Flags.WINNER, Flags.YOU_DEALT_IN, Flags.WINNER_GOT_IPPATSU], forbid=[Flags.WINNER_WAS_DAMA])
@injustice(require=[Flags.WINNER, Flags.YOU_DEALT_IN, Flags.WINNER_GOT_HAITEI], forbid=[Flags.WINNER_WAS_DAMA, Flags.WINNER_GOT_IPPATSU])
@injustice(require=[Flags.WINNER, Flags.YOU_DEALT_IN, Flags.MULTIPLE_RON], forbid=[Flags.WINNER_WAS_DAMA, Flags.WINNER_GOT_IPPATSU, Flags.WINNER_GOT_HAITEI])
@injustice(require=[Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT], forbid=[Flags.WINNER_WAS_DAMA, Flags.WINNER_GOT_IPPATSU, Flags.WINNER_GOT_HAITEI, Flags.MULTIPLE_RON])
def dealt_into_something_dumb(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    winner = data[flags.index(Flags.WINNER)]["seat"]
    score = data[flags.index(Flags.WINNER)]["score_object"].to_points()
    is_ippatsu = Flags.WINNER_GOT_IPPATSU in flags
    is_haitei = Flags.WINNER_GOT_HAITEI in flags
    num_rons = 1 if Flags.MULTIPLE_RON not in flags else data[flags.index(Flags.MULTIPLE_RON)]["number"]
    is_dama = flags.count(Flags.WINNER_WAS_DAMA) == num_rons
    is_ippatsu = flags.count(Flags.WINNER_GOT_IPPATSU) == num_rons

    content = ""
    if num_rons > 1:
        content += "double" if num_rons == 2 else "triple"
    else:
        content += f"{relative_seat_name(player, winner)}'s {score} point"
    if is_dama:
        content += " dama"
    if is_ippatsu:
        content += " ippatsu"
    if is_haitei:
        content += " " + data[flags.index(Flags.WINNER_GOT_HAITEI)]["yaku"]
    if not is_dama and not is_ippatsu:
        content += " ron"
    content += tenpai_status_string(flags)

    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="dealt into",
                        content=content))]

# Print if someone else won with bad wait ippatsu tsumo
@injustice(require=[Flags.WINNER_HAD_BAD_WAIT, Flags.WINNER_IPPATSU_TSUMO],
            forbid=[Flags.YOU_GAINED_POINTS])
def someone_got_bad_wait_ippatsu_tsumo(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    win_data = data[flags.index(Flags.WINNER_HAD_BAD_WAIT)]
    winner = win_data["seat"]
    wait = win_data["hand"].shanten[1]
    ukeire = win_data["ukeire"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject=relative_seat_name(player, winner),
                        verb="got",
                        object=f"ippatsu tsumo with a bad wait {ph(wait, kyoku.doras)} ({ukeire} outs)"))]

# Print if you are dealer and lost to baiman+ tsumo
@injustice(require=[Flags.YOU_ARE_DEALER, Flags.GAME_ENDED_WITH_TSUMO, Flags.YOU_LOST_POINTS, Flags.WINNER_GOT_BAIMAN])
def baiman_oyakaburi(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    win_data = data[flags.index(Flags.WINNER)]
    winner = win_data["seat"]
    furiten_string = ", while in furiten" if Flags.WINNER_WAS_FURITEN else ""
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you", verb="were", object="dealer")),
            Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject=relative_seat_name(player, winner),
                        verb="got",
                        object=f"a baiman tsumo{furiten_string}"))]

# Print if your riichi/tenpai tile dealt in
@injustice(require=[Flags.YOUR_TENPAI_TILE_DEALT_IN])
def your_tenpai_tile_dealt_in(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile = data[flags.index(Flags.YOUR_TENPAI_TILE_DEALT_IN)]["tile"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="declared riichi with" if Flags.YOU_DECLARED_RIICHI in flags else "reached tenpai by discarding",
                        content=f"{pt(tile + 100 if tile in kyoku.doras else tile)}")),
            Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you", verb="immediately dealt in"))]

# Print if you drew a tile that would have completed a past wait
@injustice(require=[Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE],
            forbid=[Flags.YOU_GAINED_POINTS])
def drew_tile_completing_past_wait(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile_data = data[flags.index(Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE)]
    tile = tile_data["tile"]
    wait = tile_data["wait"]
    shanten = tile_data["shanten"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="drew",
                        content=f"a tile {pt(tile + 100 if tile in kyoku.doras else tile)} that would have completed your past tenpai wait on {ph(wait, kyoku.doras)}"
                                    f" if you didn't decide to switch to a {shanten_name(shanten)}"))]

# Print if you dealt into ura 3 OR if someone else tsumoed and got ura 3
@injustice(require=[Flags.WINNER_GOT_URA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_ura_3(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    value = data[flags.index(Flags.WINNER_GOT_URA_3)]["value"]
    seat = data[flags.index(Flags.WINNER_GOT_URA_3)]["seat"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="dealt into",
                        object=f"{relative_seat_name(player, seat)}'s hand with ura {value}{tenpai_status_string(flags)}"))]
    else:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="got hit by",
                        object=f"{relative_seat_name(player, seat)}'s tsumo with ura {value}"))]

# Print if winner had 3+ han from dora tiles in the hidden part of hand
@injustice(require=[Flags.WINNER_GOT_HIDDEN_DORA_3, Flags.YOU_LOST_POINTS])
def lost_points_to_hidden_dora_3(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    seat = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["seat"]
    value = data[flags.index(Flags.WINNER_GOT_HIDDEN_DORA_3)]["value"]
    if Flags.GAME_ENDED_WITH_RON in flags:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="dealt into",
                        object=f"{relative_seat_name(player, seat)}'s hand with {value} hidden dora{tenpai_status_string(flags)}"))]
    else:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="got hit by",
                        object=f"{relative_seat_name(player, seat)}'s tsumo with {value} hidden dora"))]

# Print if an early abortive draw happened with an iishanten haipai
@injustice(require=[Flags.IISHANTEN_HAIPAI_ABORTED])
def iishanten_haipai_aborted(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    draw_name = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["draw_name"]
    shanten = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["shanten"]
    hand = data[flags.index(Flags.IISHANTEN_HAIPAI_ABORTED)]["hand"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="a {draw_name}",
                        verb="happened",
                        content=f"when you had a great hand {ph(hand, kyoku.doras)} ({shanten_name(shanten)})",
                        last_subject="you"))]

# Print if you reached yakuman tenpai but did not win
@injustice(require=[Flags.YOU_REACHED_YAKUMAN_TENPAI],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_RONNED_SOMEONE, Flags.YOU_TSUMOED])
def you_reached_yakuman_tenpai(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
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
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="reached",
                        content=f"{' and '.join(yakuman_types)} tenpai, but {what_happened}",
                        last_subject=last_subject))]

# Print if you got head bumped (or you skipped your ron)
@injustice(require=[Flags.YOU_WAITED_ON_WINNING_TILE, Flags.GAME_ENDED_WITH_RON, Flags.WINNER],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS])
def you_got_head_bumped(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    tile = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["tile"]
    wait = data[flags.index(Flags.YOU_WAITED_ON_WINNING_TILE)]["wait"]
    winner = data[flags.index(Flags.WINNER)]["seat"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="were",
                        content=f"tenpai waiting on {ph(wait, kyoku.doras)}, and would have won, but instead you got head bumped by {relative_seat_name(player, winner)}"))]

# Print if someone else's below-mangan win destroyed your mangan+ tenpai
@injustice(require=[Flags.YOU_HAD_LIMIT_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI, Flags.YOU_GAINED_POINTS,
                    Flags.WINNER_GOT_MANGAN])
def your_mangan_tenpai_destroyed(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    hand_str = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["hand_str"]
    yaku_str = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["yaku_str"]
    limit_name = data[len(data) - 1 - flags[::-1].index(Flags.YOU_HAD_LIMIT_TENPAI)]["limit_name"]
    han = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["han"]
    fu = data[flags.index(Flags.YOU_HAD_LIMIT_TENPAI)]["fu"]
    score = data[flags.index(Flags.WINNER)]["score_object"].to_points()
    winner = data[flags.index(Flags.WINNER)]["seat"]

    # it's injustice if haneman+ OR if your mangan lost to something below 3900
    if han > 5 or score < 3900:
        fu_string = f", {fu} fu" if han < 5 else "" # need to show fu if 3 or 4 han
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                CheckClause(subject="your hand",
                            subject_description=hand_str,
                            verb="could have had",
                            content=f"{limit_name} ({yaku_str}{fu_string}) but {relative_seat_name(player, winner)} just had to score a {score} point hand",
                            last_subject=relative_seat_name(player, winner)))]
    else:
        return []

# Print if you were fourth started with 3 dora but someone else won
@injustice(require=[Flags.STARTED_WITH_3_DORA, Flags.YOU_WERE_FOURTH, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def couldnt_avoid_last_with_3_dora(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    num_dora = data[flags.index(Flags.STARTED_WITH_3_DORA)]["num"]
    winner = data[flags.index(Flags.WINNER)]["seat"]
    return [Injustice(kyoku.round, kyoku.honba, "Injustice",
            CheckClause(subject="you",
                        verb="were",
                        content=f"in fourth place and had a chance to come back with three dora,"
                                f" but you couldn't since {relative_seat_name(player, winner)} won"))]

# Print if someone took your points and you dropped placement only because of ura
@injustice(require=[Flags.YOU_DEALT_IN, Flags.YOU_DROPPED_PLACEMENT, Flags.WINNER],
            forbid=[])
def dropped_placement_due_to_ura(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
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
        uraless_placement = apply_delta_scores(prev_scores, score.to_score_deltas(kyoku.round, kyoku.honba, [winner], player))
        uraless_points = score.to_points()
        score.add_dora("ura", ura)
        if orig_placement == uraless_placement:
            return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                    CheckClause(subject="you",
                                verb="dropped from",
                                content=f"{PLACEMENTS[old_placement]} to {PLACEMENTS[new_placement]},"
                                        f" which only happened because {relative_seat_name(player, winner)} got ura {ura},"
                                        f" pushing their point gain from {uraless_points} to {orig_points}",
                                last_subject=""))]

    return []

# Print if your good 4+ sided wait lost to someone else's worse wait
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def four_sided_wait_didnt_win(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    for i, flag in reversed(list(enumerate(flags))):
        if flag == Flags.YOU_REACHED_TENPAI:
            wait = data[i]["hand"].shanten[1]
            ukeire = data[i]["ukeire"]
            winner = data[flags.index(Flags.WINNER)]["seat"]
            winner_wait = data[flags.index(Flags.WINNER)]["hand"].shanten[1]
            winner_ukeire = data[flags.index(Flags.WINNER)]["ukeire"]
            if len(wait) >= 4 and ukeire >= 8 and len(winner_wait) < 4 and winner_ukeire < ukeire:
                return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                        CheckClause(subject=f"your {len(wait)}-sided wait",
                                    subject_description=f"{ph(wait, kyoku.doras)} ({ukeire} outs)",
                                    verb="lost to",
                                    content=f"{relative_seat_name(player, winner)}'s"
                                            f"{len(winner_wait)}-sided wait"
                                            f"{ph(winner_wait, kyoku.doras)} ({winner_ukeire} outs)"))]
    return []

# Print if you dealt into chankan while tenpai
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.WINNER],
            forbid=[Flags.YOU_GAINED_POINTS])
def dealt_into_chankan_while_tenpai(flags: List[Flags], data: List[Dict[str, Any]], kyoku: Kyoku, player: int) -> Sequence[CheckResult]:
    yaku = data[flags.index(Flags.WINNER)]["score_object"].yaku
    if ("chankan", 1) in yaku:
        return [Injustice(kyoku.round, kyoku.honba, "Injustice",
                CheckClause(subject="you",
                            verb="kanned",
                            content="and dealt in while tenpai"))]
    else:
        return []
