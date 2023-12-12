from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .classes import CallInfo, Dir, GameRules, Interpretation
from .constants import Event, Shanten, MANZU, PINZU, SOUZU, PRED, SUCC, DORA_INDICATOR, DOUBLE_YAKUMAN, LIMIT_HANDS, OYA_RON_SCORE, KO_RON_SCORE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, TRANSLATE
from .display import ph, pt, shanten_name
from .utils import get_score, is_mangan, normalize_red_five, normalize_red_fives, sorted_hand, try_remove_all_tiles
from .shanten import calculate_shanten

@functools.lru_cache(maxsize=2048)
def _hidden_part(hand: Tuple[int], calls: Tuple[int]) -> Tuple[int, ...]:
    """Cached helper for getting the hidden part of a hand, used below in __post_init__"""
    ret = try_remove_all_tiles(hand, calls)
    assert len(ret) + len(calls) == len(hand), f"with hand = {ph(hand)} and calls = {ph(calls)}, somehow hidden part is {ph(ret)}"
    return ret

# main hand class
@dataclass(frozen=True)
class Hand:
    """Immutable object describing the state of a single hand"""
    tiles: Tuple[int, ...]                                      # all tiles in the hand
    calls: List[CallInfo] = field(default_factory=list)         # every call the hand has made, in order of appearance
    ordered_calls: List[CallInfo] = field(default_factory=list) # every call the hand has made, in order of calling them
    open_part: Tuple[int, ...] = ()                             # all tiles currently shown as a call
    hidden_part: Tuple[int, ...] = ()                           # tiles - open_part
    closed_part: Tuple[int, ...] = ()                           # hidden_part + any ankans
    shanten: Shanten = (-1, ())                                 # shanten for the hand, or -1 if the hand is 14 tiles
                                                                # (like when it's in the middle of a draw or call)
    prev_shanten: Shanten = (-1, ())                            # shanten for the hand right before said draw or call
    tiles_with_kans: Tuple[int, ...] = ()                       # all tiles in the hand including kans
    best_discards: Tuple[int, ...] = ()                         # best discards for this hand (only for 14-tile hands)
    kita_count: int = 0                                         # number of kita calls for this hand
    
    def __post_init__(self) -> None:
        """You only need to provide `tiles` (and `calls`, if any), this calculates the rest"""
        super().__setattr__("tiles", sorted_hand(self.tiles))
        super().__setattr__("open_part", tuple(tile for call in self.calls if call.type != "kita" for tile in call.tiles[:3]))
        super().__setattr__("hidden_part", _hidden_part(self.tiles, self.open_part))
        super().__setattr__("tiles_with_kans", (*self.hidden_part, *(tile for call in self.calls for tile in call.tiles)))
        # for closed part, add any ankan back in as triplets
        closed_part = self.hidden_part
        for call in self.calls:
            if call.type == "ankan":
                closed_part = (*closed_part, call.tile, call.tile, call.tile)
        super().__setattr__("closed_part", closed_part)
        if len(self.tiles) in {1, 4, 7, 10, 13}:
            super().__setattr__("shanten", calculate_shanten(self.hidden_part))
        elif len(self.tiles) in {2, 5, 8, 11, 14}: # this disables the below
            super().__setattr__("shanten", self.prev_shanten)
        elif len(self.tiles) in {2, 5, 8, 11, 14}:
            # calculate the best shanten obtainable from this 14-tile hand"""
            best_shanten: Shanten = self.prev_shanten
            best_discards: List[int] = []
            for i, tile in enumerate(self.hidden_part):
                if self.prev_shanten[0] < 2 and tile not in self.prev_shanten[1]:
                    continue
                hand = (*self.hidden_part[:i], *self.hidden_part[i+1:])
                shanten = calculate_shanten(hand)
                (s1, w1), (s2, w2) = shanten, best_shanten
                if int(s1) < int(s2) or (int(s1) == int(s2) and len(w1) > len(w2)):
                    best_shanten = shanten
                    best_discards = []
                if shanten == best_shanten:
                    best_discards.append(tile)
            super().__setattr__("shanten", best_shanten)
            super().__setattr__("best_discards", sorted_hand(best_discards))
        else:
            assert False, f"passed a length {len(self.tiles)} hand to Hand"

    def to_str(self, doras: List[int] = [], uras: List[int] = []) -> str:
        to_str = lambda call: call.to_str(doras, uras)
        call_string = "" if len(self.calls) == 0 else "\u2007" + "\u2007".join(map(to_str, reversed(self.calls)))
        as_dora = lambda tile: tile + (100 if tile in doras or tile in uras else 0)
        hidden_part = tuple(map(as_dora, self.hidden_part))
        return f"{ph(hidden_part)}{call_string}"
    def __str__(self) -> str:
        return self.to_str()
    def __hash__(self) -> int:
        return hash((self.open_part, self.closed_part))

    def add(self, tile: int) -> "Hand":
        """Immutable update for drawing a tile"""
        return Hand((*self.tiles, tile), [*self.calls], [*self.ordered_calls], prev_shanten=self.shanten, kita_count=self.kita_count)
    def add_call(self, call: CallInfo) -> "Hand":
        """Immutable update for calling a tile"""
        return Hand(self.tiles, [*self.calls, call], [*self.ordered_calls, call], prev_shanten=self.shanten, kita_count=self.kita_count)
    def remove(self, tile: int) -> "Hand":
        """Immutable update for discarding a tile"""
        i = self.tiles.index(tile)
        return Hand((*self.tiles[:i], *self.tiles[i+1:]), [*self.calls], [*self.ordered_calls], prev_shanten=self.shanten, kita_count=self.kita_count)
    def kakan(self, called_tile: int) -> Tuple[int, "Hand"]:
        """Immutable update for adding a tile to an existing pon call (kakan)"""
        pon_index = next((i for i, calls in enumerate(self.calls) if calls.type == "pon" and normalize_red_five(calls.tile) == normalize_red_five(called_tile)), None)
        assert pon_index is not None, f"unable to find previous pon of {called_tile} in calls: {self.calls}"
        orig_direction = self.calls[pon_index].dir
        orig_tile = self.calls[pon_index].tile
        orig_tiles = (*self.calls[pon_index].tiles, called_tile)
        calls_copy = [*self.calls]
        call = CallInfo("kakan", orig_tile, orig_direction, orig_tiles)
        calls_copy[pon_index] = call
        return pon_index, Hand(self.tiles, calls_copy, [*self.ordered_calls, call], prev_shanten=self.shanten, kita_count=self.kita_count)
    def kita(self) -> "Hand":
        """Immutable update for adding kita"""
        calls_copy = [*self.calls]
        call = CallInfo("kita", 44, Dir.SELF, (44,))
        calls_copy.append(call)
        return Hand(self.tiles, calls_copy, [*self.ordered_calls, call], prev_shanten=self.prev_shanten, kita_count=self.kita_count+1)
    def print_hand_details(self,
                           ukeire: int,
                           final_tile: Optional[int] = None,
                           furiten: bool = False,
                           doras: List[int] = [],
                           uras: List[int] = []) -> str:
        """print this hand + calls + optional final tile + furiten state + shanten/waits + number of ukeire"""
        wait_string = ""
        win_string = ""
        as_dora = lambda tile: tile + (100 if tile in doras or tile in uras else 0)
        if self.shanten[0] == 0:
            wait_string = f"{' (furiten) ' if furiten else ' '}waits: {ph(sorted_hand(self.shanten[1]))} ({ukeire} out{'s' if ukeire > 1 else ''})"
            win_string = f"\u2007{pt(as_dora(final_tile))}" if final_tile is not None else ""
        elif self.shanten[0] > 0:
            wait_string = f" ({shanten_name(self.shanten)})"
        return f"{self.to_str(doras, uras)}{win_string}{wait_string}"
    def ukeire(self, visible: Iterable[int]) -> int:
        """
        Pass in all the visible tiles on board (not including hand).
        Return the ukeire of the hand, or 0 if the hand is not tenpai or iishanten.
        """
        shanten, waits = self.shanten
        if shanten >= 2:
            return 0
        relevant_tiles = set(normalize_red_fives(waits))
        visible = list(normalize_red_fives(list(self.tiles_with_kans) + list(visible)))
        return 4 * len(relevant_tiles) - sum(visible.count(wait) for wait in relevant_tiles)
    def get_majority_suit(self) -> Optional[Set[int]]:
        # returns one of {MANZU, PINZU, SOUZU}
        # or None if there is no majority suit (i.e. there's a tie)
        num_manzu = sum(1 for tile in self.tiles if tile in MANZU)
        num_pinzu = sum(1 for tile in self.tiles if tile in PINZU)
        num_souzu = sum(1 for tile in self.tiles if tile in SOUZU)
        if num_manzu > max(num_pinzu, num_souzu):
            return MANZU
        elif num_pinzu > max(num_manzu, num_souzu):
            return PINZU
        elif num_souzu > max(num_manzu, num_pinzu):
            return SOUZU
        else:
            return None
    def get_possible_tenpais(self) -> Dict[int, "Hand"]:
        if len(self.tiles) not in {2, 5, 8, 11, 14}:
            return {}
        if self.prev_shanten[0] >= 2:
            return {}
        return {tile: hand for tile in self.hidden_part for hand in (self.remove(tile),) if hand.shanten[0] == 0}
    def possible_chiis(self, tile: int) -> Iterable[CallInfo]:
        chiis = ((PRED[PRED[tile]], PRED[tile]), (PRED[tile], SUCC[tile]), (SUCC[tile], SUCC[SUCC[tile]]))
        return (CallInfo("chii", tile, Dir.KAMICHA, sorted_hand((*chii, tile)))
            for chii in chiis if all(tile in self.hidden_part for tile in chii))
