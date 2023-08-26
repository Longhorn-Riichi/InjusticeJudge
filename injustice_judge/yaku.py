import functools
import itertools
from typing import *
from .constants import CallInfo, Event, Kyoku, PRED, SUCC, YAOCHUUHAI
from .shanten import get_tenpai_waits
from .utils import remove_red_fives, try_remove_all_tiles, remove_all, remove_all_from, remove_some, remove_some_from, fix, closed_part
from pprint import pprint

# all of these functions assume the passed-in hand is a 13-tile tenpai hand

# (tenpai hand, calls) -> is it yakuman?
CheckYakumanFunc = Callable[[List[int], List[int]], bool]

# daisangen tenpai if we have 8 tiles of dragons (counting each dragon at most 3 times)
is_daisangen: CheckYakumanFunc = lambda hand, calls: sum(min(3, hand.count(tile)) for tile in {45,46,47}) >= 8

# kokushi musou tenpai if we have at least 12 terminal/honors
is_kokushi: CheckYakumanFunc = lambda hand, calls: len(YAOCHUUHAI.intersection(hand)) >= 12

# suuankou tenpai if hand is closed and we have 4 triplets, or 3 triplets and two pairs
# which is to say, 3+ triplets + at most one unpaired tile
is_suuankou: CheckYakumanFunc = lambda hand, calls: len(calls) == 0 and (mults := list(Counter(hand).values()), mults.count(3) >= 3 and mults.count(1) <= 1)[1]

# shousuushi if we have exactly 10 winds (counting each wind at most 3 times)
# OR 11 tiles of winds + no pair (i.e. only 6 kinds of tiles in hand)
is_shousuushi: CheckYakumanFunc = lambda hand, calls: (count := sum(min(3, hand.count(tile)) for tile in {41,42,43,44}), count == 10 or count == 11 and len(set(remove_red_fives(hand))) == 6)[1]

# daisuushi if we have 12 tiles of winds (counting each wind at most 3 times)
# OR 11 tiles of winds + a pair (i.e. only 5 kinds of tiles in hand)
is_daisuushi: CheckYakumanFunc = lambda hand, calls: (count := sum(min(3, hand.count(tile)) for tile in {41,42,43,44}), count == 12 or count == 11 and len(set(remove_red_fives(hand))) == 5)[1]

# tsuuiisou tenpai if all the tiles are honor tiles
is_tsuuiisou: CheckYakumanFunc = lambda hand, calls: set(hand) - {41,42,43,44,45,46,47} == set()

# ryuuiisou tenpai if all the tiles are 23468s6z
is_ryuuiisou: CheckYakumanFunc = lambda hand, calls: set(hand) - {32,33,34,36,38,46} == set()

# chinroutou tenpai if all the tiles are 19m19p19s
is_chinroutou: CheckYakumanFunc = lambda hand, calls: set(hand) - {11,19,21,29,31,39} == set()

# chuuren poutou tenpai if hand is closed and we are missing at most one tile
#   out of the required 1112345678999
CHUUREN_TILES = Counter([1,1,1,2,3,4,5,6,7,8,9,9,9])
is_chuuren: CheckYakumanFunc = lambda hand, calls: len(calls) == 0 and all(tile < 40 for tile in hand) and (ctr := Counter([t % 10 for t in remove_red_fives(hand)]), sum((CHUUREN_TILES - (CHUUREN_TILES & ctr)).values()) <= 1)[1]

# suukantsu tenpai if you have 4 kans
is_suukantsu = lambda call_info: list(map(lambda call: "kan" in call.type, call_info)).count(True) == 4

# note: evaluating {suukantsu, tenhou, chiihou, kazoe} requires information outside of the hand

CHECK_YAKUMAN = {"daisangen": is_daisangen,
                 "kokushi": is_kokushi,
                 "suuankou": is_suuankou,
                 "shousuushi": is_shousuushi,
                 "daisuushi": is_daisuushi,
                 "tsuuiisou": is_tsuuiisou,
                 "ryuuiisou": is_ryuuiisou,
                 "chinroutou": is_chinroutou,
                 "chuuren": is_chuuren}
get_yakuman_tenpais = lambda hand, calls=[], call_info=[]: {name for name, func in CHECK_YAKUMAN.items() if func(hand, calls)} | ({"suukantsu"} if is_suukantsu(call_info) else set())

def test_get_yakuman_tenpais():
    print("daisangen:")
    assert get_yakuman_tenpais([11,12,13,22,22,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,22,45,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,45,45,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,45,45,45,45,46,46,46,47,11,11]) == set()

    assert get_yakuman_tenpais([11,19,21,29,29,31,39,41,42,43,44,45,47]) == {"kokushi"}
    assert get_yakuman_tenpais([11,19,21,29,29,29,39,41,42,43,44,45,46]) == set()

    print("suuankou:")
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,13,14,14,15,15,15]) == {"suuankou"}
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,14,14,14,15,15,15]) == {"suuankou"}
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,14,14,14,15,15,15], [15,15,15]) == set()

    print("shousuushi/daisuushi:")
    assert get_yakuman_tenpais([11,12,13,41,42,42,42,43,43,43,44,44,44]) == {"shousuushi"}
    assert get_yakuman_tenpais([11,12,41,41,42,42,42,43,43,43,44,44,44]) == {"shousuushi"}
    assert get_yakuman_tenpais([11,12,13,14,42,42,42,43,43,43,44,44,44]) == set()
    assert get_yakuman_tenpais([11,11,41,41,42,42,42,43,43,43,44,44,44]) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais([11,41,41,41,42,42,42,43,43,43,44,44,44]) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais([11,41,41,41,42,42,42,43,43,43,44,44,44], [44,44,44]) == {"daisuushi"}

    print("tsuuiisou:")
    assert get_yakuman_tenpais([41,41,42,42,43,43,44,44,45,45,46,46,47]) == {"tsuuiisou"}
    assert get_yakuman_tenpais([45,45,45,46,46,47,47,47,41,41,41,42,42], [41,41,41]) == {"daisangen", "tsuuiisou"}
    assert get_yakuman_tenpais([41,41,42,42,42,43,43,43,44,47,47,11,12]) == set()
    assert get_yakuman_tenpais([41,41,41,42,42,42,43,43,43,44,44,44,45]) == {"suuankou", "daisuushi", "tsuuiisou"}

    print("ryuuiisou:")
    assert get_yakuman_tenpais([32,32,33,33,34,34,36,36,36,38,38,46,46]) == {"ryuuiisou"}
    assert get_yakuman_tenpais([22,22,23,23,24,24,26,26,26,28,28,46,46]) == set()

    print("chinroutou:")
    assert get_yakuman_tenpais([11,11,11,19,19,21,21,21,29,29,29,31,31]) == {"suuankou", "chinroutou"}
    assert get_yakuman_tenpais([11,11,11,19,19,21,21,21,29,29,29,31,31], [29,29,29]) == {"chinroutou"}

    print("chuurenpoutou:")
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,19]) == {"chuuren"}
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,19], [19,19,19]) == set()
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,11]) == {"chuuren"}
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,11,11]) == set()

# checks for:
# - yakuhai
# - riichi, double riichi, ippatsu, sanankou, sankantsu, suukantsu
# - dora
# - plus everything in get_stateless_yaku

# doesn't check for:
# - menzentsumo, haitei, houtei, rinshan, chankan, renhou
# (these are all dependent on how you get the winning tile, rather than the hand state)

# in general if you want to estimate the value of a hand, call this and
# - add 1 if closed (menzentsumo)
# - add 1 if riichi (ura)
# - add 1 if you have an open or closed triplet (rinshan)

YakuValues = Dict[int, List[Tuple[str, int]]]

def get_yaku(hand: List[int],
             shanten: Tuple[float, List[int]],
             calls: List[int],
             call_info: List[CallInfo],
             events: List[Event],
             doras: List[int],
             current_round: int,
             seat: int) -> YakuValues:
    if shanten[0] != 0:
        return {}

    waits = set(shanten[1])
    is_closed_hand = len(calls) == 0
    ctr = Counter(hand)
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    # now for each of the waits we calculate their possible yaku
    yaku: YakuValues = get_stateless_yaku(tuple(hand), shanten, is_closed_hand)

    if is_closed_hand:
        # riichi: check if there is a riichi event
        # ippatsu: check if there is are no calls or self-discards after riichi
        got_discard_event = False
        got_riichi_event = False
        is_ippatsu = True
        for event in events:
            if event[0] == seat and event[1] == "discard": # self discard
                got_discard_event = True
                if got_riichi_event:
                    is_ippatsu = False
            elif event[0] == seat and event[1] == "riichi": # self riichi
                got_riichi_event = True
                for wait in waits:
                    if got_discard_event:
                        yaku[wait].append(("riichi", 1))
                    else:
                        yaku[wait].append(("double riichi", 2))
            elif got_riichi_event and event[1] in {"chii", "pon", "minkan", "ankan", "kakan", "kita"}: # any call
                is_ippatsu = False
        if is_ippatsu:
            for wait in waits:
                yaku[wait].append(("ippatsu", 1))

    # sanankou: check in closed part of the hand
    closed_hand = closed_part(hand, calls, call_info)
    closed_count_of_counts = Counter(Counter(closed_hand).values())
    if closed_count_of_counts[3] == 3:
        for wait in waits:
            yaku[wait].append(("sanankou", 2))

    # sankantsu: check in closed part of the hand
    num_kans = list(map(lambda call: "kan" in call.type, call_info)).count(True)
    if num_kans == 3:
        for wait in waits:
            yaku[wait].append(("sankantsu", 2))

    # yakuhai: if your tenpai hand has three, then you just have yakuhai for any wait
    # alternatively if your tenpai hand has two, then any wait matching that has yakuhai
    YAKUHAI = {"haku": 45, "hatsu": 46, "chun": 47}
    seat_to_wind = ["ton", "nan", "shaa", "pei"]
    wind_to_tile = {"ton": 41, "nan": 42, "shaa": 43, "pei": 44}
    round_wind = seat_to_wind[current_round % 4]
    seat_wind = seat_to_wind[seat]
    YAKUHAI[round_wind] = wind_to_tile[round_wind]
    YAKUHAI[seat_wind] = wind_to_tile[seat_wind]
    for name, tile in YAKUHAI.items():
        for wait in waits:
            if ctr[tile] == 3 or (ctr[tile] == 2 and wait == tile):
                yaku[wait].append((name, 1))

    # dora: simply count the dora
    dora = sum(list(hand).count(dora) for dora in doras)
    for wait in waits:
        if wait in doras:
            yaku[wait].append(("dora", dora + doras.count(wait)))
        else:
            yaku[wait].append(("dora", dora))

    return yaku

def get_seat_yaku(kyoku: Kyoku, seat: int) -> YakuValues:
    return get_yaku(hand = kyoku.hands[seat],
                    shanten = kyoku.shanten[seat],
                    calls = kyoku.calls[seat],
                    call_info = kyoku.call_info[seat],
                    events = kyoku.events,
                    doras = kyoku.doras,
                    current_round = kyoku.round,
                    seat = seat)

def get_takame_han(yaku: YakuValues) -> Tuple[List[int], int]:
    # returns (takame tile(s), han)
    hans = {wait: sum(val for _, val in lst) for wait, lst in yaku.items()}
    max_han = max(hans.values(), default=0)
    return [wait for wait, han in hans.items() if han == max_han], max_han

def get_max_potential_fu(hand: Tuple[int], call_info: CallInfo, waits: Iterable[int]):
    is_closed_hand = len(call_info) == 0
    pass # TODO

# checks for:
# - tanyao, honroutou, toitoi, chinitsu, honitsu, shousangen,
# - pinfu, iitsu, sanshoku, sanshoku doukou, 
# - iipeikou, ryanpeikou, junchan, chanta, chiitoitsu
def get_stateless_yaku(hand: Tuple[int, ...], shanten: Tuple[float, List[int]], is_closed_hand: bool) -> YakuValues:
    if shanten[0] != 0:
        return {}
    waits = set(shanten[1])
    ctr = Counter(hand)
    count_of_counts = Counter(ctr.values())
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    make_groups = lambda tile: ((SUCC[SUCC[tile]], SUCC[tile], tile), (tile, tile, tile))
    remove_all_groups = lambda hands: functools.reduce(lambda hs, _: remove_all(hs, make_groups), range(4), hands)
    remove_some_groups = lambda hands: functools.reduce(lambda hs, _: remove_some(hs, make_groups), range(4), hands)
    make_taatsus = lambda tile: ((SUCC[tile], tile), (SUCC[SUCC[tile]], tile))
    remove_some_taatsus = lambda hands: fix(lambda hs: remove_some(hs, make_taatsus), hands)
    remove_all_taatsus = lambda hands: fix(lambda hs: remove_all(hs, make_taatsus), hands)
    make_pairs = lambda tile: ((tile, tile),)
    remove_some_pairs = lambda hands: fix(lambda hs: remove_some(hs, make_pairs), hands)
    remove_all_pairs = lambda hands: fix(lambda hs: remove_all(hs, make_pairs), hands)
    # waits_after_removing = lambda hand, groups: set().union(*map(get_tenpai_waits, {try_remove_all_tiles(hand, group) for group in groups} - {hand}))

    # now for each of the waits we calculate their possible yaku
    yaku: YakuValues = {wait: [] for wait in waits}

    # try for each wait:
    for wait in waits:
        if is_closed_hand:
            # pinfu: 
            # for every wait w, check if w+1,w+2 or w-2,w-1 can be taken out
            # then if removing all sequences can result in a non-honor pair, it's pinfu
            left = try_remove_all_tiles(hand, (PRED[PRED[wait]], PRED[wait])) if PRED[PRED[wait]] not in YAOCHUUHAI else hand
            right = try_remove_all_tiles(hand, (SUCC[wait], SUCC[SUCC[wait]])) if SUCC[SUCC[wait]] not in YAOCHUUHAI else hand
            # collect all hands not equal to the current hand
            hands = {left, right} - {hand}
            # remove all sequences
            hands = fix(lambda hands: remove_all(hands, lambda tile: ((SUCC[SUCC[tile]], SUCC[tile], tile),)), hands)
            # check for non-honor pairs
            for h in hands:
                if len(h) == 2 and h[0] == h[1] and h not in {41,42,43,44,45,46,47}:
                    yaku[wait].append(("pinfu", 1))

        # helpers for next section
        hand_plus_wait = (*hand, wait)
        is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
        is_winning_hand = lambda hand: any(map(is_pair, remove_all_groups({hand})))
        removing_gives_winning_hand = lambda groups: any(map(is_winning_hand, {try_remove_all_tiles(hand_plus_wait, group) for group in groups} - {hand_plus_wait}))
        
        # iitsu: there's only 3 iitsu groups, try removing each one to see if you get a winning hand
        IITSU = set(zip(range(11,40,10),range(12,40,10),range(13,40,10),
                        range(14,40,10),range(15,40,10),range(16,40,10),
                        range(17,40,10),range(18,40,10),range(19,40,10)))
        if removing_gives_winning_hand(IITSU):
            yaku[wait].append(("iitsu", 2 if is_closed_hand else 1))

        # sanshoku: there's only 7 sanshoku groups, try removing each one to see if you get a winning hand
        SANSHOKU = set(zip(range(11,18),range(12,19),range(13,20),
                           range(21,28),range(22,29),range(23,30),
                           range(31,38),range(32,39),range(33,40)))
        if removing_gives_winning_hand(SANSHOKU):
            yaku[wait].append(("sanshoku", 2 if is_closed_hand else 1))

        # sanshoku doukou: there's only 9 sanshoku doukou groups, try removing each one to see if you get a winning hand
        SANSHOKU_DOUKOU = set(zip(range(11,20),range(11,20),range(11,20),
                                  range(21,30),range(21,30),range(21,30),
                                  range(31,40),range(31,40),range(31,40)))
        if removing_gives_winning_hand(SANSHOKU_DOUKOU):
            yaku[wait].append(("sanshoku doukou", 2))

        if is_closed_hand:
            # iipeikou: there's only 21 iipeikou groups, try removing each one to see if you get a winning hand
            # ryanpeikou: try removing only iipeikou groups and seeing if it leaves a pair
            # chiitoitsu: if not ryanpeikou, if there are 6 pairs, it's chiitoitsu for the unpaired tile
            remove_some_of = lambda hands, groups: {cast(Tuple[int, ...], ())} if hands == {()} else set(try_remove_all_tiles(hand, group) for hand in hands for tile in set(hand) for group in groups)
            IIPEIKOU = set.union(set(zip(range(11,18),range(12,19),range(13,20),
                                         range(11,18),range(12,19),range(13,20))),
                                 set(zip(range(21,28),range(22,29),range(23,30),
                                         range(21,28),range(22,29),range(23,30))),
                                 set(zip(range(31,38),range(32,39),range(33,40),
                                         range(31,38),range(32,39),range(33,40))))
            if removing_gives_winning_hand(IIPEIKOU):
                for h in fix(lambda hands: remove_all_from(hands, tuple(IIPEIKOU)), {hand_plus_wait}):
                    if is_pair(h):
                        yaku[wait].append(("ryanpeikou", 3))
                        break
                    if (len(yaku[wait]) == 0 or yaku[wait][-1] != "ryanpeikou") and count_of_counts[2] == 6 and ctr[wait] == 1:
                        yaku[wait].append(("chiitoitsu", 2))
                    if len(yaku[wait]) == 0 or yaku[wait][-1] not in {"ryanpeikou", "chiitoitsu"}:
                        yaku[wait].append(("iipeikou", 1))

        # junchan: if we remove all junchan groups and we're left with a terminal pair
        # chanta: if not junchan and we remove all chanta groups and we're left with a terminal/honor pair
        JUNCHAN_GROUPS = set().union(set(zip(range(11,40,10),range(12,40,10),range(13,40,10))),
                                     set(zip(range(21,40,10),range(22,40,10),range(23,40,10))),
                                     set(zip(range(31,40,10),range(32,40,10),range(33,40,10))),
                                     {(t,t,t) for t in {11,19,21,29,31,39}})
        for h in remove_all_from({hand_plus_wait}, tuple(JUNCHAN_GROUPS)):
            if is_pair(h) and h[0] in {11,19,21,29,31,39}:
                yaku[wait].append(("junchan", 3 if is_closed_hand else 2))
                break
        CHANTA_GROUPS = JUNCHAN_GROUPS | {(t,t,t) for t in range(41,48)}
        if len(yaku[wait]) == 0 or yaku[wait][-1] != "junchan":
            for h in remove_all_from({hand_plus_wait}, tuple(CHANTA_GROUPS)):
                if is_pair(h) and h[0] in YAOCHUUHAI:
                    yaku[wait].append(("chanta", 2 if is_closed_hand else 1))
                    break

    # the following yaku don't need to check conditions for each wait
    # (we'll check conditions once and then add the yaku to the relevant waits)

    # tanyao: check that none of the hand is terminal/honors
    # then every nonterminal/honor wait gives tanyao
    if set(hand) - YAOCHUUHAI == set(hand):
        for wait in waits - YAOCHUUHAI:
            yaku[wait].append(("tanyao", 1))

    # honroutou: check that all of the hand is terminal/honors
    # then every terminal/honor wait gives tanyao
    if set(hand) & YAOCHUUHAI == set(hand):
        for wait in waits & YAOCHUUHAI:
            yaku[wait].append(("honroutou", 2))

    # toitoi: take out all triplets.
    # if there's 4, the remaining tile gives toitoi.
    # if there's 3, and there are 2 pairs, the remaining pairs give toitoi
    if count_of_counts[3] == 4:
        for wait in waits:
            if ctr[wait] == 1:
                yaku[wait].append(("toitoi", 2))
    if count_of_counts[3] == 3 and count_of_counts[2] == 2:
        for wait in waits:
            if ctr[wait] == 2:
                yaku[wait].append(("toitoi", 2))

    # chinitsu: check that all of the hand is the suit
    # then every wait of that suit gives chinitsu
    # honitsu: same, but add honor tiles to the suit
    for chinitsu_suit in [set(range(11,20)), set(range(21,30)), set(range(31,40))]:
        honitsu_suit = chinitsu_suit.union(range(41,48))
        if set(hand) - honitsu_suit == set():
            if set(hand) - chinitsu_suit == set():
                for wait in waits & chinitsu_suit:
                    yaku[wait].append(("chinitsu", 6 if is_closed_hand else 5))
            for wait in waits & honitsu_suit:
                if len(yaku[wait]) == 0 or yaku[wait][-1] != "chinitsu":
                    yaku[wait].append(("honitsu", 3 if is_closed_hand else 2))

    # shousangen: if your tenpai hand has 8 of the 9 dragons, then you just have shousangen for any wait
    # alternatively if your tenpai hand has 7, then any wait matching a missing dragon gives shousangen
    shousangen_count = {tile: min(3, ctr[tile]) for tile in {45,46,47}}
    shousangen_sum = sum(shousangen_count.values())
    for wait in waits:
        if shousangen_sum == 8 or (shousangen_sum == 7 and shousangen_count[wait] in {1,2}):
            yaku[wait].append(("shousangen", 2))

    return yaku

# remember to consider closed handedness, and the fact that e.g. ryanpeikou forbids iipeikou

def test_get_stateless_yaku():
    from .shanten import calculate_shanten
    test_hand = lambda hand: get_stateless_yaku(hand, calculate_shanten(hand), True)

    # print(test_hand((11,12,13,21,22,23,31,32,33,38,37,25,25))) # pinfu, sansuoku
    print(test_hand((11,11,12,12,13,13,23,24,25,26,27,28,31))) # iipeikou
    print(test_hand((11,11,12,12,13,31,23,24,25,26,27,28,31))) # iipeikou
    print(test_hand((11,12,12,13,13,14,15,16,21,22,23,24,24))) # pinfu, iipeikou
    print(test_hand((11,12,12,13,13,22,22,23,23,24,24,33,33))) # pinfu, ryanpeikou
