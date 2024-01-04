import functools
import itertools
from .constants import MANZU, PINZU, SOUZU, PRED, SUCC, DORA, DORA_INDICATOR, TOGGLE_RED_FIVE, TRANSLATE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, OYA_RON_SCORE, KO_RON_SCORE
from typing import *

# This file contains a bunch of utility functions that don't really belong anywhere else.

normalize_red_five = lambda tile: TOGGLE_RED_FIVE[tile] if tile in {51,52,53} else tile
normalize_red_fives = lambda hand: map(normalize_red_five, hand)
sorted_hand = lambda hand: tuple(sorted(hand, key=normalize_red_five))
is_mangan = lambda han, fu: han == 5 or (han >= 4 and fu >= 40) or (han >= 3 and fu >= 70)

@functools.cache
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

def get_score(han: int, fu: int, is_dealer: bool, is_tsumo: bool, num_players: int) -> int:
    """
    Calculate the score given han and fu.
    Of course, score is influenced by dealership, tsumo, and (for tsumo) number of players.
    """
    if is_tsumo:
        oya: int = OYA_TSUMO_SCORE[han][fu]  # type: ignore[index]
        ko: int = KO_TSUMO_SCORE[han][fu]  # type: ignore[index]
        return oya + (oya if is_dealer else ko) * (num_players - 2)
    else:
        return cast(int, (OYA_RON_SCORE if is_dealer else KO_RON_SCORE)[han][fu])  # type: ignore[index]

# Add a score delta array [0,1000,-1000,0] to an existing score array [25000,25000,25000,25000]
apply_delta_scores = lambda scores, delta_score: [score + delta for score, delta in zip(scores, delta_score)]
# Given a score array, calculate the placement: [10000,30000,20000,40000] -> [3, 1, 2, 0]
to_placement = lambda scores, num_players: (ixs := sorted(range(num_players), key=lambda x: -scores[x]), [ixs.index(p) for p in range(num_players)])[1]

def get_taatsu_wait(taatsu: Tuple[int, ...]) -> Set[int]:
    """
    Given a two-element tuple of tiles, return the tile(s) it is waiting on, if any.
    The reason the type is Tuple[int, ...] instead of Tuple[int, int] is because it's a pain
    to cast from Tuple[int, ...] to Tuple[int, int] every time you use this function.
    """
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
        # try to find pairs, ryanmens, and kanchans, using every tile in the hand
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

def calc_ko_oya_points(total_points: int, num_players: int, is_dealer: bool) -> Tuple[int, int]:
    """Reverse-calculate the ko and oya parts of the total points"""
    divisor = num_players-1 if is_dealer else num_players
    ko_payment = int(round(total_points/divisor, -2))
    num_ko_payers = num_players-1 if is_dealer else num_players-2
    oya_payment = total_points - num_ko_payers * ko_payment
    return ko_payment, oya_payment

_tiles = [*range(11,20), *range(21,30), *range(31,40), *range(41,48)]
_reds = {_tiles.index(15): 51, _tiles.index(25): 52, _tiles.index(35): 53}
ix_to_tile = lambda ix: _reds[ix//4] if ix//4 in _reds and ix%4==0 else _tiles[ix//4]

def to_dora(dora_indicator: int, num_players: int) -> int:
    return 19 if num_players == 3 and dora_indicator == 11 else DORA[dora_indicator]
def to_dora_indicator(dora: int, num_players: int) -> int:
    return 11 if num_players == 3 and dora == 19 else DORA_INDICATOR[dora]
    