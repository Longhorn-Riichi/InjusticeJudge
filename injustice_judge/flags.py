from .classes import CallInfo, Dir, Hand, Kyoku, Ron, Tsumo
from .constants import DORA_INDICATOR, MANZU, PINZU, SOUZU, JIHAI, LIMIT_HANDS, TRANSLATE, YAKUMAN, YAOCHUUHAI
from enum import Enum
from typing import *
from .utils import get_majority_suit, is_mangan, normalize_red_five, round_name, to_placement, translate_tenhou_yaku
from .wwyd import is_safe
from .yaku import get_final_yaku, get_score, get_takame_score
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
    " STARTED_WITH_TWO_147_SHAPES"
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
    " YOU_DEALT_IN"
    " YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_DOUBLE_RON"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_DECLARED_RIICHI"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
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
    " YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN"
    " YOUR_LAST_DISCARD_ENDED_NAGASHI"
    " YOUR_LAST_NAGASHI_TILE_CALLED"
    " YOUR_TENPAI_TILE_DEALT_IN"
    )

def determine_flags(kyoku: Kyoku) -> Tuple[List[List[Flags]], List[List[Dict[str, Any]]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag in `flags`
    """
    num_players = kyoku.num_players
    flags: List[List[Flags]] = [list() for i in range(num_players)]
    data: List[List[Any]] = [list() for i in range(num_players)]
    global_flags: List[Flags] = []
    global_data: List[Any] = []
    assert num_players in {3,4}, f"somehow we have {num_players} players"
    def add_flag(p, f, d = None):
        nonlocal flags
        nonlocal data
        flags[p].append(f)
        data[p].append(d)
    def add_global_flag(f, d = None):
        nonlocal global_flags
        nonlocal global_data
        global_flags.append(f)
        global_data.append(d)

    # give dealer a flag saying that they're dealer
    add_flag(kyoku.round % 4, Flags.YOU_ARE_DEALER)

    # give everyone a flag for their placement
    placement_flags = [Flags.YOU_WERE_FIRST, Flags.YOU_WERE_SECOND, Flags.YOU_WERE_THIRD, Flags.YOU_WERE_FOURTH]
    for seat, placement in enumerate(to_placement(kyoku.start_scores)):
        add_flag(seat, placement_flags[placement])

    # add final round flag (NOT all last)
    if kyoku.is_final_round:
        add_global_flag(seat, Flags.FINAL_ROUND)

    # add the flag that's the end of the game
    if kyoku.result[0] == "ron":
        add_global_flag(Flags.GAME_ENDED_WITH_RON, {"objects": kyoku.result[1:]})
    elif kyoku.result[0] == "tsumo":
        add_global_flag(Flags.GAME_ENDED_WITH_TSUMO, {"object": kyoku.result[1]})
    elif kyoku.result[0] == "ryuukyoku":
        add_global_flag(Flags.GAME_ENDED_WITH_RYUUKYOKU, {"object": kyoku.result[1]})
    elif kyoku.result[0] == "draw":
        add_global_flag(Flags.GAME_ENDED_WITH_ABORTIVE_DRAW, {"object": kyoku.result[1]})
    else:
        assert False, f"unknown result type \"{kyoku.result[0]}\""

    # Next, go through kyoku.events. This determines flags related to:
    # - starting shanten
    # - tenpais/riichis and chases/folds
    # - slow shanten changes
    # (We add these flags:)
    # - YOU_DREW_PREVIOUSLY_WAITED_TILE
    # - NINE_DRAWS_NO_IMPROVEMENT
    # - YOU_DECLARED_RIICHI
    # - YOUR_TENPAI_TILE_DEALT_IN
    # - YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT
    # - YOUR_LAST_DISCARD_ENDED_NAGASHI
    # - YOUR_LAST_NAGASHI_TILE_CALLED
    # - SEVEN_TERMINAL_START
    # - FIVE_SHANTEN_START
    # - YOU_FOLDED_FROM_TENPAI
    # - YOU_TENPAI_FIRST
    # - YOU_GOT_CHASED
    # - SOMEONE_REACHED_TENPAI
    # - YOU_REACHED_TENPAI
    # - FIRST_ROW_TENPAI
    # - TENPAI_ON_LAST_DISCARD
    # - CHANGED_WAIT_ON_LAST_DISCARD
    # - YOU_HAD_LIMIT_TENPAI
    # - YOU_REACHED_YAKUMAN_TENPAI
    # - YOU_FLIPPED_DORA_BOMB
    # - YOU_AVOIDED_LAST_PLACE
    # - YOU_DROPPED_PLACEMENT
    # - LAST_DISCARD_WAS_RIICHI
    current_hand: List[Hand] = []
    current_pond: List[List[int]] = [list() for player in range(num_players)]
    draws_since_shanten_change: List[int] = [0]*num_players
    tsumogiri_honor_discards: List[int] = [0]*num_players
    tsumogiri_without_tenpai: List[int] = [0]*num_players
    consecutive_off_suit_tiles: List[List[int]] = [list() for player in range(num_players)]
    tiles_in_wall = 70 if num_players == 4 else 55
    past_waits: List[List[List[int]]] = [list() for player in range(num_players)]
    visible_tiles: List[int] = []
    num_discards: List[int] = [0]*num_players
    opened_hand: List[bool] = [False]*num_players
    nagashi: List[bool] = [True]*num_players
    in_riichi: List[bool] = [False]*num_players
    # respects_riichi[riichi_player][respecting_player] = True/False if the first discard after riichi was a dangerous/safe tile
    respects_riichi: List[List[Optional[bool]]] = [[None]*num_players for player in range(num_players)]
    # dangerous_draws_after_riichi[seat] increments by one whenever you have no safe tiles after riichi and draw a dangerous tile
    dangerous_draws_after_riichi: List[int] = [0]*num_players
    revealed_doras = 0
    get_visible_tiles = lambda seat: visible_tiles + list(current_hand[seat].tiles_with_kans) + [DORA_INDICATOR[dora] for dora in kyoku.doras[len(kyoku.starting_doras)+revealed_doras:]]

    debug_prev_flag_len = [0]*num_players
    debug_prev_global_flag_len = 0
    for i, event in enumerate(kyoku.events):
        seat, event_type, *event_data = event

        # ### DEBUG ###
        # for i in range(debug_prev_global_flag_len, len(global_flags)):
        #     print(f"  Added global flag: {global_flags[i]} {global_data[i] if global_data[i] is not None else ''}")
        # debug_prev_global_flag_len = len(global_flags)
        # for s in range(num_players):
        #     for i in range(debug_prev_flag_len[s], len(flags[s])):
        #         print(f"  Added flag for seat {s}: {flags[s][i]} {data[s][i] if data[s][i] is not None else ''}")
        #     debug_prev_flag_len[s] = len(flags[s])
        # print(round_name(kyoku.round, kyoku.honba), ":", tiles_in_wall, "tiles left |", event)
        # ### DEBUG ###

        last_draw = [0]*num_players
        last_discard = [0]*num_players
        last_discard_was_riichi = [False]*num_players
        if event_type == "draw":
            tile = event_data[0]
            current_hand[seat] = current_hand[seat].add(tile)
            tiles_in_wall -= 1
            last_draw[seat] = tile
            # check if draw would have completed a past wait
            for wait in past_waits[seat]:
                if tile in wait:
                    add_flag(seat, Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE, {"tile": event_data[0], "wait": wait, "shanten": current_hand[seat].shanten})
            # check if it's been more than 9 draws since we changed shanten
            if current_hand[seat].shanten[0] > 0 and draws_since_shanten_change[seat] >= 9:
                add_flag(seat, Flags.NINE_DRAWS_NO_IMPROVEMENT, {"shanten": current_hand[seat].shanten, "draws": draws_since_shanten_change[seat]})
            draws_since_shanten_change[seat] += 1
            # check if we drew what we just discarded
            if tile == last_discard[seat]:
                add_flag(seat, Flags.IMMEDIATELY_DREW_DISCARDED_TILE, {"tile": tile})
                if tile in kyoku.doras:
                    add_flag(seat, Flags.IMMEDIATELY_DREW_DISCARDED_DORA, {"tile": tile})
            # check if we're going for honitsu and drew an off-suit tile
            going_for_honitsu = False
            majority_suit = get_majority_suit(current_hand[seat].tiles)
            if majority_suit is not None and tile not in majority_suit | JIHAI:
                honitsu_tiles = majority_suit | JIHAI
                majority_tiles = tuple(tile for tile in current_hand[seat].tiles if tile in honitsu_tiles)
                enough_honitsu_tiles = len(majority_tiles) >= 9
                no_off_suit_calls = all(call.tile in honitsu_tiles for call in current_hand[seat].calls)
                going_for_honitsu = enough_honitsu_tiles and no_off_suit_calls
            if going_for_honitsu:
                # tick up a counter if you drew off-suit tiles in a row
                consecutive_off_suit_tiles[seat].append(tile)
                if len(consecutive_off_suit_tiles[seat]) >= 6:
                    add_flag(seat, Flags.BAD_HONITSU_DRAWS, {"tiles": consecutive_off_suit_tiles[seat]})
            else:
                consecutive_off_suit_tiles[seat] = []
            # check if we're still 4-shanten or worse after the first row of discards
            if num_discards[seat] == 6 and current_hand[seat].prev_shanten[0] >= 4:
                add_flag(seat, Flags.FOUR_SHANTEN_AFTER_FIRST_ROW, {"shanten": current_hand[seat].prev_shanten})
            # check if we're iishanten with zero tiles left
            if 1 <= current_hand[seat].shanten[0] < 2:
                ukeire = current_hand[seat].ukeire(get_visible_tiles(seat))
                if ukeire == 0:
                    add_flag(seat, Flags.IISHANTEN_WITH_0_TILES)
            # check if there's a riichi and we drew a dangerous tile and we have no safe tiles
            for opponent, b in enumerate(in_riichi):
                if seat == opponent:
                    continue
                check_safety = lambda t: is_safe(t, current_pond[opponent], get_visible_tiles(seat))
                if b and not check_safety(tile) and not any(check_safety(t) for t in current_hand[seat].tiles):
                    dangerous_draws_after_riichi[seat] += 1
                    if dangerous_draws_after_riichi[seat] >= 4:
                        add_flag(seat, Flags.FOUR_DANGEROUS_DRAWS_AFTER_RIICHI, {"num": dangerous_draws_after_riichi[seat], "opponent": opponent})
        elif event_type in {"chii", "pon", "minkan"}:
            called_tile, call_tiles, call_dir = event_data
            if event_type != "minkan":
                current_hand[seat] = current_hand[seat].add(called_tile)
            current_hand[seat] = current_hand[seat].add_call(CallInfo(event_type, called_tile, call_dir, call_tiles))
            opened_hand[seat] = True
            # for everyone whose turn was skipped, add Flags.TURN_SKIPPED_BY_PON
            if event_type in {"pon", "minkan"}:
                if call_dir in {Dir.TOIMEN, Dir.SHIMOCHA}:
                    # called from toimen or shimocha, kamicha was skipped
                    kamicha_seat = (seat-1)%4
                    if not (num_players == 3 and kamicha_seat == 3):
                        add_flag(kamicha_seat, Flags.TURN_SKIPPED_BY_PON)
                if call_dir == Dir.SHIMOCHA:
                    # called from shimocha, toimen was skipped
                    toimen_seat = (seat-2)%4
                    if not (num_players == 3 and toimen_seat == 3):
                        add_flag(toimen_seat, Flags.TURN_SKIPPED_BY_PON)
        elif event_type in {"ankan", "kakan", "kita"}:
            called_tile, call_tiles, call_dir = event_data
            if event_type == "kakan":
                current_hand[seat] = current_hand[seat].kakan(called_tile)
            elif event_type == "ankan":
                current_hand[seat] = current_hand[seat].add_call(CallInfo("ankan", called_tile, Dir.SELF, [called_tile]*4))
            elif event_type == "kita":
                current_hand[seat] = current_hand[seat].kita()
            current_hand[seat] = current_hand[seat].remove(called_tile)
            visible_tiles.append(called_tile)
            # check if anyone's tenpai and had their waits erased by ankan
            if event_type == "ankan":
                tile = normalize_red_five(called_tile)
                for player in range(num_players):
                    if seat == player:
                        continue
                    if Flags.YOU_REACHED_TENPAI in flags[player]:
                        last_tenpai_data = data[player][len(flags[player]) - 1 - flags[player][::-1].index(Flags.YOU_REACHED_TENPAI)]
                        wait = last_tenpai_data["wait"]
                        ukeire = last_tenpai_data["ukeire"]
                        if tile in wait:
                            add_flag(player, Flags.ANKAN_ERASED_TENPAI_WAIT, {"tile": tile, "wait": wait, "caller": seat, "ukeire": ukeire})
        elif event_type in {"discard", "riichi"}:
            tile = event_data[0]
            current_hand[seat] = current_hand[seat].remove(tile)
            visible_tiles.append(tile)
            current_pond[seat].append(tile)
            num_discards[seat] += 1
            last_discard[seat] = tile
            last_discard_was_riichi[seat] = event_type == "riichi"
            # add riichi flag
            if event_type == "riichi":
                in_riichi[seat] = True
                add_flag(seat, Flags.YOU_DECLARED_RIICHI)
                # if there's a triple riichi, give Flags.AGAINST_TRIPLE_RIICHI to the non-riichi person
                if sum(1 for b in in_riichi if b) == 3:
                    non_riichi_seat = next(i for i, b in enumerate(in_riichi) if b == False)
                    add_flag(non_riichi_seat, Flags.AGAINST_TRIPLE_RIICHI)
            # check if this is the deal-in tile
            is_last_discard_of_the_game = i == max(kyoku.final_discard_event_index)
            if is_last_discard_of_the_game and kyoku.result[0] == "ron":
                # check if we just reached tenpai
                already_tenpai = Flags.YOU_REACHED_TENPAI in flags[seat]
                if not already_tenpai and any(e[0] == seat and e[1] == "tenpai" for e in kyoku.events[i:]):
                    add_flag(seat, Flags.YOUR_TENPAI_TILE_DEALT_IN, {"tile": event_data[0]})
                # check if we're tenpai and this would have been our last discard before noten payments
                if already_tenpai and tiles_in_wall <= 3:
                    add_flag(seat, Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT, {"tile": tile})
            # check if this was tsumogiri honors
            is_tsumogiri = tile == last_draw[seat]
            if 41 <= tile <= 47 and is_tsumogiri:
                tsumogiri_honor_discards[seat] += 1
                if tsumogiri_honor_discards[seat] >= 6:
                    add_flag(seat, Flags.SIX_DISCARDS_TSUMOGIRI_HONOR, {"num_discards": tsumogiri_honor_discards})
            else:
                tsumogiri_honor_discards[seat] = 0
            # check if this was tsumogiri while not in tenpai
            if Flags.YOU_REACHED_TENPAI not in flags[seat] and is_tsumogiri:
                tsumogiri_without_tenpai[seat] += 1
                if tsumogiri_without_tenpai[seat] >= 6:
                    add_flag(seat, Flags.SIX_TSUMOGIRI_WITHOUT_TENPAI, {"num_discards": tsumogiri_without_tenpai})
            else:
                tsumogiri_without_tenpai[seat] = 0
            # check if this discard respects/disrespects anyone's riichi
            for opponent, b in enumerate(in_riichi):
                if b and respects_riichi[opponent][seat] is None: # first discard after opponent's riichi
                    respects_riichi[opponent][seat] = is_safe(tile, current_pond[opponent], get_visible_tiles(seat))
                    if all(respects_riichi[opponent][player] == False for player in range(num_players) if player != opponent):
                        add_flag(opponent, Flags.EVERYONE_DISRESPECTED_YOUR_RIICHI)
        elif event_type == "end_nagashi":
            who, reason, tile = event_data
            nagashi[who] = False
            # check if this happened after our final draw (if the game ended in ryuukyoku)
            if kyoku.result[0] == "ryuukyoku" and i > kyoku.final_draw_event_index[seat]:
                if reason == "discard":
                    add_flag(who, Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI, {"tile": tile})
                elif reason in {"minkan", "pon", "chii"}:
                    add_flag(who, Flags.YOUR_LAST_NAGASHI_TILE_CALLED, {"tile": tile, "caller": seat})
        elif event_type == "haipai":
            hand = event_data[0]
            current_hand.append(Hand(hand))
            # check if we have at least 7 terminal/honor tiles
            num_types = len(set(hand) & YAOCHUUHAI) # of terminal/honor tiles
            if num_types >= 7:
                add_flag(seat, Flags.SEVEN_TERMINAL_START, {"num_types": num_types})
            # check if we have a 5 shanten start
            if current_hand[seat].shanten[0] >= 5:
                add_flag(seat, Flags.FIVE_SHANTEN_START, {"shanten": current_hand[seat].shanten})
            # check if we started with 3 dora
            starting_dora = sum(hand.count(dora) for dora in kyoku.starting_doras)
            if starting_dora >= 3:
                add_flag(seat, Flags.STARTED_WITH_3_DORA, {"num": starting_dora})
            # check if we started with at least two 1-4-7 shapes
            num_147_shapes = sum(1 for suit in (MANZU, PINZU, SOUZU)
                                   if tuple(tile // 10 for tile in hand if tile in suit) in {(1,4,7),(2,5,8),(3,6,9)})
            if num_147_shapes >= 2:
                add_flag(seat, Flags.STARTED_WITH_TWO_147_SHAPES, {"hand": hand, "num": num_147_shapes})

        elif event_type == "shanten_change":
            prev_shanten, new_shanten, hand, ukeire, furiten = event_data
            assert new_shanten[0] >= 0, f"somehow shanten for seat {seat} was {new_shanten[0]}"
            draws_since_shanten_change[seat] = 0
            # record past waits if we've changed from tenpai
            if prev_shanten[0] == 0:
                past_waits[seat].append(prev_shanten[1])
                if new_shanten[0] > 0:
                    add_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)
            # bunch of things to check if we're tenpai
            if new_shanten[0] == 0:
                # check if we're tenpai first
                if Flags.SOMEONE_REACHED_TENPAI not in global_flags:
                    add_flag(seat, Flags.YOU_TENPAI_FIRST)
                # otherwise, this is a chase
                else:
                    for other in range(num_players):
                        if other == seat:
                            continue
                        if Flags.YOU_REACHED_TENPAI in flags[other]:
                            other_data = data[other][len(flags[other]) - 1 - flags[other][::-1].index(Flags.YOU_REACHED_TENPAI)]
                            add_flag(other, Flags.YOU_GOT_CHASED,
                                           {"seat": seat,
                                            "hand": hand,
                                            "wait": new_shanten[1],
                                            "ukeire": ukeire,
                                            "furiten": kyoku.furiten[seat],
                                            "your_seat": other,
                                            "your_hand": other_data["hand"],
                                            "your_wait": other_data["wait"],
                                            "your_ukeire": other_data["ukeire"],
                                            "furiten": other_data["furiten"]})
                add_global_flag(Flags.SOMEONE_REACHED_TENPAI,
                                {"seat": seat,
                                 "hand": hand,
                                 "wait": new_shanten[1],
                                 "ukeire": ukeire,
                                 "furiten": kyoku.furiten[seat]})
                add_flag(seat, Flags.YOU_REACHED_TENPAI,
                               {"hand": hand,
                                "wait": new_shanten[1],
                                "ukeire": ukeire,
                                "furiten": kyoku.furiten[seat]})
                # check for first row tenpai
                if num_discards[seat] <= 6:
                    add_flag(seat, Flags.FIRST_ROW_TENPAI, {"seat": seat, "turn": num_discards[seat]})
                # check if we started from 5-shanten and reached tenpai
                # add a flag to everyone who had a 3-shanten start but couldn't reach tenpai
                if Flags.FIVE_SHANTEN_START in flags[seat]:
                    for player in range(num_players):
                        if seat == player:
                            continue
                        if kyoku.haipai[player].shanten[0] <= 3 and Flags.YOU_REACHED_TENPAI not in flags[player]:
                            add_flag(player, Flags.YOUR_3_SHANTEN_SLOWER_THAN_5_SHANTEN,
                                             {"seat": seat,
                                              "your_shanten": kyoku.haipai[player].shanten[0],
                                              "their_shanten": kyoku.haipai[seat].shanten[0]})

                # check if you entered tenpai on your last discard
                was_last_discard_of_the_game = i >= kyoku.final_discard_event_index[seat]
                if was_last_discard_of_the_game:
                    add_flag(seat, Flags.TENPAI_ON_LAST_DISCARD)
                    # check if you had simply changed your wait on your last discard
                    if prev_shanten[0] == 0:
                        add_flag(seat, Flags.CHANGED_WAIT_ON_LAST_DISCARD)
                # remove YOU_FOLDED_FROM_TENPAI flag if any
                if Flags.YOU_FOLDED_FROM_TENPAI in flags[seat]:
                    ix = flags[seat].index(Flags.YOU_FOLDED_FROM_TENPAI)
                    del flags[seat][ix]
                    del data[seat][ix]

                # check if we are mangan+ tenpai
                is_haitei = kyoku.tiles_in_wall == 0
                best_score, takame = get_takame_score(hand = hand,
                                                      events = kyoku.events,
                                                      doras = kyoku.doras,
                                                      uras = kyoku.uras,
                                                      round = kyoku.round,
                                                      seat = seat,
                                                      is_haitei = is_haitei)
                han = best_score.han
                fu = best_score.fu
                if han >= 5 or is_mangan(han, fu):
                    hand_str = hand.print_hand_details(ukeire=ukeire, final_tile=None, furiten=furiten)
                    add_flag(seat, Flags.YOU_HAD_LIMIT_TENPAI,
                                   {"hand_str": hand_str,
                                    "takame": takame,
                                    "limit_name": TRANSLATE[LIMIT_HANDS[han]],
                                    "yaku_str": ", ".join(name for name, value in best_score.yaku),
                                    "han": han,
                                    "fu": fu})
                # check if we are yakuman tenpai
                if han >= 13 and not any(y in map(TRANSLATE.get, YAKUMAN.values()) for y, _ in best_score.yaku):
                    # TODO filter for only the waits that let you reach kazoe yakuman
                    waits = new_shanten[1]
                    add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"types": {f"kazoe yakuman ({', '.join(y for y, _ in best_score.yaku)})"}, "waits": waits})
        elif event_type == "dora_indicator":
            dora_indicator, kan_tile = event_data
            # check if the dora indicator is the kan tile
            if dora_indicator == kan_tile:
                add_flag(seat, Flags.YOU_FLIPPED_DORA_BOMB)
        elif event_type == "yakuman_tenpai":
            yakuman_types, yakuman_waits = event_data
            add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"types": yakuman_types, "waits": yakuman_waits})
        elif event_type == "placement_change":
            old, new, prev_scores, delta_scores = event_data
            if old == 4 and Flags.FINAL_ROUND in global_flags:
                add_flag(seat, Flags.YOU_AVOIDED_LAST_PLACE, {})
            if new > old: # dropped placement
                add_flag(seat, Flags.YOU_DROPPED_PLACEMENT, {"old": old, "new": new, "prev_scores": prev_scores, "delta_scores": delta_scores})
        elif event_type == "start_game":
            # check if anyone's starting shanten is 2 worse than everyone else
            starting_shanten = [kyoku.haipai[player].shanten[0] // 1 for player in range(num_players)]
            get_starting_shanten = lambda player: kyoku.haipai[player].shanten[0] // 1
            for player in range(num_players):
                second_worst_shanten = max(get_starting_shanten(other_player) for other_player in range(num_players) if player != other_player)
                if get_starting_shanten(player) > second_worst_shanten:
                    add_flag(player, Flags.DREW_WORST_HAIPAI_SHANTEN, {"shanten": kyoku.haipai[player].shanten, "second_worst_shanten": second_worst_shanten})
        elif event_type == "end_game":
            for seat in range(num_players):
                if last_discard_was_riichi[seat]:
                    add_flag(seat, Flags.LAST_DISCARD_WAS_RIICHI, {})

        # add another dora
        if event_type in {"minkan", "ankan", "kakan"}:
            revealed_doras += 1


    # Finally, look at kyoku.result. This determines flags related to:
    # - deal-ins
    # - chases
    # - results
    result_type, *results = kyoku.result

    # every result has result.score_delta
    # here we add YOU_GAINED_POINTS or YOU_LOST_POINTS as needed
    for result in results:
        for seat in range(num_players):
            # check for points won or lost
            if result.score_delta[seat] > 0:
                add_flag(seat, Flags.YOU_GAINED_POINTS, {"amount": result.score_delta[seat]})
            elif result.score_delta[seat] < 0:
                add_flag(seat, Flags.YOU_LOST_POINTS, {"amount": -result.score_delta[seat]})

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
        for result in results:
            # first check how each player reacts to this win
            for seat in range(num_players):
                # check if we lost points to a first row win
                if result.score_delta[seat] < 0:
                    if len(kyoku.pond[seat]) <= 6:
                        add_flag(seat, Flags.LOST_POINTS_TO_FIRST_ROW_WIN, {"seat": result.winner, "turn": len(kyoku.pond[seat])})
                # if tenpai, check if the winning tile is in our waits
                # this is useful to find missed/skipped wins, or head bumps
                if kyoku.hands[seat].shanten[0] == 0:
                    winning_tile = kyoku.final_discard if result_type == "ron" else kyoku.final_draw
                    if normalize_red_five(winning_tile) in kyoku.hands[seat].shanten[1]:
                        add_flag(seat, Flags.YOU_WAITED_ON_WINNING_TILE, {"tile": winning_tile, "wait": kyoku.hands[seat].shanten[1]})

            # calculate the yaku, han, and fu for the winning hand
            # check calculated values with the han and points given in the result data
            # first get the expected values from the result data
            expected_yaku = result.score.yaku
            expected_han = 0
            ura_han = 0
            for name, han in expected_yaku:
                if name.startswith("ura"):
                    ura_han = han
                expected_han += han
            # then calculate yaku, han, and fu of the winning hand
            calculated_yaku = get_final_yaku(kyoku, result.winner, check_rons=(result_type=="ron"), check_tsumos=(result_type=="tsumo"))
            # we already take into account if the wait is dora
            #   but we don't check if the winning tile is aka
            #   let's fix it here
            final_tile = kyoku.final_discard if result_type == "ron" else kyoku.final_draw
            final_tile_is_aka = final_tile in set(kyoku.doras) and final_tile in {51,52,53}
            final_tile = normalize_red_five(final_tile)
            if final_tile_is_aka:
                calculated_yaku[final_tile].add_dora("aka", 1)

            han = calculated_yaku[final_tile].han
            fu = calculated_yaku[final_tile].fu
            # compare the han values to make sure we calculated it right
            winning_hand = kyoku.hands[result.winner]
            import os
            if os.getenv("debug"):
                assert han == expected_han, f"in {round_name(kyoku.round, kyoku.honba)}, calculated the wrong han ({han}) for a {expected_han} han hand {winning_hand!s}\nactual yaku: {expected_yaku}\ncalculated yaku: {calculated_yaku[final_tile]}"
            # compare the resulting score to make sure we calculated it right
            is_dealer = result.winner == kyoku.round % 4
            calculated_score = get_score(han, fu, is_dealer, result_type == "tsumo", kyoku.num_players)
            if os.getenv("debug"):
                tsumo_string = "tsumo" if result_type == "tsumo" else "ron"
                stored_score = result.score.to_points()
                if (calculated_score, stored_score) in {(7700, 8000), (7900, 8000), (11600, 12000), (11700, 12000)}: # ignore kiriage mangan differences for now
                    pass
                else:
                    assert calculated_score == stored_score, f"in {round_name(kyoku.round, kyoku.honba)}, calculated the wrong {tsumo_string} score ({calculated_score}) for a {stored_score} point hand {winning_hand!s}\nactual yaku: {expected_yaku}\ncalculated yaku: {calculated_yaku[final_tile]}"

            # Add potentially several WINNER flags depending on the limit hand
            # e.g. haneman wins will get WINNER_GOT_HANEMAN plus all the flags before that
            limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                                Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                                Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
            limit_hand_names = ["", "mangan", "haneman", "baiman", "sanbaiman", "yakuman"]
            limit_hand_flags = limit_hand_flags[0:limit_hand_names.index(result.score.get_limit_hand_name())+1]
            winner_data = {"seat": result.winner,
                           "wait": kyoku.hands[result.winner].shanten[1],
                           "ukeire": kyoku.final_ukeire[result.winner],
                           "score": result.score.to_points(),
                           "score_object": result.score,
                           "han": han,
                           "fu": fu,
                           "ura": ura_han,
                           "hand": winning_hand}
            for flag in limit_hand_flags:
                add_global_flag(flag, winner_data)
            if kyoku.final_ukeire[result.winner] <= 4:
                add_global_flag(Flags.WINNER_HAD_BAD_WAIT, winner_data)
            # check for 3+ han from hidden dora
            if result.score.count_dora() >= 3:
                hidden_hand = (*kyoku.hands[result.winner].hidden_part, final_tile)
                hidden_dora_han = sum(hidden_hand.count(dora) for dora in kyoku.doras)
                if hidden_dora_han >= 3:
                    add_global_flag(Flags.WINNER_GOT_HIDDEN_DORA_3, {"seat": result.winner, "value": hidden_dora_han})
            # check for 3+ ura
            if result.score.count_ura() >= 3:
                add_global_flag(Flags.WINNER_GOT_URA_3, {"seat": result.winner, "value": result.score.count_ura()})
            # check for dora bomb
            if Flags.YOU_FLIPPED_DORA_BOMB in flags[result.winner]:
                add_global_flag(Flags.WINNER_GOT_KAN_DORA_BOMB, {"seat": result.winner, "value": result.score.count_dora()})
            # check for haitei/houtei
            if result.score.has_haitei():
                haitei_type = "haitei" if ("haitei", 1) in result.score.yaku \
                         else "houtei" if ("houtei", 1) in result.score.yaku \
                         else ""
                assert haitei_type != "", f"unknown haitei type for yaku {result.score.yaku}"
                add_global_flag(Flags.WINNER_GOT_HAITEI, {"seat": result.winner, "yaku": haitei_type})

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
            # check deal-ins
            add_flag(ron.winner, Flags.YOU_RONNED_SOMEONE, {"from": ron.won_from})
            add_flag(ron.won_from, Flags.YOU_DEALT_IN, {"to": ron.winner})
            for seat in range(num_players):
                if ron.score_delta[seat] < 0:
                    if not opened_hand[ron.winner] and not in_riichi[ron.winner]:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DAMA, {"seat": ron.winner, "score": ron.score.to_points()})
                    if ron.score.has_ippatsu():
                        add_flag(seat, Flags.YOU_DEALT_INTO_IPPATSU, {"seat": ron.winner, "score": ron.score.to_points()})
                    if len(results) > 1:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DOUBLE_RON, {"number": len(results)})
        if Flags.YOU_GOT_CHASED in flags[ron.won_from]:
            assert Flags.YOU_REACHED_TENPAI in flags[ron.won_from], "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
            add_flag(ron.won_from, Flags.CHASER_GAINED_POINTS, {"seat": ron.winner, "amount": ron.score.to_points()})

    # here we add all flags that have to do with self-draw luck:
    # - YOU_TSUMOED
    # - WINNER_WAS_FURITEN
    # - WINNER_IPPATSU_TSUMO
    elif result_type == "tsumo":
        tsumo = results[0]
        add_flag(tsumo.winner, Flags.YOU_TSUMOED)
        assert isinstance(tsumo, Tsumo), f"result tagged tsumo got non-Tsumo object: {tsumo}"
        # check furiten
        if kyoku.furiten[tsumo.winner]:
            add_global_flag(Flags.WINNER_WAS_FURITEN,
                            {"seat": tsumo.winner,
                             "wait": kyoku.hands[tsumo.winner].shanten[1],
                             "ukeire": kyoku.final_ukeire[tsumo.winner]})
        # check ippatsu tsumo
        if tsumo.score.has_ippatsu():
            add_flag(seat, Flags.WINNER_IPPATSU_TSUMO, {"seat": tsumo.winner})


    # here we add all flags that have to do with exhaustive or abortive draws
    # - YOU_ACHIEVED_NAGASHI
    # - IISHANTEN_HAIPAI_ABORTED
    elif result_type == "draw":
        name = results[0].name
        if name in {"ryuukyoku", "nagashi mangan"}:
            assert tiles_in_wall == 0, f"somehow ryuukyoku with {tiles_in_wall} tiles left in wall"
            for seat in (seat for seat, achieved in enumerate(nagashi) if achieved):
                add_flag(seat, Flags.YOU_ACHIEVED_NAGASHI, {"seat": seat})
        elif name in {"9 terminals draw", "4-wind draw"}:
            # check if anyone started with a really good hand
            for seat in range(num_players):
                if kyoku.hands[seat].shanten[0] <= 1:
                    add_flag(seat, Flags.IISHANTEN_HAIPAI_ABORTED,
                             {"draw_name": name,
                              "shanten": kyoku.haipai[seat].shanten,
                              "hand": kyoku.hands[seat]})

    assert len(global_flags) == len(global_data), f"somehow got a different amount of global flags ({len(global_flags)}) than data ({len(global_data)})"
    for seat in range(num_players):
        assert len(flags[seat]) == len(data[seat]), f"somehow got a different amount of flags ({len(flags[seat])}) than data ({len(data[seat])})"
        flags[seat] = global_flags + flags[seat]
        data[seat] = global_data + data[seat]
    return flags, data
