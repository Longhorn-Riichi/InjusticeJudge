from ..classes import CallInfo, Dir, GameMetadata, GameRules
from ..classes2 import Draw, Kyoku, Hand, Ron, Score, Tsumo
from ..constants import Event, Shanten, TRANSLATE
from ..display import round_name
from ..utils import to_dora
from typing import *

###
### postprocess events obtained from parsing
###

def postprocess_events(all_events: List[List[Event]],
                       metadata: GameMetadata,
                       all_dora_indicators: List[List[int]],
                       all_ura_indicators: List[List[int]],
                       all_walls: List[List[int]]) -> List[Kyoku]:
    """
    Go through a game (represented as a list of events) and add more events to it
    e.g. shanten changes, tenpai, ending nagashi discards
    Return a list of kyoku, which contains the new event list plus all data about the round
    """
    kyokus: List[Kyoku] = []
    for events, dora_indicators, ura_indicators, wall in zip(all_events, all_dora_indicators, all_ura_indicators, all_walls):
        assert len(events) > 0, "somehow got an empty events list"
        kyoku: Kyoku = Kyoku(rules=metadata.rules, wall=wall, num_dora_indicators_visible=metadata.rules.starting_doras)
        shanten_before_last_draw: List[Shanten] = []
        flip_kan_dora_next_discard = False
        def update_shanten(seat: int) -> None:
            old_shanten = shanten_before_last_draw[seat]
            new_shanten = kyoku.hands[seat].shanten
            if old_shanten != new_shanten:
                # calculate ukeire/furiten (if not tenpai, gives 0/False)
                ukeire = kyoku.get_ukeire(seat)
                kyoku.furiten[seat] = new_shanten[0] == 0 and any(w in kyoku.pond[seat] for w in new_shanten[1])
                kyoku.events.append((seat, "shanten_change", old_shanten, new_shanten, kyoku.hands[seat], ukeire, kyoku.furiten[seat]))
        for i, (seat, event_type, *event_data) in enumerate(events):
            kyoku.events.append(events[i]) # copy every event we process
            # if len(kyoku.hands) == metadata.num_players:
            #     print(seat, event_type, ph(kyoku.hands[seat].closed_part), "|", ph(kyoku.hands[seat].open_part), event_data)
            if event_type == "start_game":
                # initialize all the variables for this round to their starting value
                kyoku.round, kyoku.honba, kyoku.riichi_sticks, kyoku.start_scores = event_data
                kyoku.num_players = metadata.num_players
                kyoku.tiles_in_wall = 70 if kyoku.num_players == 4 else 55
                kyoku.doras = ([51, 52, 53] if metadata.rules.use_red_fives else []) + [to_dora(d, metadata.num_players) for d in dora_indicators]
                kyoku.uras = [to_dora(d, metadata.num_players) for d in ura_indicators]
            elif event_type == "haipai":
                # initialize every variable for this seat to its starting value
                hand = Hand(event_data[0])
                assert len(hand.tiles) == 13, f"haipai was length {len(hand.tiles)}, expected 13"
                kyoku.hands.append(hand)
                kyoku.pond.append([])
                kyoku.furiten.append(False)
                kyoku.haipai.append(hand)
                shanten_before_last_draw.append(hand.shanten)
                kyoku.final_draw_event_index.append(-1)
                kyoku.final_discard_event_index.append(-1)
            elif event_type == "draw":
                # process the draw of a tile (whether normal or after a kan)
                tile = event_data[0]
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                kyoku.hands[seat] = kyoku.hands[seat].add(tile)
                kyoku.final_draw = tile
                kyoku.final_draw_event_index[seat] = len(kyoku.events) - 1
                kyoku.tiles_in_wall -= 1
                assert len(kyoku.hands[seat].tiles) == 14
            elif event_type in {"discard", "riichi"}: # discards
                # process the discard of a tile (whether normal or riichi)
                tile, *_ = event_data
                old_shanten = kyoku.hands[seat].shanten
                kyoku.hands[seat] = kyoku.hands[seat].remove(tile)
                kyoku.final_discard = tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                kyoku.pond[seat].append(tile)
                update_shanten(seat)
                if event_type == "riichi":
                    kyoku.riichi_sticks += 1
            elif event_type in {"chii", "pon", "minkan"}: # calls
                # process a call (which is like a special draw)
                called_tile, call_tiles, call_dir = event_data
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                if event_type != "minkan":
                    kyoku.hands[seat] = kyoku.hands[seat].add(called_tile)
                    assert len(kyoku.hands[seat].tiles) == 14
                kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo(event_type, called_tile, call_dir, call_tiles))
            elif event_type in {"ankan", "kakan", "kita"}: # special discards
                # process a self call (which is like a special discard)
                called_tile, call_tiles, call_dir = event_data
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                # if kakan, replace the old pon call with kakan
                # and add the pon call to the kakan tiles
                if event_type == "kakan":
                    _, kyoku.hands[seat] = kyoku.hands[seat].kakan(called_tile)
                elif event_type == "ankan":
                    kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo("ankan", called_tile, Dir.SELF, (called_tile,)*4))
                elif event_type == "kita":
                    kyoku.hands[seat] = kyoku.hands[seat].kita()
                kyoku.hands[seat] = kyoku.hands[seat].remove(called_tile)
                update_shanten(seat) # kans may change your wait
                kyoku.final_discard = called_tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                assert len(kyoku.hands[seat].tiles) == 13
            elif event_type == "end_game":
                # process the result of a game; most of this is handled in parse_result
                unparsed_result = event_data[0]
                hand_is_hidden = [len(hand.open_part) == 0 for hand in kyoku.hands]
                kyoku.result = parse_result(unparsed_result, kyoku.round, metadata.num_players, hand_is_hidden, [h.kita_count for h in kyoku.hands], kyoku.rules)
                kyoku.events.append((0, "result", *kyoku.result))
                # if tsumo or kyuushu kyuuhai, pop the final tile from the winner's hand
                if kyoku.result[0] == "tsumo" or (kyoku.result[0] == "draw" and kyoku.result[1].name == "9 terminals draw"):
                    for seat in range(kyoku.num_players):
                        if len(kyoku.hands[seat].tiles) == 14:
                            kyoku.hands[seat] = kyoku.hands[seat].remove(kyoku.final_draw)
                            break
            # if the flag is set, we flip kan dora after processing a discard
            if flip_kan_dora_next_discard and event_type in {"discard", "riichi"}:
                flip_kan_dora_next_discard = False
                kyoku.num_dora_indicators_visible += 1
            # if this was a kan action, we set the dora flip flag for next discard
            if event_type in {"minkan", "ankan", "kakan"}:
                if metadata.rules.immediate_kan_dora:
                    kyoku.num_dora_indicators_visible += 1
                else:
                    flip_kan_dora_next_discard = True
        assert len(kyoku.hands) > 0, f"somehow we never initialized the kyoku at index {len(kyokus)}"
        if len(kyokus) == 0:
            assert (kyoku.round, kyoku.honba) == (0, 0), f"kyoku numbering didn't start with East 1: instead it's {round_name(kyoku.round, kyoku.honba)}"
        else:
            assert (kyoku.round, kyoku.honba) != (kyokus[-1].round, kyokus[-1].honba), f"duplicate kyoku entered: {round_name(kyoku.round, kyoku.honba)}"
        for i in range(metadata.num_players):
            assert len(kyoku.hands[i].tiles) == 13, f"on {round_name(kyoku.round, kyoku.honba)}, player {i}'s hand was length {len(kyoku.hands[i].tiles)} when the round ended, should be 13"
        kyokus.append(kyoku)
        # debug_yaku(kyoku)
    return kyokus

def parse_result(result: List[Any], round: int, num_players: int, hand_is_hidden: List[bool], kita_counts: List[int], rules: GameRules) -> Tuple[Any, ...]:
    """
    Given a Tenhou game result list, parse it into a tuple where the first
    element is either "ron", "tsumo", or "draw"; the remainder of the tuple
    consists of "Ron" object(s), a "Tsumo" object, or a "Draw" object.
    These objects store all the relevant information about the win.
    (score changes, who won from who, was it dama, and yaku)
    """
    # the list consists of a string followed by all score info
    result_type, *score_info = result
    ret: List[Tuple[str, Any]] = []
    # score info is parsed in chunks of 2
    # score_info=[a, b, c, d] becomes scores=[[a,b],[c,d]]
    # score_info=[a] becomes scores=[[a]]
    scores = [score_info[i*2:i*2+2] for i in range((len(score_info)+1)//2)]
    # the result type is either "和了" (for ron/tsumo) or something else (for all draws)
    if result_type == "和了":
        rons: List[Ron] = []
        # each score info consists of a score delta list plus all info about the win
        for [score_delta, tenhou_result_list] in scores:
            # decompose the info about the win: winner, payer(s), points (ignored), and yaku names
            [winner, won_from, pao_seat, _, *yaku_strs] = tenhou_result_list
            # construct a Ron or Tsumo object
            # kwargs are common args to both objects
            kwargs = {
                "score_delta": score_delta,
                "winner": winner,
                "dama": hand_is_hidden[winner] and not any(y.startswith("立直") or y.startswith("ダブル立直") or y.startswith("両立直") for y in yaku_strs),
                "score": Score.from_tenhou_list(tenhou_result_list=tenhou_result_list,
                                                round=round,
                                                num_players=num_players,
                                                rules=rules,
                                                kita=kita_counts[winner]),
                "pao_from": None if winner == pao_seat else pao_seat,
            }
            if winner == won_from: # tsumo
                # return the single processed Tsumo object
                return ("tsumo", Tsumo(**kwargs))
            else:
                # append the processed Ron object to a list to be returned later
                rons.append(Ron(**kwargs, won_from=won_from))
        # return all the processed Ron objects
        return ("ron", *rons)
    elif result_type in ({"流局", "全員聴牌", "全員不聴", "流し満貫"} # exhaustive draws
                       | {"九種九牌", "四家立直", "三家和了", "四槓散了", "四風連打"}): # abortive draws
        # draws are either ryuukyoku or something else
        draw_type = "ryuukyoku" if result_type in {"流局", "全員聴牌", "全員不聴"} else "draw"
        # the score delta is usually given, except for abortive draws like 九種九牌
        #   in which case, we just set it to [0,0,0,0]
        score_delta = scores[0][0] if len(scores) > 0 else [0]*num_players
        # return the single processed Draw object
        return (draw_type, Draw(score_delta=score_delta, name=TRANSLATE[result_type]))
    else:
        assert False, f"unhandled Tenhou result type {result_type}"
