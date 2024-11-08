import functools
import itertools
from .classes import Interpretation
from .constants import Shanten, PRED, SUCC, TANYAOHAI, YAOCHUUHAI
from .display import ph, pt
from .utils import get_taatsu_wait, get_waits, get_waits_taatsus, normalize_red_five, normalize_red_fives, sorted_hand, to_sequence, to_triplet, try_remove_all_tiles

from typing import *
from pprint import pprint

# This file details a shanten algorithm. It's not super efficient, but the
#   goal is to be able to distinguish different types of iishanten, and to
#   be able to determine the waits for both iishanten and tenpai hands.
#  
# The algorithm basically tries to remove every combination of groups and
#   taatsus to determine the shanten, and then looks at the resulting subhands
#   to determine the iishanten type and the waits.
# 
# See `_calculate_shanten` for more info.

# Timers used for profiling shanten.
# This algorithm is slow, so the program spends most of its time here.
import time
timers = {
    "calculate_hands": 0.0,
    "remove_some_taatsus": 0.0,
    "get_hand_shanten": 0.0,
    "get_shanten_type": 0.0,
    "get_tenpai_waits": 0.0,
    "total": 0.0,
}

###
### ukeire and shanten calculations
###

# represents a collection of hands. example: {(26,26,38,38),(26,27,38,38)}
Hands = Iterable[Tuple[int, ...]]
# also represents a collection of hands, but each suit is separate
# suit datatype. example: ({},{(6,6),(6,7)},{(8,8)},{}) is equivalent to the above
# always a 4-tuple (manzu, pinzu, souzu, jihai)
# each item is a set of possibilities for that suit
Suits = Tuple[Set[Tuple[int, ...]], ...]

# conversions between the two representations
def to_suits(hand: Tuple[int, ...]) -> Suits:
    suits: Dict[int, List[int]] = {1:[],2:[],3:[],4:[]}
    for tile in sorted(hand):
        suits[tile//10].append(tile%10)
    return tuple({tuple(s)} for s in suits.values())
def from_suits(suits: Suits) -> Iterator[Tuple[int, ...]]:
    return ((*(10+v for v in a), *(20+v for v in b), *(30+v for v in c), *(40+v for v in d))
        for a in suits[0] for b in suits[1] for c in suits[2] for d in suits[3])

def eliminate_from_suits(suits: Suits, keep_some: bool,
                         sequences_to_check: Callable[[int], Tuple[Tuple[int, ...], ...]],
                         multiples_to_check: int = 0) -> Suits:
    """
    Very general function, removes all combinations of a given pattern from a hand
    The pattern is specified in either sequences_to_check or multiples_to_check
    (sequences_to_check: given a base tile, like 5, return tiles that form the pattern, like 567)
    (multiples_to_check: given 2, check for all pairs. given 3, check for all triplets.
    If keep_some is False, the returned hands will contain all possibilities of removing
      as many instances of the pattern as possible from the hand
    If keep_some is True, the returned hands will contain all possibilities of removing
      one or more instances of the pattern from the hand
    """
    def remove(hand: Tuple[int, ...], do_sequences: bool = True) -> Set[Tuple[int, ...]]:
        max_length = len(hand)
        def rec(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
            nonlocal max_length
            max_length = min(max_length, len(hand))
            candidates = set()
            for i, tile in enumerate(hand):
                # check pair/triplet
                if multiples_to_check > 0 and i + (multiples_to_check-1) < len(hand) and all(tile == hand[i+n] for n in range(1, multiples_to_check)):
                    candidates.add((*hand[:i],*hand[i+multiples_to_check:]))
                if do_sequences:
                    for sequence in sequences_to_check(tile):
                        sequence_removed = try_remove_all_tiles(hand, sequence)
                        if len(sequence_removed) < len(hand):
                            candidates.add(sequence_removed)
            if len(candidates) > 0:
                return set.union(*map(rec, candidates)) | ({hand} if keep_some else set())
            else:
                return {hand}
        return rec(hand) if keep_some else set(filter(lambda h: len(h) == max_length, rec(hand)))

    return (
        set().union(*(remove(s) for s in suits[0])),
        set().union(*(remove(s) for s in suits[1])),
        set().union(*(remove(s) for s in suits[2])),
        suits[3] if multiples_to_check == 0 else set().union(*(remove(s, do_sequences=False) for s in suits[3]))
    )

to_none = lambda tile: ()
to_sequences = lambda tile: ((tile+2, tile+1, tile),)
to_taatsus = lambda tile: ((tile+2, tile), (tile+1, tile),)
eliminate_some_groups  = lambda suits: eliminate_from_suits(suits, True,  to_sequences, 3)
eliminate_some_taatsus = lambda suits: eliminate_from_suits(suits, True,  to_taatsus)
eliminate_all_groups   = lambda suits: eliminate_from_suits(suits, False, to_sequences, 3)
eliminate_all_taatsus  = lambda suits: eliminate_from_suits(suits, False, to_taatsus)
eliminate_some_pairs   = lambda suits: eliminate_from_suits(suits, True,  to_none, 2)

def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    """Given a tenpai hand, get all its waits"""
    return {wait for i in Interpretation(hand).generate_all_interpretations() for wait in i.get_waits()}

def get_hand_shanten(suits: Suits, groups_needed: int) -> int:
    """Return the shanten of a given hand that has all of its groups, ryanmens, and kanchans removed"""
    # get the minimum number of floating tiles in each suit
    count_floating = lambda hand: tuple(Counter(hand).values()).count(1)
    floating: List[int] = [min(map(count_floating, hands), default=0) for hands in suits]

    def get_shanten(total_floating: int, pair_exists: bool) -> int:
        # needs_pair = 1 if the hand is missing a pair but is full of taatsus -- need to convert a taatsu to a pair
        # must_discard_taatsu = 1 if the hand is 6+ blocks -- one of the taatsu is actually 2 floating tiles
        # shanten = (3 + num_floating - num_groups) // 2, plus the above
        needs_pair = 1 if not pair_exists and groups_needed > total_floating else 0
        must_discard_taatsu = 1 if groups_needed >= 3 and total_floating <= 1 else 0
        shanten = needs_pair + must_discard_taatsu + (groups_needed + total_floating - 1) // 2
        return shanten

    shanten = get_shanten(sum(floating), False)

    # check if we have a pair
    # take the hand(s) with a pair that would add the least additional floating tiles to that suit
    has_pair = lambda hand: any(hand.count(tile) == 2 for tile in hand)
    extra_floating = min(min(map(count_floating, filter(has_pair, hands)), default=99) - f for f, hands in zip(floating, suits))
    if extra_floating < 50:
        shanten = min(shanten, get_shanten(sum(floating) + extra_floating, True))
    return shanten

# when the wait is any tile except the ones we have a pair of already
# e.g. tenpai with one triplet
# e.g. iishanten with two triplets
chiitoi_replacement_waits = lambda ctr: sorted_hand((TANYAOHAI | YAOCHUUHAI) - {tile for tile, count in ctr.items() if count >= 2})
# when the wait is all the single tiles we have in hand
chiitoi_single_tiles = lambda ctr: sorted_hand(k for k, v in ctr.items() if v == 1)

def calculate_chiitoitsu_shanten(starting_hand: Tuple[int, ...], ctr: Counter[int]) -> Shanten:
    # get chiitoitsu waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(normalize_red_fives(starting_hand))
    counts = tuple(ctr.values())
    tiles_needed = 7 - counts.count(2) - counts.count(3) - counts.count(4)
    useless_tiles = counts.count(3) + 2*counts.count(4)
    # tenpai is when tiles_needed == 1 and useless_tiles == 0
    shanten = max(useless_tiles, tiles_needed - 1)
    waits = () if shanten > 1 else chiitoi_replacement_waits(ctr) if useless_tiles >= tiles_needed else chiitoi_single_tiles(ctr)
    return shanten, waits

def calculate_kokushi_shanten(starting_hand: Tuple[int, ...], ctr: Counter[int]) -> Shanten:
    # get kokushi waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(normalize_red_fives(starting_hand))
    has_pair = len([v for v in ctr.values() if v > 1]) >= 1
    shanten = (12 if has_pair else 13) - len(YAOCHUUHAI.intersection(starting_hand))
    waits = () if shanten > 1 else sorted_hand(YAOCHUUHAI if not has_pair else YAOCHUUHAI.difference(starting_hand))
    return shanten, waits

# Caches for removing pairs or complex shapes from a given suit

# pair_shapes[shape] = {(pair, shape without pair), ...}
pair_shapes: Dict[Tuple[int, ...], Set[Tuple[Tuple[int, ...], Tuple[int, ...]]]] = {}
# complex_shapes[shape] = {(complex shape, shape without complex shape), ...}
complex_shapes: Dict[Tuple[int, ...], Set[Tuple[Tuple[int, ...], Tuple[int, ...]]]] = {}

def add_pair_shape(hand: Tuple[int, ...], recursed: bool = False) -> None:
    """Used to add an entry to pair_shapes"""
    global pair_shapes
    pair_shapes.setdefault(hand, set())
    for tile in hand:
        if hand.count(tile) >= 2:
            ix = hand.index(tile)
            pair = hand[ix:ix+2]
            remaining_hand = (*hand[:ix], *hand[ix+2:])
            pair_shapes[hand].add((pair, remaining_hand))
            if not recursed:
                add_complex_shape(remaining_hand, recursed=True)
                add_pair_shape(remaining_hand, recursed=True)

def add_complex_shape(hand: Tuple[int, ...], recursed: bool = False) -> None:
    """Used to add an entry to complex_shapes"""
    global complex_shapes
    complex_shapes.setdefault(hand, set())
    for tile in hand[:-2]:
        to_complex_shapes = lambda t1: (t2:=t1+1, t3:=t1+2, t5:=t1+4, ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
        for shape in to_complex_shapes(tile):
            remaining_hand = try_remove_all_tiles(hand, shape)
            if len(remaining_hand) < len(hand):
                complex_shapes[hand].add((shape, remaining_hand))
                if True: # we want multiple complex shapes; no need to stop when recursed once
                    add_complex_shape(remaining_hand, recursed=True)
                    add_pair_shape(remaining_hand, recursed=True)

def identify_pairs_and_complex(suits: Suits) -> Tuple[Suits, Suits]:
    global pair_shapes
    global complex_shapes
    pair_hands: Suits = (set(()),set(()),set(()),set(()))
    complex_hands: Suits = (set(()),set(()),set(()),set(()))
    for i, suit in enumerate(suits):
        for hand in suit:
            # check if there's a pair
            add_pair_shape(hand)
            if len(pair_shapes[hand]) > 0:
                pair_hands[i].add(hand)
            if i < 3:
                # check if there's any complex shapes
                add_complex_shape(hand)
                if len(complex_shapes[hand]) > 0:
                    complex_hands[i].add(hand)
    return pair_hands, complex_hands

def get_other_tiles(hand_size: int, suits: Suits,
                    hand1: Tuple[int, ...], i: int,
                    hand2: Tuple[int, ...] = (), j: int = -1,
                    hand3: Tuple[int, ...] = (), k: int = -1) -> Iterator[Tuple[int, ...]]:
    # get all combinations of tiles from all other suits
    # such that adding them to (*hand, *hand2) makes it length 7
    # i is the suit for hand1, j is the suit for hand2
    return ((*(tuple(10+tile for tile in a) if 0 not in (i,j,k) else ()),
             *(tuple(20+tile for tile in b) if 1 not in (i,j,k) else ()),
             *(tuple(30+tile for tile in c) if 2 not in (i,j,k) else ()),
             *(tuple(40+tile for tile in d) if 3 not in (i,j,k) else ()))
            for a in ({hand1} if i == 0 else {hand2} if j == 0 else {hand3} if k == 0 else suits[0])
            for b in ({hand1} if i == 1 else {hand2} if j == 1 else {hand3} if k == 0 else suits[1])
            for c in ({hand1} if i == 2 else {hand2} if j == 2 else {hand3} if k == 0 else suits[2])
            for d in ({hand1} if i == 3 else {hand2} if j == 3 else {hand3} if k == 0 else suits[3])
            if len(a)+len(b)+len(c)+len(d) == hand_size)

def extract_unique_groups(groups: Tuple[int, ...]) -> Tuple[List[Tuple[int, int, int]], List[Tuple[int, int, int]]]:
    sequences: List[Tuple[int, ...]] = []
    triplets: List[Tuple[int, ...]] = []
    if len(groups) == 12:
        groups = (*groups, 1)
    elif len(groups) == 9:
        groups = (*groups, 1, 1, 3, 3)
    elif len(groups) == 6:
        groups = (*groups, 1, 1, 3, 3, 5, 5, 7)
    elif len(groups) == 3:
        groups = (*groups, 1, 1, 3, 3, 5, 5, 7, 7, 9, 9)
    for interpretation in Interpretation(groups).generate_all_interpretations():
        sequences.extend(list(interpretation.sequences))
        triplets.extend(list(interpretation.triplets))
    return cast(List[Tuple[int, int, int]], list(set(sequences))), \
           cast(List[Tuple[int, int, int]], list(set(triplets)))

def calculate_wait_extensions(groups: Tuple[int, ...], waits: Set[int]) -> List[Tuple[Set[int], int, Tuple[int, int, int]]]:
    sequences, triplets = extract_unique_groups(groups)
    # only sequence extensions apply
    left_extensions = []
    left_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[tile]])) for tile in waits if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[tile]]) in sequences])
    left_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[tile]])) for ([tile], _, _) in left_extensions if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[tile]]) in sequences])
    right_extensions = []
    right_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(tile)) for tile in waits if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(tile) in sequences])
    right_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(tile)) for ([tile], _, _) in right_extensions if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(tile) in sequences])
    return left_extensions + right_extensions

def calculate_tanki_wait_extensions(groups: Tuple[int, ...], waits: Set[int]) -> List[Tuple[Set[int], int, Tuple[int, int, int]]]:
    sequences, triplets = extract_unique_groups(groups)
    # sequence extensions
    left_extensions = []
    left_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[tile]])) for tile in waits if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[tile]]) in sequences])
    left_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[tile]])) for ([tile], _, _) in left_extensions if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[tile]]) in sequences])
    left_adj_extensions = []
    left_adj_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[PRED[tile]]])) for tile in waits if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[PRED[tile]]]) in sequences])
    left_adj_extensions.extend([({PRED[PRED[PRED[tile]]]}, tile, to_sequence(PRED[PRED[PRED[tile]]])) for ([tile], _, _) in left_adj_extensions if PRED[PRED[PRED[tile]]] > 0 if to_sequence(PRED[PRED[PRED[tile]]]) in sequences])
    right_extensions = []
    right_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(tile)) for tile in waits if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(tile) in sequences])
    right_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(tile)) for ([tile], _, _) in right_extensions if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(tile) in sequences])
    right_adj_extensions = []
    right_adj_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(SUCC[tile])) for tile in waits if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(SUCC[tile]) in sequences])
    right_adj_extensions.extend([({SUCC[SUCC[SUCC[tile]]]}, tile, to_sequence(SUCC[tile])) for ([tile], _, _) in right_adj_extensions if SUCC[SUCC[SUCC[tile]]] > 0 if to_sequence(SUCC[tile]) in sequences])
    # triplet extensions
    triplet_extensions = []
    for tile in waits:
        # 3335, 4445, 5666, 5777
        possible_triplet_extensions = [
            ({PRED[tile]}, to_triplet(PRED[PRED[tile]])),
            ({PRED[PRED[tile]], SUCC[tile]}, to_triplet(PRED[tile])),
            ({PRED[tile], SUCC[SUCC[tile]]}, to_triplet(SUCC[tile])),
            ({SUCC[tile]}, to_triplet(SUCC[SUCC[tile]])),
        ]
        for tiles, triplet in possible_triplet_extensions:
            tiles = set(tile for tile in tiles if tile > 0)
            if triplet in triplets and len(tiles) > 0:
                triplet_extensions.append((tiles, tile, triplet))
    return left_extensions + left_adj_extensions + right_extensions + right_adj_extensions + triplet_extensions

def determine_kuttsuki_headless_tiles(shanten_int: int, groups_needed: int, groupless_hands: Suits) -> Tuple[Set[int], Set[int], Set[int]]:
    kuttsuki_tiles: Set[int] = set() # tiles that could be the floating kuttsuki tiles in hand
    headless_tiles: Set[int] = set() # tiles that could be part of the 7 headless tiles in hand
    pair_tiles: Set[int] = set() # pairs that exist in hand
    # the resulting hands should have 2, 4, 6 total tiles
    # if any of the suits contains a pair, then all non-pair tiles are possible kutsuki tiles
    # otherwise it's pairless and all tiles are headless tiles
    kuttsuki_always_exists = False
    taatsuless_hands = eliminate_some_taatsus(eliminate_some_pairs(groupless_hands))
    for i, (suit, taatsuless) in enumerate(zip(groupless_hands, taatsuless_hands)):
        has_kuttsuki = False
        has_non_kuttsuki = False
        for hand in taatsuless:
            ctr = Counter(hand)
            has_pair = 2 in ctr.values()
            is_kuttsuki = (shanten_int == 1 and has_pair) \
                       or (shanten_int == 2 and (has_pair or groups_needed == 1)) \
                       or (shanten_int == 3 and (has_pair or groups_needed == 2))
            pair_tiles |= {(10*(i+1))+tile for tile, cnt in ctr.items() if cnt == 2}
            if is_kuttsuki:
                # grab the non-pair tiles in this suit
                kuttsuki_tiles |= {(10*(i+1))+tile for tile, cnt in ctr.items() if cnt == 1}
                # grab every tile in every other suit
                kuttsuki_tiles |= {(10*(j+1))+tile for j, s in enumerate(taatsuless_hands) if i != j for hand in s for tile in hand}
                # grab every non-pair tile in this suit
                headless_tiles |= {(10*(i+1))+tile for tile in hand if ctr[tile] < 2}
                has_kuttsuki = True
            else:
                # grab every tile in this suit
                headless_tiles |= {(10*(i+1))+tile for tile in hand}
                has_non_kuttsuki = True
        for hand in suit - taatsuless:
            # grab every tile in this suit
            headless_tiles |= {(10*(i+1))+tile for tile in hand}
        if has_kuttsuki and not has_non_kuttsuki:
            kuttsuki_always_exists = True
    if kuttsuki_always_exists:
        headless_tiles = set()
    return kuttsuki_tiles, headless_tiles, pair_tiles

def get_headless_taatsus_waits(headless_tiles: Iterable[int]) -> Tuple[Tuple[Tuple[int, int], ...], Set[int], Tuple[int, ...]]:
    tiles_list: List[int] = list(sorted(headless_tiles))
    taatsus: Set[Tuple[int, int]] = set()
    floating_tiles: Tuple[int, ...] = ()
    added_as_taatsu: List[bool] = [False] * len(tiles_list)
    tile_possibilities: Set[Tuple[int, ...]] = {tuple(tiles_list)} | set(from_suits(eliminate_all_groups(to_suits(tuple(tiles_list)))))
    tiles = [0]
    for t in tile_possibilities:
        tiles.extend([*t, 0])
    for i, (l, t1, t2, r) in enumerate(zip(tiles[:-3], tiles[1:-2], tiles[2:-1], tiles[3:])):
        if t1 == 0 or t2 == 0:
            continue
        is_pair = t2 == t1
        is_ryanmen = t2 == SUCC[t1]
        is_kanchan = t2 == SUCC[SUCC[t1]]
        if is_ryanmen and (PRED[t1] in tiles[1:-1] or SUCC[t2] in tiles[1:-1]):
            # skip sequences (they should not be passed in, but we use this function for non-headless hands too)
            continue
        pair_side = l != 0 and r != 0 and (t1 == l or r == t2)
        ryanmen_side = l != 0 and r != 0 and (t1 == SUCC[l] or r == SUCC[t2])
        kanchan_side = l != 0 and r != 0 and (t1 == SUCC[SUCC[l]] or r == SUCC[SUCC[t2]])
        # we ignore kanchans if there is a ryanmen on either side that would provide the same wait
        ignore_kanchan = ryanmen_side
        # we ignore pairs if it's a triplet, or if there is a kanchan/ryanmen on either side
        ignore_pair = pair_side or ryanmen_side or kanchan_side
        if (not ignore_pair and is_pair) or is_ryanmen or (not ignore_kanchan and is_kanchan):
            taatsus.add((t1, t2))
            if i < len(tiles_list):
                added_as_taatsu[i] = True
                if i+1 < len(tiles_list):
                    added_as_taatsu[i+1] = True
    for in_taatsu, tile in zip(added_as_taatsu, tiles_list):
        if not in_taatsu:
            floating_tiles = (*floating_tiles, tile)
    waits = set().union(*map(get_taatsu_wait, taatsus))
    return tuple(sorted(taatsus)), waits, tuple(sorted(floating_tiles))

def get_taatsus_waits(hand: Iterable[int]) -> Iterator[Tuple[Tuple[Tuple[int, int], ...], Set[int], Tuple[int, ...]]]:
    # get all possible taatsu waits, including pair waits
    tiles: Tuple[int, ...] = tuple(sorted(hand))
    for tile, amt in Counter(tiles).items():
        if amt >= 2:
            pair = (tile, tile)
            remaining = try_remove_all_tiles(tiles, pair)
            assert len(remaining) < len(tiles)
            for taatsus, waits, floating_tiles in get_taatsus_waits(remaining):
                taatsus = (*taatsus, pair)
                waits = waits.copy() | {tile}
                yield taatsus, waits, floating_tiles
    yield get_headless_taatsus_waits(tiles)

def get_shanten_type(shanten_int: int, starting_hand: Tuple[int, ...], groupless_hands: Suits, groups_needed: int) -> Tuple[float, Set[int], Dict[str, Any]]:
    # given an 1-3 shanten hand, calculate the shanten type and its waits
    # we'll always return S.XXX shanten, where S is the shanten and XXX represents the type of iishanten
    # - 1.300 tanki iishanten (tanki tenpai, but you have all 4 tiles in hand)
    # - 1.200 kokushi musou iishanten
    # - 1.100 chiitoitsu iishanten
    # - 1.010 headless iishanten (you have three groups and 1+ taatsus, no pair)
    # - 1.020 kuttsuki iishanten (you have three groups, a pair, and 2 floating tiles)
    # - 1.030 kuttsuki headless iishanten (your hand can be interpreted as both of the above)
    # - 1.001 floating iishanten (you have two groups and a pair and two taatsus)
    # - 1.002 imperfect (complete) iishanten (same, but one taatsu has a second pair like 334)
    # - 1.003 perfect iishanten (same, but both taatsus are ryanmen)
    # - 2.200 kokushi musou ryanshanten
    # - 2.100 chiitoitsu ryanshanten
    # - 2.010 headless ryanshanten (your hand has two groups and 2+ taatsus, no pair)
    # - 2.020 kuttsuki ryanshanten (your hand has two groups, a pair, 1 taatsu, and 3+ floating tiles)
    # - 2.030 kuttsuki headless ryanshanten (your hand can be interpreted as both of the above)
    # - 2.040 kuttsuki ryanshanten (your hand has three groups and 4 floating tiles)
    # - 2.001 simple ryanshanten (your hand has a group, a pair, and 3+ taatsus)
    # - 3.200 kokushi musou sanshanten
    # - 3.100 chiitoitsu sanshanten
    # - 3.010 headless sanshanten (your hand has two groups and 3+ taatsus, no pair)
    # - 3.020 kuttsuki sanshanten (your hand has a group, a pair, 2 taatsus, and 4 floating tiles)
    # - 3.030 kuttsuki headless ryanshanten (your hand can be interpreted as both of the above)
    # - 2.040 kuttsuki sanshanten (your hand has two groups, 0-1 taatsus, and 6+ floating tiles)
    # - 3.001 simple sanshanten (your hand has no groups, a pair, and 4+ taatsus)
    # One hand could have multiple iishanten types contributing to the overall wait.
    # Combining the above is how we describe those kinds of hands:
    # - 1.120 chiitoi kuttsuki iishanten
    # - 2.021 kuttsuki floating ryanshanten
    # - 1.121 chiitoi kuttsuki floating iishanten
    shanten: float = float(shanten_int)
    waits: Set[int] = set()
    debug_info: Dict[str, Any] = {}

    assert shanten_int in {1, 2, 3}, "get_shanten_type was not passed an 1- to 3-shanten hand"

    # first check headless and kuttsuki
    is_headless_or_kutsuki = False
    if shanten_int >= groups_needed:
        kuttsuki_tiles, headless_tiles, kuttsuki_pair_tiles = determine_kuttsuki_headless_tiles(shanten_int, groups_needed, groupless_hands)
        # if there's kuttsuki tiles, then it's kuttsuki iishanten
        kuttsuki_taatsus: Set[Tuple[int, int]] = set()
        kuttsuki_taatsu_waits: Set[int] = set()
        kuttsuki_tanki_waits: Set[int] = set()
        if len(kuttsuki_tiles) > 0:
            shanten += 0.02
            is_headless_or_kutsuki = True
            # for each kuttsuki tile, its waits are {tile-2,tile-1,tile,tile+1,tile+2}
            for tile in kuttsuki_tiles:
                kuttsuki_tanki_waits |= {PRED[PRED[tile]], PRED[tile], tile, SUCC[tile], SUCC[SUCC[tile]]} - {0}
            # the pair tile also contributes to the wait
            waits |= kuttsuki_pair_tiles
            # so do the waits of the remaining taatsu
            for hand in from_suits(groupless_hands):
                remaining = try_remove_all_tiles(hand, tuple([*kuttsuki_tiles, *kuttsuki_pair_tiles, *kuttsuki_pair_tiles]))
                taatsus, taatsu_waits, floating_tiles = get_headless_taatsus_waits(remaining)
                kuttsuki_taatsus |= set(taatsus)
                kuttsuki_taatsu_waits |= taatsu_waits

        debug_info["kuttsuki_taatsus"] = tuple(sorted(kuttsuki_taatsus))
        debug_info["kuttsuki_taatsu_waits"] = kuttsuki_taatsu_waits
        debug_info["kuttsuki_tanki_waits"] = kuttsuki_tanki_waits
        waits |= kuttsuki_taatsu_waits
        debug_info["kuttsuki_tiles"] = kuttsuki_tiles
        debug_info["headless_tiles"] = headless_tiles
        debug_info["kuttsuki_pair_tiles"] = kuttsuki_pair_tiles
        # if there's headless tiles, then it's headless iishanten
        if len(headless_tiles) > 0:
            shanten += 0.01
            is_headless_or_kutsuki = True
            # for 2-shanten there's two kinds of headless: either you have three taatsus,
            #   or two taatsus + 3 floating tiles
            # the taatsu waits always contribute to the wait
            # the floating tiles are always tanki waits
            # when you have three taatsus, any can be treated as two floating tiles,
            #   so all six of the taatsu tiles are tanki waits
            taatsus, headless_taatsu_waits, floating_tiles = get_headless_taatsus_waits(headless_tiles)
            headless_tanki_waits = headless_tiles if len(taatsus) >= shanten_int+1 else set(floating_tiles)
            extensions = calculate_tanki_wait_extensions(try_remove_all_tiles(starting_hand, tuple(headless_tiles)), headless_tanki_waits)
            extended_waits = set(wait for waits, _, _ in extensions for wait in waits)
            waits |= headless_taatsu_waits | headless_tanki_waits | extended_waits
            debug_info["headless_taatsus"] = taatsus
            debug_info["headless_floating_tiles"] = floating_tiles
            debug_info["headless_taatsu_waits"] = headless_taatsu_waits
            debug_info["headless_tanki_waits"] = headless_tanki_waits
            debug_info["headless_tanki_extensions"] = extensions
            # sequences extend waits

    # helper function for the below
    is_perfect_iishanten = False
    has_complete_hand = False
    has_floating_hand = False
    debug_info["simple_hands"] = []
    def add_hand(complex_hand: Tuple[int, ...], pair_shape: Tuple[int, ...], other_tiles: Tuple[int, ...]) -> None:
        # populate complete_waits with all possible complex waits arising from this breakdown of the hand
        nonlocal waits
        nonlocal is_perfect_iishanten
        nonlocal has_complete_hand
        nonlocal has_floating_hand
        nonlocal debug_info
        is_pair = lambda h: len(h) == 2 and h[0] == h[1]
        is_ryanmen = lambda h: len(h) == 2 and SUCC[h[0]] == h[1] and h[0] not in {11,18,21,28,31,38}
        h = (*complex_hand, *pair_shape, *other_tiles)
        valid_interpretations = []
        for i, suit in enumerate(to_suits(complex_hand)):
            add_i = lambda h: tuple(10*(i+1)+tile for tile in h)
            queue: Set[Any] = {(hand, ()) for hand in suit}
            empty_hand = ((), ())
            if i == 0:
                queue.add(empty_hand)
            elif empty_hand in queue:
                queue.remove(empty_hand)
            while len(queue) > 0:
                cx_hand, all_cx_shapes = queue.pop()
                removed = complex_shapes.get(cx_hand, set())
                if len(removed) == 0:
                    remaining_tiles = (*add_i(cx_hand), *other_tiles)
                    for taatsus, taatsu_waits, floating in get_taatsus_waits(remaining_tiles):
                        # print(remaining_tiles, pair_shape, taatsus, floating)
                        # if there are shanten+1 simple/complex shapes, add to valid_interpretations
                        # we already have 1 due to the pair, so we need shanten more
                        if len(taatsus) + len(all_cx_shapes) >= shanten_int+1: 
                            valid_interpretations.append((taatsus, all_cx_shapes, floating))
                else:
                    for cx_shape, remainder in removed:
                        queue.add((remainder, (*all_cx_shapes, add_i(cx_shape))))
        # if complex_hand == ():
        #     print(pair_shape, other_tiles, valid_interpretations)
        if len(valid_interpretations) == 0:
            return
        for s_shapes, cx_shapes, floating in valid_interpretations:
            simple_waits = set()
            complex_waits = set()
            for simple_shape in s_shapes:
                if simple_shape[0] == simple_shape[1]:
                    simple_waits.add(simple_shape[0])
                else:
                    simple_waits |= get_taatsu_wait(simple_shape)
            for complex_shape in cx_shapes:
                t1, t2 = complex_shape[0:2], complex_shape[1:3]
                if shanten_int == 1 and len(s_shapes) == 1 and is_ryanmen(s_shapes[0]) and (is_ryanmen(t1) or is_ryanmen(t2)):
                    is_perfect_iishanten = True
                complex_waits |= get_taatsu_wait(t1) | get_taatsu_wait(t2)
                complex_waits |= ({t1[0], pair_shape[0]} if is_pair(t1) else set())
                complex_waits |= ({t2[0], pair_shape[0]} if is_pair(t2) else set())
            if len(floating) == 0:
                has_complete_hand = True
            else:
                has_floating_hand = True

            # calculate wait extensions
            extensions = calculate_wait_extensions(try_remove_all_tiles(starting_hand, h), simple_waits | complex_waits)
            extended_waits = set(wait for waits, _, _ in extensions for wait in waits)
            waits |= simple_waits | complex_waits | extended_waits
            debug_info["simple_hands"].append({
                "pair": pair_shape,
                "simple_shapes": s_shapes,
                "complex_shapes": cx_shapes,
                "floating_tiles": floating,
                "simple_waits": simple_waits,
                "complex_waits": complex_waits,
                "extensions": extensions,
            })
            # print(debug_info["simple_hands"][-1])

    # first identify every single pair and complex group in all suits
    suits = eliminate_some_groups(to_suits(starting_hand))
    pair_hands, complex_hands = identify_pairs_and_complex(suits)

    # then populate waits by constructing all possible floating/complete hands
    groupless_suits = eliminate_all_groups(suits)
    simple_hand_length = 4 + (3 * shanten_int)
    for i, suit in enumerate(pair_hands):
        add_i = lambda h: tuple(10*(i+1)+tile for tile in h)
        for pair_hand in suit:
            for pair_shape, remaining in pair_shapes[pair_hand]:
                # check if we broke a set for this pair shape
                pair_broke_set = pair_hand not in groupless_suits[i]
                # if we broke a set and don't have enough sets originally
                # then we cannot choose this pair
                if pair_broke_set and groups_needed > shanten:
                    continue
                # for all possible length <simple_hand_length> hands containing the pair,
                for other_tiles in get_other_tiles(simple_hand_length, suits, pair_hand, i):
                    # add this hand as a floating hand
                    # print(pair_shape, remaining, other_tiles)
                    add_hand((), add_i(pair_shape), tuple(sorted((*add_i(remaining), *other_tiles))))
                    if i == 3:
                        break # honor suit cannot have complex shapes
                    # get all combinations of complex shapes possible
                    complex_suits: Suits = (*([{remaining} if i == j else complex_hands[j].copy() for j in range(3)]), set())
                    # remove the maximum number of groups
                    groupless_complex_suits = tuple({hand for hand in suit if len(hand) == min(map(len, suit))} for suit in eliminate_all_groups(complex_suits))
                    for j, suit2 in enumerate(complex_suits):
                        queue: Set[Any] = suit2.copy()
                        suit2.clear()
                        while len(queue) > 0:
                            tiles = queue.pop()
                            for complex_shape, remaining2 in complex_shapes.get(tiles, set()):
                                # check if we broke a set for this complex shape
                                cx_broke_set = tiles not in groupless_complex_suits[j]
                                # if i != j:
                                #     cx_broke_set = cx_broke_set and tiles not in groupless_suits[j]
                                # print(pair_broke_set, cx_broke_set)
                                # if we broke a triplet and don't have enough sets originally
                                # then we cannot choose this complex shape
                                if cx_broke_set and groups_needed > shanten:
                                    continue
                                # same if we also broke a set with the pair
                                if pair_broke_set and cx_broke_set:
                                    continue
                                # print(pair_hand, tiles, pair_shape, complex_shape)
                                suit2.add(tiles)
                                queue.add((tiles, remaining2))
                    # print(i, complex_suits)

                    all_complex_shapes: List[List[Tuple[int, ...]]] = []
                    other_tiles_params: List[Tuple] = []
                    for complex_shape1 in complex_suits[i] | {()}:
                        all_complex_shapes.append([complex_shape1])
                        other_tiles_params.append((complex_shape1, i))
                        for j, suit2 in enumerate(complex_suits):
                            if i == j:
                                continue
                            for complex_shape2 in suit2:
                                all_complex_shapes.append([complex_shape1, complex_shape2])
                                other_tiles_params.append((complex_shape1, i, complex_shape2, j))
                                for k, suit3 in enumerate(complex_suits):
                                    if i == k or j == k:
                                        continue
                                    for complex_shape3 in suit3:
                                        all_complex_shapes.append([complex_shape1, complex_shape2, complex_shape3])
                                        other_tiles_params.append((complex_shape1, i, complex_shape2, j, complex_shape3, k))

                    add_ix = lambda h, ix: tuple(10*(ix+1)+tile for tile in h)
                    for shapes, params in zip(all_complex_shapes, other_tiles_params):
                        if shapes[0] == ():
                            shapes = shapes[1:]
                        if len(shapes) == 0:
                            continue
                        # add pair shape to suit i
                        cx_shapes = tuple(tile for h, ix in zip(params[0::2], params[1::2]) for tile in add_ix(h, ix))
                        for other_tiles in get_other_tiles(simple_hand_length, suits, (*params[0], *pair_shape), *params[1:]):
                            add_hand(cx_shapes, add_ix(pair_shape, i), other_tiles)
                    # print(i, other_tiles_params)

    shanten += 0.003 if is_perfect_iishanten else \
               0.002 if has_complete_hand else \
               0.001 if has_floating_hand else 0
    return round(shanten, 3), waits, debug_info

# def get_ryanshanten_type(starting_hand: Tuple[int, ...], groupless_hands: Suits, groups_needed: int) -> Tuple[float, Set[int], Dict[str, Any]]:

#     return round(shanten, 3), waits, debug_info

@functools.lru_cache(maxsize=65536)
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Shanten:
    """
    Return the shanten of the hand, plus its waits (if tenpai or iishanten).
    If the shanten is 2+, the waits returned are an empty list.
    If iishanten, the returned shanten is 1.XXX, based on the type of iishanten.
    (See get_shanten_type for details.)
    """
    assert len(starting_hand) in {1, 4, 7, 10, 13}, f"calculate_shanten() was passed a {len(starting_hand)} tile hand: {ph(starting_hand)}"
    # 1. Remove all groups
    # 2. Calculate shanten
    # 3. Check for iishanten/tenpai
    # 4. If iishanten or tenpai, calculate the waits
    # 5. Do 2-4 for chiitoitsu and kokushi

    suits = to_suits(starting_hand)
    start_time = now = time.time()
    groupless_hands = eliminate_all_groups(suits)
    timers["calculate_hands"] += time.time() - now
    groups_needed = (len(next(from_suits(groupless_hands))) - 1) // 3

    # calculate shanten for every combination of groups removed
    now = time.time()
    removed_taatsus = eliminate_some_taatsus(groupless_hands)
    timers["remove_some_taatsus"] += time.time() - now

    now = time.time()
    shanten_int: int = get_hand_shanten(removed_taatsus, groups_needed)
    shanten: float = float(shanten_int)
    timers["get_hand_shanten"] += time.time() - now
    assert shanten >= 0, f"somehow calculated negative shanten for {ph(sorted_hand(starting_hand))}"

    # if iishanten, get the type of iishanten based on tiles remaining after removing some number of taatsus
    # then do some ad-hoc processing to get its waits
    waits: Set[int] = set()
    if shanten == 1:
        assert groups_needed in {1,2}, f"{ph(sorted_hand(starting_hand))} is somehow iishanten with {4-groups_needed} groups"
        now = time.time()
        shanten, waits, _ = get_shanten_type(shanten_int, starting_hand, groupless_hands, groups_needed)
        timers["get_shanten_type"] += time.time() - now
        # assert shanten != 1, f"somehow failed to detect type of iishanten for iishanten hand {ph(sorted_hand(starting_hand))}"

    # if tenpai, get the waits
    elif shanten == 0:
        now = time.time()
        waits = get_tenpai_waits(starting_hand)
        timers["get_tenpai_waits"] += time.time() - now
        assert len(waits) > 0, f"tenpai hand {ph(sorted_hand(starting_hand))} has no waits?"

    # compare with chiitoitsu and kokushi shanten
    ctr = Counter(normalize_red_fives(starting_hand))
    if len(starting_hand) == 13:
        (c_shanten, c_waits) = calculate_chiitoitsu_shanten(starting_hand, ctr)
        (k_shanten, k_waits) = calculate_kokushi_shanten(starting_hand, ctr)
        if c_shanten <= shanten:
            # take the min, unless we're iishanten in which case we add 0.1 to the shanten
            if c_shanten == 1 and shanten >= 1 and shanten < 2:
                shanten += 0.1
                waits |= set(c_waits)
            elif c_shanten < shanten:
                shanten = c_shanten
                waits = set(c_waits)
            if shanten == 1:
                shanten = 1.1
        if k_shanten < shanten:
            shanten = k_shanten
            if shanten == 1:
                shanten = 1.2
            waits = set(k_waits)

    # at this point, every iishanten and tenpai hand should have waits
    import os
    if os.getenv("debug"):
        assert not (shanten < 2 and len(waits) == 0), f"somehow no waits for a shanten {shanten} hand: {ph(starting_hand)}"

    if shanten < 2:
        # remove all ankan in hand from the waits
        ankan_tiles = {k for k, v in ctr.items() if v == 4}
        waits -= ankan_tiles
        # in the rare case that this removes all our waits
        #   make it tanki iishanten waiting on every tile
        #   except for ones for which we already have 3 or 4 of
        #   (because we need to replace ankan with a tanki)
        if len(waits) == 0 and len(ankan_tiles) > 0:
            shanten = 1.3
            waits = (TANYAOHAI | YAOCHUUHAI) - {k for k, v in ctr.items() if v >= 3}

    assert all(red not in waits for red in {51,52,53}), f"somehow returned a waits list with red five: {ph(sorted_hand(waits))}"
    timers["total"] += time.time() - start_time
    return round(shanten, 4), sorted_hand(waits)

def calculate_shanten(starting_hand: Iterable[int]) -> Shanten:
    """This just converts the input to a sorted tuple so it can be serialized as a cache key"""
    return _calculate_shanten(tuple(sorted(normalize_red_fives(starting_hand))))
