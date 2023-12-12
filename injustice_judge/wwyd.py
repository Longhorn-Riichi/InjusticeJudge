from .constants import JIHAI, PRED, SUCC
from .shanten import calculate_shanten
from .utils import normalize_red_five
from typing import *

# This file only contains is_safe, which checks genbutsu/suji/one-chance for a given tile.
# Normally something like this would go into utils.py, but this requires shanten.py
# which depends on utils.py.

SUJI_VALUES = {1: (4,), 2: (5,), 3: (6,), 4: (1,7), 5: (2,8), 6: (3,9), 7: (4,), 8: (5,), 9: (6,)}
SUJI = {k+n: tuple(x+n for x in v) for k, v in SUJI_VALUES.items() for n in {10,20,30}}
def is_safe(tile: int, opponent_genbutsu: Set[int], visible_tiles: List[int]) -> bool:
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
