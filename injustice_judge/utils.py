import functools
import itertools
from .constants import DISCORD_TILES, DISCORD_CALLED_TILES, TOGGLE_RED_FIVE, SHANTEN_NAMES, SUCC, PRED
from typing import *
import os

###
### utility functions
###

def pt_unicode(tile: int) -> str:
    """print tile (2-char representation)"""
    TILE_REPRS = "🀇🀈🀉🀊🀋🀌🀍🀎🀏🀙🀚🀛🀜🀝🀞🀟🀠🀡🀐🀑🀒🀓🀔🀕🀖🀗🀘🀀🀁🀂🀃🀆🀅🀄︎"
    if tile < 20:
        return TILE_REPRS[tile - 11] + " "
    elif tile < 30:
        return TILE_REPRS[tile - 21 + 9] + " "
    elif tile < 40:
        return TILE_REPRS[tile - 31 + 18] + " "
    elif tile < 47:
        return TILE_REPRS[tile - 41 + 27] + " "
    elif tile == 47:
        # need to specially output 🀄︎ so it's not an emoji
        return TILE_REPRS[-2:]
    elif tile == 50:
        return "🀫 "
    elif tile == 51:
        return "🀋·"
    elif tile == 52:
        return "🀝·"
    elif tile == 53:
        return "🀔·"
    else:
        return "??"

pt = lambda tile: DISCORD_TILES[tile] if os.getenv("use_discord_tile_emoji") == "True" else pt_unicode(tile)
pt_sideways = lambda tile: DISCORD_CALLED_TILES[tile] if os.getenv("use_discord_tile_emoji") == "True" else f"₍{pt_unicode(tile)}₎"

def print_final_hand_seat(kyoku, seat, print_final_tile=False):
    final_tile = None if not print_final_tile else kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
    return kyoku.hands[seat].final_hand(
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
