import functools
import itertools
from .constants import PRED, SUCC, TANYAOHAI, YAOCHUUHAI
from typing import *
from .utils import get_taatsu_wait, get_waits, pt, ph, remove_red_five, remove_red_fives, sorted_hand, try_remove_all_tiles, remove_some, remove_all, fix
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

###
### ukeire and shanten calculations
###

# helpers for removing tiles from hand
make_groups = lambda tile: ((SUCC[SUCC[tile]], SUCC[tile], tile), (tile, tile, tile))
remove_all_groups = lambda hands: functools.reduce(lambda hs, _: remove_all(hs, make_groups), range(4), hands)
remove_some_groups = lambda hands: functools.reduce(lambda hs, _: remove_some(hs, make_groups), range(4), hands)
make_taatsus = lambda tile: ((SUCC[tile], tile), (SUCC[SUCC[tile]], tile))
remove_some_taatsus = lambda hands: fix(lambda hs: remove_some(hs, make_taatsus), hands)
remove_all_taatsus = lambda hands: fix(lambda hs: remove_all(hs, make_taatsus), hands)
make_pairs = lambda tile: ((tile, tile),)
remove_some_pairs = lambda hands: fix(lambda hs: remove_some(hs, make_pairs), hands)
remove_all_pairs = lambda hands: fix(lambda hs: remove_all(hs, make_pairs), hands)

# note: ctr = Counter(remove_red_fives(starting_hand))
# passed in so you only have to construct it once
def calculate_chiitoitsu_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get chiitoitsu waits (iishanten or tenpai) and label iishanten type
    shanten = 6 - len([v for v in ctr.values() if v > 1])
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        # since chiitoitsu can't repeat pairs, take only the single tiles in hand
        waits = sorted_hand(k for k, v in ctr.items() if v == 1)
    return shanten, list(waits)

def calculate_kokushi_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get kokushi waits (iishanten or tenpai) and label iishanten type
    has_pair = len([v for v in ctr.values() if v > 1]) >= 1
    shanten = (12 if has_pair else 13) - len(YAOCHUUHAI.intersection(starting_hand))
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        waits = sorted_hand(YAOCHUUHAI if not has_pair else YAOCHUUHAI.difference(starting_hand))
    return shanten, list(waits)



















count_floating = lambda hand: len(next(iter(remove_all_pairs(remove_all_taatsus({hand})))))

def get_floating_waits(hands: Set[Tuple[int, ...]], floating_tiles: Set[int]) -> Set[int]:
    # For each hand in hands, calculate its waits:
    # - remove every combination of one pair and one floating tile
    # - if the result is composed of taatsus, add the wait of every taatsu
    # - if 2+ distinct pairs were able to add waits, add those pairs as a shanpon wait
    # Return the combined wait of every hand in hands
    waits: Set[int] = set()
    for hand in hands:
        hand = tuple(remove_red_fives(hand))
        floating, *more = next(iter(remove_all_pairs(remove_all_taatsus({hand}))))
        if len(more) != 0:
            continue

        pairs = set()
        for tile in (tile for tile, count in Counter(hand).items() if count >= 2):
            nopair = try_remove_all_tiles(hand, (tile, tile))
            for floating in floating_tiles & set(nopair):
                nofloat = try_remove_all_tiles(nopair, (floating,))
                if count_floating(nofloat) == 0: # all taatsu still intact
                    pairs.add(tile)
                    waits |= get_waits(nofloat)
        if len(pairs) >= 2:
            waits |= pairs
    return waits

def check_headless_perfect_iishanten(starting_hand: Tuple[int, ...]) -> bool:
    # check for headless perfect iishanten, given a headless iishanten hand
    #   only true if _both_ headless shapes are ryanmen and _both_ overlap with a group
    #   such that a pair+ryanmen can be formed by dropping one side of the ryanmen
    # e.g. 234 34 -> drop 3 -> 2344
    # e.g. 234 45 -> drop 5 -> 2344
    # e.g. 34 444 -> drop 4 -> 3444
    # e.g. 34 555 -> drop 3 -> 4555 
    # there are 8 possible shapes (the above 4 plus their reverse versions)
    # exclude shapes that result in penchan!
    # these are: 12233, 12222, 11112, 77889, 88889, 89999 (so there's 6 for each suit)
    penchan_shapes = {(11,12,12,13,13),(11,12,12,12,12),(11,11,11,11,12),(17,17,18,18,19),(18,18,18,18,19),(18,19,19,19,19),
                      (21,22,22,23,23),(21,22,22,22,22),(21,21,21,21,22),(27,27,28,28,29),(28,28,28,28,29),(28,29,29,29,29),
                      (31,32,32,33,33),(31,32,32,32,32),(31,31,31,31,32),(37,37,38,38,39),(38,38,38,38,39),(38,39,39,39,39)}
    to_flexible_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t4:=SUCC[t3],
       tuple({(t1,t2,t2,t3,t4), (t2,t2,t3,t3,t4), (t1,t2,t2,t3,t3), (t1,t2,t3,t3,t4),
              (t1,t2,t3,t3,t3), (t1,t2,t2,t2,t2), (t1,t1,t1,t1,t2), (t1,t1,t1,t2,t3)} - penchan_shapes))[-1]
    flexible_shapes = set().union(*map(to_flexible_shapes, starting_hand))
    possible_shapes = remove_some_pairs(remove_some_taatsus(remove_some_groups({starting_hand})))
    return len(flexible_shapes & possible_shapes) >= 2 # both headless shapes are these flexible shapes

def check_complete_perfect_iishanten(starting_hand):
    # given a complete iishanten hand,
    # if we can take out two ryanmen shapes then it's a perfect iishanten
    # otherwise, it's imperfect iishanten
    make_ryanmen = lambda tile: ((SUCC[tile], tile),) if tile not in {11,18,21,28,31,38} else ((),)
    remove_all_ryanmen = lambda hands: fix(lambda hs: remove_all(hs, make_ryanmen), hands)
    return len(next(iter(remove_all_ryanmen(remove_all_groups({starting_hand}))))) == 3

def get_iishanten_waits(starting_hand: Tuple[int, ...], groups_needed: int) -> Tuple[float, Set[int]]:
    shanten = 1.0
    waits = set()

    def sequence_exists(seq):
        # check if, after removing the sequence, we still have headless/kutsuki iishanten
        removed_sequence = try_remove_all_tiles(starting_hand, seq)
        if len(removed_sequence) < len(starting_hand):
            return count_floating(next(iter(remove_all_groups({removed_sequence})))) <= 19
        return False

    def extend_waits(waits):
        # look for a sequence in either direction of each wait
        # 5 -> look for 345, 567
        # extend the wait if such a sequence exists
        # 5 -> add 2, 8
        for tile in waits.copy():
            if PRED[PRED[PRED[tile]]] != 0 and PRED[PRED[PRED[tile]]] not in waits and sequence_exists((PRED[PRED[tile]], PRED[tile], tile)):
                # print(f"  extended {pt(tile)} left to {pt(PRED[PRED[PRED[tile]]])}")
                waits.add(PRED[PRED[PRED[tile]]])
            if SUCC[SUCC[SUCC[tile]]] != 0 and SUCC[SUCC[SUCC[tile]]] not in waits and sequence_exists((SUCC[SUCC[tile]], SUCC[tile], tile)):
                # print(f"  extended {pt(tile)} right to {pt(SUCC[SUCC[SUCC[tile]]])}")
                waits.add(SUCC[SUCC[SUCC[tile]]])
        return waits

    # first handle kutsuki and headless iishanten
    if groups_needed == 1:
        # kutsuki:
        # we know it's kutsuki iishanten if, after removing all the taatsus, we are left with a pair + two floating tiles
        # 
        # headless:
        # if after removing all the taatsus we're left with only zero or two floating tiles, it's headless
        
        kutsuki_iishanten_tiles: Set[int] = set()
        kutsuki_pairs: Set[Tuple[int, ...]] = set()
        headless_iishanten_tiles: Set[int] = set()
        for hand in remove_some_taatsus(remove_all_groups({starting_hand})):
            pairless = next(iter(remove_all_pairs({hand})))
            if len(pairless) == 2 and len(pairless) != len(hand):
                # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten on {ph(pairless)}")
                kutsuki_iishanten_tiles |= set(pairless)
                kutsuki_pairs.add(try_remove_all_tiles(hand, pairless))
            else:
                # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten on {ph(hand)}")
                headless_iishanten_tiles |= set(hand)
        if len(kutsuki_iishanten_tiles) > 0:
            shanten += 0.01
            for tile in kutsuki_iishanten_tiles:
                kutsuki_waits = {PRED[PRED[tile]], PRED[tile], remove_red_five(tile), SUCC[tile], SUCC[SUCC[tile]]} - {0}
                waits |= kutsuki_waits
                waits = fix(extend_waits, waits)

            # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten with tiles {ph(kutsuki_iishanten_tiles)}, waits {ph(waits)}")
        if len(headless_iishanten_tiles) > 0:
            shanten += 0.001
            floating_tiles = set(next(iter(remove_all_taatsus({tuple(headless_iishanten_tiles)}))))
            if len(floating_tiles) == 0: # headless with two taatsu
                headless_waits = get_waits(tuple(headless_iishanten_tiles)).union(headless_iishanten_tiles)
            else: # headless with one taatsu and two floating tiles
                headless_waits = get_waits(tuple(headless_iishanten_tiles - floating_tiles)).union(floating_tiles)
            # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten with tiles {ph(headless_iishanten_tiles)}, waits {ph(headless_waits)}")
            waits |= headless_waits
            waits = fix(extend_waits, waits)

    # handle floating/complete iishanten
    # floating iishanten is when you have a floating tile + a pair + 2 taatsus/pairs
    # complete iishanten is when that floating tile forms a complex group with either of the 2 taatsus/pairs

    # length 7 hands are waiting to form 2 groups and a pair
    # remove groups until you have length 7 subhands, then remove a pair
    # this should give you all your waits
    subhands = set(filter(lambda hand: len(hand) == 7, remove_some_groups({starting_hand})))
    without_head = set(filter(lambda hand: len(hand) == 5, remove_some_pairs(subhands))) # remove a pair
    floating_iishanten_tiles = set().union(*filter(lambda hand: len(hand) == 1, remove_some_pairs(remove_some_taatsus(without_head))))

    # floating_subhands = set()
    # without_floating = remove_all(subhands, lambda _: tuple((tile,) for tile in floating_iishanten_tiles))
    # floating_subhands |= set(filter(lambda hand: count_floating(hand) == 0, without_floating))
    floating_waits = get_floating_waits(subhands, floating_iishanten_tiles) if len(floating_iishanten_tiles) > 0 else set()
    # get waits for complete iishanten
    # look for a complex group after removing a pair and a taatsu/pair
    complex_candidates = set(filter(lambda hand: len(hand) == 3, remove_some_pairs(remove_some_taatsus(without_head)))) # remove a taatsu/pair
    to_complex_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t5:=SUCC[SUCC[t3]], ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
    complete_iishanten_shapes = complex_candidates & {shape for hand in complex_candidates for shape in to_complex_shapes(hand[0])}
    is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
    get_complex_wait = lambda s: get_taatsu_wait(s[0:2]) | get_taatsu_wait(s[1:3]) | ({s[0]} if is_pair(s[0:2]) else set()) | ({s[1]} if is_pair(s[1:3]) else set())
    complete_waits = floating_waits.union(*map(get_complex_wait, complete_iishanten_shapes)) if len(complete_iishanten_shapes) > 0 else set()
    if shanten >= 1.001: # either kutsuki (1.01) or headless (1.001) or both (1.011)
        if check_headless_perfect_iishanten(starting_hand):
            # print(f"{ph(sorted_hand(starting_hand))} is also perfect {'kutsuki' if shanten >= 1.01 else 'headless'} with shapes {flexible_shapes}")
            shanten += 0.0003
        if len(complete_waits - waits) > 0: # check for complete iishanten
            # print(f"{ph(sorted_hand(starting_hand))} is {'kutsuki' if shanten >= 1.01 else 'headless'} complete iishanten with complex shapes {list(map(ph, complete_iishanten_shapes))}, adding extra waits {ph(complete_waits - waits)}")
            shanten += 0.0002
            waits |= complete_waits
        if len(floating_waits - waits) > 0: # check for floating iishanten
            # print(f"{ph(sorted_hand(starting_hand))} is {'kutsuki' if shanten >= 1.01 else 'headless'} floating iishanten with floating tiles {ph(floating_iishanten_tiles)}, adding extra waits {ph(floating_waits - waits)}")
            shanten += 0.0001
            waits |= floating_waits
    else:
        if len(complete_waits - waits) > 0:
            # print(f"{ph(sorted_hand(starting_hand))} is complete iishanten, with complex shapes {list(map(ph, complete_iishanten_shapes))}")
            shanten += 0.0003 if check_complete_perfect_iishanten(starting_hand) else 0.0002
            waits |= complete_waits
        if len(floating_waits - waits) > 0:
            # print(f"{ph(sorted_hand(starting_hand))} is floating tile iishanten, with floating tile(s) {ph(floating_iishanten_tiles)}")
            shanten += 0.0001 # floating
            waits |= floating_waits
    return round(shanten, 4), waits































@functools.cache
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Tuple[float, List[int]]:
    """
    Return the shanten of the hand plus its waits (if tenpai or iishanten).
    If the shanten is 2+, the waits returned are an empty list.
    If iishanten, the returned shanten is 1.XXXX, based on the type of iishanten.
    - 1.2000: kokushi musou iishanten
    - 1.1000 chiitoitsu iishanten
    - 1.0100 kutsuki iishanten
    - 1.0010 headless iishanten
    - 1.0001 floating iishanten
    - 1.0002 imperfect (complete) iishanten
    - 1.0003 perfect iishanten
    One hand could have multiple iishanten types contributing to the overall wait.
    Combining the above is how we describe those kinds of hands:
    - 1.0110 kutsuki headless iishanten
    - 1.1100 chiitoi kutsuki iishanten
    - 1.0101 kutsuki floating iishanten
    and so on.
    """
    assert len(starting_hand) in {1, 4, 7, 10, 13}, f"calculate_shanten() was passed a {len(starting_hand)} tile hand: {ph(starting_hand)}"
    # 1. Remove all groups
    # 2. Count floating tiles
    # 3. Calculate shanten
    # 4. Check for iishanten/tenpai
    # 5. If iishanten or tenpai, output the waits
    # 6. Do 3-5 for chiitoitsu and kokushi

    # remove as many groups as possible
    hands = remove_all_groups({starting_hand})
    groups_needed = (len(next(iter(hands))) - 1) // 3

    # calculate shanten for every combination of groups removed
    @functools.cache
    def get_hand_shanten(hand: Tuple[int, ...]) -> float:
        num_pairs = len(starting_hand) - len(hand)
        """Return the shanten of a hand with all of its groups, ryanmens, and kanchans removed"""
        floating_tiles = next(iter(remove_all_pairs({hand})))
        # needs_pair = 1 if the hand is missing a pair but is full of taatsus -- need to convert a taatsu to a pair
        # must_discard_taatsu = 1 if the hand is 6+ blocks -- one of the taatsu is actually 2 floating tiles
        # shanten = (3 + num_floating - num_groups) // 2, plus the above
        needs_pair = 1 if len(floating_tiles) == len(hand) and groups_needed > len(floating_tiles) else 0
        must_discard_taatsu = 1 if groups_needed >= 3 and len(floating_tiles) <= 1 else 0
        return needs_pair + must_discard_taatsu + (groups_needed + len(floating_tiles) - 1) // 2
    shanten: float = min(map(get_hand_shanten, remove_some_taatsus(hands)))
    assert shanten >= 0, f"somehow calculated negative shanten for {ph(sorted_hand(starting_hand))}"

    # if iishanten, get the type of iishanten based on tiles remaining after removing some number of taatsus
    # then do some ad-hoc processing to get its waits
    waits: Set[int] = set()
    if shanten == 1:
        assert groups_needed in {1,2}, f"{ph(sorted_hand(starting_hand))} is somehow iishanten with {4-groups_needed} groups"
        shanten, waits = get_iishanten_waits(starting_hand, groups_needed)
        assert shanten != 1, f"somehow failed to detect type of iishanten for iishanten hand {ph(sorted_hand(starting_hand))}"

    # if tenpai, get the waits
    elif shanten == 0:
        waits = get_tenpai_waits(starting_hand)
        assert len(waits) > 0, f"tenpai hand {ph(sorted_hand(starting_hand))} has no waits?"

    # compare with chiitoitsu and kokushi shanten
    ctr = Counter(remove_red_fives(starting_hand))
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
        shanten = 1.0001
        waits = (TANYAOHAI | YAOCHUUHAI) - ankan_tiles

    waits_list = list(sorted_hand(waits - ankan_tiles))
    assert all(red not in waits_list for red in {51,52,53}), f"somehow returned a waits list with red five: {ph(waits_list)}"
    return round(shanten, 4), waits_list

@functools.cache
def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    hand_copy = tuple(remove_red_fives(hand))
    possible_winning_tiles = {t for tile in hand_copy for t in (PRED[tile], tile, SUCC[tile])} - {0}
    is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
    makes_winning_hand = lambda tile: any(map(is_pair, remove_all_groups({(*hand_copy, tile)})))
    return set(filter(makes_winning_hand, possible_winning_tiles))

def calculate_shanten(starting_hand: Iterable[int]) -> Tuple[float, List[int]]:
    """This just converts the input to a sorted tuple so it can be serialized as a cache key"""
    return _calculate_shanten(tuple(sorted(remove_red_fives(starting_hand))))
