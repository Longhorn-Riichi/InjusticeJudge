from .constants import Kyoku, Ron, Tsumo, SHANTEN_NAMES, TRANSLATE
from dataclasses import dataclass
from enum import Enum
from typing import *
from .utils import ph, pt, hidden_part, relative_seat_name, round_name, shanten_name, sorted_hand, try_remove_all_tiles
from pprint import pprint

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " FIVE_SHANTEN_START"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " GAME_ENDED_WITH_ABORTIVE_DRAW"
    " YOUR_LAST_DISCARD_ENDED_NAGASHI"
    " LOST_POINTS_TO_FIRST_ROW_WIN"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " IISHANTEN_HAIPAI_ABORTED"
    " SOMEONE_REACHED_TENPAI"
    " WINNER"
    " WINNER_GOT_BAIMAN"
    " WINNER_GOT_HANEMAN"
    " WINNER_GOT_MANGAN"
    " WINNER_GOT_SANBAIMAN"
    " WINNER_GOT_YAKUMAN"
    " WINNER_GOT_HIDDEN_DORA_3"
    " WINNER_GOT_KAN_DORA_BOMB"
    " WINNER_GOT_URA_3"
    " WINNER_GOT_HAITEI"
    " WINNER_HAD_BAD_WAIT"
    " WINNER_IPPATSU_TSUMO"
    " WINNER_WAS_FURITEN"
    " YOU_ARE_DEALER"
    " YOU_DEALT_IN"
    " YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT"
    " YOU_DEALT_INTO_DAMA"
    " YOU_DEALT_INTO_DOUBLE_RON"
    " YOU_DEALT_INTO_IPPATSU"
    " YOU_DREW_PREVIOUSLY_WAITED_TILE"
    " YOU_FLIPPED_DORA_BOMB"
    " YOU_FOLDED_FROM_TENPAI"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_REACHED_YAKUMAN_TENPAI"
    " YOU_RONNED_SOMEONE"
    " YOU_TENPAI_FIRST"
    " YOU_TSUMOED"
    " YOUR_LAST_NAGASHI_TILE_CALLED"
    " YOUR_TENPAI_TILE_DEALT_IN"

    # unused:
    " CHASER_LOST_POINTS"
    " FIRST_ROW_TENPAI"
    " GAME_ENDED_WITH_TSUMO"
    " YOU_ACHIEVED_NAGASHI"
    " YOU_DECLARED_RIICHI"

    # TODO:
    " HAITEI_HAPPENED_WHILE_YOU_ARE_TENPAI"
    " YOU_HAVE_FIRST_ROW_DISCARDS"
    " YOU_HAVE_SECOND_ROW_DISCARDS"
    " YOU_HAVE_THIRD_ROW_DISCARDS"
    " YOU_PAID_TSUMO_AS_DEALER"
    " YOUR_HAND_RUINED_BY_TANYAO"
    )

def determine_flags(kyoku) -> Tuple[List[List[Flags]], List[List[Dict[str, Any]]]]:
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

    shanten: List[Tuple[float, List[int]]] = [(99, [])]*4
    draws_since_shanten_change: List[int] = [0]*num_players
    tiles_in_wall = 70 if num_players == 4 else 55
    past_waits: List[List[List[int]]] = [list() for player in range(num_players)]
    num_discards: List[int] = [0]*num_players
    opened_hand: List[bool] = [False]*num_players
    in_riichi: List[bool] = [False]*num_players
    nagashi: List[bool] = [True]*num_players
    for i, event in enumerate(kyoku.events):
        seat, event_type, *event_data = event
        # print(round_name(kyoku.round, kyoku.honba), ":", tiles_in_wall, seat, event)
        if event_type == "draw":
            tiles_in_wall -= 1
            tile = event_data[0]
            # check if draw would have completed a past wait
            for wait in past_waits[seat]:
                if tile in wait:
                    add_flag(seat, Flags.YOU_DREW_PREVIOUSLY_WAITED_TILE, {"tile": event_data[0], "wait": wait, "shanten": shanten[seat]})
            # check if it's been more than 9 draws since we changed shanten
            if shanten[seat][0] > 0 and draws_since_shanten_change[seat] >= 9:
                add_flag(seat, Flags.NINE_DRAWS_NO_IMPROVEMENT, {"shanten": shanten[seat], "draws": draws_since_shanten_change[seat]})
            draws_since_shanten_change[seat] += 1
        elif event_type == "riichi":
            in_riichi[seat] = True
            add_flag(seat, Flags.YOU_DECLARED_RIICHI)
        elif event_type in {"chii", "pon", "minkan"}:
            opened_hand[seat] = True
        elif event_type == "discard":
            num_discards[seat] += 1
            is_last_discard_of_the_game = i == max(kyoku.final_discard_event_index)
            # check if this is the deal-in tile
            if is_last_discard_of_the_game and kyoku.result[0] == "ron":
                # check if we just reached tenpai
                already_tenpai = Flags.YOU_REACHED_TENPAI in flags[seat]
                if not already_tenpai and any(e[0] == seat and e[1] == "tenpai" for e in kyoku.events[i:]):
                    add_flag(seat, Flags.YOUR_TENPAI_TILE_DEALT_IN, {"tile": event_data[0]})
                # check if we're tenpai and this would have been our last discard before noten payments
                if already_tenpai and tiles_in_wall <= 3:
                    add_flag(seat, Flags.YOU_DEALT_IN_JUST_BEFORE_NOTEN_PAYMENT, {"tile": event_data[0]})
        elif event_type == "tenpai":
            assert len(kyoku.hands[seat]) == 13, f"got tenpai event but we have a {len(kyoku.hands[seat])} tile hand {ph(kyoku.hands[seat])}"
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
                                        "hand": event_data[0],
                                        "wait": event_data[1],
                                        "ukeire": event_data[2],
                                        "furiten": kyoku.furiten[seat],
                                        "your_seat": other,
                                        "your_hand": other_data["hand"],
                                        "your_wait": other_data["wait"],
                                        "your_ukeire": other_data["ukeire"],
                                        "furiten": other_data["furiten"]})
            add_global_flag(Flags.SOMEONE_REACHED_TENPAI,
                            {"seat": seat,
                             "hand": event_data[0],
                             "wait": event_data[1],
                             "ukeire": event_data[2],
                             "furiten": kyoku.furiten[seat]})
            add_flag(seat, Flags.YOU_REACHED_TENPAI,
                           {"hand": event_data[0],
                            "wait": event_data[1],
                            "ukeire": event_data[2],
                            "furiten": kyoku.furiten[seat]})
            # check for first row tenpai
            if num_discards[seat] <= 6:
                add_flag(seat, Flags.FIRST_ROW_TENPAI, {"seat": seat, "turn": num_discards[seat]})
            # remove YOU_FOLDED_FROM_TENPAI flag if any
            if Flags.YOU_FOLDED_FROM_TENPAI in flags[seat]:
                ix = flags[seat].index(Flags.YOU_FOLDED_FROM_TENPAI)
                del flags[seat][ix]
                del data[seat][ix]
        elif event_type == "end_nagashi":
            who, reason, tile = event_data
            nagashi[who] = False
            # check if this happened after our final draw (if the game ended in ryuukyoku)
            if kyoku.result[0] == "ryuukyoku" and i > kyoku.final_draw_event_index[seat]:
                if reason == "discard":
                    add_flag(who, Flags.YOUR_LAST_DISCARD_ENDED_NAGASHI, {"tile": tile})
                elif reason in {"minkan", "pon", "chii"}:
                    add_flag(who, Flags.YOUR_LAST_NAGASHI_TILE_CALLED, {"tile": tile, "caller": seat})
        elif event_type == "haipai_shanten":
            shanten[seat] = event_data[0]
            if shanten[seat][0] >= 5:
                add_flag(seat, Flags.FIVE_SHANTEN_START, {"shanten": shanten[seat]})
        elif event_type == "shanten_change":
            prev_shanten, new_shanten = event_data
            assert shanten[seat][0] != 99, f"missing haipai_shanten event before a shanten_change event"
            assert prev_shanten == shanten[seat], f"somehow shanten changed from {shanten[seat]} to {prev_shanten} outside a shanten_change event"
            shanten[seat] = new_shanten
            draws_since_shanten_change[seat] = 0
            # record past waits if we've changed from tenpai
            if prev_shanten[0] == 0:
                past_waits[seat].append(prev_shanten[1])
                if new_shanten[0] > 0:
                    add_flag(seat, Flags.YOU_FOLDED_FROM_TENPAI)
        elif event_type == "dora_indicator":
            dora_indicator, kan_tile = event_data
            # check if the dora indicator is the kan tile
            if dora_indicator == kan_tile:
                add_flag(seat, Flags.YOU_FLIPPED_DORA_BOMB)
        elif event_type == "yakuman_tenpai":
            yakuman_types = event_data[0]
            add_flag(seat, Flags.YOU_REACHED_YAKUMAN_TENPAI, {"types": yakuman_types})


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
    # - WINNER_GOT_MANGAN, WINNER_GOT_HANEMAN, etc
    # - WINNER_HAD_BAD_WAIT
    # - WINNER_GOT_HIDDEN_DORA_3
    # - WINNER_GOT_URA_3
    # - WINNER_GOT_HAITEI
    if result_type in {"ron", "tsumo"}:
        for result in results:
            # check for first row win
            for seat in range(num_players):
                if result.score_delta[seat] < 0:
                    num_winner_discards = len(kyoku.pond[result.winner])
                    if num_winner_discards <= 6:
                        add_flag(seat, Flags.LOST_POINTS_TO_FIRST_ROW_WIN, {"seat": result.winner, "turn": num_winner_discards})

            # Add potentially several WINNER flags depending on the limit hand
            # e.g. haneman wins will get WINNER_GOT_HANEMAN plus all the flags before that
            assert len(kyoku.final_waits) > 0, "forgot to set kyoku.final_waits after processing event list"
            limit_hand_flags = [Flags.WINNER, Flags.WINNER_GOT_MANGAN,
                                Flags.WINNER_GOT_HANEMAN, Flags.WINNER_GOT_BAIMAN,
                                Flags.WINNER_GOT_SANBAIMAN, Flags.WINNER_GOT_YAKUMAN]
            limit_hand_names = ["", "", "満貫", "跳満", "倍満", "三倍満", "役満"]
            assert result.limit_name in limit_hand_names, f"unknown limit hand name {result.limit_name}"
            limit_hand_flags = limit_hand_flags[0:limit_hand_names.index(result.limit_name)]
            for flag in limit_hand_flags:
                add_global_flag(flag, {"seat": result.winner,
                                       "wait": kyoku.final_waits[result.winner],
                                       "ukeire": kyoku.final_ukeire[result.winner]})
            if kyoku.final_ukeire[result.winner] <= 4:
                add_global_flag(Flags.WINNER_HAD_BAD_WAIT,
                                {"seat": result.winner,
                                 "wait": kyoku.final_waits[result.winner],
                                 "ukeire": kyoku.final_ukeire[result.winner]})
            # check for 3+ han from hidden dora
            if result.yaku.dora >= 3:
                final_tile = kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
                hidden_hand = hidden_part(kyoku.hands[result.winner] + [final_tile], kyoku.calls[result.winner])
                hidden_dora_han = sum(hidden_hand.count(dora) for dora in kyoku.doras)
                if hidden_dora_han >= 3:
                    add_global_flag(Flags.WINNER_GOT_HIDDEN_DORA_3, {"seat": result.winner, "value": hidden_dora_han})
            # check for 3+ ura
            elif result.yaku.ura >= 3:
                add_global_flag(Flags.WINNER_GOT_URA_3, {"seat": result.winner, "value": result.yaku.ura})
            # check for dora bomb
            if Flags.YOU_FLIPPED_DORA_BOMB in flags[result.winner]:
                add_global_flag(Flags.WINNER_GOT_KAN_DORA_BOMB, {"seat": result.winner, "value": result.yaku.dora})

            # check for haitei/houtei
            if result.yaku.haitei:
                haitei_type = "haitei" if "海底摸月(1飜)" in result.yaku.yaku_strs \
                         else "houtei" if "河底撈魚(1飜)" in result.yaku.yaku_strs \
                         else ""
                assert haitei_type != "", f"unknown haitei type for yaku {result.yaku.yaku_strs}"
                add_global_flag(Flags.WINNER_GOT_HAITEI, {"seat": result.winner, "yaku": haitei_type})

    # here we add all flags that have to do with deal-ins:
    # - YOU_RONNED_SOMEONE
    # - YOU_DEALT_IN
    # - YOU_DEALT_INTO_DAMA
    # - YOU_DEALT_INTO_IPPATSU
    # - YOU_DEALT_INTO_DOUBLE_RON
    # - CHASER_GAINED_POINTS
    # - CHASER_GAINED_POINTS
    if result_type == "ron":
        # check winners
        for ron in results:
            assert isinstance(ron, Ron), f"result tagged ron got non-Ron object: {ron}"
            # check deal-ins
            assert len(kyoku.final_waits[ron.winner]) > 0, f"in {round_name(kyoku.round, kyoku.honba)}, seat {ron.winner} won with hand {ph(sorted_hand(kyoku.hands[ron.winner]))}, but has no waits saved in kyoku.final_waits"
            add_flag(ron.winner, Flags.YOU_RONNED_SOMEONE, {"from": ron.won_from})
            add_flag(ron.won_from, Flags.YOU_DEALT_IN, {"to": ron.winner})
            for seat in range(num_players):
                if ron.score_delta[seat] < 0:
                    if not opened_hand[ron.winner] and not in_riichi[ron.winner]:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DAMA, {"seat": ron.winner, "score": -ron.score_delta[seat]})
                    if ron.yaku.ippatsu:
                        add_flag(seat, Flags.YOU_DEALT_INTO_IPPATSU, {"seat": ron.winner, "score": -ron.score_delta[seat]})
                    if len(results) > 1:
                        add_flag(seat, Flags.YOU_DEALT_INTO_DOUBLE_RON, {"number": len(results)})
        if Flags.YOU_GOT_CHASED in flags[ron.won_from]:
            assert Flags.YOU_REACHED_TENPAI in flags[ron.won_from], "somehow got YOU_GOT_CHASED without YOU_REACHED_TENPAI"
            add_flag(ron.won_from, Flags.CHASER_GAINED_POINTS, {"seat": ron.winner, "amount": ron.score})

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
                             "wait": kyoku.final_waits[tsumo.winner],
                             "ukeire": kyoku.final_ukeire[tsumo.winner]})
        # check ippatsu tsumo
        if tsumo.yaku.ippatsu:
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
                if kyoku.shanten[seat][0] <= 1:
                    add_flag(seat, Flags.IISHANTEN_HAIPAI_ABORTED,
                             {"draw_name": name,
                              "shanten": kyoku.haipai_shanten[seat],
                              "hand": kyoku.hands[seat]})

    assert len(global_flags) == len(global_data), f"somehow got a different amount of global flags ({len(global_flags)}) than data ({len(global_data)})"
    for seat in range(num_players):
        assert len(flags[seat]) == len(data[seat]), f"somehow got a different amount of flags ({len(flags[seat])}) than data ({len(data[seat])})"
        flags[seat] = global_flags + flags[seat]
        data[seat] = global_data + data[seat]
    return flags, data
