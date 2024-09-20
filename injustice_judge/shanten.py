import functools
import itertools
from .classes import Interpretation
from .constants import Shanten, PRED, SUCC, TANYAOHAI, YAOCHUUHAI
from .display import ph, pt
from .utils import extract_groups, get_taatsu_wait, get_waits, get_waits_taatsus, normalize_red_five, normalize_red_fives, sorted_hand, to_sequence, try_remove_all_tiles

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
    "get_iishanten_type": 0.0,
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
        set.union(*(remove(s) for s in suits[0])),
        set.union(*(remove(s) for s in suits[1])),
        set.union(*(remove(s) for s in suits[2])),
        suits[3] if multiples_to_check == 0 else set.union(*(remove(s, do_sequences=False) for s in suits[3]))
    )

to_sequences = lambda tile: ((tile+2, tile+1, tile),)
to_taatsus = lambda tile: ((tile+2, tile), (tile+1, tile),)
eliminate_some_groups  = lambda suits: eliminate_from_suits(suits, True,  to_sequences, 3)
eliminate_some_taatsus = lambda suits: eliminate_from_suits(suits, True,  to_taatsus)
eliminate_all_groups   = lambda suits: eliminate_from_suits(suits, False, to_sequences, 3)
eliminate_all_taatsus  = lambda suits: eliminate_from_suits(suits, False, to_taatsus)

def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    """Given a tenpai hand, get all its waits"""
    return {wait for i in Interpretation(hand).generate_all_interpretations() for wait in i.get_waits()}

def get_hand_shanten(suits: Suits, groups_needed: int) -> float:
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
                if not recursed:
                    add_complex_shape(remaining_hand, recursed=True)
                    add_pair_shape(remaining_hand, recursed=True)

def get_iishanten_type(starting_hand: Tuple[int, ...], groupless_hands: Suits, groups_needed: int) -> Tuple[float, Set[int], Dict[str, Any]]:
    # given an iishanten hand, calculate the iishanten type and its waits
    # we'll always return 1.XXX shanten, where XXX represents the type of iishanten
    # - 1.300 tanki iishanten (tanki tenpai, but you have all 4 tiles in hand)
    # - 1.200 kokushi musou iishanten
    # - 1.100 chiitoitsu iishanten
    # - 1.010 headless iishanten (you have three groups and two taatsus, no pair)
    # - 1.020 kuttsuki iishanten (you have three groups and a pair and two floating tiles)
    # - 1.030 kuttsuki headless iishanten (your hand can be interpreted as both of the above)
    # - 1.001 floating iishanten (you have two groups and a pair and two taatsus)
    # - 1.002 imperfect (complete) iishanten (same, but one taatsu has a second pair like 334)
    # - 1.003 perfect iishanten (same, but both taatsus are ryanmen)
    # One hand could have multiple iishanten types contributing to the overall wait.
    # Combining the above is how we describe those kinds of hands:
    # - 1.120 chiitoi kuttsuki iishanten
    # - 1.021 kuttsuki floating iishanten
    # - 1.121 chiitoi kuttsuki floating iishanten
    shanten = 1.0
    waits: Set[int] = set()
    debug_info: Dict[str, Any] = {}

    assert groups_needed in {1, 2}, "get_iishanten_type was not passed an iishanten hand"

    # one group needed = kuttsuki or headless iishanten hand
    # since we assume the input is an iishanten hand, we just remove some taatsus
    # if what's remaining contains a pair and two other tiles, then it's kuttsuki iishanten
    # if what's remaining contains no pair, then it's headless iishanten
    # there can be multiple results after removing all the groups,
    #   so it's possible a given hand can have both kuttsuki waits and headless waits
    if groups_needed == 1:
        kuttsuki_iishanten_tiles: Set[int] = set() # tiles that could be the floating kuttsuki tiles in hand
        headless_iishanten_tiles: Set[int] = set() # tiles that could be part of the 4 headless tiles in hand
        tatsuuless_hands = eliminate_some_taatsus(groupless_hands)
        # the resulting hands should have 2 or 4 total tiles total
        # if any of the suits contains a pair, then every tile in all other suits are possible kutsuki tiles
        # otherwise it's pairless and all tiles are headless iishanten tiles
        pair_always_exists = False
        for i, suit in enumerate(tatsuuless_hands):
            has_pair = False
            has_non_pair = False
            for hand in suit:
                ctr = Counter(hand)
                if 2 in ctr.values(): # there's a pair in this suit
                    # grab the non-pair tiles in this suit
                    kuttsuki_iishanten_tiles |= {(10*(i+1))+tile for tile, cnt in ctr.items() if cnt == 1}
                    # grab every tile in every other suit
                    kuttsuki_iishanten_tiles |= {(10*(j+1))+tile for j, s in enumerate(tatsuuless_hands) if i != j for hand in s for tile in hand}
                    # grab every non-pair tile in this suit
                    headless_iishanten_tiles |= {(10*(i+1))+tile for tile in hand if ctr[tile] < 2}
                    has_pair = True
                else:
                    # grab every tile in this suit
                    headless_iishanten_tiles |= {(10*(i+1))+tile for tile in hand}
                    has_non_pair = True
            if has_pair and not has_non_pair:
                pair_always_exists = True
        if pair_always_exists:
            headless_iishanten_tiles = set()
        # if there's kuttsuki tiles, then it's kuttsuki iishanten
        if len(kuttsuki_iishanten_tiles) > 0:
            shanten += 0.02
            # for each kuttsuki tile, its waits are {tile-2,tile-1,tile,tile+1,tile+2}
            for tile in kuttsuki_iishanten_tiles:
                waits |= {PRED[PRED[tile]], PRED[tile], tile, SUCC[tile], SUCC[SUCC[tile]]} - {0}
        debug_info["kuttsuki_waits"] = waits.copy()
        debug_info["kuttsuki_tiles"] = kuttsuki_iishanten_tiles
        debug_info["headless_tiles"] = headless_iishanten_tiles
        # if there's headless tiles, then it's headless iishanten
        if len(headless_iishanten_tiles) > 0:
            shanten += 0.01
            # there's two kinds of headless: either you have two taatsus,
            #   or one taatsu + two floating tiles
            # the taatsu waits always contribute to the wait
            # the floating tiles are always tanki waits
            # when you have two taatsus, either can be treated as two floating tiles,
            #   so all four of the taatsu tiles are tanki waits
            headless_iishanten_tiles_list = sorted(list(headless_iishanten_tiles))
            taatsus = set()
            floating_tiles = set()
            added_as_taatsu = [False] * len(headless_iishanten_tiles)
            tiles = [0, *headless_iishanten_tiles_list, 0]
            for i, (l, t1, t2, r) in enumerate(zip(tiles[:-3], tiles[1:-2], tiles[2:-1], tiles[3:])):
                is_ryanmen = t2 == SUCC[t1]
                is_kanchan = t2 == SUCC[SUCC[t1]]
                # we ignore kanchans if there is a ryanmen on either side that would provide the same wait
                ignore_kanchan = t1 == SUCC[l] or r == SUCC[t2]
                if is_ryanmen or (not ignore_kanchan and is_kanchan):
                    taatsus.add((t1, t2))
                    added_as_taatsu[i] = True
                    added_as_taatsu[i+1] = True
            for in_taatsu, tile in zip(added_as_taatsu, headless_iishanten_tiles_list):
                if not in_taatsu:
                    floating_tiles.add(tile)
            headless_taatsu_waits = {wait for taatsu in taatsus for wait in get_taatsu_wait(taatsu)}
            headless_tanki_waits = headless_iishanten_tiles if len(taatsus) >= 2 else floating_tiles
            waits |= headless_taatsu_waits | headless_tanki_waits
            debug_info["headless_taatsus"] = taatsus
            debug_info["headless_floating_tiles"] = floating_tiles
            debug_info["headless_taatsu_waits"] = headless_taatsu_waits
            debug_info["headless_tanki_waits"] = headless_tanki_waits
    is_headless_or_kutsuki = shanten > 1

    # now we check for complete and floating iishanten
    # floating iishanten is when you have a floating tile + a pair + 2 taatsus/pairs
    # complete iishanten is when that floating tile forms a complex group with either of the 2 taatsus/pairs

    min_length = max_length = 7
    suits: Suits = eliminate_some_groups(to_suits(starting_hand))

    global pair_shapes
    global complex_shapes
    pair_hands: Suits = (set(()),set(()),set(()),set(()))
    complex_hands: Suits = (set(()),set(()),set(()),set(()))

    debug_info["complex_hands"] = []
    debug_info["floating_hands"] = []

    # first identify every single pair and complex group in all suits
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

    complete_waits = set()
    is_perfect_iishanten = False
    def add_complex_hand(complex_shape: Tuple[int, ...], pair_shape: Tuple[int, ...], other_tiles: Tuple[int, ...]) -> None:
        # populate complete_waits with all possible complex waits arising from this breakdown of the hand
        nonlocal complete_waits
        nonlocal is_perfect_iishanten
        nonlocal debug_info
        is_pair = lambda h: len(h) == 2 and h[0] == h[1]
        is_ryanmen = lambda h: len(h) == 2 and SUCC[h[0]] == h[1] and h[0] not in {11,18,21,28,31,38}
        h = (*complex_shape, *pair_shape, *other_tiles)
        # extra tiles must form a taatsu
        if len(other_tiles) != 2:
            return
        simple_wait = get_taatsu_wait(other_tiles)
        if not (is_pair(other_tiles) or len(simple_wait) > 0):
            return
        t1, t2 = complex_shape[0:2], complex_shape[1:3]
        if is_ryanmen(other_tiles) and (is_ryanmen(t1) or is_ryanmen(t2)):
            is_perfect_iishanten = True
        complex_waits = get_taatsu_wait(t1) | get_taatsu_wait(t2)
        complex_waits |= ({t1[0], pair_shape[0]} if is_pair(t1) else set())
        complex_waits |= ({t2[0], pair_shape[0]} if is_pair(t2) else set())

        # calculate wait extensions
        sequences, triplets = extract_groups(try_remove_all_tiles(starting_hand, h))
        # only sequence extensions apply
        left_extensions = set(PRED[PRED[PRED[tile]]] for tile in simple_wait | complex_waits if to_sequence(PRED[PRED[tile]]) in sequences)
        left_extensions |= set(PRED[PRED[PRED[tile]]] for tile in left_extensions if to_sequence(PRED[PRED[tile]]) in sequences)
        right_extensions = set(SUCC[SUCC[SUCC[tile]]] for tile in simple_wait | complex_waits if to_sequence(tile) in sequences)
        right_extensions |= set(SUCC[SUCC[SUCC[tile]]] for tile in right_extensions if to_sequence(tile) in sequences)
        complete_waits |= simple_wait | complex_waits | left_extensions | right_extensions
        debug_info["complex_hands"].append({
            "pair": pair_shape,
            "complex_shape": complex_shape,
            "simple_shape": other_tiles,
            "simple_wait": simple_wait,
            "complex_waits": complex_waits,
            "left_extensions": left_extensions,
            "right_extensions": right_extensions,
        })

    floating_waits = set()
    def add_floating_hand(pair_shape: Tuple[int, ...], other_tiles: Tuple[int, ...]) -> None:
        # populate floating_waits with all possible floating waits arising from this breakdown of the hand
        nonlocal floating_waits
        nonlocal debug_info
        h = (*pair_shape, *other_tiles)
        assert len(other_tiles) == 5
        taatsu_waits, taatsus = get_waits_taatsus(other_tiles)
        # shanpon waits are all pairs in the hand where removing it doesn't leave you with 3 floating tiles
        shanpon_waits = set()
        for i, tile in enumerate(other_tiles[:-1]):
            if other_tiles[i+1] == tile: # pair
                t1,t2,t3 = (*other_tiles[:i],*other_tiles[i+2:])
                if t2 in (t1,SUCC[t1],SUCC[SUCC[t1]]) or t3 in (t2,SUCC[t2],SUCC[SUCC[t2]]):
                    shanpon_waits |= {tile, pair_shape[0]}
                    taatsus.add((tile, tile))

        # calculate wait extensions
        sequences, triplets = extract_groups(try_remove_all_tiles(starting_hand, h))
        # only sequence extensions apply
        left_extensions = set(PRED[PRED[PRED[tile]]] for tile in taatsu_waits | shanpon_waits if to_sequence(PRED[PRED[tile]]) in sequences)
        left_extensions |= set(PRED[PRED[PRED[tile]]] for tile in left_extensions if to_sequence(PRED[PRED[tile]]) in sequences)
        right_extensions = set(SUCC[SUCC[SUCC[tile]]] for tile in taatsu_waits | shanpon_waits if to_sequence(tile) in sequences)
        right_extensions |= set(SUCC[SUCC[SUCC[tile]]] for tile in right_extensions if to_sequence(tile) in sequences)
        floating_waits |= taatsu_waits | shanpon_waits | left_extensions | right_extensions
        debug_info["floating_hands"].append({
            "pair": pair_shape,
            "simple_shapes": taatsus,
            "simple_taatsu_waits": taatsu_waits,
            "simple_shanpon_waits": shanpon_waits,
            "left_extensions": left_extensions,
            "right_extensions": right_extensions,
        })

    def get_other_tiles(hand1: Tuple[int, ...], i: int,
                        hand2: Tuple[int, ...], j: int) -> Iterator[Tuple[int, ...]]:
        # get all combinations of tiles from all other suits
        # such that adding them to (*hand, *hand2) makes it length 7
        # i is the suit for hand1, j is the suit for hand2
        return ((*(tuple(10+tile for tile in a) if 0 not in (i,j) else ()),
                 *(tuple(20+tile for tile in b) if 1 not in (i,j) else ()),
                 *(tuple(30+tile for tile in c) if 2 not in (i,j) else ()),
                 *(tuple(40+tile for tile in d) if 3 not in (i,j) else ()))
                for a in ({hand1} if i == 0 else {hand2} if j == 0 else suits[0])
                for b in ({hand1} if i == 1 else {hand2} if j == 1 else suits[1])
                for c in ({hand1} if i == 2 else {hand2} if j == 2 else suits[2])
                for d in ({hand1} if i == 3 else {hand2} if j == 3 else suits[3])
                if len(a)+len(b)+len(c)+len(d) == 7)

    # populate complex_waits and floating_waits by constructing all possible such hands
    # add_floating_hand just requires any hand with a pair
    # add_complex_hand requires both a pair and a complex group
    for i, suit in enumerate(pair_hands):
        add_i = lambda h: tuple(10*(i+1)+tile for tile in h)
        for pair_hand in suit:
            for pair_shape, remaining in pair_shapes[pair_hand]:
                contains_complex_shape = i != 3 and len(complex_shapes.get(remaining, set())) > 0
                # for all possible length 7 hands containing the pair,
                for other_tiles in get_other_tiles(pair_hand, i, (), -1):
                    # add this hand as a floating hand
                    add_floating_hand(add_i(pair_shape), tuple(sorted((*add_i(remaining), *other_tiles))))
                    # add this hand as a complex hand, if there's a complex shape
                    if contains_complex_shape:
                        for complex_shape, remaining2 in complex_shapes[remaining]:
                            add_complex_hand(add_i(complex_shape), add_i(pair_shape), tuple(sorted((*other_tiles, *add_i(remaining2)))))
                if contains_complex_shape:
                    continue
                # look for a candidate complex shape in some other suit
                for j, suit in enumerate(complex_hands[:3]):
                    if i == j:
                        continue
                    add_j = lambda h: tuple(10*(j+1)+tile for tile in h)
                    for complex_hand in suit:
                        for complex_shape, remaining2 in complex_shapes[complex_hand]:
                            # for all possible length 7 hands containing both the pair and complex hand,
                            for other_tiles in get_other_tiles(pair_hand, i, complex_hand, j):
                                # add this hand as a complex hand
                                add_complex_hand(add_j(complex_shape), add_i(pair_shape), tuple(sorted((*other_tiles, *add_i(remaining), *add_j(remaining2)))))

    debug_info["complete_waits"] = complete_waits
    debug_info["floating_waits"] = floating_waits

    shanten += 0.003 if is_perfect_iishanten and not is_headless_or_kutsuki else \
               0.002 if len(complete_waits - waits) > 0 else \
               0.001 if len(floating_waits - waits) > 0 else 0
    waits |= complete_waits | floating_waits
    return round(shanten, 3), waits, debug_info

@functools.lru_cache(maxsize=65536)
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Shanten:
    """
    Return the shanten of the hand, plus its waits (if tenpai or iishanten).
    If the shanten is 2+, the waits returned are an empty list.
    If iishanten, the returned shanten is 1.XXX, based on the type of iishanten.
    (See get_iishanten_type for details.)
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
    shanten: float = get_hand_shanten(removed_taatsus, groups_needed)
    timers["get_hand_shanten"] += time.time() - now
    assert shanten >= 0, f"somehow calculated negative shanten for {ph(sorted_hand(starting_hand))}"

    # if iishanten, get the type of iishanten based on tiles remaining after removing some number of taatsus
    # then do some ad-hoc processing to get its waits
    waits: Set[int] = set()
    if shanten == 1:
        assert groups_needed in {1,2}, f"{ph(sorted_hand(starting_hand))} is somehow iishanten with {4-groups_needed} groups"
        now = time.time()
        shanten, waits, _ = get_iishanten_type(starting_hand, groupless_hands, groups_needed)
        timers["get_iishanten_type"] += time.time() - now
        assert shanten != 1, f"somehow failed to detect type of iishanten for iishanten hand {ph(sorted_hand(starting_hand))}"

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
