import os
from .constants import Shanten, DISCORD_TILES, DISCORD_CALLED_TILES, DISCORD_DORA_TILES, DISCORD_CALLED_DORA_TILES, SHANTEN_NAMES
from typing import *

def pt_unicode(tile: int, is_sideways: bool = False) -> str:
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
        ret += "\u20f0" # combining asterisk
    if is_sideways:
        ret = f"₍{ret}₎"
    return ret

def pt_discord(tile: int, is_sideways: bool = False) -> str:
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

# print tile, print hand
pt = lambda tile, is_sideways=False: pt_discord(tile, is_sideways) if os.getenv("use_discord_tile_emoji") == "True" else pt_unicode(tile, is_sideways)
ph = lambda hand, doras=[]: "".join(map(pt, map(lambda tile: tile + 100 if tile in doras else tile, hand)))

def print_pond(pond: Iterable[int], doras: List[int] = [], riichi_index: Optional[int] = None) -> str:
    if riichi_index is None:
        return ph(pond, doras)
    else:
        i = riichi_index
        pond = tuple(pond)
        return ph(pond[:i], doras) + pt(pond[i], is_sideways=True) + ph(pond[i+1:], doras)

round_name = lambda rnd, honba: (f"East {rnd+1}" if rnd <= 3 else f"South {rnd-3}" if rnd <= 7 else f"West {rnd-7}" if rnd <= 11 else f"North {rnd-11}") + ("" if honba == 0 else f"-{honba}")
short_round_name = lambda rnd, honba: (f"E{rnd+1}" if rnd <= 3 else f"S{rnd-3}" if rnd <= 7 else f"W{rnd-7}" if rnd <= 11 else f"N{rnd-11}") + f"-{honba}"
relative_seat_name = lambda you, other: {0: "self", 1: "shimocha", 2: "toimen", 3: "kamicha"}[(other-you)%4]

def shanten_name(shanten: Shanten):
    if shanten[0] >= 2:
        return SHANTEN_NAMES[shanten[0]]
    else:
        return SHANTEN_NAMES[shanten[0]] + " accepting " + ph(shanten[1])
