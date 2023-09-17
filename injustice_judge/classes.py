from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .constants import TOGGLE_RED_FIVE
from .display import ph, pt, shanten_name
from .utils import get_waits, sorted_hand, try_remove_all_tiles

# This file contains most of the classes used in InjusticeJudge.
# It also contains some printing logic in the form of __str__ overloads.

class Dir(IntEnum):
    """Enum representing a direction, add to a seat mod 4 to get the indicated seat"""
    SELF = 0
    SHIMOCHA = 1
    TOIMEN = 2
    KAMICHA = 3

@dataclass(frozen=True)
class CallInfo:
    """Immutable object describing a single call (chii, pon, daiminkan, ankan, kakan)"""
    type: str        # one of "chii", "pon", "minkan", "ankan", "kakan"
    tile: int        # the called tile
    dir: Dir         # where the tile was called from (indicates where to point the called tile)
    tiles: List[int] # the 3 or 4 tiles set aside after calling
    def __post_init__(self):
        super().__setattr__("tiles", sorted_hand(self.tiles))
    def to_str(self, doras=[], uras=[]):
        as_dora = lambda tile: tile + (100 if tile in doras or tile in uras else 0)
        tiles = tuple(map(as_dora, self.tiles))
        tile = as_dora(self.tile)
        # other_tiles is all the non-called tiles in the call
        other_tiles = try_remove_all_tiles(tiles, (tile,))
        sideways = pt(tile, is_sideways=True)
        if self.type == "ankan":
            if any(tile in {51,52,53} for tile in tiles):
                return ph((50, TOGGLE_RED_FIVE[tile], tile, 50))
            else:
                return ph((50, tile, tile, 50))
        elif self.type == "kita":
            return pt(tile)
        elif self.type == "kakan": # print two consecutive sideways tiles
            sideways = pt(other_tiles[0], is_sideways=True) + sideways
            other_tiles = other_tiles[1:]
        if self.dir == Dir.SHIMOCHA:
            return ph(other_tiles) + sideways
        elif self.dir == Dir.TOIMEN:
            return pt(other_tiles[0]) + sideways + ph(other_tiles[1:])
        elif self.dir == Dir.KAMICHA:
            return sideways + ph(other_tiles)
        # dir == Dir.SELF is only for ankan and is handled above
    def __str__(self):
        return self.to_str()
    
# hand interpretations and yaku
@dataclass
class Interpretation:
    """A single interpretation of a single hand (decomposed into triplets, sequences, and pair)"""
    hand: Tuple[int, ...]                           # The non-decomposed part of the original hand
    ron_fu: int = 0                                 # ron fu using this interpretation of the hand (not rounded)
    tsumo_fu: int = 0                               # tsumo fu using this interpretation of the hand (not rounded)
    sequences: Tuple[Tuple[int, ...], ...] = ()     # Sequences taken from the original hand
    triplets: Tuple[Tuple[int, ...], ...] = ()      # Triplets taken from the original hand
    pair: Optional[Tuple[int, int]] = None          # A pair taken from the original hand
    calls: Tuple[CallInfo, ...] = ()                # A frozen list of calls from the original hand
    def unpack(self):
        return (self.hand, self.ron_fu, self.tsumo_fu, self.sequences, self.triplets, self.pair)
    def __hash__(self):
        return hash(self.unpack())
    def __str__(self):
        full_hand = (*self.sequences, *self.triplets, self.pair, self.hand) if self.pair is not None else (*self.sequences, *self.triplets, self.hand)
        return " ".join(map(ph, full_hand)) + f" ron {self.ron_fu} tsumo {self.tsumo_fu}"
    def get_waits(self) -> Set[int]:
        if len(self.hand) == 1: # tanki
            return {self.hand[0]}
        elif len(self.hand) == 2:
            assert self.pair is not None
            if self.hand[0] == self.hand[1]: # shanpon
                return {self.hand[0], self.pair[0]}
            else: # ryanmen, kanchan, penchan
                return get_waits(self.hand)
        return set()

@dataclass
class GameRules:
    use_red_fives: bool = True        # whether the game uses red fives
    immediate_kan_dora: bool = False  # whether kan immediately reveals a dora
    head_bump: bool = False           # whether head bump is enabled
    @classmethod
    def from_majsoul_detail_rule(cls, rules):
        return cls(use_red_fives = "doraCount" not in rules or rules["doraCount"] > 0,
                   immediate_kan_dora = "mingDoraImmediatelyOpen" in rules and rules["mingDoraImmediatelyOpen"],
                   head_bump = "haveToutiao" in rules and rules["haveToutiao"])
    @classmethod
    def from_tenhou_rules(cls, rules):
        return cls(use_red_fives = "aka51" in rules and rules["aka51"])

@dataclass
class GameMetadata:
    """Facts that apply across every kyoku"""
    num_players: int
    name: List[str]                  # name of each player indexed by seat
    game_score: List[int]            # final scores (points) indexed by seat
    final_score: List[int]           # final scores (points plus uma) indexed by seat
    # the fields below are equivalent to Kyoku.doras/uras, and only here for technical reasons
    # (they are parsed first from the raw log, and then used to populate Kyoku)
    dora_indicators: List[List[int]] # lists of dora indicators, one for each kyoku
    ura_indicators: List[List[int]]  # lists of ura indicators, one for each kyoku
    rules: GameRules                 # game rules
