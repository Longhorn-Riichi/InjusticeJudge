import functools
import itertools
from .constants import MANZU, PINZU, SOUZU, JIHAI, PRED, SUCC, DORA, DORA_INDICATOR, TOGGLE_RED_FIVE, TRANSLATE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, OYA_RON_SCORE, KO_RON_SCORE
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

to_sequence = lambda tile: (SUCC[SUCC[tile]], SUCC[tile], tile)
to_triplet = lambda tile: (tile, tile, tile)

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
apply_delta_scores = lambda scores, delta_score: [round(score + delta, 1) for score, delta in zip(scores, delta_score)]
def to_placement(scores: Sequence[float], num_players: int, dealer_seat: int) -> List[int]:
    # Given a score array, calculate the placement: [10000,30000,20000,40000] -> [3, 1, 2, 0]
    scores_east_first = (*scores[dealer_seat:], *scores[:dealer_seat])
    ixs = sorted(range(num_players), key=lambda x: -scores_east_first[x])
    placements_east_first = [ixs.index(p) for p in range(num_players)]
    dealer_position = (num_players-dealer_seat)%4
    return placements_east_first[dealer_position:] + placements_east_first[:dealer_position]

def get_taatsu_wait(taatsu: Tuple[int, ...]) -> Set[int]:
    """
    Given a two-element tuple of tiles, return the tile(s) it is waiting on, if any.
    The reason the type is Tuple[int, ...] instead of Tuple[int, int] is because it's a pain
    to cast from Tuple[int, ...] to Tuple[int, int] every time you use this function.
    """
    t1, t2 = normalize_red_fives(taatsu)
    return {PRED[t1], SUCC[t2]} - {0} if SUCC[t1] == t2 else {SUCC[t1]} if SUCC[SUCC[t1]] == t2 else set()

@functools.lru_cache(maxsize=2048)
def get_waits_taatsus(hand: Tuple[int, ...]) -> Tuple[Set[int], Set[Tuple[int, int]]]:
    """Get all waits and taatsus in a hand full of taatsus and no floating tiles, excluding pair waits"""
    hand = sorted_hand(hand)

    # parse out all the taatsus
    waits = set()
    all_taatsus = set()
    to_update: Set[Tuple[Tuple[int, ...], Tuple[Tuple[int, int], ...]]] = {(hand, ())}
    while len(to_update) > 0:
        hand, taatsus = to_update.pop()
        if len(hand) <= 1: # done
            all_taatsus |= set(taatsus)
            waits |= set().union(*map(get_taatsu_wait, taatsus))
            continue
        # try to find pairs, ryanmens, and kanchans, using every tile in the hand
        for i, tile in enumerate(hand):
            if tile in (*hand[:i], *hand[i+1:]): # pair, ignore
                all_taatsus.add((tile, tile))
                to_update.add((try_remove_all_tiles(hand, (tile, tile)), taatsus))
            if SUCC[tile] in hand:
                taatsu = (tile, SUCC[tile])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
            if SUCC[SUCC[tile]] in hand:
                taatsu = (tile, SUCC[SUCC[tile]])
                to_update.add((try_remove_all_tiles(hand, taatsu), (*taatsus, taatsu)))
    return waits, all_taatsus

def get_waits(hand: Tuple[int, ...]) -> Set[int]:
    return get_waits_taatsus(hand)[0]

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

SUJI_VALUES = {1: (4,), 2: (5,), 3: (6,), 4: (1,7), 5: (2,8), 6: (3,9), 7: (4,), 8: (5,), 9: (6,)}
SUJI = {k+n: tuple(x+n for x in v) for k, v in SUJI_VALUES.items() for n in {10,20,30}}
def is_safe(tile: int, opponent_genbutsu: Set[int], visible_tiles: List[int]) -> bool:
    """Returns true if the tile is any of genbutsu/suji/one-chance."""
    # genbutsu
    if tile in opponent_genbutsu:
        return True
    if tile not in JIHAI:
        # suji
        if all(suji in opponent_genbutsu for suji in SUJI[normalize_red_five(tile)]):
            return True
        # one-chance
        # check all possible taatsu waiting on this tile
        # if every taatsu is one-chance or no-chance then consider it safe
        possible_taatsus = ((PRED[PRED[tile]], PRED[tile]), (PRED[tile], SUCC[tile]), (SUCC[tile], SUCC[SUCC[tile]]))
        if all(any(visible_tiles.count(tile) >= 3 for tile in taatsu) for taatsu in possible_taatsus if 0 not in taatsu):
            return True
    else:
        # check if there's 3 copies already
        if visible_tiles.count(tile) >= 3:
            return True

    return False

def save_cache(filename: str, data: bytes) -> None:
    """Save data to a cache file"""
    import os
    # make sure the cache directory exists
    if not os.path.isdir("cached_games"):
        os.mkdir("cached_games")
    # make sure we have enough space
    dir_size = sum(os.path.getsize(os.path.join(dirpath, f)) for dirpath, _, filenames in os.walk("cached_games") for f in filenames)
    if dir_size < (1024 ** 3): # 1GB
        with open(f"cached_games/{filename}", "wb") as file:
            file.write(data)
