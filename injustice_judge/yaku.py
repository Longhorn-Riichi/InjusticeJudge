from dataclasses import dataclass
import functools
import itertools
from typing import *
from .classes import CallInfo, Event, Hand, Kyoku, YakuForWait, Score, Interpretation
from .constants import KO_RON_SCORE, LIMIT_HANDS, OYA_RON_SCORE, OYA_TSUMO_SCORE, KO_TSUMO_SCORE, PRED, SUCC, YAOCHUUHAI
from .shanten import get_tenpai_waits
from .utils import fix, get_score, get_taatsu_wait, is_mangan, pt, ph, print_hand_details_seat, remove_red_five, remove_red_fives, round_name, shanten_name, sorted_hand, try_remove_all_tiles
from pprint import pprint

# This file details some algorithms for checking the yaku of a given `Hand` object.
# It's used in `fetch.py` and `flags.py` to calculate some information that will be
#   included in their event list and flags list respectively.


###
### yakuman checking functions
###

# All of these functions below assume the passed-in hand is a 13-tile tenpai hand

# (tenpai hand, calls) -> is it yakuman?
CheckYakumanFunc = Callable[[Hand], bool]

# daisangen tenpai if we have 8 tiles of dragons (counting each dragon at most 3 times)
is_daisangen: CheckYakumanFunc = lambda hand: sum(min(3, hand.tiles.count(tile)) for tile in {45,46,47}) >= 8

# kokushi musou tenpai if we have at least 12 terminal/honors
is_kokushi: CheckYakumanFunc = lambda hand: len(YAOCHUUHAI.intersection(hand.tiles)) >= 12

# suuankou tenpai if hand is closed and we have 4 triplets, or 3 triplets and two pairs
# which is to say, 3+ triplets + at most one unpaired tile
is_suuankou: CheckYakumanFunc = lambda hand: len(hand.calls) == 0 and (mults := list(Counter(hand.tiles).values()), mults.count(3) >= 3 and mults.count(1) <= 1)[1]

# shousuushi if we have exactly 10 winds (counting each wind at most 3 times)
# OR 11 tiles of winds + no pair (i.e. only 6 kinds of tiles in hand)
is_shousuushi: CheckYakumanFunc = lambda hand: (count := sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44}), count == 10 or count == 11 and len(set(remove_red_fives(hand.tiles))) == 6)[1]

# daisuushi if we have 12 tiles of winds (counting each wind at most 3 times)
# OR 11 tiles of winds + a pair (i.e. only 5 kinds of tiles in hand)
is_daisuushi: CheckYakumanFunc = lambda hand: (count := sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44}), count == 12 or count == 11 and len(set(remove_red_fives(hand.tiles))) == 5)[1]

# tsuuiisou tenpai if all the tiles are honor tiles
is_tsuuiisou: CheckYakumanFunc = lambda hand: set(hand.tiles) - {41,42,43,44,45,46,47} == set()

# ryuuiisou tenpai if all the tiles are 23468s6z
is_ryuuiisou: CheckYakumanFunc = lambda hand: set(hand.tiles) - {32,33,34,36,38,46} == set()

# chinroutou tenpai if all the tiles are 19m19p19s
is_chinroutou: CheckYakumanFunc = lambda hand: set(hand.tiles) - {11,19,21,29,31,39} == set()

# chuuren poutou tenpai if hand is closed and we are missing at most one tile
#   out of the required 1112345678999
CHUUREN_TILES = Counter([1,1,1,2,3,4,5,6,7,8,9,9,9])
is_chuuren: CheckYakumanFunc = lambda hand: len(hand.calls) == 0 and all(tile < 40 for tile in hand.tiles) and (ctr := Counter([t % 10 for t in remove_red_fives(hand.tiles)]), sum((CHUUREN_TILES - (CHUUREN_TILES & ctr)).values()) <= 1)[1]

# suukantsu tenpai if you have 4 kans
is_suukantsu = lambda hand: list(map(lambda call: "kan" in call.type, hand.calls)).count(True) == 4

# note: evaluating {suukantsu, tenhou, chiihou, kazoe} requires information outside of the hand

CHECK_YAKUMAN = {"daisangen": is_daisangen,
                 "kokushi": is_kokushi,
                 "suuankou": is_suuankou,
                 "shousuushi": is_shousuushi,
                 "daisuushi": is_daisuushi,
                 "tsuuiisou": is_tsuuiisou,
                 "ryuuiisou": is_ryuuiisou,
                 "chinroutou": is_chinroutou,
                 "chuuren": is_chuuren,
                 "suukantsu": is_suukantsu}
get_yakuman_tenpais = lambda hand: {name for name, func in CHECK_YAKUMAN.items() if func(hand)}

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

###
### yaku calculation
###

# doesn't check for:
# - rinshan, chankan, renhou

def get_hand_interpretations(hand: Hand, yakuhai: Set[int]) -> Set[Interpretation]:
    if hand.shanten[0] != 0:
        return set()
    waits = set(hand.shanten[1])

    is_closed_hand = len(hand.closed_part) == 13
    base_fu = 20

    # first, use the call info to filter some groups out of the hand
    called_sequences = []
    called_triplets = []
    for call in hand.calls:
        if call.type == "chii":
            called_sequences.append(tuple(call.tiles))
        if call.type == "pon":
            base_fu += 4 if call.tile in YAOCHUUHAI else 2
            # print(f"add {4 if call.tile in YAOCHUUHAI else 2} for open triplet {pt(call.tile)}")
            called_triplets.append(tuple(call.tiles))
        if "kan" in call.type: 
            base_fu += 16 if call.tile in YAOCHUUHAI else 8
            if call.type == "ankan":
                base_fu += 16 if call.tile in YAOCHUUHAI else 8
                # print(f"add {32 if call.tile in YAOCHUUHAI else 16} for closed kan {pt(call.tile)}")
            else:
                pass
                # print(f"add {16 if call.tile in YAOCHUUHAI else 8} for open kan {pt(call.tile)}")
            called_triplets.append(tuple(call.tiles[:3]))

    # print(f"base fu + calls = {base_fu} fu")

    base_tsumo_fu = base_fu + 2
    base_ron_fu = base_fu + (10 if is_closed_hand else 0)

    frozen_hand_calls = tuple(hand.calls)
    initial_interpretation = Interpretation(hand.hidden_part,
                                            sequences=tuple(called_sequences),
                                            triplets=tuple(called_triplets),
                                            calls=frozen_hand_calls)

    # let's get all the interpretations of the hand
    # (fu, sequences, triplets, remainder)
    interpretations: Set[Interpretation] = set()
    to_update: Set[Interpretation] = {initial_interpretation}
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
                to_update.add(Interpretation(removed_triplet, fu + triplet_fu, fu + triplet_fu, sequences, add_group(triplets, triplet), pair, calls=frozen_hand_calls))

            # remove a sequence
            sequence = (SUCC[SUCC[tile]], SUCC[tile], tile)
            removed_sequence = try_remove_all_tiles(unprocessed_part, sequence)
            if removed_sequence != unprocessed_part: # removal was a success
                to_update.add(Interpretation(removed_sequence, fu, fu, add_group(sequences, sequence), triplets, pair, calls=frozen_hand_calls))

            # remove a pair, if we haven't yet
            if pair is None:
                yakuhai_fu = 2 if tile in yakuhai else 0
                # print(f"add {yakuhai_fu} for yakuhai pair {pt(tile)}, {ph(unprocessed_part)}")
                removed_pair = try_remove_all_tiles(unprocessed_part, (tile, tile))
                if removed_pair != unprocessed_part: # removal was a success
                    to_update.add(Interpretation(removed_pair, fu + yakuhai_fu, fu + yakuhai_fu, sequences, triplets, (tile, tile), calls=frozen_hand_calls))
            
        if len(unprocessed_part) == 2:
            # now evaluate the remaining taatsu
            tile1, tile2 = sorted_hand(remove_red_fives(unprocessed_part))
            is_shanpon = tile1 == tile2
            is_penchan = SUCC[tile1] == tile2 and 0 in {PRED[tile1], SUCC[tile2]}
            is_ryanmen = SUCC[tile1] == tile2 and 0 not in {PRED[tile1], SUCC[tile2]}
            is_kanchan = SUCC[SUCC[tile1]] == tile2
            single_wait_fu = 2 if is_shanpon or is_penchan or is_kanchan else 0
            # print(f"add {single_wait_fu} for single wait {pt(tile1)pt(tile2)}, {ph(unprocessed_part)}")
            if True in {is_ryanmen, is_shanpon, is_penchan, is_kanchan}:
                ron_fu = base_ron_fu + fu + single_wait_fu
                tsumo_fu = base_tsumo_fu + fu + single_wait_fu
                interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, pair, calls=frozen_hand_calls))
        elif len(unprocessed_part) == 1:
            # either a tanki or aryanmen wait for pinfu
            # first take care of the tanki possibility:
            # print(f"add 2 for single wait {pt(unprocessed_part[0])}")
            tanki = unprocessed_part[0]
            yakuhai_fu = 2 if tanki in yakuhai else 0
            ron_fu = base_ron_fu + fu + yakuhai_fu + 2
            tsumo_fu = base_tsumo_fu + fu + yakuhai_fu + 2
            interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, calls=frozen_hand_calls))
            # then take care of the pinfu aryanmen possibility:
            if len(triplets) == 0: # all sequences
                # check that it's a tanki overlapping a sequence
                has_pair = False
                for t1,t2,t3 in sequences:
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
                    interpretations.add(Interpretation(ryanmen, 30, 22, sequences, triplets, (tanki, tanki), calls=frozen_hand_calls))

            

    return interpretations if len(interpretations) > 0 else {initial_interpretation}

# checks for:
# - tanyao, honroutou, toitoi, chinitsu, honitsu, shousangen,
# - pinfu, iitsu, sanshoku, sanshoku doukou, 
# - iipeikou, ryanpeikou, junchan, chanta, chiitoitsu
# - sanankou, sankantsu
def get_stateless_yaku(interpretation: Interpretation, shanten: Tuple[float, List[int]], is_closed_hand: bool) -> YakuForWait:
    if shanten[0] != 0:
        return {}
    waits = set(shanten[1])
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    # remove all red fives from the interpretation
    taatsu, ron_fu, tsumo_fu, sequences, triplets, pair = interpretation.unpack()
    taatsu = tuple(tuple(remove_red_fives(taatsu)))
    sequences = tuple(tuple(remove_red_fives(seq)) for seq in sequences)
    triplets = tuple(tuple(remove_red_fives(tri)) for tri in triplets)
    pair_tile = None if pair is None else remove_red_five(pair[0])

    # filter for only waits that satisfy this interpretation
    if len(taatsu) == 1: # tanki
        waits &= set(taatsu)
    elif len(taatsu) == 2:
        if taatsu[0] == taatsu[1] and pair_tile is not None: # shanpon
            waits &= {taatsu[0], pair_tile}
        else: # penchan, kanchan, ryanmen
            waits &= get_taatsu_wait(taatsu)
    if len(waits) == 0:
        return {}

    # get the full hand (for checking chiitoitsu)
    full_hand = (*taatsu,
                 *(tile for seq in sequences for tile in seq),
                 *(tile for tri in triplets for tile in tri),
                 *(() if pair is None else pair))
    ctr = Counter(full_hand)
    count_of_counts = Counter(ctr.values())

    # now for each of the waits we calculate their possible yaku
    yaku: YakuForWait = {wait: [] for wait in waits}

    # stateless closed hand yaku
    if is_closed_hand:
        # iipeikou: see if any duplicates of sequences exist,
        #           or if adding a wait gives you that sequence
        # ryanpeikou: check how many times the above is true for a hand
        # chiitoitsu: check full_hand for 6 pairs
        seq_ctr = Counter(sequences)
        for wait in waits:
            # assume count >= 1 for all counts (since that's how Counter works)
            iipeikou_count = [count >= 2 or seq == sorted_hand((*taatsu, wait)) for seq, count in seq_ctr.items()].count(True)
            # priority list is: first ryanpeikou, then chiitoitsu, lastly iipeikou
            if iipeikou_count == 2:
                yaku[wait].append(("ryanpeikou", 3))
            elif count_of_counts[2] == 6 and ctr[wait] == 1:
                yaku[wait].append(("chiitoitsu", 2))
            elif iipeikou_count == 1:
                yaku[wait].append(("iipeikou", 1))

        # pinfu: has 22 tsumo fu and 30 ron fu
        if (tsumo_fu, ron_fu) == (22, 30):
            for wait in waits:
                yaku[wait].append(("pinfu", 1))

    # iitsu: just check if all 3 sequences are there for every suit
    # or if adding each wait to the remaining hand gives the 3rd sequence
    IITSU = [{(11,12,13),(14,15,16),(17,18,19)},
             {(21,22,23),(24,25,26),(27,28,29)},
             {(31,32,33),(34,35,36),(37,38,39)}]
    for suit in IITSU:
        remaining = suit - set(sequences)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku[wait].append(("iitsu", 2 if is_closed_hand else 1))

    # sanshoku: there's only 7 sanshoku groups, so do the same as before
    SANSHOKU = list(zip(zip(range(11,18),range(12,19),range(13,20)),
                        zip(range(21,28),range(22,29),range(23,30)),
                        zip(range(31,38),range(32,39),range(33,40))))
    for group in SANSHOKU:
        remaining = set(group) - set(sequences)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku[wait].append(("sanshoku", 2 if is_closed_hand else 1))

    # sanshoku: there's only 9 sanshoku doukou groups, so do the same as before
    SANSHOKU_DOUKOU = list(zip(zip(range(11,20),range(11,20),range(11,20)),
                               zip(range(21,30),range(21,30),range(21,30)),
                               zip(range(31,40),range(31,40),range(31,40))))
    for group in SANSHOKU_DOUKOU:
        remaining = set(group) - set(triplets)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku[wait].append(("sanshoku doukou", 2))

    # junchan: if we remove all junchan groups and we're left with a terminal pair
    # chanta: if not junchan and we remove all chanta groups and we're left with a terminal/honor pair
    TERMINAL_SEQS = set().union(set(zip(range(11,40,10),range(12,40,10),range(13,40,10))),
                                set(zip(range(21,40,10),range(22,40,10),range(23,40,10))),
                                set(zip(range(31,40,10),range(32,40,10),range(33,40,10))),
                                set(zip(range(17,40,10),range(18,40,10),range(19,40,10))),
                                set(zip(range(27,40,10),range(28,40,10),range(29,40,10))),
                                set(zip(range(37,40,10),range(38,40,10),range(39,40,10))))
    JUNCHAN_TRIS = {(t,t,t) for t in {11,19,21,29,31,39}}
    JUNCHAN_PAIRS = {(t,t) for t in {11,19,21,29,31,39}}
    CHANTA_TRIS = {(t,t,t) for t in range(41,48)} | JUNCHAN_TRIS
    CHANTA_PAIRS = {(t,t) for t in range(41,48)} | JUNCHAN_PAIRS
    # check that every existing group is junchan
    if set(sequences) - TERMINAL_SEQS == set():
        if set(triplets) - JUNCHAN_TRIS == set() and (pair_tile is None or pair_tile in {11,19,21,29,31,39}):
            for wait in waits:
                if sorted_hand((*taatsu, wait)) in JUNCHAN_TRIS | TERMINAL_SEQS | JUNCHAN_PAIRS:
                    yaku[wait].append(("junchan", 3 if is_closed_hand else 2))
                elif sorted_hand((*taatsu, wait)) in CHANTA_TRIS | CHANTA_PAIRS:
                    yaku[wait].append(("chanta", 2 if is_closed_hand else 1))
        elif set(triplets) - CHANTA_TRIS == set() and (pair_tile is None or pair_tile in YAOCHUUHAI):
            for wait in waits:
                if sorted_hand((*taatsu, wait)) in CHANTA_TRIS | CHANTA_PAIRS:
                    yaku[wait].append(("chanta", 2 if is_closed_hand else 1))

    # the following yaku don't need to check the structure of the hand (sequences/triplets)

    # tanyao: check that none of the hand is terminal/honors
    # then every nonterminal/honor wait gives tanyao
    if set(full_hand) & YAOCHUUHAI == set():
        for wait in waits - YAOCHUUHAI:
            yaku[wait].append(("tanyao", 1))

    # honroutou: check that all of the hand is terminal/honors
    # then every terminal/honor wait gives tanyao
    if set(full_hand) - YAOCHUUHAI == set():
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
        if set(full_hand) - honitsu_suit == set():
            if set(full_hand) - chinitsu_suit == set():
                for wait in waits & chinitsu_suit:
                    yaku[wait].append(("chinitsu", 6 if is_closed_hand else 5))
            else:
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

    # sanankou: check if there's three closed triplets
    # the case where there's two closed triplets and a pair waiting for a tsumo
    #   is handled in add_tsumo_yaku
    if len(triplets) >= 3:
        # check they are all closed
        num_open_triplets = sum(1 for tri in triplets for call in interpretation.calls if tri == tuple(remove_red_fives(call.tiles[:3])))
        if len(triplets) - num_open_triplets >= 3:
            for wait in waits:
                yaku[wait].append(("sanankou", 2))

    # sankantsu: check calls
    num_kans = list(map(lambda call: "kan" in call.type, interpretation.calls)).count(True)
    if num_kans == 3:
        for wait in waits:
            yaku[wait].append(("sankantsu", 2))

    return yaku

# pass in the stateless yakus + the whole state
# get back all the yakus (stateless + stateful)
# this will only be missing yakus that are based on how the winning tile is obtained
# (menzentsumo, haitei, houtei, rinshan, chankan, renhou, tenhou, chiihou)
def add_stateful_yaku(yaku: YakuForWait,
                      hand: Hand,
                      events: List[Event],
                      doras: List[int],
                      uras: List[int],
                      round: int,
                      seat: int,
                      is_haitei: bool):
    is_closed_hand = len(hand.closed_part) == 13
    ctr = Counter(hand.tiles)
    waits = set(yaku.keys())
    # this is kind of a state machine over the events to figure out five yaku
    # first state machine checks for self-riichis, self-discards, and all calls
    # - riichi: check if there is a self-riichi event anywhere
    # - double riichi: check if no discard event before a self-riichi event
    # - ippatsu: check if there is are no call events or self-discard events after self-riichi
    # second state machine checks for kans and draws and discards
    # - chankan: check if there is any kakan and no draw after it
    # - rinshan: check if there is any kan, then a draw, and no discard after it
    self_discard_event_exists = False
    is_ippatsu = False
    is_chankan = False
    is_rinshan = False
    for event_seat, event_type, *event_data in events:
        if event_seat != seat and event_type == "draw": # someone draws
            if is_chankan:
                is_ippatsu = False # kakan call succeeded
            is_chankan = False
        elif event_seat == seat and event_type == "discard": # self discard
            self_discard_event_exists = True
            is_ippatsu = False
            is_rinshan = False
        elif is_closed_hand and event_seat == seat and event_type == "riichi": # self riichi
            is_ippatsu = True
            for wait in waits:
                if self_discard_event_exists:
                    yaku[wait].append(("riichi", 1))
                else:
                    yaku[wait].append(("double riichi", 2))
        elif event_seat != seat and event_type == "kakan": # someone kakans
            is_chankan = True # only handle ippatsu cancellation if a draw happens next
        elif event_seat != seat and event_type in {"chii", "pon", "minkan", "ankan", "kita"}: # any non-kakan call
            is_ippatsu = False
        elif event_seat == seat and event_type in {"minkan", "ankan", "kakan", "kita"}: # self kan
            is_rinshan = True
    if is_ippatsu:
        for wait in waits:
            yaku[wait].append(("ippatsu", 1))
    if is_chankan:
        for wait in waits:
            yaku[wait].append(("chankan", 1))
    if is_rinshan:
        for wait in waits:
            yaku[wait].append(("rinshan", 1))

    # yakuhai: if your tenpai hand has three, then you just have yakuhai for any wait
    # alternatively if your tenpai hand has two, then any wait matching that has yakuhai
    YAKUHAI_NAMES = {41: "ton", 42: "nan", 43: "shaa", 44: "pei", 45: "haku", 46: "hatsu", 47: "chun"}
    YAKUHAI = [45,46,47,(round//4)+41,((seat-round)%4)+41]
    for tile in YAKUHAI:
        for wait in waits:
            if ctr[tile] == 3 or (ctr[tile] == 2 and wait == tile):
                yaku[wait].append((YAKUHAI_NAMES[tile], 1))

    # kita: just check the number of kita in hand
    if hand.kita_count > 0:
        for wait in waits:
            yaku[wait].append((f"kita {hand.kita_count}" if hand.kita_count > 1 else "kita", hand.kita_count))

    # dora: count the dora of the hand, removing red fives (we'll count them next)
    full_hand = (*hand.hidden_part, *(tile for call in hand.calls for tile in call.tiles))
    hand_without_reds = tuple(remove_red_fives(full_hand))
    non_red_dora = [dora for dora in doras if dora not in {51,52,53}]
    dora = sum(non_red_dora.count(tile) for tile in hand_without_reds)
    # kita can be dora too
    if 44 in doras:
        dora += hand.kita_count * doras.count(44)
    # now add dora to the yaku list
    for wait in waits:
        if wait in doras:
            wait_dora = dora + doras.count(wait)
            if wait_dora > 0:
                yaku[wait].append((f"dora {wait_dora}" if wait_dora > 1 else "dora", wait_dora))
        else:
            if dora > 0:
                yaku[wait].append((f"dora {dora}" if dora > 1 else "dora", dora))

    # aka: simply count the aka
    red_dora = set(doras) & {51,52,53} # might be empty if there's no red dora this game
    aka = len(set(full_hand) & red_dora)
    if aka > 0:
        for wait in waits:
            yaku[wait].append((f"aka {aka}" if aka > 1 else "aka", aka))

    # ura: same as dora, except our hand has to have riichi in order to have ura
    ura = sum(uras.count(tile) for tile in hand_without_reds)
    # kita can be ura too
    if 44 in uras:
        ura += hand.kita_count * uras.count(44)
    for wait in waits:
        if ("riichi", 1) in yaku[wait]:
            if wait in uras:
                wait_ura = ura + uras.count(wait)
                if wait_ura > 0:
                    yaku[wait].append((f"ura {wait_ura}" if wait_ura > 1 else "ura", wait_ura))
            else:
                if ura > 0:
                    yaku[wait].append((f"ura {ura}" if ura > 1 else "ura", ura))

    # houtei: just need is_haitei passed in
    if is_haitei:
        for wait in waits:
            yaku[wait].append(("houtei", 1))
    return yaku


# literally only menzentsumo, sanankou, and haitei depend on tsumo to achieve
def add_tsumo_yaku(yaku: YakuForWait, interpretation: Interpretation, is_closed_hand: bool) -> YakuForWait:
    waits = set(yaku.keys())

    # menzentsumo only requires a closed hand
    if is_closed_hand:
        for wait in waits:
            yaku[wait].append(("tsumo", 1))

    # sanankou requires two closed triplets, and that the taatsu part is a shanpon wait
    taatsu, _, _, sequences, triplets, pair = interpretation.unpack()
    is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
    if len(triplets) >= 2 and is_pair(taatsu) and pair is not None:
        # check they are all closed
        num_open_triplets = sum(1 for tri in triplets for call in interpretation.calls if tuple(remove_red_fives(tri)) == tuple(remove_red_fives(call.tiles[:3])))
        if len(triplets) - num_open_triplets >= 2:
            for wait in waits & {taatsu[0], pair[0]}:
                if ("sanankou", 2) not in yaku[wait]:
                    yaku[wait].append(("sanankou", 2))

    # haitei: if houtei is there, make it haitei
    for wait in waits:
        if ("houtei", 1) in yaku[wait]:
            yaku[wait].remove(("houtei", 1))
            yaku[wait].append(("haitei", 1))

    return yaku

def add_yakuman(yaku: YakuForWait, hand: Hand, is_tsumo: bool) -> YakuForWait:
    waits = set(hand.shanten[1])
    yakumans = get_yakuman_tenpais(hand)
    if len(yakumans) > 0:
        for wait in waits:
            yaku[wait] = [(y, 13) for y in yakumans]

    return yaku

def get_yaku(hand: Hand,
             events: List[Event],
             doras: List[int],
             uras: List[int],
             round: int,
             seat: int,
             is_haitei: bool,
             check_rons: bool = True,
             check_tsumos: bool = True) -> Dict[int, Score]:
    if hand.shanten[0] != 0:
        return {}

    waits = set(hand.shanten[1])
    is_closed_hand = len(hand.closed_part) == 13
    assert len(waits) > 0, f"hand {hand!s} is tenpai, but has no waits?"

    # now for each of the waits we calculate their possible yaku
    interpretations = get_hand_interpretations(hand, yakuhai={45,46,47,(round//4)+41,((seat-round)%4)+41})

    assert len(interpretations) > 0, f"tenpai hand {hand!s} had no interpretations?"
    # best_score[wait] = the Score value representing the best interpretation for that wait
    best_score: Dict[int, Score] = {}
    def add_best_score(wait, new_score):
        nonlocal best_score
        assert (new_score.han, new_score.fu) != (0, 0), f"somehow got a zero score: {new_score})"
        if wait not in best_score:
            best_score[wait] = new_score
        else:
            best_score[wait] = max(best_score[wait], new_score)

    # we want to get the best yaku for each wait
    # each hand interpretation gives han and fu for some number of waits
    # get the best han and fu for each wait acrosss all interpretations
    for interpretation in interpretations:
        # print("========")
        # for k, v in best_score.items():
        #     print(f"{pt(k)}, {v.hand!s}")
        yaku: YakuForWait = get_stateless_yaku(interpretation, hand.shanten, is_closed_hand)

        # pprint(yaku)
        yaku = add_stateful_yaku(yaku, hand, events, doras, uras, round, seat, is_haitei)
        # print(round_name(round, 0), yaku)
        # pprint([(a, b) for a, b, *_ in events])
        if check_tsumos:
            tsumo_yaku = add_tsumo_yaku(yaku.copy(), interpretation, is_closed_hand)
            tsumo_yaku = add_yakuman(yaku, hand, is_tsumo=True)
        yaku = add_yakuman(yaku, hand, is_tsumo=False)
        # pprint(yaku)

        # if `interpretations.hand` is a pair, it's a shanpon wait
        # if it's a terminal pair then it's +4 fu for ron and +8 for tsumo
        # otherwise it's +2 fu for ron and +4 for tsumo
        is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
        shanpon_tiles = set()
        shanpon_fu = {wait: 0 for wait in yaku.keys()} # times 2 for tsumo
        if is_pair(interpretation.hand) and interpretation.pair is not None:
            shanpon_tiles = {interpretation.hand[0], interpretation.pair[0]}
            for tile in shanpon_tiles:
                shanpon_fu[tile] = 4 if tile in YAOCHUUHAI else 2

        # now total up the fu for each wait
        round_fu = lambda fu: (((fu-1)//10)+1)*10
        for wait in yaku.keys():
            fixed_fu = 25 if ("chiitoitsu", 2) in yaku[wait] else None
            if check_rons:
                han = sum(b for _, b in yaku[wait])
                ron_fu = interpretation.ron_fu + shanpon_fu[wait]
                fixed_fu = fixed_fu or (30 if ron_fu == 20 else None) # open pinfu ron = 30
                add_best_score(wait, Score(yaku[wait], han, fixed_fu or round_fu(ron_fu), False, interpretation, hand))
            if check_tsumos:
                han = sum(b for _, b in tsumo_yaku[wait])
                if is_closed_hand:
                    tsumo_fu = interpretation.tsumo_fu + 2*shanpon_fu[wait]
                    fixed_fu = fixed_fu or (20 if ("pinfu", 1) in tsumo_yaku[wait] else None) # closed pinfu tsumo = 20
                    add_best_score(wait, Score(tsumo_yaku[wait], han, fixed_fu or round_fu(tsumo_fu), True, interpretation, hand))
                else:
                    tsumo_fu = interpretation.tsumo_fu + 2*shanpon_fu[wait]
                    add_best_score(wait, Score(tsumo_yaku[wait], han, fixed_fu or round_fu(tsumo_fu), True, interpretation, hand))
        # for k, v in best_score.items():
        #     print(f"{pt(k)}, {v!s}")
        # print("========")
    return best_score

def get_final_yaku(kyoku: Kyoku,
                   seat: int,
                   check_rons: bool = True,
                   check_tsumos: bool = True) -> Dict[int, Score]:
    assert kyoku.hands[seat].shanten[0] == 0, f"on {round_name(kyoku.round, kyoku.honba)}, get_seat_yaku was passed in seat {seat}'s non-tenpai hand {kyoku.hands[seat]!s} ({shanten_name(kyoku.hands[seat].shanten)})"
    ret = get_yaku(hand = kyoku.hands[seat],
                   events = kyoku.events,
                   doras = kyoku.doras,
                   uras = kyoku.uras,
                   round = kyoku.round,
                   seat = seat,
                   is_haitei = kyoku.tiles_in_wall == 0,
                   check_rons = check_rons,
                   check_tsumos = check_tsumos)
    return ret

def test_get_yaku():
    from .shanten import calculate_shanten
    def test_hand(hand):
        return get_yaku(hand = Hand(hand),
                   events = [],
                   doras = [],
                   uras = [],
                   round = 0,
                   seat = 0,
                   is_haitei = False,
                   check_rons = True,
                   check_tsumos = True)

    pprint(test_hand((13,14,14,15,51,16,25,26,31,32,33,46,46)))
    
    
    
    
    # print(test_hand((11,12,13,21,22,23,31,32,33,38,37,25,25))) # pinfu, sansuoku
    # print(test_hand((11,11,12,12,13,13,23,24,25,26,27,28,31))) # iipeikou
    # print(test_hand((11,11,12,12,13,31,23,24,25,26,27,28,31))) # iipeikou
    # print(test_hand((11,12,12,13,13,14,15,16,21,22,23,24,24))) # pinfu, iipeikou
    # print(test_hand((11,12,12,13,13,22,22,23,23,24,24,33,33))) # pinfu, ryanpeikou

def get_takame_score(hand: Hand,
                     events: List[Event],
                     doras: List[int],
                     uras: List[int],
                     round: int,
                     seat: int,
                     is_haitei: bool) -> Tuple[Score, int]:
    assert hand.shanten[0] == 0
    
    # if no calls, use tsumo score. else, get ron score
    calls_present = len(hand.calls) > 0
    scores: Dict[int, Score] = get_yaku(hand = hand,
                                        events = events,
                                        doras = doras,
                                        uras = uras,
                                        round = round,
                                        seat = seat,
                                        is_haitei = is_haitei,
                                        check_rons = calls_present,
                                        check_tsumos = not calls_present)
    best_score, takame = max((score, wait) for wait, score in scores.items())
    han = best_score.han
    fu = best_score.fu   
    # if we added tsumo, then we might not need the extra han from menzentsumo
    # (e.g. 6 han + tsumo -> 7 han, still haneman, no need for tsumo)
    # recalculate fu for a ron, and return that score if it results in the same limit hand
    recalculate = han in {7, 9, 10, 12} or (han == 5 and fu >= 40) or (han == 4 and fu >= 70)
    if recalculate and not calls_present:
        ron_scores: Dict[int, Score] = get_yaku(hand = hand,
                                                events = events,
                                                doras = doras,
                                                uras = uras,
                                                round = round,
                                                seat = seat,
                                                is_haitei = is_haitei,
                                                check_rons = True,
                                                check_tsumos = False)
        best_ron_score, ron_takame = max((score, wait) for wait, score in ron_scores.items())
        ron_han = best_score.han
        ron_fu = best_score.fu
        if LIMIT_HANDS[ron_han] == LIMIT_HANDS[han] or (is_mangan(han, fu) and is_mangan(ron_han, ron_fu)):
            best_score = best_ron_score
            takame = ron_takame
    return best_score, takame

###
### for debug use
###

def debug_yaku(kyoku):
    if kyoku.result[0] in {"ron", "tsumo"}:
        w = kyoku.result[1].winner
        is_dealer = w == kyoku.round % 4
        ron_score = get_final_yaku(kyoku, w, True, False)
        tsumo_score = get_final_yaku(kyoku, w, False, True)
        print(f"{round_name(kyoku.round, kyoku.honba)} | seat {w} {print_hand_details_seat(kyoku, w)} | dora {ph(kyoku.doras)} ura {ph(kyoku.uras)}")
        final_tile = kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
        print(f"actual    | {kyoku.result[0]} {pt(final_tile)} giving {kyoku.result[1].score} with yaku {kyoku.result[1].yaku.yaku_strs}")
        if kyoku.result[0] == "ron":
            for t in ron_score.keys():
                assert (ron_score[t].han, ron_score[t].fu) != (0, 0), f"somehow got a 0/0 score: {ron_score}"
                score = get_score(ron_score[t].han, ron_score[t].fu, is_dealer, False, kyoku.num_players)
                han_fu_string = f"{ron_score[t].han}/{ron_score[t].fu}={score} (ron)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {ron_score[t].yaku}")
        else:
            for t in tsumo_score.keys():
                assert (tsumo_score[t].han, tsumo_score[t].fu) != (0, 0), f"somehow got a 0/0 score: {ron_score}"
                score = get_score(tsumo_score[t].han, tsumo_score[t].fu, is_dealer, True, kyoku.num_players)
                han_fu_string = f"{tsumo_score[t].han}/{tsumo_score[t].fu}={score} (tsumo)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {tsumo_score[t].yaku}")
        print("")
