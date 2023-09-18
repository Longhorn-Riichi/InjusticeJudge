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

@functools.lru_cache(maxsize=1048576) # (hashed args + result size) * 1MiB cache
def try_remove_all_tiles(hand: Tuple[int, ...], tiles: Tuple[int, ...]) -> Tuple[int, ...]:
    """
    Tries to remove all of `tiles` from `hand`. If it can't, returns `hand` unchanged
    On profiling a long game, the cache missed 430578/2219864 calls (19.397%)
    """
    orig_hand = hand
    for tile in tiles:
        if tile in hand or tile in TOGGLE_RED_FIVE and (tile := TOGGLE_RED_FIVE[tile]) in hand:
            i = hand.index(tile)
            hand = (*hand[:i], *hand[i+1:])
        else:
            return orig_hand
    return hand

@functools.lru_cache(maxsize=2048)
def get_score(han: int, fu: int, is_dealer: bool, is_tsumo: bool, num_players: int):
    if is_tsumo:
        oya = OYA_TSUMO_SCORE[han][fu]  # type: ignore[index]
        ko = KO_TSUMO_SCORE[han][fu]  # type: ignore[index]
        return oya + (oya if is_dealer else ko) * (num_players - 2)
    else:
        return (OYA_RON_SCORE if is_dealer else KO_RON_SCORE)[han][fu]  # type: ignore[index]

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
