from dataclasses import dataclass, field
from enum import IntEnum
import functools
from typing import *

from .constants import PRED, SUCC, TOGGLE_RED_FIVE, YAOCHUUHAI
from .display import ph, pt, shanten_name
from .utils import get_waits, normalize_red_five, normalize_red_fives, sorted_hand, try_remove_all_tiles

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
    tile: int              # the called tile (the one that is technically in the pond)
    dir: Dir               # where the tile was called from (indicates where to point the called tile)
    tiles: Tuple[int, ...] # the 3 or 4 tiles set aside after calling
    def __post_init__(self) -> None:
        super().__setattr__("tiles", sorted_hand(self.tiles))
    def to_str(self, doras: List[int] = [], uras: List[int] = []) -> str:
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
        assert False, f"Somehow got Dir.SELF for a non-ankan call {self!r}"
        # dir == Dir.SELF is only for ankan and is handled above
    def __str__(self) -> str:
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
    def unpack(self) -> Tuple[Any, ...]:
        return (self.hand, self.ron_fu, self.tsumo_fu, self.sequences, self.triplets, self.pair)
    def __hash__(self) -> int:
        return hash(self.unpack())
    def __str__(self) -> str:
        full_hand = (*self.sequences, *self.triplets, self.pair, self.hand) if self.pair is not None else (*self.sequences, *self.triplets, self.hand)
        return " ".join(map(ph, full_hand)) + f" ron {self.ron_fu} tsumo {self.tsumo_fu}"
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
    def generate_all_interpretations(self, yakuhai: Tuple[int, ...] = (), is_closed_hand: bool = False) -> Set["Interpretation"]:
        """
        From this Interpretation, remove all combinations of sequences,
        triplets, and pair from self.hand to arrive at several
        Interpretations. Calculates fu obtained in the process, after you
        pass in the yakuhai tiles, base ron fu, and base tsumo fu.
        """

        # first, use the call info to filter some groups out of the hand
        base_fu = 20
        for call in self.calls:
            if call.type == "chii":
                self.sequences = (*self.sequences, tuple(call.tiles))
            if call.type == "pon":
                base_fu += 4 if call.tile in YAOCHUUHAI else 2
                # print(f"add {4 if call.tile in YAOCHUUHAI else 2} for open triplet {pt(call.tile)}")
                self.triplets = (*self.triplets, tuple(call.tiles))
            if "kan" in call.type: 
                base_fu += 16 if call.tile in YAOCHUUHAI else 8
                if call.type == "ankan":
                    base_fu += 16 if call.tile in YAOCHUUHAI else 8
                    # print(f"add {32 if call.tile in YAOCHUUHAI else 16} for closed kan {pt(call.tile)}")
                else:
                    pass
                    # print(f"add {16 if call.tile in YAOCHUUHAI else 8} for open kan {pt(call.tile)}")
                self.triplets = (*self.triplets, tuple(call.tiles[:3]))
        # print(f"base fu + calls = {base_fu} fu")
        base_ron_fu = base_fu + (10 if is_closed_hand else 0)
        base_tsumo_fu = base_fu + 2

        # finally, iterate through all possible interpretations of the hand
        interpretations: Set[Interpretation] = set()
        to_update: Set[Interpretation] = {self}
        already_processed: Set[Tuple[int, ...]] = set()
        add_group = lambda groups, group: tuple(sorted((*groups, tuple(sorted(group)))))
        while len(to_update) > 0:
            unprocessed_part, fu, _, sequences, triplets, pair = to_update.pop().unpack()
            if unprocessed_part in already_processed:
                continue
            else:
                already_processed.add(unprocessed_part)
            for tile in set(unprocessed_part):
                # remove a triplet
                triplet = (tile, tile, tile)
                removed_triplet = try_remove_all_tiles(unprocessed_part, triplet)
                if removed_triplet != unprocessed_part: # removal was a success
                    # add fu for this triplet
                    triplet_fu = 8 if tile in YAOCHUUHAI else 4
                    # print(f"add {triplet_fu} for closed triplet {pt(tile)}, {ph(unprocessed_part)}")
                    to_update.add(Interpretation(removed_triplet, fu + triplet_fu, fu + triplet_fu, sequences, add_group(triplets, triplet), pair, calls=self.calls))

                # remove a sequence
                sequence = (SUCC[SUCC[tile]], SUCC[tile], tile)
                removed_sequence = try_remove_all_tiles(unprocessed_part, sequence)
                if removed_sequence != unprocessed_part: # removal was a success
                    to_update.add(Interpretation(removed_sequence, fu, fu, add_group(sequences, sequence), triplets, pair, calls=self.calls))

                # remove a pair, if we haven't yet
                if pair is None:
                    yakuhai_fu = 2 * yakuhai.count(tile)
                    # print(f"add {yakuhai_fu} for yakuhai pair {pt(tile)}, {ph(unprocessed_part)}")
                    removed_pair = try_remove_all_tiles(unprocessed_part, (tile, tile))
                    if removed_pair != unprocessed_part: # removal was a success
                        to_update.add(Interpretation(removed_pair, fu + yakuhai_fu, fu + yakuhai_fu, sequences, triplets, (tile, tile), calls=self.calls))
                
            if len(unprocessed_part) == 2:
                # now evaluate the remaining taatsu
                tile1, tile2 = sorted_hand(normalize_red_fives(unprocessed_part))
                is_shanpon = tile1 == tile2
                is_penchan = SUCC[tile1] == tile2 and 0 in {PRED[tile1], SUCC[tile2]}
                is_ryanmen = SUCC[tile1] == tile2 and 0 not in {PRED[tile1], SUCC[tile2]}
                is_kanchan = SUCC[SUCC[tile1]] == tile2
                single_wait_fu = 2 if is_penchan or is_kanchan else 0
                # print(f"add {single_wait_fu} for single wait {pt(tile1)pt(tile2)}, {ph(unprocessed_part)}")
                if True in {is_ryanmen, is_shanpon, is_penchan, is_kanchan}:
                    ron_fu = base_ron_fu + fu + single_wait_fu
                    tsumo_fu = base_tsumo_fu + fu + single_wait_fu
                    interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, pair, calls=self.calls))
            elif len(unprocessed_part) == 1:
                # either a tanki or aryanmen wait for pinfu
                # first take care of the tanki possibility:
                # print(f"add 2 for single wait {pt(unprocessed_part[0])}")
                tanki = unprocessed_part[0]
                yakuhai_fu = 2 * yakuhai.count(tile)
                ron_fu = base_ron_fu + fu + yakuhai_fu + 2
                tsumo_fu = base_tsumo_fu + fu + yakuhai_fu + 2
                interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, calls=self.calls))
                # then take care of the pinfu aryanmen possibility:
                if len(triplets) == 0: # all sequences
                    # check that it's a tanki overlapping a sequence
                    has_pair = False
                    for i, (t1,t2,t3) in enumerate(sequences):
                        remaining_seqs = (*sequences[:i], *sequences[i+1:])

                        if tanki == t1 and PRED[t1] != 0:
                            ryanmen = (t2,t3)
                        elif tanki == t3 and SUCC[t3] != 0:
                            ryanmen = (t1,t2)
                        else:
                            continue
                        if tanki not in yakuhai:
                            has_pair = True
                            break
                    if has_pair == True:
                        interpretations.add(Interpretation(ryanmen, 30, 22, remaining_seqs, triplets, (tanki, tanki), calls=self.calls))
        return interpretations if len(interpretations) > 0 else {self}

@dataclass
class GameRules:
    """Details all the rules that InjusticeJudge cares about."""
    use_red_fives: bool = True        # whether the game uses red fives
    immediate_kan_dora: bool = False  # whether kan immediately reveals a dora
    head_bump: bool = False           # whether head bump is enabled
    renhou: bool = False              # whether renhou is enabled
    kiriage_mangan: bool = False      # whether kiriage mangan is enabled
    nagashi_mangan: bool = True       # whether nagashi mangan is enabled
    double_round_wind: bool = True    # whether double round wind is enabled (E = E+W; S = S+N)
    double_wind_4_fu: bool = True     # whether a round+seat wind pair is worth 4 fu
    starting_doras: int = 1           # number of doras started with
    riichi_value: int = 1000          # value of riichi bet
    honba_value: int = 100            # value of each honba (continuation stick) per player
    noten_payment: Tuple[int, int, int] = (1000, 1500, 3000) # noten payment paid for 1/2/3 players tenpai
    @classmethod
    def from_majsoul_detail_rule(cls, rules: Dict[str, Any]) -> "GameRules":
        return cls(use_red_fives = rules.get("doraCount", 3) > 0,
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
                   )
    @classmethod
    def from_tenhou_rules(cls, rule: List[str], csrule: List[str]) -> "GameRules":
        if isinstance(rule, dict):
            # normal game
            return cls(use_red_fives = "aka51" in rule and rule["aka51"])
        # lobby game
        rule1 = int(rule[2] or "0", 16)
        rule2 = int(csrule[0] or "0", 16)
        rule3 = int(csrule[1] or "0", 16)
        return cls(use_red_fives = 0x0002 & rule1 == 0,
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
                   )
@dataclass
class GameMetadata:
    """Facts that apply across every kyoku"""
    num_players: int
    name: List[str]                  # name of each player indexed by seat
    game_score: List[int]            # final scores (points) indexed by seat
    final_score: List[int]           # final scores (points plus uma) indexed by seat
    # the fields below are equivalent to Kyoku.doras/uras/rules, and only here for technical reasons
    # (they are parsed first from the raw log, and then used to populate each Kyoku)
    dora_indicators: List[List[int]] # lists of dora indicators, one for each kyoku
    ura_indicators: List[List[int]]  # lists of ura indicators, one for each kyoku
    rules: GameRules                 # game rules
