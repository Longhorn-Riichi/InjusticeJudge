from .classes import CallInfo, Dir
from .classes2 import Draw, Hand, Kyoku, Ron, Score, Tsumo, Win
from dataclasses import dataclass, field
from .constants import Event, Shanten, JIHAI, LIMIT_HANDS, PRED, SUCC, TRANSLATE, YAKUMAN, YAOCHUUHAI
from .display import ph, pt, print_pond, round_name
from enum import Enum
from .shanten import to_suits, from_suits, eliminate_all_groups
from .utils import apply_delta_scores, get_score, get_taatsu_wait, is_mangan, is_safe, normalize_red_five, normalize_red_fives, to_dora_indicator, to_placement, try_remove_all_tiles
from .wall import print_wall, get_hidden_dead_wall, get_remaining_draws
from .yaku import get_final_yaku, get_yaku, get_yakuman_tenpais, get_yakuman_waits
from typing import *
from pprint import pprint

# This file provides a `Flags` enum and a single function, `determine_flags`,
#   which is called by `evaluate_injustices` in `injustices.py`
# 
# Every flag is generated from an event in Kyoku.events, and the idea in
#   `determine_flags` is to process the events in order, resulting in an
#   ordered list of facts about the given `Kyoku`, one for each player.
#   
# Flags are represented by a list of `Flags` objects, each one corresponding
#   to a fact and each one associated with some data represented by a `data`
#   dict. The list of `data` dicts is returned alongside the `flags` list,
#   where the data at index `i` corresponds to the flag at index `i`. There's
#   no documentation on the `data` dict associated with each type of flag --
#   you'll have to go down and examine the code generating that specific
#   flag.
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
    " ALL_LAST"
    " ALL_TENPAI_DISCARDS_DEAL_IN"
    " ANKAN_ERASED_TENPAI_WAIT"
    " BAD_HONITSU_DRAWS"
    " CALLS_CONTAIN_THREE_DORA"
    " CHANGED_WAIT_ON_LAST_DISCARD"
    " CHASER_GAINED_POINTS"
    " CHASER_LOST_POINTS"
    " CHII_GOT_OVERRIDDEN"
    " COULD_HAVE_RONNED"
    " COULD_HAVE_TSUMOED"
    " DEAL_IN_TILE_WAS_LAST_DISCARD"
    " DREW_LAST_HONOR_AFTER_SKIPPING_THIRD"
    " DREW_WORST_HAIPAI_SHANTEN"
    " EVERYONE_DISRESPECTED_YOUR_RIICHI"
    " EVERYONE_RESPECTED_YOUR_RIICHI"
    " FINAL_ROUND"
    " FIRST_ROW_TENPAI"
    " FIVE_SHANTEN_START"
    " FOUR_DANGEROUS_DRAWS_AFTER_RIICHI"
    " FOUR_SHANTEN_AFTER_FIRST_ROW"
    " GAME_ENDED_WITH_ABORTIVE_DRAW"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " GAME_ENDED_WITH_TSUMO"
    " IISHANTEN_HAIPAI_ABORTED"
    " IISHANTEN_START"
    " IISHANTEN_WITH_ZERO_TILES"
    " IMMEDIATELY_DREW_DISCARDED_DORA"
    " IMMEDIATELY_DREW_DISCARDED_TILE"
    " LAST_DISCARD_WAS_RIICHI"
    " LAST_CALL_TENPAI"
    " LAST_DRAW_TENPAI"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " MULTIPLE_RON"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " PASSED_FOUR_DANGEROUS_DISCARDS"
    " REACHED_DOUBLE_STARTING_POINTS"
    " SEVEN_TERMINAL_START"
    " SIX_DISCARDS_TSUMOGIRI_HONOR"
    " SIX_TSUMOGIRI_WITHOUT_TENPAI"
    " SOMEONE_FOLDED_FROM_TENPAI"
    " SOMEONE_HAS_THREE_DORA_VISIBLE"
    " SOMEONE_REACHED_TENPAI"
    " SOMEONE_WAITED_ON_WINNING_TILE"
    " STARTED_WITH_3_DORA"
    " TENPAI_ON_LAST_DISCARD"
    " TURN_SKIPPED_BY_PON"
    " WAIT_WAS_IN_DEAD_WALL"
    " WAITED_TO_RIICHI"
    " WINNER"
    " WINNER_GOT_BAIMAN"
    " WINNER_GOT_DOUBLE_WIND"
    " WINNER_GOT_HAITEI"
    " WINNER_GOT_HANEMAN"
    " WINNER_GOT_HIDDEN_DORA_3"
    " WINNER_GOT_IPPATSU"
    " WINNER_GOT_KAN_DORA_BOMB"
    " WINNER_GOT_MANGAN"
    " WINNER_GOT_SANBAIMAN"
    " WINNER_GOT_URA_3"
    " WINNER_GOT_YAKUMAN"
    " WINNER_HAD_BAD_WAIT"
    " WINNER_HAD_NAKED_TANKI"
    " WINNER_IPPATSU_TSUMO"
    " WINNER_WAS_DAMA"
    " WINNER_WAS_FURITEN"
    " WINNER_WON_WITH_PON_PON_RON"
    " WON_AFTER_CHANGING_WAIT"
    " YOU_ACHIEVED_NAGASHI"
    " YOU_ALMOST_GOT_NAGASHI"
    " YOU_ARE_DEALER"
    " YOU_AVOIDED_LAST_PLACE"
    " YOU_CAN_CALL_RON"
    " YOU_CAN_CALL_TSUMO"
    " YOU_CHASED"
    " YOU_CHOSE_WRONG_TENPAI"
    " YOU_DEALT_IN"
    " YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT"
    " YOU_DECLARED_RIICHI"
    " YOU_DREW_CALLABLE_TILE"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
    " YOU_DROPPED_PLACEMENT"
    " YOU_DREW_THREE_SINGLE_WAITS"
    " YOU_FLIPPED_DORA_BOMB"
    " YOU_FOLDED_FROM_TENPAI"
    " YOU_GAINED_PLACEMENT"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_GOT_NON_COUNTED_YAKUMAN"
    " YOU_HAD_LIMIT_TENPAI"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_REACHED_YAKUMAN_TENPAI"
    " YOU_RONNED_SOMEONE"
    " YOU_SKIPPED_RON"
    " YOU_SKIPPED_TSUMO"
    " YOU_TENPAI_FIRST"
    " YOU_TSUMOED"
    " YOU_WAITED_ON_WINNING_TILE"
    " YOU_WERE_FIRST"
    " YOU_WERE_SECOND"
    " YOU_WERE_THIRD"
    " YOU_WERE_FOURTH"
    " YOU_WON"
    " YOU_WON_OFF_RIICHI_TILE"
    " YOU_WON_AFTER_SOMEONES_RIICHI"
    " YOUR_FURITEN_HAND_COULD_HAVE_WON"
    " YOUR_LAST_DISCARD_ENDED_NAGASHI"
    " YOUR_LAST_NAGASHI_TILE_CALLED"
    " YOUR_RIICHI_TILE_DEALT_IN"
    " YOUR_TENPAI_TILE_DEALT_IN"
    " YOUR_TILES_ALL_DEAL_IN"
    " YOUR_WIN_BLOCKED_BY_TEMP_FURITEN"
    " YOUR_YAKULESS_HAND_COULD_HAVE_WON"
    )

@dataclass
class KyokuPlayerState:
    """The state of a player that gets updated as we calculate flags."""
    num_players: int
    hand: Hand
    pond: List[int]                                   = field(default_factory=list)
    genbutsu: Set[int]                                = field(default_factory=set)
    turn: int                                         = 0
    draws_since_shanten_change: int                   = 0
    tsumogiri_honor_discards: int                     = 0
    tsumogiri_without_tenpai: int                     = 0
    num_discards: int                                 = 0
    last_draw: int                                    = 0
    consecutive_calls: int                            = 0
    last_discard: int                                 = 0
    last_discard_was_riichi: bool                     = False
    furiten: bool                                     = False
    temporary_furiten: Optional[Tuple[Dir, int]]      = None
    nagashi: bool                                     = True
    in_riichi: bool                                   = False
    riichi_index: Optional[int]                       = None
    consecutive_off_suit_tiles: List[int]             = field(default_factory=list)
    past_waits: List[List[int]]                       = field(default_factory=list)
    dangerous_discards_passed: List[int]              = field(default_factory=list)
    dangerous_draws_after_riichi: List[int]           = field(default_factory=list)
    respects_riichi: List[Optional[bool]]             = field(default_factory=list)
    chiiable_tiles: Set[int]                          = field(default_factory=set)
    ponnable_tiles: Set[int]                          = field(default_factory=set)
    passed_calls: List[Tuple[str, int, Dir]]          = field(default_factory=list)
    all_passed_calls: List[Tuple[str, int, Dir, int]] = field(default_factory=list)
    single_wait_fills: List[Tuple[int, ...]]          = field(default_factory=list)
    def __post_init__(self) -> None:
        # respects_riichi[other_player] =
        #   True if their first discard after our riichi was a safe tile
        #   False if their first discard after our riichi was a dangerous tile
        #   None if they didn't discard after our riichi yet
        self.respects_riichi = [None] * self.num_players

@dataclass
class KyokuState:
    """
    Information about a round, the most important being the flags.
    Also provides a method for each event that generates flags for the event.
    """
    kyoku: Kyoku
    num_players: int
    tiles_in_wall: int              = 0
    num_kitas: int                  = 0
    num_kans: int                   = 0
    pending_kan: Optional[CallInfo] = None
    starting_doras: List[int]       = field(default_factory=list) # TODO 3 starting doras
    current_doras: List[int]        = field(default_factory=list)
    at: List[KyokuPlayerState]      = field(default_factory=list)
    visible_tiles: List[int]        = field(default_factory=list) # TODO remove
    flags: List[List[Flags]]        = field(default_factory=list)
    data: List[List[Any]]           = field(default_factory=list)
    global_flags: List[Flags]       = field(default_factory=list)
    global_data: List[Any]          = field(default_factory=list)
    def get_visible_tiles(self) -> List[int]:
        return self.visible_tiles \
             + [to_dora_indicator(dora, self.num_players) for dora in self.current_doras if dora not in {51,52,53}]
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
    def remove_global_flag(self, flag: Flags, data: Optional[Dict[str, Any]] = None) -> None:
        ix = None
        for i, f in enumerate(self.global_flags):
            if f == flag and (data is None or self.global_data[i] == data):
                ix = i
                break
        if ix is not None:
            del self.global_flags[ix]
            del self.global_data[ix]

    def process_haipai(self, i: int, seat: int, event_type: str, hand: Tuple[int, ...]) -> None:
        assert len(self.at) == seat, f"got haipai out of order, expected seat {len(self.at)} but got seat {seat}"
        self.at.append(KyokuPlayerState(num_players=self.num_players, hand=Hand(hand), nagashi=self.kyoku.rules.nagashi_mangan))
        # check if we have at least 7 terminal/honor tiles
        num_types = len(set(hand) & YAOCHUUHAI) # of terminal/honor tiles
        if num_types >= 7:
            self.add_flag(seat, Flags.SEVEN_TERMINAL_START, {"num_types": num_types})
        # check if we have a iishanten start or better
        if self.at[seat].hand.shanten[0] <= 1:
            self.add_flag(seat, Flags.IISHANTEN_START, {"hand": self.at[seat].hand})
        # check if we have a 5 shanten start or worse
        if self.at[seat].hand.shanten[0] >= 5:
            self.add_flag(seat, Flags.FIVE_SHANTEN_START, {"hand": self.at[seat].hand})
        # check if we started with 3 dora
        starting_dora = sum(hand.count(dora) for dora in self.kyoku.get_starting_doras())
        if starting_dora >= 3:
            self.add_flag(seat, Flags.STARTED_WITH_3_DORA, {"num": starting_dora})

    def process_draw(self, i: int, seat: int, event_type: str, tile: int) -> None:
        prev_hand = self.at[seat].hand
        self.at[seat].hand = self.at[seat].hand.add(tile)
        self.at[seat].turn += 1
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
        majority_suit = self.at[seat].hand.get_majority_suit()
        if majority_suit is not None and tile not in majority_suit | JIHAI:
            honitsu_tiles = majority_suit | JIHAI
            majority_tiles = tuple(tile for tile in self.at[seat].hand.tiles if tile in honitsu_tiles)
            enough_honitsu_tiles = len(majority_tiles) >= 12 - int(self.at[seat].hand.shanten[0])
            no_off_suit_calls = all(call.tile in honitsu_tiles for call in self.at[seat].hand.calls)
            going_for_honitsu = enough_honitsu_tiles and no_off_suit_calls
        if going_for_honitsu:
            # tick up a counter if you drew off-suit tiles in a row
            self.at[seat].consecutive_off_suit_tiles.append(tile)
            if len(self.at[seat].consecutive_off_suit_tiles) >= 6:
                self.add_flag(seat, Flags.BAD_HONITSU_DRAWS,
                                    {"tiles": self.at[seat].consecutive_off_suit_tiles,
                                     "hand": prev_hand})
        else:
            self.at[seat].consecutive_off_suit_tiles = []
        # check if there's a riichi, we drew a dangerous tile, and we have no safe tiles
        for opponent, at in enumerate(self.at):
            if seat == opponent or not at.in_riichi:
                continue
            safe = lambda t: is_safe(t, self.at[opponent].genbutsu, self.get_visible_tiles())
            if not safe(tile) and not any(safe(t) for t in self.at[seat].hand.hidden_part):
                self.at[seat].dangerous_draws_after_riichi.append(tile)
                if len(self.at[seat].dangerous_draws_after_riichi) >= 4:
                    self.add_flag(seat, Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI,
                                        {"tiles": self.at[seat].dangerous_draws_after_riichi,
                                         "opponent": opponent,
                                         "pond_str": print_pond(self.at[opponent].pond, self.current_doras, self.at[opponent].riichi_index)
                                         })
                break
        # check if we drew something we just declined a call for
        for call_type, call_tile, call_direction in reversed(self.at[seat].passed_calls):
            if normalize_red_five(tile) == call_tile:
                self.add_flag(seat, Flags.YOU_DREW_CALLABLE_TILE,
                                    {"call_type": call_type,
                                     "call_tile": tile,
                                     "call_direction": call_direction})
                break
        # if the call is honors and we have three of them now, check if it was ever callable by us
        if tile in JIHAI and self.at[seat].hand.tiles.count(tile) == 3:
            for call_type, call_tile, call_direction, turn in self.at[seat].all_passed_calls:
                if call_tile == tile:
                    self.add_flag(seat, Flags.DREW_LAST_HONOR_AFTER_SKIPPING_THIRD,
                                        {"tile": tile,
                                         "call_direction": call_direction,
                                         "turns_ago": self.at[seat].turn - turn})
                    break
        # see if we filled a kanchan/penchan from a draw
        old_groups_removed = next(from_suits(eliminate_all_groups(to_suits(tuple(normalize_red_fives(prev_hand.hidden_part))))))
        new_groups_removed = next(from_suits(eliminate_all_groups(to_suits(tuple(normalize_red_fives(self.at[seat].hand.hidden_part))))))
        taatsu_filled = try_remove_all_tiles(old_groups_removed, new_groups_removed)
        if taatsu_filled != old_groups_removed:
            import os
            if os.getenv("debug"):
                assert len(taatsu_filled) == 2, "filled taatsu was not length 2"
            if len(taatsu_filled) == 2:
                (t1, t2) = sorted(taatsu_filled)
                is_penchan = t2 == SUCC[t1] and 0 in (PRED[t1], SUCC[t2])
                is_kanchan = t2 == SUCC[SUCC[t1]]
                if is_penchan or is_kanchan:
                    self.at[seat].single_wait_fills.append(taatsu_filled)
                    if len(self.at[seat].single_wait_fills) >= 3:
                        self.add_flag(seat, Flags.YOU_DREW_THREE_SINGLE_WAITS, {"taatsus": self.at[seat].single_wait_fills})

        self.at[seat].consecutive_calls = 0
        self._process_draw_call(i, seat, event_type, tile, prev_hand)

    def process_chii_pon_daiminkan(self, i: int, seat: int, event_type: str, called_tile: int, call_tiles: Tuple[int, ...], call_dir: Dir) -> None:
        self.at[seat].turn += 1
        self.at[seat].consecutive_calls += 1
        prev_hand = self.at[seat].hand
        if event_type != "minkan":
            self.at[seat].hand = self.at[seat].hand.add(called_tile)
        call = CallInfo(event_type, called_tile, call_dir, call_tiles)
        self.at[seat].hand = self.at[seat].hand.add_call(call)
        # end their nagashi
        callee_seat = (seat + call_dir) % 4
        if self.at[callee_seat].nagashi:
            self.at[callee_seat].nagashi = False
            # check if this happened after our final draw (if the game ended in ryuukyoku)
            if self.kyoku.result[0] == "ryuukyoku" and i > self.kyoku.final_draw_event_index[seat]:
                self.add_flag(callee_seat, Flags.YOUR_LAST_NAGASHI_TILE_CALLED, {"tile": called_tile, "caller": seat})
        if event_type in {"pon", "minkan"}:
            # for everyone whose turn was skipped, add Flags.TURN_SKIPPED_BY_PON
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
            # check if this could have overridden a chii call that would have brought us into tenpai
            chii_seat = (seat+call_dir+1)%4
            if chii_seat < len(self.at) and len(self.at[chii_seat].hand.tiles) == 13 and 1 < self.at[chii_seat].hand.shanten[0] < 2:
                call_hand = self.at[chii_seat].hand.add(called_tile)
                best_score = None
                chii_data = None
                for chii in call_hand.possible_chiis(called_tile):
                    chii_hand = call_hand.add_call(chii)
                    for discard, tenpai in chii_hand.get_possible_tenpais().items():
                        score = max(get_yaku(
                            hand = tenpai,
                            events = self.kyoku.events[:i],
                            doras = self.kyoku.doras,
                            uras = self.kyoku.uras,
                            round = self.kyoku.round,
                            seat = chii_seat,
                            is_last_tile = self.kyoku.tiles_in_wall == 0,
                            num_players = self.num_players,
                            rules = self.kyoku.rules,
                            check_rons = True,
                            check_tsumos = True).values())
                        is_limit = score.han >= 6 or is_mangan(score.han, score.fu)
                        if score.han >= 4: # minimum of 4 han to trigger this flag
                            if best_score is None or score > best_score:
                                best_score = score
                                chii_data = {"score": score,
                                             "tile": called_tile,
                                             "hand_name": TRANSLATE[LIMIT_HANDS[score.han]] if is_limit else f"{score.han} han {score.fu} fu",
                                             "chii": chii,
                                             "caller": seat,
                                             "orig_call_name": "pon" if call.type == "pon" else "kan"}
                if best_score is not None:
                    self.add_flag(chii_seat, Flags.CHII_GOT_OVERRIDDEN, chii_data)

        self._process_call(seat, call)
        self._process_draw_call(i, seat, event_type, called_tile, prev_hand)

    def _process_draw_call(self, i: int, seat: int, event_type: str, tile: int, prev_hand: Hand) -> None:
        # clear all passed calls
        self.at[seat].passed_calls = []
        # check if we're still 4-shanten or worse after the first row of discards
        if self.at[seat].num_discards == 6 and prev_hand.shanten[0] >= 4:
            self.add_flag(seat, Flags.FOUR_SHANTEN_AFTER_FIRST_ROW, {"shanten": prev_hand.shanten})
        # check if we're iishanten with zero tiles left
        if 1 <= self.at[seat].hand.shanten[0] < 2:
            ukeire = self.at[seat].hand.ukeire(self.get_visible_tiles())
            if ukeire == 0:
                self.add_flag(seat, Flags.IISHANTEN_WITH_ZERO_TILES, {"shanten": self.at[seat].hand.shanten})
        # check if we drew into potential tenpai
        # but every discard that would give us tenpai deals into someone
        if 0 <= prev_hand.shanten[0] < 2:
            just_reached_tenpai = tile in prev_hand.shanten[1]
            deals_into_someone = lambda tile: any(at.hand.shanten[0] == 0 and tile in at.hand.shanten[1] for at in self.at)
            for player in range(self.num_players):
                if player == seat:
                    continue
                tenpai_discards = self.at[seat].hand.get_possible_tenpais()
                if len(tenpai_discards) >= 1 and all(deals_into_someone(discard) for discard in tenpai_discards.keys()):
                    self.add_flag(seat, Flags.ALL_TENPAI_DISCARDS_DEAL_IN, {
                        "hand": self.at[seat].hand,
                        "discards": tuple(tenpai_discards.keys()),
                        "just_reached_tenpai": just_reached_tenpai,
                        "furiten": all(any(tile in self.at[seat].pond for tile in hand.shanten[1]) for hand in tenpai_discards.values())})

    def process_self_kan(self, i: int, seat: int, event_type: str, called_tile: int, call_tiles: Tuple[int, ...], call_dir: Dir) -> None:
        self.at[seat].turn += 1
        self.at[seat].consecutive_calls += 1
        if event_type == "kakan":
            i, self.at[seat].hand = self.at[seat].hand.kakan(called_tile)
            call = self.at[seat].hand.calls[i]
            # add to genbutsu for this player + all the riichi players
            for player in {player for player, at in enumerate(self.at) if at.in_riichi} | {seat}:
                self.at[player].genbutsu.add(called_tile)
        elif event_type == "ankan":
            call = CallInfo("ankan", called_tile, Dir.SELF, (called_tile,)*4)
            self.at[seat].hand = self.at[seat].hand.add_call(call)
        elif event_type == "kita":
            self.at[seat].hand = self.at[seat].hand.kita()
            self.num_kitas += 1
            call = self.at[seat].hand.calls[-1]
        else:
            assert False, f"process_self_kan called with non-self-kan type {event_type}"
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
                    wait = last_tenpai_data["hand"].shanten[1]
                    ukeire = last_tenpai_data["ukeire"]
                    if tile in wait:
                        self.add_flag(player, Flags.ANKAN_ERASED_TENPAI_WAIT, {"tile": tile, "wait": wait, "caller": seat, "ukeire": ukeire})
        self._process_call(seat, call)

    def process_discard(self, i: int, seat: int, event_type: str, tile: int) -> None:
        if event_type == "riichi":
            self.at[seat].riichi_index = len(self.at[seat].pond)
        prev_hand = self.at[seat].hand
        prev_discard = self.at[seat].last_discard
        self.at[seat].hand = self.at[seat].hand.remove(tile)
        self.visible_tiles.append(tile)
        self.at[seat].pond.append(tile)
        self.at[seat].num_discards += 1
        self.at[seat].last_discard = tile
        self.at[seat].last_discard_was_riichi = event_type == "riichi"
        # clear temporary furiten, unless we are already in riichi
        if not self.at[seat].in_riichi:
            self.at[seat].temporary_furiten = None
        # check if this makes us furiten
        if self.at[seat].hand.shanten[0] == 0 and normalize_red_five(tile) in self.at[seat].hand.shanten[1]:
            self.at[seat].furiten = True
        # check if this ends our nagashi
        if self.at[seat].nagashi and tile not in YAOCHUUHAI:
            self.at[seat].nagashi = False
            # check if this happened after our final draw (if the game ended in ryuukyoku)
            if self.kyoku.result[0] == "ryuukyoku" and i > self.kyoku.final_draw_event_index[seat]:
                self.add_flag(seat, Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI, {"tile": tile})
        # add riichi flag
        if event_type == "riichi":
            self.at[seat].in_riichi = True
            self.add_flag(seat, Flags.YOU_DECLARED_RIICHI)
            # if there's a triple riichi, give Flags.AGAINST_TRIPLE_RIICHI to the non-riichi person
            if self.num_players == 4 and sum(1 for at in self.at if at.in_riichi) == 3:
                non_riichi_seat = next(i for i, b in enumerate(self.at) if b.in_riichi == False)
                self.add_flag(non_riichi_seat, Flags.AGAINST_TRIPLE_RIICHI)
            # check if we waited to riichi
            if prev_hand.prev_shanten[0] == 0:
                self.add_flag(seat, Flags.WAITED_TO_RIICHI)
        # check if this is the deal-in tile
        is_last_discard_of_the_game = i == max(self.kyoku.final_discard_event_index)
        if is_last_discard_of_the_game and self.kyoku.result[0] == "ron":
            # check if this ron was on a riichi discard
            if event_type == "riichi":
                self.add_flag(seat, Flags.YOUR_RIICHI_TILE_DEALT_IN, {"tile": tile})
                for win in self.kyoku.result[1:]:
                    self.add_flag(win.winner, Flags.YOU_WON_OFF_RIICHI_TILE, {"seat": seat, "tile": tile})
            # check if this ron was on a tenpai discard
            if any(e[0] == seat and e[1] == "tenpai" for e in self.kyoku.events[i:]):
                # check if we just became tenpai
                if Flags.YOU_REACHED_TENPAI not in self.flags[seat]:
                    self.add_flag(seat, Flags.YOUR_TENPAI_TILE_DEALT_IN, {"tile": tile})
                # check if we dealt in on our last discard before getting noten payments
                if self.tiles_in_wall <= 3:
                    self.add_flag(seat, Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT, {"tile": tile})
            # check if we had no choice but to deal in
            waits = {player: wait
                     for player in range(self.num_players)
                     if player != seat
                     for (shanten, wait) in (self.at[player].hand.shanten,)
                     if shanten == 0
                     if any(tile in wait for tile in self.at[seat].hand.hidden_part)}
            if all(any(tile in wait for wait in waits.values()) for tile in self.at[seat].hand.hidden_part):
                self.add_flag(seat, Flags.YOUR_TILES_ALL_DEAL_IN, {"hand": prev_hand, "waits": waits})
            # check if the tile we discarded last turn was the same tile
            # (i.e. the person calling ron on us _just_ started waiting on that tile)
            if normalize_red_five(tile) == normalize_red_five(prev_discard):
                self.add_flag(seat, Flags.DEAL_IN_TILE_WAS_LAST_DISCARD, {"prev_tile": prev_discard, "tile": tile})
        # flip kan dora, if needed
        if self.pending_kan is not None:
            self._process_new_dora(seat, self.pending_kan)
            self.pending_kan = None

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
                self.add_flag(seat, Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI, {"num_discards": self.at[seat].tsumogiri_without_tenpai, "shanten": self.at[seat].hand.shanten})
        else:
            self.at[seat].tsumogiri_without_tenpai = 0
        # check if this discard respects/disrespects anyone's riichi
        for opponent, at in enumerate(self.at):
            if at.in_riichi and self.at[opponent].respects_riichi[seat] is None: # first discard after opponent's riichi
                self.at[opponent].respects_riichi[seat] = is_safe(tile, self.at[opponent].genbutsu, self.get_visible_tiles())
                if all(self.at[opponent].respects_riichi[player] == False for player in range(self.num_players) if player != opponent):
                    self.add_flag(opponent, Flags.EVERYONE_DISRESPECTED_YOUR_RIICHI)
                elif all(self.at[opponent].respects_riichi[player] == True for player in range(self.num_players) if player != opponent):
                    self.add_flag(opponent, Flags.EVERYONE_RESPECTED_YOUR_RIICHI)
        # if we're not tenpai and there's a riichi, check if this discard passed
        if self.at[seat].hand.shanten[0] > 0:
            riichi_waits = {player: at.hand.shanten[1] for player, at in enumerate(self.at) if at.in_riichi}
            if len(riichi_waits) > 0 and not any(tile in waits for waits in riichi_waits.values()):
                # check if it was dangerous against any of the riichis
                is_generally_safe = tile in YAOCHUUHAI
                if not is_generally_safe and any(not is_safe(tile, self.at[player].genbutsu, self.get_visible_tiles()) for player in riichi_waits.keys()):
                    self.at[seat].dangerous_discards_passed.append(tile)
                    if len(self.at[seat].dangerous_discards_passed) >= 4:
                        self.add_flag(seat, Flags.PASSED_FOUR_DANGEROUS_DISCARDS, {"discards": self.at[seat].dangerous_discards_passed})
        # add to genbutsu for this player + all the riichi players
        for player in {player for player, at in enumerate(self.at) if at.in_riichi} | {seat}:
            self.at[player].genbutsu.add(tile)
        # populate passed_calls/all_passed_calls for every player who could have called this discard
        for player, at in enumerate(self.at):
            if player == seat:
                continue
            call_direction = Dir((4+seat-player)%4)
            if call_direction == Dir.KAMICHA and normalize_red_five(tile) in at.chiiable_tiles:
                at.passed_calls.append(("chii", tile, call_direction))
                at.all_passed_calls.append(("chii", tile, call_direction, at.turn))
            if normalize_red_five(tile) in at.ponnable_tiles:
                at.passed_calls.append(("pon", tile, call_direction))
                at.all_passed_calls.append(("pon", tile, call_direction, at.turn))
        # check if anyone can ron/tsumo on this discard
        for player, at in enumerate(self.at):
            is_tsumo = player == seat
            if at.hand.shanten[0] == 0 and normalize_red_five(tile) in at.hand.shanten[1]:
                # check if we were yakuless, which would prevent us from winning
                yaku = get_yaku(hand = at.hand,
                                events = self.kyoku.events,
                                doras = self.current_doras,
                                uras = self.kyoku.uras,
                                round = self.kyoku.round,
                                seat = player,
                                is_last_tile = self.tiles_in_wall == 0,
                                num_players = self.num_players,
                                rules = self.kyoku.rules,
                                check_rons = not is_tsumo,
                                check_tsumos = is_tsumo)
                current_dir = Dir((4+seat-player)%4)
                # check if we were furiten, which would prevent us from ronning
                furiten = not is_tsumo and (at.furiten or at.temporary_furiten is not None)
                if furiten:
                    self.add_flag(player, Flags.YOUR_FURITEN_HAND_COULD_HAVE_WON, {"tile": tile, "wait": at.hand.shanten[1], "turns_left": self.tiles_in_wall})
                    if not at.furiten:
                        self.add_flag(player, Flags.YOUR_WIN_BLOCKED_BY_TEMP_FURITEN, {"tile": tile, "wait": at.hand.shanten[1], "turns_left": self.tiles_in_wall, "discard_dir": current_dir, "furiten_dir": at.temporary_furiten[0], "furiten_tile": at.temporary_furiten[1]})

                yakuless = yaku[normalize_red_five(tile)].is_yakuless()
                if yakuless:
                    self.add_flag(player, Flags.YOUR_YAKULESS_HAND_COULD_HAVE_WON, {"tile": tile, "wait": at.hand.shanten[1], "turns_left": self.tiles_in_wall})
                    # set temporary furiten
                    at.temporary_furiten = (current_dir, tile)

                # otherwise, we can legally call ron/tsumo on this discard
                if not yakuless and not furiten:
                    flag = Flags.YOU_CAN_CALL_TSUMO if is_tsumo else Flags.YOU_CAN_CALL_RON
                    self.add_flag(player, flag, {"tile": tile, "wait": at.hand.shanten[1], "turns_left": self.tiles_in_wall})
        # check if this discard puts us from not tenpai to tenpai
        if prev_hand.prev_shanten[0] > 0 and self.at[seat].hand.shanten[0] == 0:
            # check if we could have discarded something else for a different tenpai wait
            possible_tenpais = prev_hand.get_possible_tenpais()
            other_tenpais: Dict[int, Set[int]] = {} # wait => tiles you could have discarded
            for tile, tenpai_hand in possible_tenpais.items():
                if self.at[seat].hand.shanten[1] != tenpai_hand.shanten[1]:
                    for wait in tenpai_hand.shanten[1]:
                        if wait not in self.at[seat].hand.shanten[1]:
                            if wait not in other_tenpais:
                                other_tenpais[wait] = set()
                            other_tenpais[wait].add(tile)
            # now check if the very next discard would have dealt into one of those tenpai waits
            next_discard = next((event_data[0] for _, event_type, *event_data in self.kyoku.events[i+1:] if event_type in ["discard", "riichi"]), None)
            if next_discard in other_tenpais:
                data = {
                    "next_discard": next_discard,
                    "chosen_wait": self.at[seat].hand.shanten[1],
                    "counterfactual_discards": other_tenpais[next_discard],
                    "possible_tenpais": possible_tenpais
                }
                self.add_flag(seat, Flags.YOU_CHOSE_WRONG_TENPAI, data)

    def process_shanten_change(self, i: int, seat: int, event_type: str,
                               prev_shanten: Shanten, new_shanten: Shanten,
                               hand: Hand, ukeire: int, furiten: bool) -> None:
        assert new_shanten[0] >= 0, f"somehow shanten for seat {seat} was {new_shanten[0]}"
        self.at[seat].draws_since_shanten_change = 0
        # get all possible chii/pon calls (not kan)
        tiles = tuple(normalize_red_fives(hand.hidden_part))
        tiles_unique = tuple(set(tiles))
        self.at[seat].chiiable_tiles = set().union(*map(get_taatsu_wait, zip(tiles_unique[:-1],tiles_unique[1:])),
                                                   *map(get_taatsu_wait, zip(tiles_unique[:-2],tiles_unique[2:])))
        self.at[seat].ponnable_tiles = {k for k, v in Counter(tiles).items() if v in {2, 3}}
        # record past waits if we've changed from tenpai
        if prev_shanten[0] == 0:
            self.at[seat].past_waits.append(list(prev_shanten[1]))
            if new_shanten[0] > 0:
                self.add_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)
                self.add_global_flag(Flags.SOMEONE_FOLDED_FROM_TENPAI, {"seat": seat})

    def process_tenpai(self, i: int, seat: int, event_type: str,
                       prev_shanten: Shanten, new_shanten: Shanten,
                       hand: Hand, ukeire: int, furiten: bool) -> None:
        self.at[seat].furiten = furiten
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
                    visible_tiles = self.get_visible_tiles()
                    self.add_flag(seat, Flags.YOU_CHASED,
                                         {"your_seat": seat,
                                          "your_hand": hand,
                                          "your_ukeire": hand.ukeire(visible_tiles),
                                          "your_furiten": furiten,
                                          "seat": other,
                                          "hand": other_data["hand"],
                                          "ukeire": other_data["hand"].ukeire(visible_tiles),
                                          "furiten": other_data["furiten"]})
                    self.add_flag(other, Flags.YOU_GOT_CHASED,
                                         {"seat": seat,
                                          "hand": hand,
                                          "ukeire": hand.ukeire(visible_tiles),
                                          "furiten": furiten,
                                          "your_seat": other,
                                          "your_hand": other_data["hand"],
                                          "your_ukeire": other_data["hand"].ukeire(visible_tiles),
                                          "your_furiten": other_data["furiten"]})
        self.add_global_flag(Flags.SOMEONE_REACHED_TENPAI,
                             {"seat": seat,
                              "hand": hand,
                              "furiten": furiten,
                              "turn": len(self.at[seat].pond),
                              "haipai": self.kyoku.haipai[seat]})
        self.add_flag(seat, Flags.YOU_REACHED_TENPAI,
                            {"hand": hand,
                             "ukeire": hand.ukeire(self.get_visible_tiles()),
                             "furiten": furiten,
                             "turn": len(self.at[seat].pond),
                             "haipai": self.kyoku.haipai[seat]})
        # check for first row tenpai
        if self.at[seat].num_discards <= 6:
            self.add_flag(seat, Flags.FIRST_ROW_TENPAI, {"seat": seat, "turn": self.at[seat].num_discards})
        # check for last draw/call tenpai
        if self.tiles_in_wall <= 3 and prev_shanten[0] > 0:
            flag = Flags.LAST_CALL_TENPAI if self.at[seat].consecutive_calls > 0 else Flags.LAST_DRAW_TENPAI
            self.add_flag(seat, flag, {"seat": seat, "turn": self.at[seat].num_discards})

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
            self.remove_global_flag(Flags.SOMEONE_FOLDED_FROM_TENPAI, {"seat": seat})

        # check if we are mangan+ tenpai
        get_yaku_args = {
            "hand": hand,
            "events": self.kyoku.events[:i],
            "doras": self.kyoku.doras,
            "uras": self.kyoku.uras if self.at[seat].in_riichi else [],
            "round": self.kyoku.round,
            "seat": seat,
            "is_last_tile": self.kyoku.tiles_in_wall == 0,
            "num_players": self.kyoku.num_players,
            "rules": self.kyoku.rules,
        }
        # if no calls, use tsumo score. else, get ron score
        calls_present = len(get_yaku_args["hand"].calls) > 0  # type: ignore[attr-defined]
        all_scores = get_yaku(**get_yaku_args, check_rons = calls_present, check_tsumos = not calls_present)  # type: ignore[arg-type]
        visible_tiles = self.kyoku.get_visible_tiles()
        formatted_scores = [(score, wait) for wait, score in all_scores.items() if visible_tiles.count(wait) > 0]
        if len(formatted_scores) > 0: # if wait is not dead
            best_score, takame = max(formatted_scores)
            han = best_score.han
            fu = best_score.fu
            # if we added tsumo, then we might not need the extra han from menzentsumo
            # (e.g. 6 han + tsumo -> 7 han, still haneman, no need for tsumo)
            # recalculate fu for a ron, and return that score if it results in the same limit hand
            recalculate = han in {7, 9, 10, 12} or is_mangan(han-1, fu)
            if recalculate and not calls_present:
                ron_scores = get_yaku(**get_yaku_args, check_rons = True, check_tsumos = False)  # type: ignore[arg-type]
                formatted_ron_scores = [(score, wait) for wait, score in ron_scores.items() if visible_tiles.count(wait) > 0]
                if len(formatted_ron_scores) > 0: # if wait is not dead
                    best_ron_score, ron_takame = max(formatted_ron_scores)
                    ron_han = best_score.han
                    ron_fu = best_score.fu
                    if LIMIT_HANDS[ron_han] == LIMIT_HANDS[han] or (is_mangan(han, fu) and is_mangan(ron_han, ron_fu)):
                        best_score = best_ron_score
                        takame = ron_takame
            han = best_score.han
            fu = best_score.fu
            if han >= 5 or is_mangan(han, fu):
                hand_str = hand.print_hand_details(ukeire=ukeire, final_tile=None, furiten=furiten, doras=self.kyoku.doras, uras=self.kyoku.uras if self.at[seat].in_riichi else [])
                self.add_flag(seat, Flags.YOU_HAD_LIMIT_TENPAI,
                               {"hand_str": hand_str,
                                "takame": takame,
                                "limit_name": TRANSLATE[LIMIT_HANDS[han]],
                                "yaku_str": ", ".join(name for name, value in best_score.yaku),
                                "han": han,
                                "fu": fu})

            # check if we are yakuman tenpai
            # first, do standard yakuman, otherwise, try kazoe yakuman
            yakuman_waits: List[Tuple[str, Set[int]]] = [(y, get_yakuman_waits(self.at[seat].hand, y)) for y in get_yakuman_tenpais(self.at[seat].hand)]
            # only report the yakuman if the waits are not dead
            visible = self.get_visible_tiles()
            yakuman_types: Set[str] = {t for t, waits in yakuman_waits if not all(visible.count(wait) == 4 for wait in waits)}
            if len(yakuman_types) > 0:
                self.add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"hand": self.at[seat].hand, "types": yakuman_types, "waits": yakuman_waits})
            elif han >= 13 and not any(y in YAKUMAN for y, _ in best_score.yaku):
                # filter for only the waits that let you reach kazoe yakuman
                kazoe_waits: List[Tuple[str, Set[int]]] = [("kazoe yakuman", {wait for wait, score in all_scores.items() if score.han >= 13})]
                self.add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"hand": self.at[seat].hand, "types": {f"kazoe yakuman ({', '.join(y for y, _ in best_score.yaku)})"}, "waits": kazoe_waits})

    def process_start_game(self, i: int, seat: int, event_type: str,
                           round: int, honba: int, riichi_sticks: int, scores: List[int]) -> None:
        # give dealer a flag saying that they're dealer
        self.add_flag(round % 4, Flags.YOU_ARE_DEALER)
        # give everyone a flag for their placement
        placement_flags = [Flags.YOU_WERE_FIRST, Flags.YOU_WERE_SECOND, Flags.YOU_WERE_THIRD, Flags.YOU_WERE_FOURTH][:self.num_players]
        for seat, placement in enumerate(to_placement(self.kyoku.start_scores, num_players=self.num_players, dealer_seat=round%4)):
            self.add_flag(seat, placement_flags[placement])
        # add all last flag
        hanchan = self.kyoku.rules.is_hanchan
        sanma = self.kyoku.rules.is_sanma
        all_last_round = (6 if sanma else 7) if hanchan else (2 if sanma else 3)
        if round >= all_last_round:
            self.add_global_flag(Flags.ALL_LAST)
        # add final round flag (NOT all last)
        if self.kyoku.is_final_round:
            self.add_global_flag(Flags.FINAL_ROUND)
        # # check who has the worst haipai shanten
        # starting_shanten = [self.kyoku.haipai[player].shanten[0] // 1 for player in range(self.num_players)]
        # get_starting_shanten = lambda player: self.kyoku.haipai[player].shanten[0] // 1
        # for player in range(self.num_players):
        #     second_worst_shanten = max(get_starting_shanten(other_player) for other_player in range(self.num_players) if player != other_player)
        #     if get_starting_shanten(player) > second_worst_shanten:
        #         self.add_flag(player, Flags.DREW_WORST_HAIPAI_SHANTEN, {"hand": self.kyoku.haipai[player], "second_worst_shanten": second_worst_shanten})
        
    def process_end_game(self, i: int, seat: int, event_type: str, raw_result: List[Any]):
        if len(self.kyoku.wall) > 0:
            dead_wall = get_hidden_dead_wall(wall=self.kyoku.wall,
                                             num_kans=self.num_kans,
                                             sanma=self.num_players == 3,
                                             num_kitas=self.num_kitas)
            winners = {r[0] for r in raw_result[2::2]}
            for i in range(self.num_players):
                player = (seat+i)%self.num_players
                if self.at[player].hand.shanten[0] == 0:
                    # check the dead wall for our waits
                    in_dead_wall = sum(dead_wall.count(tile) for tile in self.at[player].hand.shanten[1])
                    ukeire = self.kyoku.get_ukeire(player)
                    if ukeire > 0 and in_dead_wall >= (ukeire+1) // 2:
                        self.add_flag(player, Flags.WAIT_WAS_IN_DEAD_WALL,
                                 {"wait": self.at[player].hand.shanten[1],
                                  "ukeire": ukeire,
                                  "num_tiles": in_dead_wall})
                    # check the wall to see if we would have won had the game not ended
                    if player not in winners:
                        wait = self.at[player].hand.shanten[1]
                        yakuman_tenpais = get_yakuman_tenpais(self.at[player].hand)
                        # check if we would have tsumoed the tile
                        draws = get_remaining_draws(wall=self.kyoku.wall,
                                                    tiles_in_wall=self.tiles_in_wall - ((i+3)%4),
                                                    sanma=self.num_players == 3,
                                                    num_kans_kitas=self.num_kans + self.num_kitas)
                        if len(yakuman_tenpais) == 0:
                            draws = draws[:3]
                        if not set(wait).isdisjoint(set(normalize_red_fives(draws))):
                            self.add_flag(player, Flags.COULD_HAVE_TSUMOED, {"wait": wait, "draws": draws, "yakuman_tenpais": yakuman_tenpais})
                        # check if a riichi player would have drawn the tile and we could call ron on it
                        if not self.at[player].furiten:
                            for j in range(self.num_players):
                                riichi_player = (seat+j)%self.num_players
                                if player == riichi_player or not self.at[riichi_player].in_riichi:
                                    continue
                                riichi_wait = self.at[riichi_player].hand.shanten[1]
                                draws = get_remaining_draws(wall=self.kyoku.wall,
                                                            tiles_in_wall=self.tiles_in_wall - ((j+3)%4),
                                                            sanma=self.num_players == 3,
                                                            num_kans_kitas=self.num_kans + self.num_kitas)
                                if len(yakuman_tenpais) == 0:
                                    draws = draws[:3]
                                if not (set(wait) - set(riichi_wait)).isdisjoint(set(normalize_red_fives(draws))):
                                    self.add_flag(player, Flags.COULD_HAVE_RONNED, {"riichi_player": riichi_player, "wait": wait, "draws": draws, "yakuman_tenpais": yakuman_tenpais})

    def process_result(self, i: int, seat: int, event_type: str, result_type: str, *results: Union[Ron, Tsumo, Draw]) -> None:
        # check if the last discard was a riichi (it must have dealt in)
        for player in range(self.num_players):
            if self.at[player].last_discard_was_riichi:
                self.add_flag(player, Flags.LAST_DISCARD_WAS_RIICHI, {})
                # the winner gets a flag if the riichi player dealt into them
                for result in results:
                    if isinstance(result, Ron) and player == result.won_from:
                        self.add_flag(result.winner, Flags.YOU_WON_AFTER_SOMEONES_RIICHI, {"seat": player})

        # every result has result.score_delta
        # here we add YOU_GAINED_POINTS or YOU_LOST_POINTS as needed
        for result in results:
            for player in range(self.num_players):
                # check for points won or lost
                if result.score_delta[player] > 0:
                    self.add_flag(player, Flags.YOU_GAINED_POINTS, {"amount": result.score_delta[player]})
                elif result.score_delta[player] < 0:
                    self.add_flag(player, Flags.YOU_LOST_POINTS, {"amount": -result.score_delta[player]})

        # check for placement changes
        placement_before = to_placement(self.kyoku.start_scores, self.kyoku.num_players, self.kyoku.round%4)
        old_scores = apply_delta_scores(self.kyoku.start_scores, [-1000 if at.in_riichi else 0 for at in self.at])
        new_scores = apply_delta_scores(old_scores, self.kyoku.result[1].score_delta)
        placement_after = to_placement(new_scores, self.kyoku.num_players, self.kyoku.round%4)
        for old, new in set(zip(placement_before, placement_after)) - {(x,x) for x in range(4)}:
            self._process_placement_change(placement_before.index(old), old+1, new+1, self.kyoku.start_scores, self.kyoku.result[1].score_delta)

        # check if anyone skipped a valid ron or tsumo call
        for seat, (flags, data) in enumerate(zip(self.flags, self.data)):
            for i, flag in enumerate(flags):
                if flag == Flags.YOU_CAN_CALL_RON:
                    if data[i]["turns_left"] != self.tiles_in_wall:
                        self.add_flag(seat, Flags.YOU_SKIPPED_RON, data[i])
                elif flag == Flags.YOU_CAN_CALL_TSUMO:
                    if data[i]["turns_left"] != self.tiles_in_wall:
                        self.add_flag(seat, Flags.YOU_SKIPPED_TSUMO, data[i])

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
                self._process_win_result(win, is_tsumo = result_type == "tsumo")

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
                self._process_ron_result(ron, num_rons = len(results))
            self.add_global_flag(Flags.GAME_ENDED_WITH_RON, {"objects": results})

        # here we add all flags that have to do with self-draw luck:
        # - YOU_TSUMOED
        # - WINNER_WAS_FURITEN
        # - WINNER_IPPATSU_TSUMO
        elif result_type == "tsumo":
            tsumo = results[0]
            assert isinstance(tsumo, Tsumo), f"result tagged tsumo got non-Tsumo object: {tsumo}"
            self._process_tsumo_result(tsumo)
            self.add_global_flag(Flags.GAME_ENDED_WITH_TSUMO, {"object": tsumo})

        # here we add all flags that have to do with ryuukyoku
        elif result_type == "ryuukyoku":
            draw = results[0]
            assert isinstance(draw, Draw), f"result tagged ryuukyoku got non-Draw object: {draw}"
            self._process_draw_result(draw)
            self.add_global_flag(Flags.GAME_ENDED_WITH_RYUUKYOKU, {"object": draw})

        # here we add all flags that have to do with exhaustive or abortive draws
        # - YOU_ACHIEVED_NAGASHI
        # - IISHANTEN_HAIPAI_ABORTED
        elif result_type == "draw":
            draw = results[0]
            assert isinstance(draw, Draw), f"result tagged draw got non-Draw object: {draw}"
            self._process_draw_result(draw)
            self.add_global_flag(Flags.GAME_ENDED_WITH_ABORTIVE_DRAW, {"object": draw})

    def _process_ron_result(self, ron: Ron, num_rons: int) -> None:
        # check deal-ins
        self.add_flag(ron.winner, Flags.YOU_RONNED_SOMEONE, {"from": ron.won_from})
        self.add_flag(ron.won_from, Flags.YOU_DEALT_IN, {"to": ron.winner})
        # check for this was after a chase (to see if a chaser won)
        if Flags.YOU_GOT_CHASED in self.flags[ron.won_from]:
            assert Flags.YOU_REACHED_TENPAI in self.flags[ron.won_from], "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
            self.add_flag(ron.won_from, Flags.CHASER_GAINED_POINTS, {"seat": ron.winner, "amount": ron.score.to_points()})
        # check for multiple ron
        if num_rons > 1:
            self.add_global_flag(Flags.MULTIPLE_RON, {"number": num_rons})

    def _process_tsumo_result(self, tsumo: Tsumo) -> None:
        self.add_flag(tsumo.winner, Flags.YOU_TSUMOED)
        # check furiten
        if self.kyoku.furiten[tsumo.winner]:
            self.add_global_flag(Flags.WINNER_WAS_FURITEN,
                            {"seat": tsumo.winner,
                             "wait": self.at[tsumo.winner].hand.shanten[1],
                             "ukeire": self.kyoku.get_ukeire(tsumo.winner)})
        # check ippatsu tsumo
        if tsumo.score.has_ippatsu():
            self.add_global_flag(Flags.WINNER_IPPATSU_TSUMO, {"seat": tsumo.winner})

    def _process_draw_result(self, draw: Draw) -> None:
        if draw.name in {"ryuukyoku", "nagashi mangan"}:
            assert self.tiles_in_wall == 0, f"somehow ryuukyoku with {self.tiles_in_wall} tiles left in wall"
            # check nagashi
            for seat in (seat for seat, at in enumerate(self.at) if at.nagashi):
                self.add_flag(seat, Flags.YOU_ACHIEVED_NAGASHI, {"seat": seat})
        elif draw.name in {"9 terminals draw", "4-wind draw"}:
            # check if anyone started with a really good hand
            for seat in range(self.num_players):
                if self.at[seat].hand.shanten[0] <= 1:
                    self.add_flag(seat, Flags.IISHANTEN_HAIPAI_ABORTED,
                             {"draw_name": draw.name,
                              "shanten": self.kyoku.haipai[seat].shanten,
                              "hand": self.at[seat].hand})

    def _process_win_result(self, result: Win, is_tsumo: bool) -> None:
        winning_tile = self.kyoku.final_draw if is_tsumo else self.kyoku.final_discard

        # first check how each player reacts to this win
        for seat in range(self.num_players):
            # check if anyone lost points to a first row win
            if result.score_delta[seat] < 0:
                if len(self.at[seat].pond) <= 6:
                    self.add_flag(seat, Flags.LOST_POINTS_TO_FIRST_ROW_WIN, {"seat": result.winner, "turn": len(self.at[seat].pond)})
            # check if the win denied any third row nagashi
            if self.at[seat].nagashi:
                self.at[seat].nagashi = False
                if len(self.at[seat].pond) >= 12:
                    self.add_flag(seat, Flags.YOU_ALMOST_GOT_NAGASHI);
        
        # if tenpai, check if any player could have ronned the winning tile
        for seat, (flags, data) in enumerate(zip(self.flags, self.data)):
            if Flags.YOU_CAN_CALL_RON in flags:
                # check if the last instance of the flag refers to this turn
                ron_data = data[len(flags) - 1 - flags[::-1].index(Flags.YOU_CAN_CALL_RON)]
                if ron_data["turns_left"] == self.tiles_in_wall:
                    self.add_flag(seat, Flags.YOU_WAITED_ON_WINNING_TILE, {"tile": winning_tile, "wait": self.at[seat].hand.shanten[1]})
                    self.add_global_flag(Flags.SOMEONE_WAITED_ON_WINNING_TILE, {"seat": seat, "tile": winning_tile, "wait": self.at[seat].hand.shanten[1]})

        # next, calculate the yaku, han, and fu for the winning hand
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
        winning_tile_is_aka = winning_tile in set(self.current_doras) and winning_tile in {51,52,53}
        winning_tile = normalize_red_five(winning_tile)
        score = calculated_yaku[winning_tile]
        if winning_tile_is_aka:
            score.add_dora("aka", 1)

        han = score.han
        fu = score.fu
        assert score.tsumo == is_tsumo

        # compare the han values to make sure we calculated it right
        winning_hand = self.at[result.winner].hand
        import os
        if os.getenv("debug"):
            assert score.han == expected_han, f"in {round_name(self.kyoku.round, self.kyoku.honba)}, calculated the wrong han ({score.han}) for a {expected_han} han hand {winning_hand.to_str(doras=self.kyoku.doras, uras=self.kyoku.uras)}\nactual yaku: {expected_yaku}\ncalculated yaku: {score}\n\nall waits (winning tile is {pt(winning_tile)}): {str({pt(k): str(v) for k, v in calculated_yaku.items()})}"
        # compare the resulting score to make sure we calculated it right
        is_dealer = result.winner == self.kyoku.round % 4
        calculated_score = score.to_points()
        if os.getenv("debug"):
            tsumo_string = "tsumo" if is_tsumo else "ron"
            stored_score = result.score.to_points()
            assert calculated_score == stored_score, f"in {round_name(self.kyoku.round, self.kyoku.honba)}, calculated the wrong {tsumo_string} score ({calculated_score}) for a {stored_score} point hand {winning_hand.to_str(doras=self.kyoku.doras, uras=self.kyoku.uras)}\nactual yaku: {expected_yaku}\ncalculated yaku: {score}\n\nall waits (winning tile is {pt(winning_tile)}): {str({pt(k): str(v) for k, v in calculated_yaku.items()})}"

        # Add potentially several WINNER flags depending on the limit hand
        # e.g. haneman wins will get WINNER_GOT_HANEMAN plus all the flags before that
        limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                            Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                            Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
        limit_hand_names = ["", "mangan", "haneman", "baiman", "sanbaiman", "yakuman"]
        limit_hand_name = result.score.get_limit_hand_name()
        limit_hand_name = "yakuman" if "yakuman" in limit_hand_name else limit_hand_name
        limit_hand_flags = limit_hand_flags[0:limit_hand_names.index(limit_hand_name)+1]
        winner_data = {"seat": result.winner,
                       "won_from": result.won_from if isinstance(result, Ron) else None,
                       "hand": winning_hand,
                       "haipai": self.kyoku.haipai[result.winner],
                       "ukeire": self.kyoku.get_ukeire(result.winner),
                       "score_object": result.score,
                       "turn": len(self.at[result.winner].pond),
                       "winning_tile": winning_tile,
                       "han": han,
                       "fu": fu,
                       "ura": ura}
        for flag in limit_hand_flags:
            self.add_global_flag(flag, winner_data)
        self.add_flag(result.winner, Flags.YOU_WON, winner_data)
        if any(v in {13, 26} for k, v in score.yaku):
            self.add_flag(result.winner, Flags.YOU_GOT_NON_COUNTED_YAKUMAN, winner_data)
        if self.kyoku.get_ukeire(result.winner) <= 4:
            self.add_global_flag(Flags.WINNER_HAD_BAD_WAIT, winner_data)
        # check for 3+ han from hidden dora
        if result.score.count_dora() >= 3:
            hidden_hand = self.at[result.winner].hand.hidden_part
            if is_tsumo:
                hidden_hand = (*hidden_hand, winning_tile)
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
        # check for dama
        if len(self.at[result.winner].hand.open_part) == 0 and not self.at[result.winner].in_riichi:
            self.add_global_flag(Flags.WINNER_WAS_DAMA, {"seat": result.winner, "score": result.score.to_points()})
        # check for naked tanki
        if len(self.at[result.winner].hand.hidden_part) == 1:
            self.add_global_flag(Flags.WINNER_HAD_NAKED_TANKI, {"seat": result.winner})
        # check for ippatsu
        if result.score.has_ippatsu():
            self.add_global_flag(Flags.WINNER_GOT_IPPATSU, {"seat": result.winner, "score": result.score.to_points()})
        # check for double wind
        if any(result.score.yaku.count((wind, 1)) == 2 for wind in ("ton","nan","shaa","pei")):
            self.add_global_flag(Flags.WINNER_GOT_DOUBLE_WIND, {"seat": result.winner})
        # check if the win was immediately after changing waits
        if self.at[result.winner].hand.shanten != self.at[result.winner].hand.prev_shanten \
           and self.at[result.winner].hand.prev_shanten[0] == 0:
            self.add_flag(result.winner, Flags.WON_AFTER_CHANGING_WAIT,
                                         {"hand": self.at[result.winner].hand,
                                          "winning_tile": winning_tile})
        # check if the win was immediately after calling 2+ times
        if self.at[result.winner].consecutive_calls >= 2:
            self.add_global_flag(Flags.WINNER_WON_WITH_PON_PON_RON,
                                 {"hand": self.at[result.winner].hand,
                                  "winning_tile": winning_tile,
                                  "num_calls": self.at[result.winner].consecutive_calls})

    def _process_placement_change(self, seat: int, old_placement: int, new_placement: int,
                                 prev_scores: Tuple[int, ...], delta_scores: Tuple[int, ...]) -> None:
        # add flags for dropping/gaining placement
        if new_placement > old_placement: # dropped placement
            self.add_flag(seat, Flags.YOU_DROPPED_PLACEMENT,
                                {"old": old_placement, "new": new_placement,
                                 "prev_scores": prev_scores, "delta_scores": delta_scores})
        elif new_placement < old_placement: # gained placement
            self.add_flag(seat, Flags.YOU_GAINED_PLACEMENT,
                                {"old": old_placement, "new": new_placement,
                                 "prev_scores": prev_scores, "delta_scores": delta_scores})
        # check if we just got out of 4th in the final round
        if old_placement == 4 and Flags.FINAL_ROUND in self.global_flags:
            self.add_flag(seat, Flags.YOU_AVOIDED_LAST_PLACE)
        # check if we're got double starting points
        for player in range(self.num_players):
            end_points = prev_scores[player] + delta_scores[player]
            times_starting_score = end_points // self.kyoku.get_starting_score()
            if times_starting_score >= 2:
                self.add_flag(player, Flags.REACHED_DOUBLE_STARTING_POINTS, {"points": end_points, "multiple": times_starting_score})

    def _process_call(self, seat: int, call: CallInfo) -> None:
        # flip kan dora, if needed
        if call.type in {"minkan", "ankan", "kakan"}:
            if self.kyoku.rules.immediate_kan_dora:
                self._process_new_dora(seat, call)
            else:
                if self.pending_kan is not None:
                    self._process_new_dora(seat, self.pending_kan)
                self.pending_kan = call
        # if our resulting calls contain 3+ dora, add a flag
        num_dora = sum(self.current_doras.count(tile) for c in self.at[seat].hand.calls for tile in c.tiles)
        if num_dora >= 3:
            self.add_flag(seat, Flags.CALLS_CONTAIN_THREE_DORA, {"amount": num_dora})
            self.add_global_flag(Flags.SOMEONE_HAS_THREE_DORA_VISIBLE, {"seat": seat, "amount": num_dora})

    def _process_new_dora(self, seat: int, kan_call: CallInfo) -> None:
        # need to check if there's dora since it's possible to have called kan and not reveal a dora
        # (it's when you kan, but win on rinshan before the dora flip)
        if len(self.current_doras) < len(self.kyoku.doras):
            new_dora = self.kyoku.doras[len(self.current_doras)]
            self.current_doras.append(new_dora)
            # check if that just gave us 4 dora
            if list(normalize_red_fives(self.at[seat].hand.tiles_with_kans)).count(new_dora) == 4:
                self.add_flag(seat, Flags.YOU_FLIPPED_DORA_BOMB, {"doras": self.current_doras.copy(), "call": kan_call, "hand": self.at[seat].hand})
            # if anyone's resulting calls contain 3+ dora, add a flag
            for player in range(self.num_players):
                num_dora = sum(self.current_doras.count(tile) for call in self.at[player].hand.calls for tile in call.tiles)
                if num_dora >= 3:
                    self.add_flag(player, Flags.CALLS_CONTAIN_THREE_DORA, {"amount": num_dora})
                    self.add_global_flag(Flags.SOMEONE_HAS_THREE_DORA_VISIBLE, {"seat": player, "amount": num_dora})
        self.num_kans += 1

def determine_flags(kyoku: Kyoku) -> Tuple[List[List[Flags]], List[List[Dict[str, Any]]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag in `flags`
    """
    assert kyoku.num_players in {3,4}, f"somehow we have {kyoku.num_players} players"

    # get all flags by parsing kyoku events
    state = KyokuState(kyoku = kyoku,
                       num_players = kyoku.num_players,
                       tiles_in_wall = 70 if kyoku.num_players == 4 else 55,
                       starting_doras = kyoku.get_starting_doras(),
                       current_doras = kyoku.get_starting_doras(),
                       flags = [[] for i in range(kyoku.num_players)],
                       data = [[] for i in range(kyoku.num_players)])

    # Call the relevant state.process_* function on each event to generate
    # flags from each event in turn.
    debug_prev_flag_len = [0] * state.num_players
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
            state.process_haipai(i, *event)
        elif event_type == "draw":
            state.process_draw(i, *event)
        elif event_type in {"chii", "pon", "minkan"}:
            state.process_chii_pon_daiminkan(i, *event)
        elif event_type in {"ankan", "kakan", "kita"}:
            prev_shanten = state.at[seat].hand.shanten
            state.process_self_kan(i, *event)
            new_shanten = state.at[seat].hand.shanten
            # self kans change the value of our tenpai
            if new_shanten[0] == 0:
                state.process_tenpai(i, seat, event_type,
                    prev_shanten = prev_shanten,
                    new_shanten = new_shanten,
                    hand = state.at[seat].hand,
                    ukeire = state.at[seat].hand.ukeire(state.get_visible_tiles()),
                    furiten = state.at[seat].furiten)
        elif event_type in {"discard", "riichi"}:
            state.process_discard(i, *event[:3]) # riichi has extra args we don't care about
        elif event_type == "shanten_change":
            state.process_shanten_change(i, *event)
            # check for tenpai
            prev_shanten, new_shanten, hand, ukeire, furiten = event_data
            if new_shanten[0] == 0:
                state.process_tenpai(i, *event)
        elif event_type == "start_game":
            state.process_start_game(i, *event)
            # check if anyone is tenpai at draw
            for seat in range(state.num_players):
                shanten = state.kyoku.haipai[seat].shanten
                if shanten[0] == 0:
                    state.process_tenpai(i, seat, event_type,
                        prev_shanten = shanten,
                        new_shanten = shanten,
                        hand = state.at[seat].hand,
                        ukeire = state.at[seat].hand.ukeire(state.get_visible_tiles()),
                        furiten = state.at[seat].furiten)
        elif event_type == "end_game":
            state.process_end_game(i, *event)
        elif event_type == "result":
            state.process_result(i, *event)

    assert len(state.global_flags) == len(state.global_data), f"somehow got a different amount of global flags ({len(state.global_flags)}) than data ({len(state.global_data)})"
    for seat in range(kyoku.num_players):
        assert len(state.flags[seat]) == len(state.data[seat]), f"somehow got a different amount of flags ({len(state.flags[seat])}) than data ({len(state.data[seat])})"
        state.flags[seat] = state.global_flags + state.flags[seat]
        state.data[seat] = state.global_data + state.data[seat]
    return state.flags, state.data
