import functools
import itertools
from .constants import MANZU, PINZU, SOUZU, PRED, SUCC, TOGGLE_RED_FIVE, TRANSLATE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, OYA_RON_SCORE, KO_RON_SCORE
from typing import *


# This file contains a bunch of utility functions that don't really belong anywhere else.
# The goal is to move these someday, so they're not really documented right now.

normalize_red_five = lambda tile: TOGGLE_RED_FIVE[tile] if tile in {51,52,53} else tile
normalize_red_fives = lambda hand: map(normalize_red_five, hand)
sorted_hand = lambda hand: tuple(sorted(hand, key=normalize_red_five))
is_mangan = lambda han, fu: han == 5 or (han >= 4 and fu >= 40) or (han >= 3 and fu >= 70)

# helpers for removing tiles from hand
@functools.lru_cache(maxsize=1048576) # (hashed args + result size) * 1MiB cache
def try_remove_all_tiles(hand: Tuple[int, ...], tiles: Tuple[int, ...]) -> Tuple[int, ...]:
    """
    Tries to remove all of `tiles` from `hand`. If it can't, returns `hand` unchanged
    On profiling a long game, the cache missed 430578/2219864 calls (19.397%)
    """
    hand_copy = list(hand)
    for tile in tiles:
        if tile in hand_copy or tile in TOGGLE_RED_FIVE and (tile := TOGGLE_RED_FIVE[tile]) in hand_copy:
            hand_copy.remove(tile)
        else:
            return hand
    return tuple(hand_copy)

remove_some = lambda hands, tile_to_groups: hands if hands == {()} else set(try_remove_all_tiles(hand, group) for hand in hands for tile in set(hand) for group in tile_to_groups(tile))
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

# takes in "場風 東(1飜)", "ドラ(2飜)", "裏ドラ(1飜)"
# outputs ("ton", 1), ("dora 2", 2), ("ura", 1)
def translate_tenhou_yaku(yaku: str) -> Tuple[str, int]:
    name, rest = yaku.split("(")
    name = TRANSLATE[name]
    if "役満" in yaku: # e.g. "大三元(役満)"
        han = 13
    else: # e.g. "ドラ(2飜)"
        han = int(rest.split("飜")[0])
    if name in {"dora", "aka", "ura", "kita"} and han > 1:
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

apply_delta_scores = lambda scores, delta_score: [score + delta for score, delta in zip(scores, delta_score)]
to_placement = lambda scores: (ixs := sorted(range(len(scores)), key=lambda x: -scores[x]), [ixs.index(p) for p in range(len(scores))])[1]

def get_taatsu_wait(taatsu: Tuple[int, int]) -> Set[int]:
    t1, t2 = normalize_red_fives(taatsu)
    return {PRED[t1], SUCC[t2]} - {0} if SUCC[t1] == t2 else {SUCC[t1]} if SUCC[SUCC[t1]] == t2 else set()

@functools.lru_cache(maxsize=2048)
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
        for i, tile in enumerate(hand):
            if tile in (*hand[:i], *hand[i+1:]): # pair, ignore
                to_update.add((try_remove_all_tiles(hand, (tile, tile)), taatsus))
            if SUCC[tile] in hand:
                taatsu = (tile, SUCC[tile])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
            if SUCC[SUCC[tile]] in hand:
                taatsu = (tile, SUCC[SUCC[tile]])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
    return waits

def get_majority_suit(hand: Tuple[int, ...]) -> Optional[Set[int]]:
    # returns one of {MANZU, PINZU, SOUZU}
    # or None if there is no majority suit (i.e. there's a tie)
    num_manzu = sum(1 for tile in hand if tile in MANZU)
    num_pinzu = sum(1 for tile in hand if tile in PINZU)
    num_souzu = sum(1 for tile in hand if tile in SOUZU)
    if num_manzu > max(num_pinzu, num_souzu):
        return MANZU
    elif num_pinzu > max(num_manzu, num_souzu):
        return PINZU
    elif num_souzu > max(num_manzu, num_pinzu):
        return SOUZU
    else:
        return None
