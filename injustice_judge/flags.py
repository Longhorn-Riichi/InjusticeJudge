from .classes import CallInfo, Dir, Draw, Event, Hand, Kyoku, Ron, Tsumo, Win
from dataclasses import dataclass, field
from .constants import DORA, DORA_INDICATOR, MANZU, PINZU, SOUZU, JIHAI, LIMIT_HANDS, TRANSLATE, YAKUMAN, YAOCHUUHAI
from enum import Enum
from typing import *
from .utils import get_majority_suit, is_mangan, normalize_red_five, print_pond, round_name, to_placement, translate_tenhou_yaku
from .wwyd import is_safe
from .yaku import get_final_yaku, get_score, get_takame_score, get_yakuman_tenpais, get_yakuman_waits
from pprint import pprint

# This file provides a `Flags` enum and a single function, `determine_flags`,
#   which is called by `` in `injustices.py`
# 
# After getting a list of `Kyoku`s from `parse_game_link` in `fetch.py`,
#   `determine_flags` turns each `Kyoku` into an ordered list of facts about
#   the `Kyoku` for each player. This is represented by (for each player) a
#   list of `Flags`, each one corresponding to a fact and each one associated
#   with some data represented by a `data` dict. The list of `data` dicts is
#   returned alongside the `flags` list, where the data at index `i`
#   corresponds to the flag at index `i`. There's no documentation on the
#   `data` dict associated with each type of flag -- you'll have to go down
#   and examine the code generating that specific flag.
# 
# The resulting flags are used in `evaluate_injustices` in `injustices.py`,
#   which checks for combinations of flags that might constitute an injustice.
#   The `data` dicts are used for further checks, but mainly they contain
#   information used to detail the injustice to the user.

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " AGAINST_TRIPLE_RIICHI"
    " ANKAN_ERASED_TENPAI_WAIT"
    " BAD_HONITSU_DRAWS"
    " CHANGED_WAIT_ON_LAST_DISCARD"
    " CHASER_GAINED_POINTS"
    " CHASER_LOST_POINTS"
    " DREW_WORST_HAIPAI_SHANTEN"
    " EVERYONE_DISRESPECTED_YOUR_RIICHI"
    " FIRST_ROW_TENPAI"
    " FIVE_SHANTEN_START"
    " FOUR_DANGEROUS_DRAWS_AFTER_RIICHI"
    " FOUR_SHANTEN_AFTER_FIRST_ROW"
    " GAME_ENDED_WITH_ABORTIVE_DRAW"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " GAME_ENDED_WITH_TSUMO"
    " IISHANTEN_HAIPAI_ABORTED"
    " IISHANTEN_WITH_0_TILES"
    " IMMEDIATELY_DREW_DISCARDED_DORA"
    " IMMEDIATELY_DREW_DISCARDED_TILE"
    " LAST_DISCARD_WAS_RIICHI"
    " FINAL_ROUND"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " SEVEN_TERMINAL_START"
    " SIX_DISCARDS_TSUMOGIRI_HONOR"
    " SIX_TSUMOGIRI_WITHOUT_TENPAI"
    " SOMEONE_REACHED_TENPAI"
    " STARTED_WITH_3_DORA"
    # " STARTED_WITH_TWO_147_SHAPES"
    " TENPAI_ON_LAST_DISCARD"
    " TURN_SKIPPED_BY_PON"
    " WINNER"
    " WINNER_GOT_BAIMAN"
    " WINNER_GOT_HAITEI"
    " WINNER_GOT_HANEMAN"
    " WINNER_GOT_HIDDEN_DORA_3"
    " WINNER_GOT_KAN_DORA_BOMB"
    " WINNER_GOT_MANGAN"
    " WINNER_GOT_SANBAIMAN"
    " WINNER_GOT_URA_3"
    " WINNER_GOT_YAKUMAN"
    " WINNER_HAD_BAD_WAIT"
    " WINNER_IPPATSU_TSUMO"
    " WINNER_WAS_FURITEN"
    " YOU_ACHIEVED_NAGASHI"
    " YOU_ARE_DEALER"
    " YOU_AVOIDED_LAST_PLACE"
    " YOU_CHASED"
    " YOU_DEALT_IN"
    " YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_DOUBLE_RON"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_DECLARED_RIICHI"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
    " YOU_GAINED_PLACEMENT"
    " YOU_DROPPED_PLACEMENT"
    " YOU_FLIPPED_DORA_BOMB"
    " YOU_FOLDED_FROM_TENPAI"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_HAD_LIMIT_TENPAI"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_REACHED_YAKUMAN_TENPAI"
    " YOU_RONNED_SOMEONE"
    " YOU_TENPAI_FIRST"
    " YOU_TSUMOED"
    " YOU_WAITED_ON_WINNING_TILE"
    " YOU_WERE_FIRST"
    " YOU_WERE_SECOND"
    " YOU_WERE_THIRD"
    " YOU_WERE_FOURTH"
    " YOU_WON"
    " YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN"
    " YOUR_LAST_DISCARD_ENDED_NAGASHI"
    " YOUR_LAST_NAGASHI_TILE_CALLED"
    " YOUR_TENPAI_TILE_DEALT_IN"
    )

@dataclass
class KyokuPlayerInfo:
    num_players: int
    hand: Hand
    pond: List[int]                         = field(default_factory=list)
    draws_since_shanten_change: int         = 0
    tsumogiri_honor_discards: int           = 0
    tsumogiri_without_tenpai: int           = 0
    num_discards: int                       = 0
    last_draw: int                          = 0
    last_discard: int                       = 0
    last_discard_was_riichi: int            = False
    opened_hand: bool                       = False
    nagashi: bool                           = True
    in_riichi: bool                         = False
    riichi_index: Optional[int]             = None
    consecutive_off_suit_tiles: List[int]   = field(default_factory=list)
    past_waits: List[List[int]]             = field(default_factory=list)
    dangerous_draws_after_riichi: List[int] = field(default_factory=list)
    respects_riichi: List[Optional[bool]]   = field(default_factory=list)
    def __post_init__(self):
        # respects_riichi[other_player] =
        #   True if their first discard after our riichi was a safe tile
        #   False if their first discard after our riichi was a dangerous tile
        #   None if they didn't discard after our riichi yet
        self.respects_riichi = [None] * self.num_players

@dataclass
class KyokuInfo:
    kyoku: Kyoku
    num_players: int
    tiles_in_wall: int        = 0
    starting_doras: List[int] = field(default_factory=list)
    current_doras: List[int]  = field(default_factory=list)
    at: List[KyokuPlayerInfo] = field(default_factory=list)
    visible_tiles: List[int]  = field(default_factory=list)
    flags: List[List[Flags]]  = field(default_factory=list)
    data: List[List[Any]]     = field(default_factory=list)
    global_flags: List[Flags] = field(default_factory=list)
    global_data: List[Any]    = field(default_factory=list)
    def get_visible_tiles(self, seat: int) -> List[int]:
        return self.visible_tiles \
             + list(self.at[seat].hand.tiles_with_kans) \
             + [DORA_INDICATOR[dora] for dora in self.current_doras if dora not in {51,52,53}]
    def add_flag(self, seat: int, flag: Flags, data: Optional[Dict[str, Any]] = None) -> None:
        self.flags[seat].append(flag)
        self.data[seat].append(data)
    def remove_flag(self, seat: int, flag: Flags) -> None:
        ix = self.flags[seat].index(flag)
        del self.flags[seat][ix]
        del self.data[seat][ix]
    def add_global_flag(self, flag: Flags, data: Optional[Dict[str, Any]] = None) -> None:
        self.global_flags.append(flag)
        self.global_data.append(data)
    def remove_global_flag(self, flag: Flags) -> None:
        ix = self.global_flags.index(flag)
        del self.global_flags[ix]
        del self.global_data[ix]

    def process_haipai(self, i: int, seat: int, event_type: str, hand: Tuple[int]) -> None:
        assert len(self.at) == seat, f"got haipai out of order, expected seat {len(self.at)} but got seat {seat}"
        self.at.append(KyokuPlayerInfo(num_players=self.num_players, hand=Hand(hand)))
        # check if we have at least 7 terminal/honor tiles
        num_types = len(set(hand) & YAOCHUUHAI) # of terminal/honor tiles
        if num_types >= 7:
            self.add_flag(seat, Flags.SEVEN_TERMINAL_START, {"num_types": num_types})
        # check if we have a 5 shanten start
        if self.at[seat].hand.shanten[0] >= 5:
            self.add_flag(seat, Flags.FIVE_SHANTEN_START, {"shanten": self.at[seat].hand.shanten})
        # check if we started with 3 dora
        starting_dora = sum(hand.count(dora) for dora in self.starting_doras)
        if starting_dora >= 3:
            self.add_flag(seat, Flags.STARTED_WITH_3_DORA, {"num": starting_dora})
        # check if we started with at least two 1-4-7 shapes
        # num_147_shapes = sum(1 for suit in (MANZU, PINZU, SOUZU)
        #                        if tuple(tile // 10 for tile in hand if tile in suit) in {(1,4,7),(2,5,8),(3,6,9)})
        # if num_147_shapes >= 2:
        #     add_flag(seat, Flags.STARTED_WITH_TWO_147_SHAPES, {"hand": hand, "num": num_147_shapes})

    def process_draw(self, i: int, seat: int, event_type: str, tile: int) -> None:
        self.at[seat].hand = self.at[seat].hand.add(tile)
        self.tiles_in_wall -= 1
        self.at[seat].last_draw = tile
        # check if draw would have completed a past wait
        for wait in self.at[seat].past_waits:
            if tile in wait:
                self.add_flag(seat, Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE, {"tile": tile, "wait": wait, "shanten": self.at[seat].hand.shanten})
        # check if it's been more than 9 draws since we changed shanten
        if self.at[seat].hand.shanten[0] > 0 and self.at[seat].draws_since_shanten_change >= 9:
            self.add_flag(seat, Flags.NINE_DRAWS_NO_IMPROVEMENT, {"shanten": self.at[seat].hand.shanten, "draws": self.at[seat].draws_since_shanten_change})
        self.at[seat].draws_since_shanten_change += 1
        # check if we drew what we just discarded
        if tile == self.at[seat].last_discard:
            self.add_flag(seat, Flags.IMMEDIATELY_DREW_DISCARDED_TILE, {"tile": tile})
            if tile in self.current_doras:
                self.add_flag(seat, Flags.IMMEDIATELY_DREW_DISCARDED_DORA, {"tile": tile})
        # check if we're going for honitsu and drew an off-suit tile
        going_for_honitsu = False
        majority_suit = get_majority_suit(self.at[seat].hand.tiles)
        if majority_suit is not None and tile not in majority_suit | JIHAI:
            honitsu_tiles = majority_suit | JIHAI
            majority_tiles = tuple(tile for tile in self.at[seat].hand.tiles if tile in honitsu_tiles)
            enough_honitsu_tiles = len(majority_tiles) >= 10
            no_off_suit_calls = all(call.tile in honitsu_tiles for call in self.at[seat].hand.calls)
            going_for_honitsu = enough_honitsu_tiles and no_off_suit_calls
        if going_for_honitsu:
            # tick up a counter if you drew off-suit tiles in a row
            self.at[seat].consecutive_off_suit_tiles.append(tile)
            if len(self.at[seat].consecutive_off_suit_tiles) >= 6:
                self.add_flag(seat, Flags.BAD_HONITSU_DRAWS,
                                    {"tiles": self.at[seat].consecutive_off_suit_tiles,
                                     "hand": self.at[seat].hand})
        else:
            self.at[seat].consecutive_off_suit_tiles = []
        # check if we're still 4-shanten or worse after the first row of discards
        if self.at[seat].num_discards == 6 and self.at[seat].hand.prev_shanten[0] >= 4:
            self.add_flag(seat, Flags.FOUR_SHANTEN_AFTER_FIRST_ROW, {"shanten": self.at[seat].hand.prev_shanten})
        # check if we're iishanten with zero tiles left
        if 1 <= self.at[seat].hand.shanten[0] < 2:
            ukeire = self.at[seat].hand.ukeire(self.get_visible_tiles(seat))
            if ukeire == 0:
                self.add_flag(seat, Flags.IISHANTEN_WITH_0_TILES, {"shanten": self.at[seat].hand.shanten})
        # check if there's a riichi and we drew a dangerous tile and we have no safe tiles
        for opponent, at in enumerate(self.at):
            if seat == opponent or not at.in_riichi:
                continue
            safe = lambda t: is_safe(t, self.at[opponent].pond, self.get_visible_tiles(seat))
            if not safe(tile) and not any(safe(t) for t in self.at[seat].hand.tiles):
                self.at[seat].dangerous_draws_after_riichi.append(tile)
                if len(self.at[seat].dangerous_draws_after_riichi) >= 4:
                    self.add_flag(seat, Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI,
                                        {"tiles": self.at[seat].dangerous_draws_after_riichi,
                                         "opponent": opponent,
                                         "pond_str": print_pond(self.at[opponent].pond, self.current_doras, self.at[opponent].riichi_index)
                                         })

    def process_chii_pon_kan(self, i: int, seat: int, event_type: str, called_tile: int, call_tiles: List[int], call_dir: Dir) -> None:
        if event_type != "minkan":
            self.at[seat].hand = self.at[seat].hand.add(called_tile)
        self.at[seat].hand = self.at[seat].hand.add_call(CallInfo(event_type, called_tile, call_dir, call_tiles))
        self.at[seat].opened_hand = True
        # for everyone whose turn was skipped, add Flags.TURN_SKIPPED_BY_PON
        if event_type in {"pon", "minkan"}:
            if call_dir in {Dir.TOIMEN, Dir.SHIMOCHA}:
                # called from toimen or shimocha, kamicha was skipped
                kamicha_seat = (seat-1)%4
                if not (self.num_players == 3 and kamicha_seat == 3):
                    self.add_flag(kamicha_seat, Flags.TURN_SKIPPED_BY_PON)
            if call_dir == Dir.SHIMOCHA:
                # called from shimocha, toimen was skipped
                toimen_seat = (seat-2)%4
                if not (self.num_players == 3 and toimen_seat == 3):
                    self.add_flag(toimen_seat, Flags.TURN_SKIPPED_BY_PON)

    def process_self_kan(self, i: int, seat: int, event_type: str, called_tile: int, call_tiles: List[int], call_dir: Dir) -> None:
        if event_type == "kakan":
            self.at[seat].hand = self.at[seat].hand.kakan(called_tile)
        elif event_type == "ankan":
            self.at[seat].hand = self.at[seat].hand.add_call(CallInfo("ankan", called_tile, Dir.SELF, [called_tile]*4))
        elif event_type == "kita":
            self.at[seat].hand = self.at[seat].hand.kita()
        self.at[seat].hand = self.at[seat].hand.remove(called_tile)
        self.visible_tiles.append(called_tile)
        # check if anyone's tenpai and had their waits erased by ankan
        if event_type == "ankan":
            tile = normalize_red_five(called_tile)
            for player in range(self.num_players):
                if seat == player:
                    continue
                if Flags.YOU_REACHED_TENPAI in self.flags[player]:
                    last_tenpai_data = self.data[player][len(self.flags[player]) - 1 - self.flags[player][::-1].index(Flags.YOU_REACHED_TENPAI)]
                    wait = last_tenpai_data["wait"]
                    ukeire = last_tenpai_data["ukeire"]
                    if tile in wait:
                        self.add_flag(player, Flags.ANKAN_ERASED_TENPAI_WAIT, {"tile": tile, "wait": wait, "caller": seat, "ukeire": ukeire})

    def process_discard(self, i: int, seat: int, event_type: str, tile: int) -> None:
        if event_type == "riichi":
            self.at[seat].riichi_index = len(self.at[seat].pond)
        self.at[seat].hand = self.at[seat].hand.remove(tile)
        self.visible_tiles.append(tile)
        self.at[seat].pond.append(tile)
        self.at[seat].num_discards += 1
        self.at[seat].last_discard = tile
        self.at[seat].last_discard_was_riichi = event_type == "riichi"
        # add riichi flag
        if event_type == "riichi":
            self.at[seat].in_riichi = True
            self.add_flag(seat, Flags.YOU_DECLARED_RIICHI)
            # if there's a triple riichi, give Flags.AGAINST_TRIPLE_RIICHI to the non-riichi person
            if sum(1 for at in self.at if at.in_riichi) == 3:
                non_riichi_seat = next(i for i, b in enumerate(self.at) if b.in_riichi == False)
                self.add_flag(non_riichi_seat, Flags.AGAINST_TRIPLE_RIICHI)
        # check if this is the deal-in tile
        is_last_discard_of_the_game = i == max(self.kyoku.final_discard_event_index)
        if is_last_discard_of_the_game and self.kyoku.result[0] == "ron":
            # check if we just reached tenpai
            already_tenpai = Flags.YOU_REACHED_TENPAI in self.flags[seat]
            if not already_tenpai and any(e[0] == seat and e[1] == "tenpai" for e in self.kyoku.events[i:]):
                self.add_flag(seat, Flags.YOUR_TENPAI_TILE_DEALT_IN, {"tile": tile})
            # check if we're tenpai and this would have been our last discard before noten payments
            if already_tenpai and self.tiles_in_wall <= 3:
                self.add_flag(seat, Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT, {"tile": tile})
        # check if this was tsumogiri honors (and you're not going for nagashi)
        is_tsumogiri = tile == self.at[seat].last_draw
        if not self.at[seat].nagashi and 41 <= tile <= 47 and is_tsumogiri:
            self.at[seat].tsumogiri_honor_discards += 1
            if self.at[seat].tsumogiri_honor_discards >= 6:
                self.add_flag(seat, Flags.SIX_DISCARDS_TSUMOGIRI_HONOR, {"num_discards": self.at[seat].tsumogiri_honor_discards})
        else:
            self.at[seat].tsumogiri_honor_discards = 0
        # check if this was tsumogiri while not in tenpai
        if Flags.YOU_REACHED_TENPAI not in self.flags[seat] and is_tsumogiri:
            self.at[seat].tsumogiri_without_tenpai += 1
            if self.at[seat].tsumogiri_without_tenpai >= 6:
                self.add_flag(seat, Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI, {"num_discards": self.at[seat].tsumogiri_without_tenpai})
        else:
            self.at[seat].tsumogiri_without_tenpai = 0
        # check if this discard respects/disrespects anyone's riichi
        for opponent, at in enumerate(self.at):
            if at.in_riichi and self.at[opponent].respects_riichi[seat] is None: # first discard after opponent's riichi
                self.at[opponent].respects_riichi[seat] = is_safe(tile, self.at[opponent].pond, self.get_visible_tiles(seat))
                if all(self.at[opponent].respects_riichi[player] == False for player in range(self.num_players) if player != opponent):
                    self.add_flag(opponent, Flags.EVERYONE_DISRESPECTED_YOUR_RIICHI)

    def process_end_nagashi(self, i: int, seat: int, event_type: str, who: int, reason: str, tile: int) -> None:
        self.at[who].nagashi = False
        # check if this happened after our final draw (if the game ended in ryuukyoku)
        if self.kyoku.result[0] == "ryuukyoku" and i > self.kyoku.final_draw_event_index[seat]:
            if reason == "discard":
                self.add_flag(who, Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI, {"tile": tile})
            elif reason in {"minkan", "pon", "chii"}:
                self.add_flag(who, Flags.YOUR_LAST_NAGASHI_TILE_CALLED, {"tile": tile, "caller": seat})

    def process_shanten_change(self, i: int, seat: int, event_type: str,
                               prev_shanten: Tuple[float, List[int]], new_shanten: Tuple[float, List[int]],
                               hand: Hand, ukeire: int, furiten: bool) -> None:
        assert new_shanten[0] >= 0, f"somehow shanten for seat {seat} was {new_shanten[0]}"
        self.at[seat].draws_since_shanten_change = 0
        # record past waits if we've changed from tenpai
        if prev_shanten[0] == 0:
            self.at[seat].past_waits.append(prev_shanten[1])
            if new_shanten[0] > 0:
                self.add_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)
        # bunch of things to check if we're tenpai

    def process_tenpai(self, i: int, seat: int, event_type: str,
                       prev_shanten: Tuple[float, List[int]], new_shanten: Tuple[float, List[int]],
                       hand: Hand, ukeire: int, furiten: bool) -> None:
        # check if we're the first to tenpai
        if Flags.SOMEONE_REACHED_TENPAI not in self.global_flags:
            self.add_flag(seat, Flags.YOU_TENPAI_FIRST)
        # otherwise, this is a chase
        else:
            for other in range(self.num_players):
                if other == seat:
                    continue
                if Flags.YOU_REACHED_TENPAI in self.flags[other]:
                    other_data = self.data[other][len(self.flags[other]) - 1 - self.flags[other][::-1].index(Flags.YOU_REACHED_TENPAI)]
                    self.add_flag(other, Flags.YOU_CHASED,
                                         {"your_seat": seat,
                                          "your_hand": hand,
                                          "your_ukeire": hand.ukeire(self.get_visible_tiles(seat)),
                                          "your_furiten": furiten,
                                          "seat": other,
                                          "hand": other_data["hand"],
                                          "ukeire": other_data["hand"].ukeire(self.get_visible_tiles(other)),
                                          "furiten": other_data["furiten"]})
                    self.add_flag(other, Flags.YOU_GOT_CHASED,
                                         {"seat": seat,
                                          "hand": hand,
                                          "ukeire": hand.ukeire(self.get_visible_tiles(seat)),
                                          "furiten": furiten,
                                          "your_seat": other,
                                          "your_hand": other_data["hand"],
                                          "your_ukeire": other_data["hand"].ukeire(self.get_visible_tiles(other)),
                                          "your_furiten": other_data["furiten"]})
        self.add_global_flag(Flags.SOMEONE_REACHED_TENPAI,
                             {"seat": seat,
                              "hand": hand,
                              "furiten": furiten})
        self.add_flag(seat, Flags.YOU_REACHED_TENPAI,
                            {"hand": hand,
                             "ukeire": hand.ukeire(self.get_visible_tiles(seat)),
                             "furiten": furiten})
        # check for first row tenpai
        if self.at[seat].num_discards <= 6:
            self.add_flag(seat, Flags.FIRST_ROW_TENPAI, {"seat": seat, "turn": self.at[seat].num_discards})
        # check if we started from 5-shanten and reached tenpai
        # add a flag to everyone who had a 3-shanten start but couldn't reach tenpai
        if Flags.FIVE_SHANTEN_START in self.flags[seat]:
            for player in range(self.num_players):
                if seat == player:
                    continue
                if self.kyoku.haipai[player].shanten[0] <= 3 and Flags.YOU_REACHED_TENPAI not in self.flags[player]:
                    self.add_flag(player, Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN,
                                          {"seat": seat,
                                           "your_shanten": self.kyoku.haipai[player].shanten[0],
                                           "their_shanten": self.kyoku.haipai[seat].shanten[0]})

        # check if you entered tenpai on your last discard
        was_last_discard_of_the_game = i >= self.kyoku.final_discard_event_index[seat]
        if was_last_discard_of_the_game:
            self.add_flag(seat, Flags.TENPAI_ON_LAST_DISCARD)
            # check if you had simply changed your wait on your last discard
            if prev_shanten[0] == 0:
                self.add_flag(seat, Flags.CHANGED_WAIT_ON_LAST_DISCARD)
        # remove YOU_FOLDED_FROM_TENPAI flag if any
        if Flags.YOU_FOLDED_FROM_TENPAI in self.flags[seat]:
            self.remove_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)

        # check if we are mangan+ tenpai
        is_haitei = self.kyoku.tiles_in_wall == 0 and seat == self.kyoku.final_draw_seat
        is_houtei = self.kyoku.tiles_in_wall == 0 and seat != self.kyoku.final_draw_seat
        best_score, takame = get_takame_score(hand = hand,
                                              events = self.kyoku.events,
                                              doras = self.kyoku.doras,
                                              uras = self.kyoku.uras,
                                              round = self.kyoku.round,
                                              seat = seat,
                                              is_haitei = is_haitei,
                                              is_houtei = is_houtei,
                                              num_players = self.kyoku.num_players)
        han = best_score.han
        fu = best_score.fu
        if han >= 5 or is_mangan(han, fu):
            hand_str = hand.print_hand_details(ukeire=ukeire, final_tile=None, furiten=furiten)
            self.add_flag(seat, Flags.YOU_HAD_LIMIT_TENPAI,
                           {"hand_str": hand_str,
                            "takame": takame,
                            "limit_name": TRANSLATE[LIMIT_HANDS[han]],
                            "yaku_str": ", ".join(name for name, value in best_score.yaku),
                            "han": han,
                            "fu": fu})
        # check if we are yakuman tenpai
        # first, do standard yakuman, otherwise, try kazoe yakuman
        yakuman_waits: List[Tuple[str, Set[int]]] = [(y, get_yakuman_waits(self.kyoku.hands[seat], y)) for y in get_yakuman_tenpais(self.kyoku.hands[seat])]
        # only report the yakuman if the waits are not dead
        visible = self.get_visible_tiles(seat)
        yakuman_types: Set[str] = {t for t, waits in yakuman_waits if not all(visible.count(wait) == 4 for wait in waits)}
        if len(yakuman_types) > 0:
            self.add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"types": yakuman_types, "waits": yakuman_waits})
        elif han >= 13 and not any(y in map(TRANSLATE.get, YAKUMAN.values()) for y, _ in best_score.yaku):
            # TODO filter for only the waits that let you reach kazoe yakuman
            waits = new_shanten[1]
            self.add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"types": {f"kazoe yakuman ({', '.join(y for y, _ in best_score.yaku)})"}, "waits": waits})

    def process_new_dora(self, i: int, seat: int, event_type: str,
                         dora_indicator: int, kan_call: CallInfo) -> None:
        dora = DORA[dora_indicator]
        self.current_doras.append(dora)
        # check if that just gave us 4 dora
        if self.at[seat].hand.tiles_with_kans.count(dora) == 4:
            self.add_flag(seat, Flags.YOU_FLIPPED_DORA_BOMB, {"doras": self.current_doras.copy(), "call": kan_call, "hand": self.at[seat].hand})

    def process_placement_change(self, i: int, seat: int, event_type: str,
                                 old_placement: int, new_placement: int,
                                 prev_scores: List[int], delta_scores: List[int]) -> None:
        if old_placement == 4 and Flags.FINAL_ROUND in self.global_flags:
            self.add_flag(seat, Flags.YOU_AVOIDED_LAST_PLACE, {})
        if new_placement > old_placement: # dropped placement
            self.add_flag(seat, Flags.YOU_DROPPED_PLACEMENT,
                                {"old": old_placement, "new": new_placement,
                                 "prev_scores": prev_scores, "delta_scores": delta_scores})
        elif new_placement < old_placement: # gained placement
            self.add_flag(seat, Flags.YOU_GAINED_PLACEMENT,
                                {"old": old_placement, "new": new_placement,
                                 "prev_scores": prev_scores, "delta_scores": delta_scores})

    def process_start_game(self, i: int, seat: int, event_type: str,
                           round: int, honba: int, riichi_sticks: int, scores: List[int]) -> None:
        # give dealer a flag saying that they're dealer
        self.add_flag(round % 4, Flags.YOU_ARE_DEALER)
        # give everyone a flag for their placement
        placement_flags = [Flags.YOU_WERE_FIRST, Flags.YOU_WERE_SECOND, Flags.YOU_WERE_THIRD, Flags.YOU_WERE_FOURTH]
        for seat, placement in enumerate(to_placement(self.kyoku.start_scores)):
            self.add_flag(seat, placement_flags[placement])
        # add final round flag (NOT all last)
        if self.kyoku.is_final_round:
            self.add_global_flag(Flags.FINAL_ROUND)
        # check who has the worst haipai shanten
        starting_shanten = [self.kyoku.haipai[player].shanten[0] // 1 for player in range(self.num_players)]
        get_starting_shanten = lambda player: self.kyoku.haipai[player].shanten[0] // 1
        for player in range(self.num_players):
            second_worst_shanten = max(get_starting_shanten(other_player) for other_player in range(self.num_players) if player != other_player)
            if get_starting_shanten(player) > second_worst_shanten:
                self.add_flag(player, Flags.DREW_WORST_HAIPAI_SHANTEN, {"shanten": self.kyoku.haipai[player].shanten, "second_worst_shanten": second_worst_shanten})
        
    def process_result(self, i: int, seat: int, event_type: str, result_type: str, *results: Union[Ron, Tsumo, Draw]) -> None:
        # check if the last discard was a riichi (it must have dealt in)
        for seat in range(self.num_players):
            if self.at[seat].last_discard_was_riichi:
                self.add_flag(seat, Flags.LAST_DISCARD_WAS_RIICHI, {})

        # every result has result.score_delta
        # here we add YOU_GAINED_POINTS or YOU_LOST_POINTS as needed
        for result in results:
            for seat in range(self.num_players):
                # check for points won or lost
                if result.score_delta[seat] > 0:
                    self.add_flag(seat, Flags.YOU_GAINED_POINTS, {"amount": result.score_delta[seat]})
                elif result.score_delta[seat] < 0:
                    self.add_flag(seat, Flags.YOU_LOST_POINTS, {"amount": -result.score_delta[seat]})

        # here we add flags that pertain to the winning hand(s):
        # - LOST_POINTS_TO_FIRST_ROW_WIN
        # - YOU_WAITED_ON_WINNING_TILE
        # - WINNER
        # - WINNER_GOT_MANGAN, WINNER_GOT_HANEMAN, etc
        # - WINNER_HAD_BAD_WAIT
        # - WINNER_GOT_HIDDEN_DORA_3
        # - WINNER_GOT_URA_3
        # - WINNER_GOT_KAN_DORA_BOMB
        # - WINNER_GOT_HAITEI
        if result_type in {"ron", "tsumo"}:
            for win in results:
                assert isinstance(win, Win)
                self.process_win_result(win, is_tsumo = result_type == "tsumo")

        # here we add all flags that have to do with deal-ins:
        # - YOU_RONNED_SOMEONE
        # - YOU_DEALT_IN
        # - YOU_DEALT_INTO_DAMA
        # - YOU_DEALT_INTO_IPPATSU
        # - YOU_DEALT_INTO_DOUBLE_RON
        # - CHASER_GAINED_POINTS
        if result_type == "ron":
            # check winners
            for ron in results:
                assert isinstance(ron, Ron), f"result tagged ron got non-Ron object: {ron}"
                self.process_ron_result(ron, num_rons = len(results))
            self.add_global_flag(Flags.GAME_ENDED_WITH_RON, {"objects": results})

        # here we add all flags that have to do with self-draw luck:
        # - YOU_TSUMOED
        # - WINNER_WAS_FURITEN
        # - WINNER_IPPATSU_TSUMO
        elif result_type == "tsumo":
            tsumo = results[0]
            assert isinstance(tsumo, Tsumo), f"result tagged tsumo got non-Tsumo object: {tsumo}"
            self.process_tsumo_result(tsumo)
            self.add_global_flag(Flags.GAME_ENDED_WITH_TSUMO, {"object": tsumo})

        # here we add all flags that have to do with ryuukyoku
        elif result_type == "ryuukyoku":
            draw = results[0]
            assert isinstance(draw, Draw), f"result tagged draw got non-Draw object: {draw}"
            self.process_ryuukyoku_result(draw)
            self.add_global_flag(Flags.GAME_ENDED_WITH_RYUUKYOKU, {"object": draw})

        # here we add all flags that have to do with exhaustive or abortive draws
        # - YOU_ACHIEVED_NAGASHI
        # - IISHANTEN_HAIPAI_ABORTED
        elif result_type == "draw":
            draw = results[0]
            assert isinstance(draw, Draw), f"result tagged draw got non-Draw object: {draw}"
            self.process_draw_result(draw)
            self.add_global_flag(Flags.GAME_ENDED_WITH_RYUUKYOKU, {"object": draw})

        elif result_type == "draw":
            self.add_global_flag(Flags.GAME_ENDED_WITH_ABORTIVE_DRAW, {"object": self.kyoku.result[1]})

    def process_ron_result(self, ron: Ron, num_rons: int) -> None:
        # check deal-ins
        self.add_flag(ron.winner, Flags.YOU_RONNED_SOMEONE, {"from": ron.won_from})
        self.add_flag(ron.won_from, Flags.YOU_DEALT_IN, {"to": ron.winner})
        for seat in range(self.num_players):
            if ron.score_delta[seat] < 0:
                if not self.at[ron.winner].opened_hand and not self.at[ron.winner].in_riichi:
                    self.add_flag(seat, Flags.YOU_DEALT_INTO_DAMA, {"seat": ron.winner, "score": ron.score.to_points()})
                if ron.score.has_ippatsu():
                    self.add_flag(seat, Flags.YOU_DEALT_INTO_IPPATSU, {"seat": ron.winner, "score": ron.score.to_points()})
                if num_rons > 1:
                    self.add_flag(seat, Flags.YOU_DEALT_INTO_DOUBLE_RON, {"number": num_rons})
        if Flags.YOU_GOT_CHASED in self.flags[ron.won_from]:
            assert Flags.YOU_REACHED_TENPAI in self.flags[ron.won_from], "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
            self.add_flag(ron.won_from, Flags.CHASER_GAINED_POINTS, {"seat": ron.winner, "amount": ron.score.to_points()})

    def process_tsumo_result(self, tsumo: Tsumo) -> None:
        self.add_flag(tsumo.winner, Flags.YOU_TSUMOED)
        # check furiten
        if self.kyoku.furiten[tsumo.winner]:
            self.add_global_flag(Flags.WINNER_WAS_FURITEN,
                            {"seat": tsumo.winner,
                             "wait": self.kyoku.hands[tsumo.winner].shanten[1],
                             "ukeire": self.kyoku.final_ukeire[tsumo.winner]})
        # check ippatsu tsumo
        if tsumo.score.has_ippatsu():
            self.add_global_flag(Flags.WINNER_IPPATSU_TSUMO, {"seat": tsumo.winner})

    def process_ryuukyoku_result(self, draw: Draw) -> None:
        pass

    def process_draw_result(self, draw: Draw) -> None:
        name = draw.name
        if name in {"ryuukyoku", "nagashi mangan"}:
            assert self.tiles_in_wall == 0, f"somehow ryuukyoku with {self.tiles_in_wall} tiles left in wall"
            for seat in (seat for seat, at in enumerate(self.at) if at.nagashi):
                self.add_flag(seat, Flags.YOU_ACHIEVED_NAGASHI, {"seat": seat})
        elif name in {"9 terminals draw", "4-wind draw"}:
            # check if anyone started with a really good hand
            for seat in range(self.num_players):
                if self.kyoku.hands[seat].shanten[0] <= 1:
                    self.add_flag(seat, Flags.IISHANTEN_HAIPAI_ABORTED,
                             {"draw_name": name,
                              "shanten": self.kyoku.haipai[seat].shanten,
                              "hand": self.at[seat].hand})

    def process_win_result(self, result: Win, is_tsumo: bool) -> None:
        # first check how each player reacts to this win
        for seat in range(self.num_players):
            # check if we lost points to a first row win
            if result.score_delta[seat] < 0:
                if len(self.at[seat].pond) <= 6:
                    self.add_flag(seat, Flags.LOST_POINTS_TO_FIRST_ROW_WIN, {"seat": result.winner, "turn": len(self.at[seat].pond)})
            # if tenpai, check if the winning tile is in our waits
            # this is useful to find missed/skipped wins, or head bumps
            if self.at[seat].hand.shanten[0] == 0:
                winning_tile = self.kyoku.final_draw if is_tsumo else self.kyoku.final_discard
                if normalize_red_five(winning_tile) in self.at[seat].hand.shanten[1]:
                    self.add_flag(seat, Flags.YOU_WAITED_ON_WINNING_TILE, {"tile": winning_tile, "wait": self.at[seat].hand.shanten[1]})

        # calculate the yaku, han, and fu for the winning hand
        # check calculated values with the han and points given in the result data
        # first get the expected values from the result data
        expected_yaku = result.score.yaku
        expected_han = 0
        ura = 0
        for name, han in expected_yaku:
            if name.startswith("ura"):
                ura = han
            expected_han += han
        # then calculate yaku, han, and fu of the winning hand
        calculated_yaku = get_final_yaku(self.kyoku, result.winner, check_rons=not is_tsumo, check_tsumos=is_tsumo)
        # we already take into account if the wait is dora
        #   but we don't check if the winning tile is aka
        #   let's fix it here
        final_tile = self.kyoku.final_draw if is_tsumo else self.kyoku.final_discard
        final_tile_is_aka = final_tile in set(self.current_doras) and final_tile in {51,52,53}
        final_tile = normalize_red_five(final_tile)
        if final_tile_is_aka:
            calculated_yaku[final_tile].add_dora("aka", 1)

        han = calculated_yaku[final_tile].han
        fu = calculated_yaku[final_tile].fu
        # compare the han values to make sure we calculated it right
        winning_hand = self.at[result.winner].hand
        import os
        if os.getenv("debug"):
            assert han == expected_han, f"in {round_name(self.kyoku.round, self.kyoku.honba)}, calculated the wrong han ({han}) for a {expected_han} han hand {winning_hand!s}\nactual yaku: {expected_yaku}\ncalculated yaku: {calculated_yaku[final_tile]}"
        # compare the resulting score to make sure we calculated it right
        is_dealer = result.winner == self.kyoku.round % 4
        calculated_score = get_score(han, fu, is_dealer, is_tsumo, self.num_players)
        if os.getenv("debug"):
            tsumo_string = "tsumo" if is_tsumo else "ron"
            stored_score = result.score.to_points()
            if (calculated_score, stored_score) in {(7700, 8000), (7900, 8000), (11600, 12000), (11700, 12000)}: # ignore kiriage mangan differences for now
                pass
            else:
                assert calculated_score == stored_score, f"in {round_name(self.kyoku.round, self.kyoku.honba)}, calculated the wrong {tsumo_string} score ({calculated_score}) for a {stored_score} point hand {winning_hand!s}\nactual yaku: {expected_yaku}\ncalculated yaku: {calculated_yaku[final_tile]}"

        # Add potentially several WINNER flags depending on the limit hand
        # e.g. haneman wins will get WINNER_GOT_HANEMAN plus all the flags before that
        limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                            Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                            Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
        limit_hand_names = ["", "mangan", "haneman", "baiman", "sanbaiman", "yakuman"]
        limit_hand_flags = limit_hand_flags[0:limit_hand_names.index(result.score.get_limit_hand_name())+1]
        winner_data = {"seat": result.winner,
                       "hand": winning_hand,
                       "ukeire": self.kyoku.final_ukeire[result.winner],
                       "score_object": result.score,
                       "han": han,
                       "fu": fu,
                       "ura": ura}
        for flag in limit_hand_flags:
            self.add_global_flag(flag, winner_data)
        self.add_flag(result.winner, Flags.YOU_WON, winner_data)
        if self.kyoku.final_ukeire[result.winner] <= 4:
            self.add_global_flag(Flags.WINNER_HAD_BAD_WAIT, winner_data)
        # check for 3+ han from hidden dora
        if result.score.count_dora() >= 3:
            hidden_hand = (*self.at[result.winner].hand.hidden_part, final_tile)
            hidden_dora_han = sum(hidden_hand.count(dora) for dora in self.current_doras)
            if hidden_dora_han >= 3:
                self.add_global_flag(Flags.WINNER_GOT_HIDDEN_DORA_3, {"seat": result.winner, "value": hidden_dora_han})
        # check for 3+ ura
        if result.score.count_ura() >= 3:
            self.add_global_flag(Flags.WINNER_GOT_URA_3, {"seat": result.winner, "value": result.score.count_ura()})
        # check for dora bomb
        if Flags.YOU_FLIPPED_DORA_BOMB in self.flags[result.winner]:
            self.add_global_flag(Flags.WINNER_GOT_KAN_DORA_BOMB, {"seat": result.winner, "value": result.score.count_dora()})
        # check for haitei/houtei
        if result.score.has_haitei():
            haitei_type = "haitei" if ("haitei", 1) in result.score.yaku \
                     else "houtei" if ("houtei", 1) in result.score.yaku \
                     else ""
            assert haitei_type != "", f"unknown haitei type for yaku {result.score.yaku}"
            self.add_global_flag(Flags.WINNER_GOT_HAITEI, {"seat": result.winner, "yaku": haitei_type})

def determine_flags(kyoku: Kyoku) -> Tuple[List[List[Flags]], List[List[Dict[str, Any]]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag in `flags`
    """
    assert kyoku.num_players in {3,4}, f"somehow we have {kyoku.num_players} players"

    # get all flags by parsing kyoku events
    info = KyokuInfo(kyoku = kyoku,
                     num_players = kyoku.num_players,
                     tiles_in_wall = 70 if kyoku.num_players == 4 else 55,
                     starting_doras = kyoku.starting_doras.copy(),
                     current_doras = kyoku.starting_doras.copy(),
                     flags = [[] for i in range(kyoku.num_players)],
                     data = [[] for i in range(kyoku.num_players)])

    debug_prev_flag_len = [0] * info.num_players
    debug_prev_global_flag_len = 0
    for i, event in enumerate(kyoku.events):
        seat, event_type, *event_data = event

        # ### DEBUG ###
        # for i in range(debug_prev_global_flag_len, len(global_flags)):
        #     print(f"  Added global flag: {global_flags[i]} {global_data[i] if global_data[i] is not None else ''}")
        # debug_prev_global_flag_len = len(global_flags)
        # for s in range(kyoku.num_players):
        #     for i in range(debug_prev_flag_len[s], len(flags[s])):
        #         print(f"  Added flag for seat {s}: {flags[s][i]} {data[s][i] if data[s][i] is not None else ''}")
        #     debug_prev_flag_len[s] = len(flags[s])
        # print(round_name(kyoku.round, kyoku.honba), ":", tiles_in_wall, "tiles left |", event)
        # ### DEBUG ###

        if event_type == "haipai":
            info.process_haipai(i, *event)
        elif event_type == "draw":
            info.process_draw(i, *event)
        elif event_type in {"chii", "pon", "minkan"}:
            info.process_chii_pon_kan(i, *event)
        elif event_type in {"ankan", "kakan", "kita"}:
            info.process_self_kan(i, *event)
        elif event_type in {"discard", "riichi"}:
            info.process_discard(i, *event[:3]) # riichi has extra args we don't care about
        elif event_type == "end_nagashi":
            info.process_end_nagashi(i, *event)
        elif event_type == "shanten_change":
            info.process_shanten_change(i, *event)
            # check for tenpai
            prev_shanten, new_shanten, hand, ukeire, furiten = event_data
            if new_shanten[0] == 0:
                info.process_tenpai(i, *event)
        elif event_type == "dora_indicator":
            info.process_new_dora(i, *event)
        elif event_type == "placement_change":
            info.process_placement_change(i, *event)
        elif event_type == "start_game":
            # check if anyone's starting shanten is 2 worse than everyone else
            info.process_start_game(i, *event)
        elif event_type == "result":
            info.process_result(i, *event)


    assert len(info.global_flags) == len(info.global_data), f"somehow got a different amount of global flags ({len(info.global_flags)}) than data ({len(info.global_data)})"
    for seat in range(kyoku.num_players):
        assert len(info.flags[seat]) == len(info.data[seat]), f"somehow got a different amount of flags ({len(info.flags[seat])}) than data ({len(info.data[seat])})"
        info.flags[seat] = info.global_flags + info.flags[seat]
        info.data[seat] = info.global_data + info.data[seat]
    return info.flags, info.data
