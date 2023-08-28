from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .constants import TOGGLE_RED_FIVE
from .utils import ph, pt, pt_sideways, remove_red_five, remove_red_fives, shanten_name, sorted_hand, try_remove_all_tiles
from .shanten import calculate_shanten



@dataclass
class YakuList:
    yaku_strs: List[str]
    dora: int = 0 # count of all round dora and aka
    ura: int = 0
    kita: int = 0 
    riichi: bool = False
    ippatsu: bool = False
    haitei: bool = False
@dataclass(frozen = True)
class Ron:
    score_delta: List[int]
    winner: int
    won_from: int
    han: int
    fu: int
    limit_name: str
    score_string: str
    score: int
    yaku: YakuList
@dataclass(frozen = True)
class Tsumo:
    score_delta: List[int]
    winner: int
    han: int
    fu: int
    limit_name: str
    score_string: str
    score_oya: int
    score_ko: int
    score: int
    yaku: YakuList
@dataclass(frozen = True)
class Draw:
    score_delta: List[int]
    name: str

@dataclass
class GameMetadata:
    num_players: int
    num_rounds: int
    last_round: Tuple[int, int] # (round, honba)
    name: List[str]
    game_score: List[int]
    final_score: List[int]
    dora_indicators: List[List[int]]
    ura_indicators: List[List[int]]
    use_red_fives: bool

# hand interpretations and yaku
@dataclass
class Interpretation:
    hand: Tuple[int, ...]
    ron_fu: int = 0
    tsumo_fu: int = 0
    sequences: Tuple[Tuple[int, ...], ...] = ()
    triplets: Tuple[Tuple[int, ...], ...] = ()
    pair: Optional[Tuple[int, int]] = None
    def unpack(self):
        return (self.hand, self.ron_fu, self.tsumo_fu, self.sequences, self.triplets, self.pair)
    def __hash__(self):
        return hash(self.unpack())
YakuValues = Dict[int, List[Tuple[str, int]]]
@dataclass
class YakuHanFu:
    yaku: YakuValues # wait -> list of ("yaku name", value)
    han: Dict[int, int] # wait -> han
    fu: int
    tsumo: bool
    interpretation: Interpretation # basically only for debug use
    def __hash__(self):
        return hash((self.fu, tuple(self.yaku)))





@functools.cache
def _hidden_part(hand: Tuple[int], calls: Tuple[int]) -> Tuple[int, ...]:
    ret = try_remove_all_tiles(hand, calls)
    assert len(ret) + len(calls) == len(hand), f"with hand = {ph(hand)} and calls = {ph(calls)}, somehow closed part is {ph(ret)}"
    return ret

class Dir(IntEnum):
    SELF = 0
    SHIMOCHA = 1
    TOIMEN = 2
    KAMICHA = 3

@dataclass(frozen=True)
class CallInfo:
    type: str
    tile: int
    dir: Dir
    tiles: List[int]
    def __post_init__(self):
        super().__setattr__("tiles", sorted_hand(self.tiles))
    def __str__(self):
        # other_tiles is all the non-called tiles in the call
        other_tiles = try_remove_all_tiles(self.tiles, (self.tile,))
        sideways = pt_sideways(self.tile)
        if self.type == "ankan":
            if any(tile in {51,52,53} for tile in self.tiles):
                return ph((50, TOGGLE_RED_FIVE[self.tile], self.tile, 50))
            else:
                return ph((50, self.tile, self.tile, 50))
        elif self.type == "kakan": # print two consecutive sideways tiles
            sideways = pt_sideways(other_tiles[0]) + sideways
            other_tiles = other_tiles[1:]
        if self.dir == Dir.SHIMOCHA:
            return ph(other_tiles) + sideways
        elif self.dir == Dir.TOIMEN:
            return pt(other_tiles[0]) + sideways + ph(other_tiles[1:])
        elif self.dir == Dir.KAMICHA:
            return sideways + ph(other_tiles)
        # dir == Dir.SELF is only for ankan and is handled above

# main hand class
@dataclass(frozen=True)
class Hand:
    tiles: Tuple[int, ...]
    calls: List[CallInfo] = field(default_factory=list)
    open_part: Tuple[int, ...] = ()
    hidden_part: Tuple[int, ...] = ()
    closed_part: Tuple[int, ...] = ()
    shanten: Tuple[float, List[int]] = (-1, [])
    def __post_init__(self):
        super().__setattr__("tiles", sorted_hand(self.tiles))
        super().__setattr__("open_part", tuple(tile for call in self.calls for tile in call.tiles[:3]))
        super().__setattr__("hidden_part", _hidden_part(self.tiles, self.open_part))
        # for closed part, add any ankan back in as triplets
        closed_part = self.hidden_part
        for call in self.calls:
            if call.type == "ankan":
                closed_part = (*closed_part, call.tile, call.tile, call.tile)
        super().__setattr__("closed_part", closed_part)
        if len(self.tiles) in {1, 4, 7, 10, 13}:
            super().__setattr__("shanten", calculate_shanten(self.hidden_part))
    def add(self, tile: int) -> "Hand":
        return Hand((*self.tiles, tile), [*self.calls])
    def add_call(self, calls: CallInfo) -> "Hand":
        return Hand(self.tiles, [*self.calls, calls])
    def remove(self, tile: int) -> "Hand":
        tiles = list(self.tiles)
        tiles.remove(tile)
        return Hand(tuple(tiles), [*self.calls])
    def __str__(self):
        call_string = "" if len(self.calls) == 0 else "⠀" + "⠀".join(map(str, reversed(self.calls)))
        return f"{ph(self.hidden_part)}{call_string}"

    def final_hand(self, ukeire: int, final_tile: Optional[int] = None, furiten: bool = False):
        wait_string = ""
        win_string = ""
        if self.shanten[0] == 0:
            wait_string = f"{' (furiten) ' if furiten else ' '}waits: {ph(sorted_hand(self.shanten[1]))} ({ukeire} out{'s' if ukeire > 1 else ''})"
            win_string = f"⠀{pt(final_tile)}" if final_tile is not None else ""
        elif self.shanten[0] > 0:
            wait_string = f" ({shanten_name(self.shanten)})"
        return f"{self!s}{win_string}{wait_string}"
    def ukeire(self, visible: Iterable[int]):
        """
        Pass in all the visible tiles on board (not including hand).
        Return the ukeire of the hand, or 0 if the hand is not tenpai.
        """
        shanten, waits = self.shanten
        if shanten > 0:
            return 0
        relevant_tiles = set(remove_red_fives(waits))
        visible = list(remove_red_fives(list(self.tiles) + list(visible)))
        return 4 * len(relevant_tiles) - sum(visible.count(wait) for wait in relevant_tiles)
    def kakan(self, called_tile):
        pon_index = next((i for i, calls in enumerate(self.calls) if calls.type == "pon" and calls.tile == called_tile), None)
        assert pon_index is not None, f"unable to find previous pon in calls: {self.calls}"
        orig_direction = self.calls[pon_index].dir
        orig_tiles = [*self.calls[pon_index].tiles, called_tile]
        calls_copy = [*self.calls]
        calls_copy[pon_index] = CallInfo("kakan", called_tile, orig_direction, orig_tiles)
        return Hand(self.tiles, calls_copy)
    
    def __hash__(self):
        return hash((self.open_part, self.closed_part))

Event = Tuple[Any, ...]

@dataclass
class Kyoku:
    round: int                                    = 0
    honba: int                                    = 0
    num_players: int                              = 0
    final_draw: int                               = 0
    final_discard: int                            = 0
    final_draw_event_index: List[int]             = field(default_factory=list)
    final_discard_event_index: List[int]          = field(default_factory=list)
    # doras include the round doras AND the red fives; each appearance means it's +1 han
    doras: List[int]                              = field(default_factory=list)
    uras: List[int]                               = field(default_factory=list)
    events: List[Event]                           = field(default_factory=list)
    result: Tuple[Any, ...]                       = field(default_factory=tuple)
    hands: List[Hand]                             = field(default_factory=list)
    pond: List[List[int]]                         = field(default_factory=list)
    furiten: List[bool]                           = field(default_factory=list)
    final_waits: List[List[int]]                  = field(default_factory=list)
    final_ukeire: List[int]                       = field(default_factory=list)
    haipai: List[Hand]                            = field(default_factory=list)
    haipai_ukeire: List[int]                      = field(default_factory=list)
    kita_counts: List[int]                        = field(default_factory=list)
    start_scores: List[int]                       = field(default_factory=list)
