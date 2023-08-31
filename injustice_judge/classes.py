from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .constants import TOGGLE_RED_FIVE
from .utils import ph, pt, pt_sideways, remove_red_five, remove_red_fives, shanten_name, sorted_hand, try_remove_all_tiles
from .shanten import calculate_shanten

# This file contains most of the classes used in InjusticeJudge.
# It also contains some printing logic in the form of __str__ overloads.

@dataclass
class ResultYakuList:
    """Parsed version of tenhou's game result yaku list"""
    yaku_strs: List[str]   # the raw list of yaku
    dora: int = 0          # count of all round dora and aka
    ura: int = 0           # count of ura
    kita: int = 0          # count of kita (sanma)
    riichi: bool = False   # is riichi in the list?
    ippatsu: bool = False  # is ippatsu in the list?
    haitei: bool = False   # is haitei/houtei in the list?

@dataclass(frozen = True)
class Ron:
    """Parsed version of a single tenhou ron result"""
    score_delta: List[int] # list of score differences for this round
    winner: int            # winner's seat (0-3)
    won_from: int          # loser's seat (0-3)
    dama: bool             # whether it was a dama hand or not
    han: int               # han for the winning hand
    fu: int                # fu for the winning hand
    limit_name: str        # e.g. "mangan", or empty string if not a limit hand
    score_string: str      # raw score string, e.g. "30符1飜1000点"
    score: int             # parsed score; e.g. 1000 for the above string
    yaku: ResultYakuList   # parsed yaku list
@dataclass(frozen = True)
class Tsumo:
    """Parsed version of a tenhou tsumo result"""
    score_delta: List[int] # list of score differences for this round
    winner: int            # winner's seat (0-3)
    dama: bool             # whether it was a dama hand or not
    han: int               # han for the winning hand
    fu: int                # fu for the winning hand
    limit_name: str        # e.g. "mangan", or empty string if not a limit hand
    score_string: str      # raw score string, e.g. "50符3飜1600-3200点"
    score_oya: int         # parsed oya score; e.g. 3200 for the above string
    score_ko: int          # parsed ko score; e.g. 1600 for the above string
    score: int             # total score; e.g. 6400 for the above string (if it's yonma)
    yaku: ResultYakuList   # parsed yaku list
@dataclass(frozen = True)
class Draw:
    """Parsed version of a tenhou ryuukyoku or any draw result"""
    score_delta: List[int] # list of score differences for this round
    name: str              # name of the draw, e.g. "ryuukyoku"




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

@functools.cache
def _hidden_part(hand: Tuple[int], calls: Tuple[int]) -> Tuple[int, ...]:
    """Cached helper for getting the hidden part of a hand, used below in __post_init__"""
    ret = try_remove_all_tiles(hand, calls)
    assert len(ret) + len(calls) == len(hand), f"with hand = {ph(hand)} and calls = {ph(calls)}, somehow hidden part is {ph(ret)}"
    return ret

# main hand class
@dataclass(frozen=True)
class Hand:
    """Immutable object describing the state of a single hand"""
    tiles: Tuple[int, ...]                              # all tiles in the hand
    calls: List[CallInfo] = field(default_factory=list) # every call the hand has made, in order
    open_part: Tuple[int, ...] = ()                     # all tiles currently shown as a call
    hidden_part: Tuple[int, ...] = ()                   # tiles - open_part
    closed_part: Tuple[int, ...] = ()                   # hidden_part + any ankans
    shanten: Tuple[float, List[int]] = (-1, [])         # shanten for the hand, or -1 if the hand is 14 tiles
                                                        # (like when it's in the middle of a draw or call)
    prev_shanten: Tuple[float, List[int]] = (-1, [])    # shanten for the hand right before said draw or call
    def __post_init__(self):
        """You only need to provide `tiles` (and `calls`, if any), this calculates the rest"""
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
        else:
            super().__setattr__("shanten", self.prev_shanten)
    def __str__(self):
        call_string = "" if len(self.calls) == 0 else "⠀" + "⠀".join(map(str, reversed(self.calls)))
        return f"{ph(self.hidden_part)}{call_string}"
    def __hash__(self):
        return hash((self.open_part, self.closed_part))

    def add(self, tile: int) -> "Hand":
        """Immutable update for drawing a tile"""
        return Hand((*self.tiles, tile), [*self.calls], prev_shanten=self.shanten)
    def add_call(self, calls: CallInfo) -> "Hand":
        """Immutable update for calling a tile"""
        return Hand(self.tiles, [*self.calls, calls], prev_shanten=self.shanten)
    def remove(self, tile: int) -> "Hand":
        """Immutable update for discarding a tile"""
        tiles = list(self.tiles)
        tiles.remove(tile)
        return Hand(tuple(tiles), [*self.calls], prev_shanten=self.shanten)
    def kakan(self, called_tile):
        """Immutable update for adding a tile to an existing pon call (kakan)"""
        pon_index = next((i for i, calls in enumerate(self.calls) if calls.type == "pon" and calls.tile == called_tile), None)
        assert pon_index is not None, f"unable to find previous pon in calls: {self.calls}"
        orig_direction = self.calls[pon_index].dir
        orig_tiles = [*self.calls[pon_index].tiles, called_tile]
        calls_copy = [*self.calls]
        calls_copy[pon_index] = CallInfo("kakan", called_tile, orig_direction, orig_tiles)
        return Hand(self.tiles, calls_copy, prev_shanten=self.shanten)
    def print_hand_details(self, ukeire: int, final_tile: Optional[int] = None, furiten: bool = False) -> str:
        """print this hand + calls + optional final tile + furiten state + shanten/waits + number of ukeire"""
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

YakuForWait = Dict[int, List[Tuple[str, int]]]
@dataclass
class Score:
    """Generated score for a given hand (does NOT come from parsed game result scores)"""
    yaku: List[Tuple[str, int]] # list of ("yaku name", han value)
    han: int                    # total han for those yaku
    fu: int                     # total fu for some interpretation of the hand
    tsumo: bool
    def __hash__(self):
        return hash((self.fu, tuple(self.yaku)))
    def __lt__(self, other):
        return (self.han, self.fu) < (other.han, other.fu)
    def __str__(self):
        return f"{self.han}/{self.fu} {self.yaku} ({self.interpretation!s})"
    # these fields are only for debug use
    interpretation: Interpretation # the interpretation used to calculate yaku and fu
    hand: Hand                     # the original hand


Event = Tuple[Any, ...]
@dataclass
class Kyoku:
    """
    Main state object representing a single round
    Generated in `fetch.py` for use in `flags.py`
    The idea is to store enough data to be able to get all the facts about a round
    This gets turned into a list of facts about a round (see flags.py)
    """
    # Some basic facts about this kyoku
    round: int                                    = 0
    honba: int                                    = 0
    num_players: int                              = 0
    final_draw: int                               = 0
    final_discard: int                            = 0
    tiles_in_wall: int                            = 0
    is_final_round: bool                          = False

    # Events describing what happened in this kyoku
    # Each event is of the form (seat, event type, *event data)
    # e.g. (2, "draw", 34) means original West seat drew 4 sou
    events: List[Event]                           = field(default_factory=list)

    # Index of the final "draw" and "discard" events for each player
    # Used to check if a given event is a player's last draw/discard
    final_draw_event_index: List[int]             = field(default_factory=list)
    final_discard_event_index: List[int]          = field(default_factory=list)

    # doras include the round doras AND the red fives; there can be multiple of the same dora tile
    doras: List[int]                              = field(default_factory=list)
    uras: List[int]                               = field(default_factory=list)

    # The result of the kyoku in the format (type, result object(s))
    # either ("ron", Ron(...), ...) for a (double, triple) ron
    #     or ("tsumo", Tsumo(...)) for a tsumo
    #     or ("draw", Draw(...)) for a draw
    result: Tuple[Any, ...]                       = ()

    # for each player, we keep track of the current state of that player
    # this is represented by several lists indexed by seat, below
    # `hands` keeps track of hand, calls, shanten
    hands: List[Hand]                             = field(default_factory=list)
    # `pond` keeps track of all discards so far
    pond: List[List[int]]                         = field(default_factory=list)
    # `furiten` keeps track of whether a player is in furiten
    furiten: List[bool]                           = field(default_factory=list)
    # `kita_counts` keeps track of how many times one has called kita
    kita_counts: List[int]                        = field(default_factory=list)

    # we also keep track of some facts for each player
    # store the scores of each player at the beginning of the kyoku
    start_scores: List[int]                       = field(default_factory=list)
    # store the starting hand of each player
    haipai: List[Hand]                            = field(default_factory=list)
    # store each player's ukeire count at the start and the end of a round (if tenpai)
    # -1 if the player is not tenpai
    haipai_ukeire: List[int]                      = field(default_factory=list)
    final_ukeire: List[int]                       = field(default_factory=list)

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
    use_red_fives: bool              # whether the game uses red fives (only checks tenhou right now)
