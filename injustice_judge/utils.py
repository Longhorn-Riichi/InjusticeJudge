import functools
import itertools
from .constants import DISCORD_TILES, DISCORD_CALLED_TILES, DISCORD_DORA_TILES, DISCORD_CALLED_DORA_TILES, PRED, SHANTEN_NAMES, SUCC, TOGGLE_RED_FIVE, TRANSLATE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, OYA_RON_SCORE, KO_RON_SCORE
from typing import *
import os

# This file contains a bunch of utility functions that don't really belong anywhere else.
# The goal is to move these someday, so they're not really documented right now.

###
### utility functions
###

LIMIT_HANDS = {2: "満貫", 3: "満貫", 4: "満貫", 5: "満貫",
               6: "跳満", 7: "跳満",
               8: "倍満", 9: "倍満", 10: "倍満",
               11: "三倍満", 12: "三倍満"}

def limit_hands(han: int) -> str:
    # maps han count to tenhou's limit hand name
    if han >= 13:
        return "役満"
    else:
        return LIMIT_HANDS[han]


def pt_unicode(tile: int) -> str:
    """print tile (2-char representation)"""
    TILE_REPRS = "🀇🀈🀉🀊🀋🀌🀍🀎🀏🀙🀚🀛🀜🀝🀞🀟🀠🀡🀐🀑🀒🀓🀔🀕🀖🀗🀘🀀🀁🀂🀃🀆🀅🀄︎"
    is_dora = tile >= 100
    if is_dora:
        tile -= 100
    ret = "??"
    if tile < 20:
        ret = TILE_REPRS[tile - 11] + " "
    elif tile < 30:
        ret = TILE_REPRS[tile - 21 + 9] + " "
    elif tile < 40:
        ret = TILE_REPRS[tile - 31 + 18] + " "
    elif tile < 47:
        ret = TILE_REPRS[tile - 41 + 27] + " "
    elif tile == 47:
        # need to specially output 🀄︎ so it's not an emoji
        ret = TILE_REPRS[-2:]
    elif tile == 50:
        ret = "🀫 "
    elif tile == 51:
        ret = "🀋·"
    elif tile == 52:
        ret = "🀝·"
    elif tile == 53:
        ret = "🀔·"
    if is_dora:
        return ret + "\u20f0" # combining asterisk
    return ret

def pt_discord(tile: int, is_sideways=False) -> str:
    if tile >= 100:
        # tile is dora
        tile -= 100
        if is_sideways:
            return DISCORD_CALLED_DORA_TILES[tile]
        else: 
            return DISCORD_DORA_TILES[tile]
    else:
        if is_sideways:
            return DISCORD_CALLED_TILES[tile]
        else: 
            return DISCORD_TILES[tile]

pt = lambda tile: pt_discord(tile) if os.getenv("use_discord_tile_emoji") == "True" else pt_unicode(tile)
pt_sideways = lambda tile: pt_discord(tile, True) if os.getenv("use_discord_tile_emoji") == "True" else f"₍{pt_unicode(tile)}₎"

def print_hand_details_seat(kyoku, seat, print_final_tile=False):
    final_tile = None if not print_final_tile else kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
    return kyoku.hands[seat].print_hand_details(
            ukeire=kyoku.final_ukeire[seat],
            final_tile=final_tile,
            furiten=kyoku.furiten[seat])

ph = lambda hand: "".join(map(pt, hand)) # print hand
remove_red_five = lambda tile: TOGGLE_RED_FIVE[tile] if tile in {51,52,53} else tile
remove_red_fives = lambda hand: map(remove_red_five, hand)
sorted_hand = lambda hand: tuple(sorted(hand, key=remove_red_five))
round_name = lambda rnd, honba: (f"East {rnd+1}" if rnd <= 3 else f"South {rnd-3}" if rnd <= 7 else f"West {rnd-7}") + ("" if honba == 0 else f"-{honba}")
short_round_name = lambda rnd, honba: (f"E{rnd+1}" if rnd <= 3 else f"S{rnd-3}" if rnd <= 7 else f"W{rnd-7}") + f"-{honba}"
relative_seat_name = lambda you, other: {0: "self", 1: "shimocha", 2: "toimen", 3: "kamicha"}[(other-you)%4]
is_mangan = lambda han, fu: han == 5 or (han >= 4 and fu >= 40) or (han >= 3 and fu >= 70)
to_placement = lambda scores: (ixs := sorted(range(len(scores)), key=lambda x: -scores[x]), [ixs.index(p) for p in range(len(scores))])[1]

# helpers for removing tiles from hand
@functools.cache
def try_remove_all_tiles(hand: Tuple[int, ...], tiles: Tuple[int, ...]) -> Tuple[int, ...]:
    """
    Tries to remove all of `tiles` from `hand`. If it can't, returns `hand` unchanged
    """
    hand_copy = list(hand)
    for tile in tiles:
        if tile in hand_copy or tile in TOGGLE_RED_FIVE and (tile := TOGGLE_RED_FIVE[tile]) in hand_copy:
            hand_copy.remove(tile)
        else:
            return hand
    return tuple(hand_copy)
remove_some_from = lambda hands, groups: hands if hands == {()} else set(try_remove_all_tiles(hand, group) for hand in hands for group in groups)
remove_some = lambda hands, tile_to_groups: hands if hands == {()} else set(try_remove_all_tiles(hand, group) for hand in hands for tile in set(hand) for group in tile_to_groups(tile))
def remove_all_from(hands: Set[Tuple[int, ...]], groups: Tuple[Tuple[int, ...], ...]):
    # Tries to remove the maximum number of groups in groups from the hand.
    # Basically same as remove_some but filters the result for min length hands.
    assert isinstance(hands, set)
    if len(hands) == 0:
        return hands
    result = remove_some_from(hands, groups)
    min_length = min(map(len, result), default=0)
    ret = set(filter(lambda hand: len(hand) == min_length, result))
    assert len(ret) > 0
    # print(list(map(ph,hands)),"\n=>\n",list(map(ph,result)), "\n=>\n",list(map(ph,ret)),"\n")
    return ret
def remove_all(hands: Set[Tuple[int, ...]], tile_to_groups: Callable[[int], Tuple[Tuple[int, ...], ...]]):
    # Tries to remove the maximum number of groups in tile_to_groups(tile) from the hand.
    # Basically same as remove_some but filters the result for min length hands.
    assert isinstance(hands, set)
    if len(hands) == 0:
        return hands
    result = remove_some(hands, tile_to_groups)
    assert len(result) > 0
    min_length = min(map(len, result), default=0)
    ret = set(filter(lambda hand: len(hand) == min_length, result))
    assert len(ret) > 0
    # print(list(map(ph,hands)),"\n=>\n",list(map(ph,result)), "\n=>\n",list(map(ph,ret)),"\n")
    return ret
fix = lambda f, x: next(x for _ in itertools.cycle([None]) if x == (x := f(x)))

def shanten_name(shanten: Tuple[float, List[int]]):
    if shanten[0] >= 2:
        return SHANTEN_NAMES[shanten[0]]
    else:
        return SHANTEN_NAMES[shanten[0]] + " accepting " + ph(shanten[1])

# takes in "場風 東(1飜)", "ドラ(2飜)", "裏ドラ(1飜)"
# outputs ("ton", 1), ("dora 2", 2), ("ura", 1)
def translate_tenhou_yaku(yaku: str) -> Tuple[str, int]:
    name, rest = yaku.split("(")
    name = TRANSLATE[name]
    if "役満" in yaku: # e.g. "大三元(役満)"
        han = 13
    else: # e.g. "ドラ(2飜)"
        han = int(rest.split("飜")[0])
    if "ドラ" in name and han > 1:
        name = f"{name} {han}"
    return name, han

def get_score(han: int, fu: int, is_dealer: bool, is_tsumo: bool, num_players: int):
    if is_tsumo:
        oya = OYA_TSUMO_SCORE[han][fu]  # type: ignore[index]
        ko = KO_TSUMO_SCORE[han][fu]  # type: ignore[index]
        return oya + (oya if is_dealer else ko) * (num_players - 2)
    else:
        return (OYA_RON_SCORE if is_dealer else KO_RON_SCORE)[han][fu]  # type: ignore[index]

def calculate_delta_scores(han: int, fu: int, is_tsumo: bool, winner: int, dealer: int, num_players: int, loser: Optional[int]) -> List[int]:
    delta_scores = [0]*num_players
    if is_tsumo:
        oya = OYA_TSUMO_SCORE[han][fu]  # type: ignore[index]
        ko = KO_TSUMO_SCORE[han][fu]  # type: ignore[index]
        delta_scores = [-ko]*num_players
        delta_scores[dealer] = -oya
        delta_scores[winner] = 0
        delta_scores[winner] = -sum(delta_scores)
    else:
        assert loser is not None
        score = (OYA_RON_SCORE if winner == dealer else KO_RON_SCORE)[han][fu]  # type: ignore[index]
        delta_scores[winner] = score
        delta_scores[loser] = -score
    return delta_scores

apply_delta_scores = lambda scores, delta_score:  [score + delta for score, delta in zip(scores, delta_score)]

def get_taatsu_wait(taatsu: Tuple[int, int]) -> Set[int]:
    t1, t2 = remove_red_fives(taatsu)
    return {PRED[t1], SUCC[t2]} - {0} if SUCC[t1] == t2 else {SUCC[t1]} if SUCC[SUCC[t1]] == t2 else set()
def get_waits(hand: Tuple[int, ...]) -> Set[int]:
    """Get all waits in a hand full of taatsus and no floating tiles, excluding pair waits"""
    hand = sorted_hand(hand)

    # parse out all the taatsus
    waits = set()
    to_update: Set[Tuple[Tuple[int, ...], Tuple[Tuple[int, int], ...]]] = {(hand, ())}
    while len(to_update) > 0:
        hand, taatsus = to_update.pop()
        if len(hand) <= 1: # done
            waits |= set().union(*map(get_taatsu_wait, taatsus))
            continue
        for tile in hand:
            if SUCC[tile] in hand:
                taatsu = (tile, SUCC[tile])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
            if SUCC[SUCC[tile]] in hand:
                taatsu = (tile, SUCC[SUCC[tile]])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
    return waits

