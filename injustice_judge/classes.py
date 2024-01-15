from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .constants import PRED, SUCC, TOGGLE_RED_FIVE, YAOCHUUHAI
from .display import ph, pt, shanten_name
from .utils import apply_delta_scores, get_waits, normalize_red_five, normalize_red_fives, sorted_hand, to_placement, try_remove_all_tiles

# This file and classes2.py contain most of the classes used in InjusticeJudge.
# In this file, we have:
# - Dir: enum representing the direction of a call.
# - CallInfo: stores all information about a call (name, tiles, direction)
# - Interpretation: represents one way to break up a given hand into sets and a pair.
# - GameRules: parses all game rules that InjusticeJudge cares about.
# - GameMetadata: stores data about the players and round-to-round scores of a game.

class Dir(IntEnum):
    """Enum representing a direction, add to a seat mod 4 to get the indicated seat"""
    SELF     = 0
    SHIMOCHA = 1
    TOIMEN   = 2
    KAMICHA  = 3

@dataclass(frozen=True)
class CallInfo:
    """Immutable object describing a single call (chii, pon, daiminkan, ankan, kakan)"""
    type: str              # one of "chii", "pon", "minkan", "ankan", "kakan"
    tile: int              # the called tile (the one that is technically in the pond, if not ankan/kakan)
    dir: Dir               # where the tile was called from (indicates where to point the called tile)
    tiles: Tuple[int, ...] # the 3 or 4 tiles set aside after calling
    def __post_init__(self) -> None:
        super().__setattr__("tiles", sorted_hand(self.tiles))
    def to_str(self, doras: List[int] = [], uras: List[int] = []) -> str:
        # other_tiles is all the non-called tiles in the call
        d = doras+uras
        other_tiles = try_remove_all_tiles(self.tiles, (self.tile,))
        sideways = pt(self.tile, doras=d, is_sideways=True)
        if self.type == "ankan":
            if any(tile in {51,52,53} for tile in self.tiles):
                return ph((50, TOGGLE_RED_FIVE[self.tile], self.tile, 50), doras=d)
            else:
                return ph((50, self.tile, self.tile, 50), doras=d)
        elif self.type == "kita":
            return pt(self.tile, doras=d)
        elif self.type == "kakan": # print two consecutive sideways tiles
            sideways = pt(other_tiles[0], doras=d, is_sideways=True) + sideways
            other_tiles = other_tiles[1:]
        if self.dir == Dir.SHIMOCHA:
            return ph(other_tiles, doras=d) + sideways
        elif self.dir == Dir.TOIMEN:
            return pt(other_tiles[0], doras=d) + sideways + ph(other_tiles[1:], doras=d)
        elif self.dir == Dir.KAMICHA:
            return sideways + ph(other_tiles, doras=d)
        assert False, f"Somehow got Dir.SELF for a non-ankan call {self!r}"
        # dir == Dir.SELF is only for ankan and is handled above
    def __str__(self) -> str:
        return self.to_str()
    
add_group = lambda groups, group: tuple(sorted((*groups, tuple(sorted(group)))))

# hand interpretations and yaku
@dataclass
class Interpretation:
    """A single interpretation of a single hand (decomposed into triplets, sequences, and pair)"""
    hand: Tuple[int, ...]                           # The non-decomposed part of the original hand
    ron_fu: int = 20                                # ron fu using this interpretation of the hand (not rounded)
    tsumo_fu: int = 22                              # tsumo fu using this interpretation of the hand (not rounded)
    sequences: Tuple[Tuple[int, ...], ...] = ()     # Sequences taken from the original hand
    triplets: Tuple[Tuple[int, ...], ...] = ()      # Triplets taken from the original hand
    pair: Optional[Tuple[int, int]] = None          # A pair taken from the original hand
    calls: Tuple[CallInfo, ...] = ()                # A frozen list of calls from the original hand
    def unpack(self) -> Tuple[Any, ...]:
        return (self.hand, self.ron_fu, self.tsumo_fu, self.sequences, self.triplets, self.pair)
    def __hash__(self) -> int:
        return hash(self.unpack())
    def __str__(self) -> str:
        full_hand = (*self.sequences, *self.triplets, self.pair, self.hand) if self.pair is not None else (*self.sequences, *self.triplets, self.hand)
        return " ".join(map(ph, full_hand)) + f" ron {self.ron_fu} tsumo {self.tsumo_fu}" + ("" if len(self.calls) == 0 else f" ({len(self.calls)} calls)")
    def is_shanpon(self) -> bool:
        hand = tuple(normalize_red_fives(self.hand))
        return self.pair is not None and hand[0] == hand[1]
    def get_waits(self) -> Set[int]:
        hand = tuple(normalize_red_fives(self.hand))
        if len(hand) == 1: # tanki
            return {hand[0]}
        elif len(hand) == 2:
            assert self.pair is not None
            if hand[0] == hand[1]: # shanpon
                return {hand[0]} # don't include pair as a wait
            else: # ryanmen, kanchan, penchan
                return get_waits(hand)
        elif len(hand) == 13: # chiitoi or kokushi
            ctr = Counter(hand)
            if tuple(ctr.values()).count(2) == 6: # chiitoi
                return {tile for tile, num in ctr.items() if num == 1}
            elif set(hand).issubset(YAOCHUUHAI): # kokushi
                kokushi_wait = YAOCHUUHAI - set(hand)
                if len(kokushi_wait) == 1:
                    return kokushi_wait
                elif len(kokushi_wait) == 0: # 13-way wait
                    return YAOCHUUHAI
        return set()
    def add_triplet(self, triplet: Tuple[int, int, int], call: bool = False, closed: bool = True, kan: bool = False) -> "Interpretation":
        triplet_fu = (4 if triplet[0] in YAOCHUUHAI else 2) * (2 if closed else 1) * (4 if kan else 1)
        # print(f"add {triplet_fu} for closed triplet {ph(triplet)}, {ph(self.hand)}")
        return Interpretation(self.hand if call else try_remove_all_tiles(self.hand, triplet),
                              self.ron_fu + triplet_fu,
                              self.tsumo_fu + triplet_fu,
                              self.sequences,
                              add_group(self.triplets, triplet),
                              self.pair, calls=self.calls)
    def add_sequence(self, sequence: Tuple[int, int, int], call: bool = False) -> "Interpretation":
        return Interpretation(self.hand if call else try_remove_all_tiles(self.hand, sequence),
                              self.ron_fu,
                              self.tsumo_fu,
                              add_group(self.sequences, sequence),
                              self.triplets,
                              self.pair, calls=self.calls)
    def add_pair(self, pair: Tuple[int, int], yakuhai: Tuple[int, ...]) -> "Interpretation":
        if self.pair is None:
            yakuhai_fu = 2 * yakuhai.count(pair[0])
            # print(f"add {yakuhai_fu} for yakuhai pair {ph(pair)}, {ph(self.hand)}")
            return Interpretation(try_remove_all_tiles(self.hand, pair),
                                  self.ron_fu + yakuhai_fu,
                                  self.tsumo_fu + yakuhai_fu,
                                  self.sequences, self.triplets,
                                  pair, calls=self.calls)
        return self
    def add_wait_fu(self, yakuhai: Tuple[int, ...]) -> bool:
        """return True if the final wait is valid"""
        if len(self.hand) == 2:
            # taatsu wait -- might be a single wait
            is_shanpon = self.is_shanpon()
            waits = self.get_waits()
            if is_shanpon or len(waits) > 0:
                single_wait_fu = 2 if (len(waits) == 1 and not is_shanpon) else 0
                self.ron_fu += single_wait_fu
                self.tsumo_fu += single_wait_fu
                # print(f"add {single_wait_fu} for single wait {ph(self.hand)}")
                return True
        elif len(self.hand) == 1:
            # tanki wait -- is a single wait, and might be yakuhai
            yakuhai_fu = 2 * yakuhai.count(self.hand[0])
            self.ron_fu += yakuhai_fu + 2
            self.tsumo_fu += yakuhai_fu + 2
            # print(f"add 2 for single wait {pt(self.hand[0])}")
            # print(f"add {yakuhai_fu} for yakuhai pair {pt(self.hand[0])}")
            return True
        return False
    def generate_all_interpretations(self, yakuhai: Tuple[int, ...] = (), is_closed_hand: bool = False) -> Set["Interpretation"]:
        """
        From this Interpretation, remove all combinations of sequences,
        triplets, and pair from self.hand to arrive at several
        Interpretations. Calculates fu obtained in the process, requiring you
        pass in the yakuhai tiles. Doesn't take into account the fu obtained
        by completing a triplet as a final wait (shanpon fu) -- that's taken
        care of in `get_yaku` in yaku.py.

        Note: calling this will reset self.ron_fu and self.tsumo_fu
        """

        base_interpretation = self
        self.ron_fu = 20 + (10 if is_closed_hand else 0)
        self.tsumo_fu = 22

        # the call info forces some sequences/triplets
        for call in self.calls:
            mktuple = lambda t: cast(Tuple[int, int, int], tuple(t))
            if call.type == "chii":
                base_interpretation = base_interpretation.add_sequence(mktuple(call.tiles), call=True)
            elif call.type == "pon":
                base_interpretation = base_interpretation.add_triplet(mktuple(call.tiles), call=True, closed=False)
            elif "kan" in call.type: 
                base_interpretation = base_interpretation.add_triplet(mktuple(call.tiles[:3]), call=True, closed=(call.type == "ankan"), kan=True)

        # finally, iterate through all possible interpretations of the hand
        interpretations: Set[Interpretation] = set()
        to_update: Set[Interpretation] = {base_interpretation}
        already_processed: Set[Tuple[int, ...]] = set()

        while len(to_update) > 0:
            interpretation = to_update.pop()
            # skip if we've already seen this one
            if interpretation.hand in already_processed:
                continue
            else:
                already_processed.add(interpretation.hand)
            # either output the interpretation, or recurse with smaller hands
            if len(interpretation.hand) <= 2:
                if interpretation.add_wait_fu(yakuhai):
                    interpretations.add(interpretation)
            else:
                for tile in set(interpretation.hand):
                    tile2 = normalize_red_five(tile) # non red version
                    nodes = [interpretation.add_triplet((tile, tile2, tile2)),
                             interpretation.add_sequence((SUCC[SUCC[tile]], SUCC[tile], tile)),
                             interpretation.add_pair((tile, tile2), yakuhai=yakuhai)]
                    to_update |= {n for n in nodes if n is not None}

            # special case: aryanmen pinfu requires a single sequence remain unprocessed
            if len(interpretation.hand) == 1:
                # check pinfu conditions
                no_calls_except_kita = all(call.type == "kita" for call in self.calls)
                all_sequences = len(interpretation.sequences) == 4
                no_yakuhai_pair = interpretation.hand[0] not in yakuhai
                if no_calls_except_kita and all_sequences and no_yakuhai_pair:
                    # interpret as aryanmen wait for pinfu
                    tanki = interpretation.hand[0]
                    # look for sequences that form aryanmen with the tanki,
                    # where the ryanmen part is not penchan
                    for i, (t1,t2,t3) in enumerate(interpretation.sequences):
                        remaining_seqs = (*interpretation.sequences[:i], *interpretation.sequences[i+1:])
                        if tanki == t1 and SUCC[t3] != 0:
                            interpretations.add(Interpretation((t2,t3), 30, 22, remaining_seqs, interpretation.triplets, (tanki, tanki), calls=self.calls))
                        elif tanki == t3 and PRED[t1] != 0:
                            interpretations.add(Interpretation((t1,t2), 30, 22, remaining_seqs, interpretation.triplets, (tanki, tanki), calls=self.calls))
            
        return interpretations if len(interpretations) > 0 else {self}

@dataclass
class GameRules:
    """Stores all the rules that InjusticeJudge cares about."""
    num_players: int = 4              # number of players
    has_double_yakuman: bool = True   # whether the game treats certain yakuman as double
    use_red_fives: bool = True        # whether the game uses red fives
    immediate_kan_dora: bool = False  # whether kan immediately reveals a dora
    head_bump: bool = False           # whether head bump is enabled
    renhou: bool = False              # whether renhou is enabled
    kiriage_mangan: bool = False      # whether kiriage mangan is enabled
    nagashi_mangan: bool = True       # whether nagashi mangan is enabled
    double_round_wind: bool = False   # whether double round wind is enabled (E = E+W; S = S+N)
    double_wind_4_fu: bool = True     # whether a round+seat wind pair is worth 4 fu
    starting_doras: int = 1           # number of doras started with
    riichi_value: int = 1000          # value of riichi bet
    honba_value: int = 100            # value of each honba (continuation stick) per player
    noten_payment: Tuple[int, int, int] = (1000, 1500, 3000) # noten payment paid for 1/2/3 players tenpai
    is_hanchan: bool = True           # if the game is a hanchan
    is_sanma: bool = True             # if the game is 3 player
    starting_points: int = 25000      # starting points
    total_points: int = 25000         # total points (difference is given to 1st place for placement bonus)
    placement_bonus: List[List[float]] = field(default_factory=list)
    @classmethod
    def from_majsoul_detail_rule(cls, num_players: int, rules: Dict[str, Any], mode: int) -> "GameRules":
        # see GameDetailRule in liqi_combined.proto to find all the valid field names
        # note: the python protobuf library converts every name to camelCase
        if "shunweima2" not in rules and "shunweima3" not in rules and "shunweima4" not in rules:
            placement_bonus = []
        else:
            placement_bonus = 5*[[rules.get("shunweima2", 0), rules.get("shunweima3", 0), rules.get("shunweima4", 0)]][:num_players]
        return cls(num_players = num_players,
                   has_double_yakuman = True,
                   use_red_fives = rules.get("doraCount", 3) > 0,
                   immediate_kan_dora = rules.get("mingDoraImmediatelyOpen", False),
                   head_bump = rules.get("haveToutiao", False),
                   renhou = rules.get("enableRenhe", False),
                   kiriage_mangan = rules.get("haveQieshangmanguan", False),
                   nagashi_mangan = rules.get("haveLiujumanguan", True),
                   double_round_wind = False,
                   double_wind_4_fu = not rules.get("disableDoubleWindFourFu", False),
                   starting_doras = 3 if rules.get("dora3Mode", False) else 1,
                   riichi_value = rules.get("liqibang_value", 1000),
                   honba_value = rules.get("changbang_value", 100),
                   noten_payment = (rules.get("noting_fafu_1", 1000), rules.get("noting_fafu_2", 1500), rules.get("noting_fafu_3", 3000)),
                   # mode: 1,2,11,12 = 4p east, 4p south, 3p east, 3p south
                   is_hanchan = mode % 10 == 2,
                   is_sanma = mode > 10,
                   starting_points = rules.get("init_point", 35000 if num_players == 3 else 25000),
                   total_points = rules.get("jingsuanyuandian", 35000 if num_players == 3 else 25000),
                   placement_bonus = placement_bonus
                   )
    @classmethod
    def from_tenhou_rules(cls, num_players: int, rule: List[str], csrule: List[str]) -> "GameRules":
        # see example_arml_game.json for info on how this is parsed
        if isinstance(rule, dict):
            # normal game
            return cls(use_red_fives = "aka51" in rule and rule["aka51"])
        # lobby game
        rule1 = int(rule[2] or "0", 16)
        rule2 = int(csrule[0] or "0", 16)
        rule3 = int(csrule[1] or "0", 16)
        f0 = lambda s: float(s or 0)
        if all(v == "" for v in csrule[21:35]):
            placement_bonus = []
        else:
            placement_bonus = [[f0(csrule[21]), f0(csrule[22]), f0(csrule[23])],
                               [f0(csrule[24]), f0(csrule[25]), f0(csrule[26])],
                               [f0(csrule[27]), f0(csrule[28]), f0(csrule[29])],
                               [f0(csrule[30]), f0(csrule[31]), f0(csrule[32])],
                               [f0(csrule[33]), f0(csrule[34]), f0(csrule[35])]]
        return cls(num_players = num_players,
                   has_double_yakuman = False,
                   use_red_fives = 0x0002 & rule1 == 0,
                   immediate_kan_dora = 0x00000008 & rule2 != 0,
                   head_bump = 0x00002000 & rule2 != 0,
                   renhou = 0x01000000 & rule2 != 0,
                   kiriage_mangan = 0x00000002 & rule2 != 0,
                   nagashi_mangan = 0x00000001 & rule2 != 0,
                   double_round_wind = 0x00100000 & rule2 != 0,
                   double_wind_4_fu = 0x00000001 & rule3 == 0,
                   starting_doras = 1,
                   riichi_value = int(csrule[10] or 1000),
                   honba_value = int(csrule[10] or 100),
                   noten_payment = (int(csrule[16] or 1000), int(csrule[17] or 1500), int(csrule[18] or 3000)),
                   is_hanchan = 0x0008 & rule1 != 0,
                   is_sanma = 0x0010 & rule1 != 0,
                   starting_points = int(csrule[4] or 35000 if num_players == 3 else 25000),
                   total_points = int(csrule[6] or 35000 if num_players == 3 else 25000),
                   placement_bonus = placement_bonus)
    @classmethod
    def from_riichicity_metadata(cls, num_players: int, metadata: Dict[str, Any]) -> "GameRules":
        return cls(num_players = num_players,
                   has_double_yakuman = True,
                   use_red_fives = True,
                   immediate_kan_dora = True,
                   head_bump = False,
                   renhou = False,
                   kiriage_mangan = False,
                   nagashi_mangan = True,
                   double_round_wind = False,
                   double_wind_4_fu = True,
                   starting_doras = 1,
                   riichi_value = 1000,
                   honba_value = 100,
                   noten_payment = (1000, 1500, 3000),
                   is_hanchan = metadata["round"] == 2,
                   is_sanma = num_players == 3,
                   starting_points = 35000 if num_players == 3 else 25000,
                   total_points = 40000 if num_players == 3 else 30000,
                   placement_bonus = []
                   )
    
    def calculate_placement_bonus(self, final_points: List[int], final_scores: List[float]):
        if len(self.placement_bonus) == 0:
            to_bonus = lambda p, s: round(s-float((p-self.starting_points)/1000))
            bonuses = [to_bonus(p, s) for p, s in zip(final_points, final_scores)]
            self.placement_bonus = 5*[list(reversed(list(sorted(bonuses))))[1:]]

    def apply_placement_bonus(self, round: int, score: Iterable[int]):
        # get the correct uma table
        num_below_starting_score = sum(1 for s in score if s < self.starting_points)
        uma = self.placement_bonus[num_below_starting_score]

        # calculate first place bonus
        oka: float = (self.num_players-1)*(self.total_points-self.starting_points)/1000.0
        placement_bonus = [oka-sum(uma)] + uma

        # apply placement bonus
        base_scores = [(s-self.total_points)/1000.0 for s in score]
        placements = to_placement(base_scores, num_players=self.num_players, dealer_seat=round%4)
        bonuses = [placement_bonus[i] for i in placements]
        return apply_delta_scores(base_scores, bonuses)
                                  

@dataclass
class GameMetadata:
    """Facts that apply across every kyoku"""
    num_players: int
    name: List[str]                  # name of each player indexed by seat
    game_score: List[int]            # final scores (points) indexed by seat
    final_score: List[float]         # final scores (points plus uma) indexed by seat
    rules: GameRules                 # game rules
