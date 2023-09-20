import functools
import itertools
from .classes import Interpretation
from .constants import PRED, SUCC, TANYAOHAI, YAOCHUUHAI
from .display import ph, pt
from .utils import get_taatsu_wait, get_waits, normalize_red_five, normalize_red_fives, sorted_hand, try_remove_all_tiles

from typing import *
from pprint import pprint

# This file details a shanten algorithm. It's not super efficient, but the
#   goal is to be able to distinguish different types of iishanten, and to
#   be able to determine the waits for both iishanten and tenpai hands.
#  
# The algorithm basically tries to remove every combination of groups
#   and taatsus to determine the shanten, and then checks for the existence
#   of certain combinations of resulting subhands to determine the iishanten
#   type and the waits.
# 
# See `_calculate_shanten` for more info.

import time
timers = {
    "calculate_hands": 0.0,
    "remove_all_taatsus": 0.0,
    "get_hand_shanten": 0.0,
    "get_iishanten_type": 0.0,
    "get_tenpai_waits": 0.0,
    "total": 0.0,
}

###
### ukeire and shanten calculations
###

# helpers for removing tiles from hand
fix = lambda f, x: next(x for _ in itertools.cycle([None]) if x == (x := f(x)))

Suits = Tuple[Set[Tuple[int, ...]], ...]
Hands = Iterable[Tuple[int, ...]]

def to_suits(hands: Hands) -> Suits:
    # TODO actually it's invalid to have more than one hand in hands
    # if you have 2 hands with 2 differing suits each, the resulting representation will represent 4 hands
    # need to remove this functionality once we get rid of the remove_* functions
    ret: Suits = (set(),set(),set(),set())
    for hand in hands:
        suits: Dict[int, List[int]] = {1:[],2:[],3:[],4:[]}
        for tile in sorted(hand):
            suits[tile//10].append(tile%10)
        ret[0].add(tuple(suits[1]))
        ret[1].add(tuple(suits[2]))
        ret[2].add(tuple(suits[3]))
        ret[3].add(tuple(suits[4]))
    return ret

def from_suits(suits: Suits) -> Iterator[Tuple[int, ...]]:
    return ((*(10+v for v in a), *(20+v for v in b), *(30+v for v in c), *(40+v for v in d))
        for a in suits[0] for b in suits[1] for c in suits[2] for d in suits[3])

def eliminate_groups(suits: Suits, removing_all: bool = False) -> Suits:
    def remove(hand: Tuple[int, ...], do_sequences: bool = True) -> Set[Tuple[int, ...]]:
        max_length = len(hand)
        def rec(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
            nonlocal max_length
            max_length = min(max_length, len(hand))
            candidates = set()
            for i, tile in enumerate(hand):
                if i + 2 < len(hand) and hand[i+2] == hand[i+1] == tile: # triplet
                    candidates.add((*hand[:i],*hand[i+3:]))
                if do_sequences:
                    sequence_removed = try_remove_all_tiles(hand, (tile+2, tile+1, tile))
                    if len(sequence_removed) < len(hand):
                        candidates.add(sequence_removed)
            if len(candidates) > 0:
                return set.union(*map(rec, candidates)) | (set() if removing_all else {hand})
            else:
                return {hand}
        return set(filter(lambda h: len(h) == max_length, rec(hand))) if removing_all else rec(hand)

    return (
        set.union(*(remove(s) for s in suits[0])),
        set.union(*(remove(s) for s in suits[1])),
        set.union(*(remove(s) for s in suits[2])),
        set.union(*(remove(s, do_sequences=False) for s in suits[3]))
    )

def eliminate_taatsus(suits: Suits, removing_all: bool = False) -> Suits:
    def remove(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
        max_length = len(hand)
        def rec(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
            nonlocal max_length
            max_length = min(max_length, len(hand))
            candidates = set()
            for tile in hand:
                kanchan_removed = try_remove_all_tiles(hand, (tile+2, tile))
                if len(kanchan_removed) < len(hand):
                    candidates.add(kanchan_removed)
                ryanmen_removed = try_remove_all_tiles(hand, (tile+1, tile))
                if len(ryanmen_removed) < len(hand):
                    candidates.add(ryanmen_removed)
            if len(candidates) > 0:
                return set.union(*map(rec, candidates)) | (set() if removing_all else {hand})
            else:
                return {hand}
        return set(filter(lambda h: len(h) == max_length, rec(hand))) if removing_all else rec(hand)

    return (
        set().union(*(remove(s) for s in suits[0])),
        set().union(*(remove(s) for s in suits[1])),
        set().union(*(remove(s) for s in suits[2])),
        suits[3]
    )

def eliminate_pairs(suits: Suits, removing_all: bool = False) -> Suits:
    def remove(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
        max_length = len(hand)
        def rec(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
            nonlocal max_length
            max_length = min(max_length, len(hand))
            candidates = set()
            for i, tile in enumerate(hand[:-1]):
                if hand[i+1] == tile: # pair
                    candidates.add((*hand[:i],*hand[i+2:]))
            if len(candidates) > 0:
                return set.union(*map(rec, candidates)) | (set() if removing_all else {hand})
            else:
                return {hand}
        return set(filter(lambda h: len(h) == max_length, rec(hand))) if removing_all else rec(hand)

    return (
        set().union(*(remove(s) for s in suits[0])),
        set().union(*(remove(s) for s in suits[1])),
        set().union(*(remove(s) for s in suits[2])),
        set().union(*(remove(s) for s in suits[3])),
    )

def eliminate_taatsus_pairs(suits: Suits, removing_all: bool = False) -> Suits:
    def remove(hand: Tuple[int, ...], do_taatsus: bool = True) -> Set[Tuple[int, ...]]:
        max_length = len(hand)
        def rec(hand: Tuple[int, ...]) -> Set[Tuple[int, ...]]:
            nonlocal max_length
            max_length = min(max_length, len(hand))
            candidates = set()
            for i, tile in enumerate(hand):
                if i + 1 < len(hand) and hand[i+1] == tile: # pair
                    candidates.add((*hand[:i],*hand[i+2:]))
                if do_taatsus:
                    kanchan_removed = try_remove_all_tiles(hand, (tile+2, tile))
                    if len(kanchan_removed) < len(hand):
                        candidates.add(kanchan_removed)
                    ryanmen_removed = try_remove_all_tiles(hand, (tile+1, tile))
                    if len(ryanmen_removed) < len(hand):
                        candidates.add(ryanmen_removed)
            if len(candidates) > 0:
                return set.union(*map(rec, candidates)) | (set() if removing_all else {hand})
            else:
                return {hand}
        return set(filter(lambda h: len(h) == max_length, rec(hand))) if removing_all else rec(hand)

    return (
        set().union(*(remove(s) for s in suits[0])),
        set().union(*(remove(s) for s in suits[1])),
        set().union(*(remove(s) for s in suits[2])),
        set().union(*(remove(s, do_taatsus=False) for s in suits[3])),
    )

def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    return {wait for i in Interpretation(hand).generate_all_interpretations() for wait in i.get_waits()}

@functools.lru_cache(maxsize=2048)
def count_floating(hand: Tuple[int, ...]) -> int:
    # count number of floating tiles in a given hand
    minimum = len(hand)
    for i, tile in enumerate(hand):
        removed_tile = (*hand[:i], *hand[i+1:])
        for candidate in ((tile,), (SUCC[tile],), (SUCC[SUCC[tile]],)):
            removed = try_remove_all_tiles(removed_tile, candidate)
            if len(removed) < len(removed_tile):
                minimum = min(minimum, count_floating(removed))
    return minimum

def get_hand_shanten(suits: Suits, groups_needed: int) -> float:
    """Return the shanten of a given hand that has all of its groups, ryanmens, and kanchans removed"""
    # get the minimum number of floating tiles in each suit
    floating: Dict[int, int] = {}
    for i, hands in enumerate(suits):
        for hand in hands:
            num_floating = tuple(Counter(hand).values()).count(1)
            if i not in floating:
                floating[i] = num_floating
            else:
                floating[i] = min(floating[i], num_floating)

    # check if we have a pair
    # take the hand(s) with a pair that would add the least additional floating tiles to that suit
    extra_floating = 0
    have_pair = False
    for i, hands in enumerate(suits):
        for hand in hands:
            if any(hand.count(tile) == 2 for tile in hand):
                num_extra_floating = tuple(Counter(hand).values()).count(1) - floating[i]
                if not have_pair:
                    extra_floating = num_extra_floating
                else:
                    extra_floating = min(extra_floating, num_extra_floating)
                have_pair = True
    def get_shanten(total_floating: int, have_pair: bool) -> int:
        # needs_pair = 1 if the hand is missing a pair but is full of taatsus -- need to convert a taatsu to a pair
        # must_discard_taatsu = 1 if the hand is 6+ blocks -- one of the taatsu is actually 2 floating tiles
        # shanten = (3 + num_floating - num_groups) // 2, plus the above
        needs_pair = 1 if not have_pair and groups_needed > total_floating else 0
        must_discard_taatsu = 1 if groups_needed >= 3 and total_floating <= 1 else 0
        shanten = needs_pair + must_discard_taatsu + (groups_needed + total_floating - 1) // 2
        return shanten

    total_floating = sum(floating.values()) + extra_floating
    return min(get_shanten(total_floating, have_pair),
               get_shanten(total_floating - extra_floating, False))  # without the pair

def calculate_chiitoitsu_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get chiitoitsu waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(normalize_red_fives(starting_hand))
    shanten = 6 - len([v for v in ctr.values() if v >= 2])
    if shanten == 0:
        # make it 2-shanten if the last tile is a triplet
        shanten = 6 - len([v for v in ctr.values() if v == 2])
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        # since chiitoitsu can't repeat pairs, take only the single tiles in hand
        waits = sorted_hand(k for k, v in ctr.items() if v == 1)
    return shanten, list(waits)

def calculate_kokushi_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get kokushi waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(normalize_red_fives(starting_hand))
    has_pair = len([v for v in ctr.values() if v > 1]) >= 1
    shanten = (12 if has_pair else 13) - len(YAOCHUUHAI.intersection(starting_hand))
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        waits = sorted_hand(YAOCHUUHAI if not has_pair else YAOCHUUHAI.difference(starting_hand))
    return shanten, list(waits)

# pair_shapes[shape] = [(pair, shape without pair)]
pair_shapes: Dict[Tuple[int, ...], Set[Tuple[Tuple[int, ...], Tuple[int, ...]]]] = {}
# complex_shapes[shape] = [(complex shape, shape without complex shape)]
complex_shapes: Dict[Tuple[int, ...], Set[Tuple[Tuple[int, ...], Tuple[int, ...]]]] = {}

def add_pair_shape(hand: Tuple[int, ...], recursed: bool = False) -> None:
    global pair_shapes
    if hand not in pair_shapes:
        pair_shapes[hand] = set()
        for tile in hand:
            if hand.count(tile) >= 2:
                ix = hand.index(tile)
                pair = hand[ix:ix+2]
                remaining_hand = (*hand[:ix], *hand[ix+2:])
                if hand not in pair_shapes:
                    pair_shapes[hand] = set()
                pair_shapes[hand].add((pair, remaining_hand))
                if not recursed:
                    add_complex_shape(remaining_hand, recursed=True)
                    add_pair_shape(remaining_hand, recursed=True)
def add_complex_shape(hand: Tuple[int, ...], recursed: bool = False) -> None:
    global complex_shapes
    if hand not in complex_shapes:
        complex_shapes[hand] = set()
        for tile in hand[:-2]:
            to_complex_shapes = lambda t1: (t2:=t1+1, t3:=t1+2, t5:=t1+4, ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
            for shape in to_complex_shapes(tile):
                remaining_hand = try_remove_all_tiles(hand, shape)
                if len(remaining_hand) < len(hand):
                    if hand not in complex_shapes:
                        complex_shapes[hand] = set()
                    complex_shapes[hand].add((shape, remaining_hand))
                    if not recursed:
                        add_complex_shape(remaining_hand, recursed=True)
                        add_pair_shape(remaining_hand, recursed=True)

def get_iishanten_type(starting_hand: Tuple[int, ...], groupless_hands: Suits, groups_needed: int) -> Tuple[float, Set[int]]:
    # given an iishanten hand, calculate the iishanten type and its waits
    # we'll always return 1.XXX shanten, where XXX represents the type of iishanten
    # - 1.200 kokushi musou iishanten
    # - 1.100 chiitoitsu iishanten
    # - 1.010 headless iishanten
    # - 1.020 kuttsuki iishanten
    # - 1.030 kuttsuki headless iishanten
    # - 1.001 floating iishanten
    # - 1.002 imperfect (complete) iishanten
    # - 1.003 perfect iishanten
    # One hand could have multiple iishanten types contributing to the overall wait.
    # Combining the above is how we describe those kinds of hands:
    # - 1.120 chiitoi kuttsuki iishanten
    # - 1.021 kuttsuki floating iishanten
    # - 1.121 chiitoi kuttsuki floating iishanten
    shanten = 1.0

    # tanki waits and shanpon waits are the only waits relying on having
    #   the waited tile in hand, which is bad since extend_waits relies on
    #   being able to choose an arbitrary sequence in hand which might
    #   include those tiles necessary for the tanki or shanpon.
    # tanki isn't an issue since whenever we find tanki as part of a sequence
    #   like 4 -> 456, we can always interpret it as a group and move on
    # shanpon is an issue since whenever we find shanpon as part of a sequence
    #   like 44 -> 4456, we can't always extend the shanpon 4 wait to 7
    #   since it's not always true that the 56 can be used as a ryanmen.
    #   example: in the hand 344566m345p1178s, we have a shanpon wait on 6m1s
    #   but the 4566m shape doesn't extend the 6m wait to 3m.
    # so we treat shanpon waits as separate so that we only call extend_waits
    #   on the non-shanpon waits.
    waits: Set[int] = set()
    shanpon_waits: Set[int] = set()

    assert groups_needed in {1, 2}, "get_iishanten_type was not passed an iishanten hand"

    # one group needed = possibility for kuttsuki and headless iishanten
    # since we assume the input is an iishanten hand, we just remove some taatsus
    # if what's remaining contains a pair and two other tiles, then it's kuttsuki iishanten
    # if what's remaining contains no pair, then it's headless iishanten
    # there can be multiple results after removing all the groups,
    #   so it's possible a given hand can have both kuttsuki waits and headless waits

    if groups_needed == 1:
        # get all the kuttsuki tiles and headless tiles
        # e.g. ({(2, 3), (1, 1), ()}, {(8,), (5,)}, {(8,)}, {()})
        # from (11,11,11,12,13,21,22,23,25,26,27,28,38)
        kuttsuki_iishanten_tiles: Set[int] = set() # tiles that could be the floating kuttsuki tiles in hand
        headless_iishanten_tiles: Set[int] = set() # tiles that could be part of the 4 headless tiles in hand
        tatsuuless_hands = eliminate_taatsus(groupless_hands)
        # the resulting hands should have 2 or 4 total tiles total
        # if any of the suits contains a pair, then every tile in all other suits are possible kutsuki tiles
        # otherwise it's pairless and all tiles are headless iishanten tiles
        pair_always_exists = False
        for i, suit in enumerate(tatsuuless_hands):
            has_pair = False
            has_non_pair = False
            for hand in suit:
                ctr = Counter(hand)
                if 2 in ctr.values():
                    kuttsuki_iishanten_tiles |= {(10*(i+1))+tile for tile, cnt in ctr.items() if cnt == 1}
                    kuttsuki_iishanten_tiles |= {(10*(j+1))+tile for j, s in enumerate(tatsuuless_hands) if i != j for hand in s for tile in hand}
                    has_pair = True
                else:
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
            # print(f"{ph(sorted_hand(starting_hand))} is kuttsuki iishanten with tiles {ph(kuttsuki_iishanten_tiles)}, waits {ph(waits)}")

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
            for t1, t2 in zip(headless_iishanten_tiles_list[:-1], headless_iishanten_tiles_list[1:]):
                if t2 in (SUCC[t1], SUCC[SUCC[t1]]):
                    taatsus.add((t1, t2))
            taatsu_tiles: Set[int] = set(tile for taatsu in taatsus for tile in taatsu)
            headless_taatsu_waits = get_waits(tuple(taatsu_tiles))
            headless_tanki_waits = headless_iishanten_tiles.difference(set() if len(taatsus) >= 2 else taatsu_tiles)
            waits |= headless_taatsu_waits | headless_tanki_waits
            # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten with tiles {ph(headless_iishanten_tiles)}, waits {ph(waits)}")


    # now we check for complete and floating iishanten
    # floating iishanten is when you have a floating tile + a pair + 2 taatsus/pairs
    # complete iishanten is when that floating tile forms a complex group with either of the 2 taatsus/pairs

    min_length = max_length = 7
    suits: Suits = eliminate_groups(to_suits((starting_hand,)))

    global pair_shapes
    global complex_shapes
    pair_hands: Suits = (set(()),set(()),set(()),set(()))
    complex_hands: Suits = (set(()),set(()),set(()),set(()))

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
    complete_shanpon_waits = set()
    is_perfect_iishanten = False
    def add_complex_hand(complex_shape, pair_shape, extra_tiles):
        nonlocal complete_waits
        nonlocal complete_shanpon_waits
        nonlocal is_perfect_iishanten
        is_pair = lambda h: len(h) == 2 and h[0] == h[1]
        is_ryanmen = lambda h: len(h) == 2 and SUCC[h[0]] == h[1] and h[0] not in {11,18,21,28,31,38}
        h = (*complex_shape, *pair_shape, *extra_tiles)
        # extra tiles must form a taatsu
        if len(extra_tiles) != 2:
            return
        extra_wait = get_taatsu_wait(extra_tiles)
        if not (is_pair(extra_tiles) or len(extra_wait) > 0):
            return
        complete_waits |= extra_wait
        t1, t2 = complex_shape[0:2], complex_shape[1:3]
        if is_ryanmen(extra_tiles) and (is_ryanmen(t1) or is_ryanmen(t2)):
            is_perfect_iishanten = True
        complete_waits |= get_taatsu_wait(t1) | get_taatsu_wait(t2) | extra_wait
        complete_shanpon_waits |= ({t1[0], pair_shape[0]} if is_pair(t1) else set())
        complete_shanpon_waits |= ({t2[0], pair_shape[0]} if is_pair(t2) else set())

    floating_waits = set()
    floating_shanpon_waits = set()
    def add_floating_hand(pair_shape, extra_tiles):
        nonlocal floating_waits
        nonlocal floating_shanpon_waits
        h = (*pair_shape, *extra_tiles)
        assert len(extra_tiles) == 5
        floating_waits |= get_waits(extra_tiles)
        # shanpon waits are all pairs in the hand where removing it doesn't leave you with 3 floating tiles
        for i, tile in enumerate(extra_tiles[:-1]):
            if extra_tiles[i+1] == tile: # pair
                t1,t2,t3 = (*extra_tiles[:i],*extra_tiles[i+2:])  # type: ignore[misc]
                if t2 in (t1,SUCC[t1],SUCC[SUCC[t1]]) or t3 in (t2,SUCC[t2],SUCC[SUCC[t2]]):
                    floating_shanpon_waits.add(tile)
                    floating_shanpon_waits.add(pair_shape[0])

    for i, suit in enumerate(pair_hands):
        add_i = lambda h: tuple(10*(i+1)+tile for tile in h)
        for hand in suit:
            for shape, remaining in pair_shapes[hand]:
                # get all combinations of extra tiles from other suits
                # such that adding them to our existing hand makes it length 7
                possible_extra_tiles = [tuple(tile for x in (
                    *((tuple(10+tile for tile in a),) if i != 0 else ()),
                    *((tuple(20+tile for tile in b),) if i != 1 else ()),
                    *((tuple(30+tile for tile in c),) if i != 2 else ()),
                    *((tuple(40+tile for tile in d),) if i != 3 else ()),
                    ) for tile in x)
                    for a in ({hand} if i == 0 else suits[0])
                    for b in ({hand} if i == 1 else suits[1])
                    for c in ({hand} if i == 2 else suits[2])
                    for d in ({hand} if i == 3 else suits[3])
                    if len(a)+len(b)+len(c)+len(d) == 7]
                is_also_complex = i != 3 and remaining in complex_shapes and len(complex_shapes[remaining]) > 0
                for extra_tiles in possible_extra_tiles:
                    add_floating_hand(add_i(shape), tuple(sorted((*add_i(remaining), *extra_tiles))))
                    if is_also_complex:
                        # this fragment alone has both a pair and a complex shape
                        for shape2, remaining2 in complex_shapes[remaining]:
                            add_complex_hand(add_i(shape2), add_i(shape), tuple(sorted((*extra_tiles, *add_i(remaining2)))))
                if not is_also_complex:
                    # need to look for a candidate complex shape in some other suit
                    for j, suit in enumerate(complex_hands[:3]):
                        if i == j:
                            continue
                        add_j = lambda h: tuple(10*(j+1)+tile for tile in h)
                        for hand2 in suit:
                            for shape2, remaining2 in complex_shapes[hand2]:
                                possible_extra_tiles = [tuple(tile for x in (
                                    *((tuple(10+tile for tile in a),) if 0 not in (i,j) else ()),
                                    *((tuple(20+tile for tile in b),) if 1 not in (i,j) else ()),
                                    *((tuple(30+tile for tile in c),) if 2 not in (i,j) else ()),
                                    *((tuple(40+tile for tile in d),) if 3 not in (i,j) else ()),
                                    ) for tile in x)
                                    for a in ({hand} if i == 0 else {hand2} if j == 0 else suits[0])
                                    for b in ({hand} if i == 1 else {hand2} if j == 1 else suits[1])
                                    for c in ({hand} if i == 2 else {hand2} if j == 2 else suits[2])
                                    for d in ({hand} if i == 3 else {hand2} if j == 3 else suits[3])
                                    if len(a)+len(b)+len(c)+len(d) == 7]
                                for extra_tiles in possible_extra_tiles:
                                    add_complex_hand(add_j(shape2), add_i(shape), tuple(sorted((*extra_tiles, *add_i(remaining), *add_j(remaining2)))))

    complete_waits |= floating_waits
    complete_shanpon_waits |= floating_shanpon_waits
    if shanten > 1: # it's already headless or kutsuki
        is_perfect_iishanten = False
    if len(complete_waits - waits) > 0 or len(complete_shanpon_waits - shanpon_waits - waits) > 0: # check for complete iishanten
        shanten += 0.003 if is_perfect_iishanten else 0.002
        waits |= complete_waits
        shanpon_waits |= complete_shanpon_waits
    elif len(floating_waits - waits) > 0 or len(floating_shanpon_waits - shanpon_waits - waits) > 0: # check for floating iishanten
        shanten += 0.003 if is_perfect_iishanten else 0.001
        # print(f"{ph(sorted_hand(starting_hand))} is floating iishanten with floating tiles {ph(floating_iishanten_tiles)}, adding extra waits {ph(floating_waits - waits)}")
        waits |= floating_waits
        shanpon_waits |= floating_shanpon_waits
    elif is_perfect_iishanten:
        shanten += 0.003

    # now we extend all the non-shanpon waits
    # extending is when you have a wait 4 and an overlapping sequence 456
    # this extends the 4 wait to a 7 wait
    def extend_waits(waits):
        # look for a sequence in either direction of each wait
        # 5 -> look for 345, 567
        # extend the wait if such a sequence exists
        # 5 -> add 2, 8
        def sequence_exists(seq):
            # check if, after removing the sequence, we still have headless/kuttsuki iishanten
            removed_sequence = try_remove_all_tiles(starting_hand, seq)
            return len(removed_sequence) < len(starting_hand) and count_floating(next(from_suits(eliminate_groups(to_suits((removed_sequence,)), removing_all=True)))) <= 2
        for tile in waits.copy():
            left = PRED[PRED[PRED[tile]]]
            right = SUCC[SUCC[SUCC[tile]]]
            if left != 0 and left not in waits and sequence_exists((PRED[PRED[tile]], PRED[tile], tile)):
                # print(f"  extended {pt(tile)} left to {pt(left)}")
                waits.add(PRED[PRED[PRED[tile]]])
            if right != 0 and right not in waits and sequence_exists((SUCC[SUCC[tile]], SUCC[tile], tile)):
                # print(f"  extended {pt(tile)} right to {pt(right)}")
                waits.add(SUCC[SUCC[SUCC[tile]]])
        return waits
    waits = fix(extend_waits, waits)

    return round(shanten, 3), waits | shanpon_waits

@functools.lru_cache(maxsize=65536)
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Tuple[float, List[int]]:
    """
    Return the shanten of the hand plus its waits (if tenpai or iishanten).
    If the shanten is 2+, the waits returned are an empty list.
    If iishanten, the returned shanten is 1.XXX, based on the type of iishanten.
    (See get_iishanten_type for details.)
    """
    assert len(starting_hand) in {1, 4, 7, 10, 13}, f"calculate_shanten() was passed a {len(starting_hand)} tile hand: {ph(starting_hand)}"
    # 1. Remove all groups
    # 2. Count floating tiles
    # 3. Calculate shanten
    # 4. Check for iishanten/tenpai
    # 5. If iishanten or tenpai, calculate the waits
    # 6. Do 3-5 for chiitoitsu and kokushi

    suits = to_suits((starting_hand,))
    start_time = now = time.time()
    hands = eliminate_groups(suits, removing_all=True)
    hands_set = set(from_suits(hands))
    timers["calculate_hands"] += time.time() - now

    groups_needed = (len(next(iter(hands_set))) - 1) // 3

    # calculate shanten for every combination of groups removed
    now = time.time()
    removed_taatsus = eliminate_taatsus(hands)
    timers["remove_all_taatsus"] += time.time() - now

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
        shanten, waits = get_iishanten_type(starting_hand, hands, groups_needed)
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

    # remove all ankan in hand from the waits
    ankan_tiles = {k for k, v in ctr.items() if v == 4}
    waits -= ankan_tiles
    # in the rare case that this removes all our waits
    #   make it floating iishanten waiting on every tile but that
    #   (because it's a tanki wait on ankan)
    if len(waits) == 0 and len(ankan_tiles) > 0:
        shanten = 1.001
        waits = (TANYAOHAI | YAOCHUUHAI) - ankan_tiles

    waits_list = list(sorted_hand(waits - ankan_tiles))
    assert all(red not in waits_list for red in {51,52,53}), f"somehow returned a waits list with red five: {ph(waits_list)}"
    timers["total"] += time.time() - start_time
    return round(shanten, 4), waits_list

# import time
# shanten_runtime = 0.0
def calculate_shanten(starting_hand: Iterable[int]) -> Tuple[float, List[int]]:
    """This just converts the input to a sorted tuple so it can be serialized as a cache key"""
    # global shanten_runtime
    processed = tuple(sorted(normalize_red_fives(starting_hand)))
    # now = time.time()
    ret = _calculate_shanten(processed)
    # shanten_runtime += time.time() - now
    return ret
