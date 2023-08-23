import functools
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

def pt(tile: int) -> str:
    if os.getenv("use_discord_tile_emoji") == "True":
        return DISCORD_TILES[tile]
    else:
        return pt_unicode(tile)

def print_call_info(call_info):
    call_type, called_tile, call_direction, call_tiles = call_info
    other_tiles = sorted_hand(try_remove_all_tiles(tuple(call_tiles), (called_tile,)))
    if os.getenv("use_discord_tile_emoji") == "True":
        sideways = DISCORD_CALLED_TILES[called_tile]
    else:
        sideways = f"₍{pt(called_tile)}₎"
    if call_type == "ankan":
        return ph((50, called_tile, called_tile, 50))
    elif call_type == "kakan": # two consecutive sideways tiles
        sideways = sideways*2
        other_tiles = other_tiles[:-1]
    if call_direction == 1: # shimocha
        return ph(other_tiles) + sideways
    elif call_direction == 2: # toimen
        return pt(other_tiles[0]) + sideways + ph(other_tiles[1:])
    elif call_direction == 3: # kamicha
        return sideways + ph(other_tiles)
    else:
        assert False, f"print_call_info got invalid call direction {call_direction}"

def print_full_hand(closed_part, call_info, shanten, ukeire, final_tile = None, furiten = False):
    call_string = "" if len(call_info) == 0 else "⠀" + "⠀".join(map(print_call_info, reversed(call_info)))
    if shanten[0] == 0:
        wait_string = f"{' (furiten) ' if furiten else ' '}waits: {ph(sorted_hand(shanten[1]))} ({ukeire} out{'s' if ukeire > 1 else ''})"
        win_string = "⠀" + pt(final_tile)
    else:
        wait_string = f" ({shanten_name(shanten)})"
        win_string = ""
    return f"{ph(sorted_hand(closed_part))}{call_string}{win_string}{wait_string}"

ph = lambda hand: "".join(map(pt, hand)) # print hand
remove_red_five = lambda tile: TOGGLE_RED_FIVE[tile] if tile in {51,52,53} else tile
remove_red_fives = lambda hand: map(remove_red_five, hand)
sorted_hand = lambda hand: tuple(sorted(hand, key=remove_red_five))
round_name = lambda rnd, honba: (f"East {rnd+1}" if rnd <= 3 else f"South {rnd-3}" if rnd <= 7 else f"West {rnd-7}") + ("" if honba == 0 else f"-{honba}")
short_round_name = lambda rnd, honba: (f"E{rnd+1}" if rnd <= 3 else f"S{rnd-3}" if rnd <= 7 else f"W{rnd-7}") + f"-{honba}"
relative_seat_name = lambda you, other: {0: "self", 1: "shimocha", 2: "toimen", 3: "kamicha"}[(other-you)%4]

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
            return tuple(hand)
    return tuple(hand_copy)

def shanten_name(shanten: Tuple[int, List[int]]):
    if shanten[0] >= 2:
        return SHANTEN_NAMES[shanten[0]]
    else:
        return SHANTEN_NAMES[shanten[0]] + " accepting " + ph(shanten[1])

def get_waits(hand: Tuple[int, ...]) -> Set[int]:
    """Get all waits resulting from each pair of consecutive tiles, excluding pair waits"""
    hand = sorted_hand(hand)
    def get_taatsu_wait(taatsu: Tuple[int, int]) -> Set[int]:
        t1, t2 = remove_red_fives(taatsu)
        return {PRED[t1], SUCC[t2]} if SUCC[t1] == t2 else {SUCC[t1]} if SUCC[SUCC[t1]] == t2 else set()
    return set().union(*map(get_taatsu_wait, zip(hand[:-1], hand[1:]))) - {0}
