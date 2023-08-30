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

def get_hand_interpretations(hand: Hand, round: int, seat: int) -> Set[Interpretation]:
    if hand.shanten[0] != 0:
        return set()
    waits = set(hand.shanten[1])

    is_closed_hand = len(hand.calls) == 0
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

    # not interpreting the hand is always an interpretation
    # (this is necessary if we want to count chiitoitsu or kokushi)
    initial_interpretation = Interpretation(hand.hidden_part,
                                            sequences=tuple(called_sequences),
                                            triplets=tuple(called_triplets))

    # let's get all the interpretations of the hand
    # (fu, sequences, triplets, remainder)
    interpretations: Set[Interpretation] = {initial_interpretation}
    to_update: Set[Interpretation] = {initial_interpretation}
    already_processed: Set[Tuple[int, ...]] = set()
    add_group = lambda groups, group: tuple(sorted((*groups, tuple(sorted(group)))))
    while len(to_update) > 0:
        unprocessed_part, fu, _, sequences, triplets, _ = to_update.pop().unpack()
        if unprocessed_part in already_processed:
            continue
        else:
            already_processed.add(unprocessed_part)
        removed_something = False
        for tile in set(unprocessed_part):
            # remove a triplet
            triplet = (tile, tile, tile)
            removed_triplet = try_remove_all_tiles(unprocessed_part, triplet)
            if removed_triplet != unprocessed_part: # removal was a success
                removed_something = True
                # add fu for this triplet
                # print(f"add {8 if tile in YAOCHUUHAI else 4} for closed triplet {pt(tile)}, {ph(unprocessed_part)}")
                triplet_fu = 8 if tile in YAOCHUUHAI else 4
                to_update.add(Interpretation(removed_triplet, fu + triplet_fu, fu + triplet_fu, sequences, add_group(triplets, triplet)))

            # remove a sequence
            sequence = (SUCC[SUCC[tile]], SUCC[tile], tile)
            removed_sequence = try_remove_all_tiles(unprocessed_part, sequence)
            if removed_sequence != unprocessed_part: # removal was a success
                removed_something = True
                to_update.add(Interpretation(removed_sequence, fu, fu, add_group(sequences, sequence), triplets))

        if not removed_something: # no sequences or triplets in unprocessed_part
            # take out the pair
            assert len(unprocessed_part) > 0
            for tile in unprocessed_part:
                pair = (tile, tile)
                removed_pair = try_remove_all_tiles(unprocessed_part, pair)
                if removed_pair != unprocessed_part: # removal was a success
                    break

            # get the set of all yakuhai tiles for us (dragons, round wind, seat wind)
            YAKUHAI = [45,46,47,(round//4)+41,((seat-round)%4)+41]
            
            if removed_pair != unprocessed_part: # removal was a success
                yakuhai_fu = 2 if tile in YAKUHAI else 0
                    # print(f"add 2 for yakuhai pair {pt(tile)}")
                unprocessed_part = removed_pair
                # discard if it's not length 2
                if len(unprocessed_part) == 2:
                    # now evaluate the remaining taatsu
                    tile1, tile2 = sorted_hand(remove_red_fives(unprocessed_part))
                    is_shanpon = tile1 == tile2
                    is_penchan = SUCC[tile1] == tile2 and 0 in {PRED[tile1], SUCC[tile2]}
                    is_ryanmen = SUCC[tile1] == tile2 and 0 not in {PRED[tile1], SUCC[tile2]}
                    is_kanchan = SUCC[SUCC[tile1]] == tile2
                    single_wait_fu = 2 if is_shanpon or is_penchan or is_kanchan else 0
                    if True in {is_ryanmen, is_shanpon, is_penchan, is_kanchan}:
                        ron_fu = base_ron_fu + fu + yakuhai_fu + single_wait_fu
                        tsumo_fu = base_tsumo_fu + fu + yakuhai_fu + single_wait_fu
                        interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, (tile, tile)))
            elif len(unprocessed_part) == 1:
                # tanki wait
                # print(f"add 2 for single wait {pt(unprocessed_part[0])}")
                yakuhai_fu = 2 if unprocessed_part[0] in YAKUHAI else 0
                ron_fu = base_ron_fu + fu + yakuhai_fu + 2
                tsumo_fu = base_tsumo_fu + fu + yakuhai_fu + 2
                interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets))

    return interpretations

def test_get_hand_interpretations():
    pprint(get_hand_interpretations(Hand((11,12,13,14,15,16,17,18,19,22,21,21,21)), 0, 0))
    print("===")
    pprint(get_hand_interpretations(Hand((11,11,11,12,13,14,15,16,17,18,19,19,19)), 0, 0))

    [interpretation] = get_hand_interpretations(Hand((11,12,13,14,15,16,17,18,19,22,21,21,21)), 0, 0)
    print(get_stateless_yaku(interpretation, (0, [21, 24]), True))

# checks for:
# - tanyao, honroutou, toitoi, chinitsu, honitsu, shousangen,
# - pinfu, iitsu, sanshoku, sanshoku doukou, 
# - iipeikou, ryanpeikou, junchan, chanta, chiitoitsu
def get_stateless_yaku(interpretation: Interpretation, shanten: Tuple[float, List[int]], is_closed_hand: bool) -> YakuForWait:
    if shanten[0] != 0:
        return {}
    waits = set(shanten[1])
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    # remove all red fives from the interpretation
    taatsu, _, _, sequences, triplets, pair = interpretation.unpack()
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

        # pinfu: no triplets and the remaining hand is a pair + ryanmen
        # since the pair could overlap with the ryanmen creating a tanki + sequence,
        # also check for that
        if len(triplets) == 0 and len(taatsu) in {1,2}:
            has_pair = pair is not None
            ryanmen = taatsu
            # set has_pair if it's a tanki overlapping a sequence
            if not has_pair and len(sequences) == 4 and len(ryanmen) == 1:
                tanki = ryanmen[0]
                for t1,t2,t3 in sequences:
                    if tanki == t1:
                        ryanmen = (t2,t3)
                        has_pair = True
                        break
                    elif tanki == t3:
                        ryanmen = (t1,t2)
                        has_pair = True
                        break
            if has_pair:
                tile1, tile2 = sorted_hand(ryanmen)
                outside = {PRED[tile1], SUCC[tile2]}
                # check that it's a ryanmen and not a penchan
                if SUCC[tile1] == tile2 and 0 not in outside:
                    for wait in waits & outside:
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
    CHANTA_TRIS = {(t,t,t) for t in range(41,48)}
    CHANTA_PAIRS = {(t,t) for t in range(41,48)}
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
                      seat: int):
    is_closed_hand = len(hand.calls) == 0
    ctr = Counter(hand.tiles)
    waits = list(yaku.keys())
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
        if got_riichi_event and is_ippatsu:
            for wait in waits:
                yaku[wait].append(("ippatsu", 1))

    # sanankou: check in closed part of the hand
    if Counter(Counter(hand.closed_part).values())[3] == 3:
        for wait in waits:
            yaku[wait].append(("sanankou", 2))

    # sankantsu: check in closed part of the hand
    num_kans = list(map(lambda call: "kan" in call.type, hand.calls)).count(True)
    if num_kans == 3:
        for wait in waits:
            yaku[wait].append(("sankantsu", 2))

    # yakuhai: if your tenpai hand has three, then you just have yakuhai for any wait
    # alternatively if your tenpai hand has two, then any wait matching that has yakuhai
    YAKUHAI_NAMES = {41: "ton", 42: "nan", 43: "shaa", 44: "pei", 45: "chun", 46: "hatsu", 47: "haku"}
    YAKUHAI = [45,46,47,(round//4)+41,((seat-round)%4)+41]
    for tile in YAKUHAI:
        for wait in waits:
            if ctr[tile] == 3 or (ctr[tile] == 2 and wait == tile):
                yaku[wait].append((YAKUHAI_NAMES[tile], 1))

    # dora: simply count the dora
    dora = sum(hand.tiles.count(dora) for dora in doras)
    for wait in waits:
        if wait in doras:
            wait_dora = dora + doras.count(wait)
            if wait_dora > 0:
                yaku[wait].append((f"dora {wait_dora}" if wait_dora > 1 else "dora", wait_dora))
        else:
            if dora > 0:
                yaku[wait].append((f"dora {dora}" if dora > 1 else "dora", dora))

    # ura: simply count the ura
    ura = sum(hand.tiles.count(ura) for ura in uras)
    for wait in waits:
        if wait in uras:
            wait_ura = ura + uras.count(wait)
            if wait_ura > 0:
                yaku[wait].append((f"ura {wait_ura}" if wait_ura > 1 else "ura", wait_ura))
        else:
            if ura > 0:
                yaku[wait].append((f"ura {ura}" if ura > 1 else "ura", ura))
    return yaku


def get_yaku(hand: Hand,
             events: List[Event],
             doras: List[int],
             uras: List[int],
             round: int,
             seat: int,
             check_rons: bool = True,
             check_tsumos: bool = True) -> Dict[int, Score]:
    if hand.shanten[0] != 0:
        return {}

    waits = set(hand.shanten[1])
    is_closed_hand = len(hand.calls) == 0
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    # now for each of the waits we calculate their possible yaku
    interpretations = get_hand_interpretations(hand, round, seat)
    # best_score[wait] = the Score value representing the best interpretation for that wait
    best_score = {wait: Score([], 0, 0, False, Interpretation(()), hand) for wait in waits}

    # we want to get the best yaku for each wait
    # each hand interpretation gives han and fu for some number of waits
    # get the best han and fu for each wait acrosss all interpretations
    for interpretation in interpretations:
        # print("========")
        # for k, v in best_score.items():
        #     print(f"{pt(k)}, {v.hand!s}")
        yaku: YakuForWait = get_stateless_yaku(interpretation, hand.shanten, is_closed_hand)
        # pprint(yaku)
        yaku = add_stateful_yaku(yaku, hand, events, doras, uras, round, seat)
        # pprint(yaku)
        round_fu = lambda fu: (((fu-1)//10)+1)*10
        for wait in yaku.keys():
            han = sum(b for _, b in yaku[wait])
            fixed_fu = 25 if ("chiitoitsu", 2) in yaku[wait] else None
            if check_rons:
                fixed_fu = fixed_fu or (30 if ("pinfu", 1) in yaku[wait] else None) # open pinfu ron = 30
                ron_fu = fixed_fu or round_fu(interpretation.ron_fu)
                best_score[wait] = max(best_score[wait], Score(yaku[wait], han, ron_fu, False, interpretation, hand))
            if check_tsumos:
                if is_closed_hand:
                    fixed_fu = fixed_fu or (20 if ("pinfu", 1) in yaku[wait] else None) # closed pinfu tsumo = 20
                    tsumo_fu = fixed_fu or round_fu(interpretation.tsumo_fu)
                    best_score[wait] = max(best_score[wait], Score(yaku[wait] + [("tsumo", 1)], han + 1, tsumo_fu, True, interpretation, hand))
                else:
                    tsumo_fu = fixed_fu or round_fu(interpretation.tsumo_fu)
                    best_score[wait] = max(best_score[wait], Score(yaku[wait], han, tsumo_fu, True, interpretation, hand))
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
                    check_rons = check_rons,
                    check_tsumos = check_tsumos)
    return ret

def test_get_stateless_yaku():
    from .shanten import calculate_shanten
    test_hand = lambda hand: get_stateless_yaku(hand, calculate_shanten(hand), True)

    # print(test_hand((11,12,13,21,22,23,31,32,33,38,37,25,25))) # pinfu, sansuoku
    print(test_hand((11,11,12,12,13,13,23,24,25,26,27,28,31))) # iipeikou
    print(test_hand((11,11,12,12,13,31,23,24,25,26,27,28,31))) # iipeikou
    print(test_hand((11,12,12,13,13,14,15,16,21,22,23,24,24))) # pinfu, iipeikou
    print(test_hand((11,12,12,13,13,22,22,23,23,24,24,33,33))) # pinfu, ryanpeikou

def get_takame_score(hand: Hand,
                     events: List[Event],
                     doras: List[int],
                     uras: List[int],
                     round: int,
                     seat: int) -> Tuple[Score, int]:
    assert hand.shanten[0] == 0
    
    # if no calls, use tsumo score. else, get ron score
    calls_present = len(hand.calls) > 0
    scores: Dict[int, Score] = get_yaku(hand = hand,
                                        events = events,
                                        doras = doras,
                                        uras = uras,
                                        round = round,
                                        seat = seat,
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
        y = get_seat_yaku(kyoku, w)
        ron_takame_tiles, ron_han, ron_fu, ron_yaku = get_takame(y, tsumo=False)
        tsumo_takame_tiles, tsumo_han, tsumo_fu, tsumo_yaku = get_takame(y, tsumo=True)
        print(f"{round_name(kyoku.round, kyoku.honba)} | seat {w} {print_hand_details_seat(kyoku, w)} | dora {ph(kyoku.doras)} ura {ph(kyoku.uras)}")
        if kyoku.result[0] == "ron":
            for t in ron_takame_tiles:
                score = get_score(ron_hand, ron_fu, is_dealer, False, kyoku.num_players)
                han_fu_string = f"{ron_han}/{ron_fu}={score} (ron)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {ron_yaku[t]}")
        else:
            for t in tsumo_takame_tiles:
                score = get_score(tsumo_hand, tsumo_fu, is_dealer, True, kyoku.num_players)
                han_fu_string = f"{tsumo_han}/{tsumo_fu}={score} (tsumo)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {tsumo_yaku[t]}")
        final_tile = kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
        print(f"actual    | {kyoku.result[0]} {pt(final_tile)} giving {kyoku.result[1].score} with yaku {kyoku.result[1].yaku.yaku_strs}")
        print("")
