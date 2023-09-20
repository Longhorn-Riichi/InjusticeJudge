from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .classes import CallInfo, Dir, Interpretation
from .constants import Event, Shanten, MANZU, PINZU, SOUZU, LIMIT_HANDS, OYA_RON_SCORE, KO_RON_SCORE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, TRANSLATE
from .display import ph, pt, shanten_name
from .utils import is_mangan, normalize_red_five, normalize_red_fives, sorted_hand, try_remove_all_tiles
from .shanten import calculate_shanten

# these classes depend on shanten.py, which depends on classes.py, so we can't put them in classes.py

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

    def to_str(self, doras=[], uras=[]) -> str:
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
    def kakan(self, called_tile: int):
        """Immutable update for adding a tile to an existing pon call (kakan)"""
        pon_index = next((i for i, calls in enumerate(self.calls) if calls.type == "pon" and normalize_red_five(calls.tile) == normalize_red_five(called_tile)), None)
        assert pon_index is not None, f"unable to find previous pon in calls: {self.calls}"
        orig_direction = self.calls[pon_index].dir
        orig_tiles = [*self.calls[pon_index].tiles, called_tile]
        calls_copy = [*self.calls]
        call = CallInfo("kakan", called_tile, orig_direction, orig_tiles)
        calls_copy[pon_index] = call
        return Hand(self.tiles, calls_copy, [*self.ordered_calls, call], prev_shanten=self.shanten, kita_count=self.kita_count)
    def kita(self):
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
    def ukeire(self, visible: Iterable[int]):
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

# takes in "場風 東(1飜)", "ドラ(2飜)", "裏ドラ(1飜)"
# outputs ("ton", 1), ("dora 2", 2), ("ura", 1)
def translate_tenhou_yaku(yaku: str) -> Tuple[str, int]:
    name, rest = yaku.split("(")
    name = TRANSLATE[name]
    if "役満" in yaku: # e.g. "大三元(役満)"
        han = 13
    else: # e.g. "ドラ(2飜)"
        han = int(rest.split("飜")[0])
    if name in {"dora", "aka", "ura", "kita"} and han > 1:
        name = f"{name} {han}"
    return name, han

@dataclass
class Score:
    """Generated score for a given hand (does NOT come from parsed game result scores)"""
    yaku: List[Tuple[str, int]] # list of ("yaku name", han value)
    han: int                    # total han for those yaku
    fu: int                     # total fu for some interpretation of the hand
    is_dealer: bool             # whether it was dealer win (for calculating points)
    tsumo: bool                 # whether it was a tsumo (for calculating points)
    num_players: int            # number of players (for calculating tsumo points)
    def __hash__(self):
        return hash((self.fu, tuple(self.yaku)))
    def __lt__(self, other):
        return (self.han, self.fu) < (other.han, other.fu)
    def __str__(self):
        ret = f"{self.han}/{self.fu} {self.yaku}"
        if self.interpretation is not None:
            ret += f" ({self.interpretation!s})"
        return ret
    def add_dora(self, dora_type: str, amount: int):
        # get the current amount
        i = self.get_dora_index(dora_type)
        if i is None:
            if amount >= 1:
                new_dora = (dora_type + f" {amount}", amount)
                self.yaku.append(new_dora)
        else:
            new_value = self.yaku[i][1] + amount
            # apply the change
            if new_value == 0:
                del self.yaku[i]
            else:
                new_dora = (dora_type + (f" {new_value}" if new_value > 1 else ""), new_value)
                self.yaku[i] = new_dora
        self.han += amount
    def to_points(self):
        if self.tsumo:
            assert self.num_players is not None
            oya = OYA_TSUMO_SCORE[self.han][self.fu]  # type: ignore[index]
            ko = oya if self.is_dealer else KO_TSUMO_SCORE[self.han][self.fu]  # type: ignore[index]
            return oya + (self.num_players-2)*ko
        else:
            return (OYA_RON_SCORE if self.is_dealer else KO_RON_SCORE)[self.han][self.fu]  # type: ignore[index]
    def to_score_deltas(self, round: int, honba: int, winners: List[int], payer: int, pao_seat: Optional[int] = None) -> List[int]:
        score_deltas = [0]*self.num_players
        if pao_seat is not None:
            assert len(winners) == 1, "don't know how to handle pao when there's a multiple ron"
            winner = winners[0]
            oya_payment = winner == round%4
            points = (OYA_RON_SCORE if oya_payment else KO_RON_SCORE)[self.han][self.fu]  # type: ignore[index]
            score_deltas[winner] += points
            if self.tsumo:
                score_deltas[pao_seat] -= points
            else:
                score_deltas[payer] -= points//2
                score_deltas[pao_seat] -= points//2
        else:
            if self.tsumo:
                assert len(winners) == 1
                for payer in set(range(self.num_players)) - {winners[0]}:
                    oya_payment = (winners[0] == round%4) or (payer == round%4)
                    score_deltas[payer] -= (OYA_TSUMO_SCORE if oya_payment else KO_TSUMO_SCORE)[self.han][self.fu]  # type: ignore[index]
                    score_deltas[payer] -= 100 * honba
                score_deltas[payer] -= sum(score_deltas)
            else:
                for winner in winners:
                    oya_payment = winner == round%4
                    score_deltas[winner] += (OYA_RON_SCORE if oya_payment else KO_RON_SCORE)[self.han][self.fu]  # type: ignore[index]
                    score_deltas[winner] += 300 * honba
                score_deltas[winner] -= sum(score_deltas)
        return score_deltas
    def has_riichi(self) -> bool:
        return ("riichi", 1) in self.yaku
    def has_ippatsu(self) -> bool:
        return ("ippatsu", 1) in self.yaku
    def has_haitei(self) -> bool:
        return ("haitei", 1) in self.yaku or ("houtei", 1) in self.yaku
    def get_dora_index(self, dora_type) -> Optional[int]:
        for i, (name, value) in enumerate(self.yaku):
            if name.startswith(dora_type):
                return i
        return None
    def count_dora(self) -> int:
        dora_index = self.get_dora_index("dora")
        aka_index = self.get_dora_index("aka")
        dora = self.yaku[dora_index][1] if dora_index is not None else 0
        aka = self.yaku[aka_index][1] if aka_index is not None else 0
        return dora + aka
    def count_ura(self) -> int:
        ura_index = self.get_dora_index("ura")
        ura = self.yaku[ura_index][1] if ura_index is not None else 0
        return ura
    def is_yakuless(self) -> bool:
        for y, _ in self.yaku:
            if not y.startswith(("dora", "ura", "aka", "kita")):
                return False
        return True
    def get_limit_hand_name(self):
        if self.han >= 6 or is_mangan(self.han, self.fu):
            return TRANSLATE[LIMIT_HANDS[self.han]]
        return ""
    @classmethod
    def from_tenhou_list(cls, tenhou_result_list: List[Any],
                              round: int,
                              num_players: int,
                              kita: int = 0):
        w, won_from, _, score_str, *yaku_strs = tenhou_result_list
        is_dealer = w == round%4
        is_tsumo = w == won_from
        dora_index: Optional[int] = None
        yaku_dora: int = 0
        yaku_kita: int = 0
        if not any("役満" in y for y in yaku_strs): # not a yakuman hand
            # add in missing kita yaku (tenhou counts kita as normal dora)
            for i, y in enumerate(yaku_strs):
                name_str, han_str = y.split("(")
                name = TRANSLATE[name_str]
                han = int(han_str.split("飜")[0])
                if "dora" in name:
                    dora_index = i # keep track of where "dora" is in the list
                    yaku_dora += han
                elif name == "aka":
                    yaku_dora += han
                elif name == "kita":
                    yaku_kita = han
            if kita > 0 and yaku_kita == 0:
                assert dora_index is not None, f"somehow we know there's {kita} kita, but tenhou didn't count it as dora?"
                # must be a Tenhou sanma game hand with kita because
                # it counts kita as regular dora (not "抜きドラ")
                non_kita_dora_count = yaku_dora - kita
                assert non_kita_dora_count >= 0
                if non_kita_dora_count == 0:
                    del yaku_strs[dora_index]
                else:
                    yaku_strs[dora_index] = f"ドラ({non_kita_dora_count}飜)"
                yaku_strs.append(f"抜きドラ({kita}飜)")

        # convert yaku_strs=["立直(1飜)", "一発(1飜)"] into yaku=[("riichi", 1), ("ippatsu", 1)]
        yaku: List[Tuple[str, int]] = list(map(translate_tenhou_yaku, yaku_strs))

        # grab han/fu from yaku/score_str, respectively
        # score_str is "30符1飜1000点", "50符3飜1600-3200点" if below mangan
        # otherwise, it's "倍満16000点", "満貫4000点∀", "満貫2000-4000点"
        # extract fu if below mangan, otherwise set it to 70 if mangan+
        han = sum(han for _, han in yaku)
        assert han > 0, f"somehow got a {han} han score"
        fu = int(score_str.split("符")[0]) if "符" in score_str else 70
        return cls(yaku, han, fu, is_dealer, is_tsumo, num_players)

    # these fields are only for debug use
    interpretation: Optional[Interpretation] = None # the interpretation used to calculate yaku and fu
    hand: Optional[Hand] = None                     # the original hand

@dataclass(frozen = True)
class Win:
    score_delta: List[int]  # list of score differences for this round
    winner: int             # winner's seat (0-3)
    dama: bool              # whether it was a dama hand or not
    score: Score            # Score object (contains han, fu, score, and yaku list)
    pao_from: Optional[int] # if not None, it's the seat that pays pao (sekinin barai)
@dataclass(frozen = True)
class Ron(Win):
    """Parsed version of a single tenhou ron result"""
    won_from: int           # loser's seat (0-3)
@dataclass(frozen = True)
class Tsumo(Win):
    """Parsed version of a tenhou tsumo result"""
    pass
@dataclass(frozen = True)
class Draw:
    """Parsed version of a tenhou ryuukyoku or any draw result"""
    score_delta: List[int] # list of score differences for this round
    name: str              # name of the draw, e.g. "ryuukyoku"

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
    riichi_sticks: int                            = 0
    num_players: int                              = 0
    final_draw: int                               = 0
    final_discard: int                            = 0
    final_draw_seat: int                          = 0
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
    starting_doras: List[int]                     = field(default_factory=list)
    uras: List[int]                               = field(default_factory=list)

    # The result of the kyoku in the format (type, result object(s))
    # either ("ron", Ron(...), ...) for a (single, double, triple) ron
    #     or ("tsumo", Tsumo(...)) for a tsumo
    #     or ("ryuukyoku", Draw(...)) for a ryuukyoku
    #     or ("draw", Draw(...)) for a draw
    result: Tuple[Any, ...]                       = ()

    # for each player, we keep track of the current state of that player
    # this is represented by several lists indexed by seat, below
    # `hands` keeps track of hand, calls, shanten
    hands: List[Hand]                             = field(default_factory=list)
    # `pond` keeps track of all discards so far by each player
    pond: List[List[int]]                         = field(default_factory=list)
    # `furiten` keeps track of whether a player is in furiten
    furiten: List[bool]                           = field(default_factory=list)

    # we also keep track of some facts for each player
    # store the scores of each player at the beginning of the kyoku
    start_scores: Tuple[int, ...]                 = ()
    # store the starting hand of each player
    haipai: List[Hand]                            = field(default_factory=list)
    # store each player's ukeire count at the start and the end of a round (if tenpai)
    # -1 if the player is not tenpai
    haipai_ukeire: List[int]                      = field(default_factory=list)
    final_ukeire: List[int]                       = field(default_factory=list)
    def get_starting_score(self):
        return (sum(self.start_scores) + 1000*self.riichi_sticks) // self.num_players
