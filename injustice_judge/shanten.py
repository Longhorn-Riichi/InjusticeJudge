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
count_floating = lambda hand: len(next(iter(remove_all_pairs(remove_all_taatsus({hand})))))

def calculate_chiitoitsu_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get chiitoitsu waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(remove_red_fives(starting_hand))
    shanten = 6 - len([v for v in ctr.values() if v > 1])
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        # since chiitoitsu can't repeat pairs, take only the single tiles in hand
        waits = sorted_hand(k for k, v in ctr.items() if v == 1)
    return shanten, list(waits)

def calculate_kokushi_shanten(starting_hand: Tuple[int, ...], ctr: Counter) -> Tuple[float, List[int]]:
    # get kokushi waits (iishanten or tenpai) and label iishanten type
    # note: ctr = Counter(remove_red_fives(starting_hand))
    has_pair = len([v for v in ctr.values() if v > 1]) >= 1
    shanten = (12 if has_pair else 13) - len(YAOCHUUHAI.intersection(starting_hand))
    waits: Tuple[int, ...] = ()
    if shanten <= 1:
        waits = sorted_hand(YAOCHUUHAI if not has_pair else YAOCHUUHAI.difference(starting_hand))
    return shanten, list(waits)

def get_floating_waits(hands: Set[Tuple[int, ...]], floating_tiles: Set[int]) -> Tuple[Set[int], Set[int]]:
    # For each hand in `hands`, calculate its waits:
    # - remove every combination of one pair and one floating tile
    # - if the result is composed of taatsus, add the wait of every taatsu
    # - if 2+ distinct pairs were able to add waits, add those pairs as a shanpon wait
    # Return the combined wait of every hand in `hands`
    waits: Set[int] = set()
    shanpon_waits: Set[int] = set()
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
            shanpon_waits |= pairs
    return waits, shanpon_waits

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

def get_iishanten_type(starting_hand: Tuple[int, ...]) -> Tuple[float, Set[int]]:
    # given an iishanten hand, calculate the iishanten type and its waits
    # we'll always return 1.XXX shanten, where XXX represents the type of iishanten
    # - 1.200 kokushi musou iishanten
    # - 1.100 chiitoitsu iishanten
    # - 1.010 headless iishanten
    # - 1.020 kutsuki iishanten
    # - 1.030 kutsuki headless iishanten
    # - 1.001 floating iishanten
    # - 1.002 imperfect (complete) iishanten
    # - 1.003 perfect iishanten
    # One hand could have multiple iishanten types contributing to the overall wait.
    # Combining the above is how we describe those kinds of hands:
    # - 1.120 chiitoi kutsuki iishanten
    # - 1.021 kutsuki floating iishanten
    # - 1.121 chiitoi kutsuki floating iishanten
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

    # figure out how many groups we need to complete
    hands = remove_all_groups({starting_hand})
    groups_needed = (len(next(iter(hands))) - 1) // 3
    assert groups_needed in {1, 2}, "get_iishanten_type was not passed an iishanten hand, "

    # one group needed = possibility for kutsuki and headless iishanten
    # since we assume the input is an iishanten hand, we just remove some taatsus
    # if what's remaining contains a pair and two other tiles, then it's kutsuki iishanten
    # if what's remaining contains no pair, then it's headless iishanten
    # there can be multiple results after removing all the groups,
    #   so it's possible a given hand can have both kutsuki waits and headless waits
    if groups_needed == 1:
        # get all the kutsuki tiles and headless tiles
        kutsuki_iishanten_tiles: Set[int] = set()  # tiles that could be the floating kutsuki tiles in hand
        headless_iishanten_tiles: Set[int] = set() # tiles that could be part of the 4 headless tiles in hand
        for hand in remove_some_taatsus(hands):
            pairless = next(iter(remove_all_pairs({hand})))
            if len(pairless) == 2 and len(pairless) != len(hand):
                # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten on {ph(pairless)}")
                kutsuki_iishanten_tiles |= set(pairless)
            else:
                # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten on {ph(hand)}")
                headless_iishanten_tiles |= set(hand)

        # if there's kutsuki tiles, then it's kutsuki iishanten
        if len(kutsuki_iishanten_tiles) > 0:
            shanten += 0.02
            # for each kutsuki tile, its waits are {tile-2,tile-1,tile,tile+1,tile+2}
            for tile in kutsuki_iishanten_tiles:
                waits |= {PRED[PRED[tile]], PRED[tile], remove_red_five(tile), SUCC[tile], SUCC[SUCC[tile]]} - {0}
            # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten with tiles {ph(kutsuki_iishanten_tiles)}, waits {ph(waits)}")

        # if there's headless tiles, then it's headless iishanten
        if len(headless_iishanten_tiles) > 0:
            shanten += 0.01
            # there's two kinds of headless: either you have two taatsus,
            #   or one taatsu + two floating tiles
            # the taatsu waits always contribute to the wait
            # the floating tiles are always tanki waits
            # when you have two taatsus, either can be treated as two floating tiles,
            #   so all four of the taatsu tiles are tanki waits
            floating_tiles = set(next(iter(remove_all_taatsus({tuple(headless_iishanten_tiles)}))))
            waits |= get_waits(tuple(headless_iishanten_tiles - floating_tiles))              # taatsu waits
            waits |= headless_iishanten_tiles if len(floating_tiles) == 0 else floating_tiles # tanki waits
            # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten with tiles {ph(headless_iishanten_tiles)}, waits {ph(waits)}")

    # now we check for complete and floating iishanten
    # floating iishanten is when you have a floating tile + a pair + 2 taatsus/pairs
    # complete iishanten is when that floating tile forms a complex group with either of the 2 taatsus/pairs

    # since we're looking for hands that need two groups and a pair,
    # get all length 7 subhands that contain a pair (remove a pair to get length 5 hands)
    subhands = set(filter(lambda hand: len(hand) == 7, remove_some_groups({starting_hand})))
    without_head = set(filter(lambda hand: len(hand) == 5, remove_some_pairs(subhands))) # remove a pair

    # for each of these length 5 hands, remove pairs/taatsus to get all the possible floating tiles
    # use get_floating_waits to calculate the waits for every length 7 subhand
    without_taatsus = remove_some_pairs(remove_some_taatsus(without_head))
    floating_iishanten_tiles = set().union(*filter(lambda hand: len(hand) == 1, without_taatsus))
    floating_waits, floating_shanpon_waits = get_floating_waits(subhands, floating_iishanten_tiles) if len(floating_iishanten_tiles) > 0 else (set(), set())

    # for each of these length 5 hands, remove pairs/taatsus to get length 3 hands
    # the idea is to check if these length 3 hands are complex shapes
    # check if each length 3 hand is in the set of all possible complex shapes
    #   to get all the complex shapes that exist in the hand
    complex_candidates = set(filter(lambda hand: len(hand) == 3, without_taatsus))
    to_complex_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t5:=SUCC[SUCC[t3]], ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
    all_complex_shapes = set().union(*(to_complex_shapes(t1) for t1,t2,t3 in complex_candidates))
    complete_iishanten_shapes = complex_candidates & all_complex_shapes

    # if a complex shape exists then we have complete iishanten
    # for every complex shape t1t2t3, grab the waits for t1t2 and t2t3 to get the taatsu waits
    get_complex_wait = lambda s: get_taatsu_wait(s[0:2]) | get_taatsu_wait(s[1:3])
    complete_taatsu_waits = floating_waits.union(*map(get_complex_wait, complete_iishanten_shapes)) if len(complete_iishanten_shapes) > 0 else set()
    # then check if t1t2, t2t3 are pairs to get the shanpon waits
    is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
    get_complex_shanpon_wait = lambda s: ({s[0]} if is_pair(s[0:2]) else set()) | ({s[1]} if is_pair(s[1:3]) else set())
    complete_shanpon_waits = floating_shanpon_waits.union(*map(get_complex_shanpon_wait, complete_iishanten_shapes)) if len(complete_iishanten_shapes) > 0 else set()

    # add complete/floating waits to the overall wait, and set the shanten number accordingly
    # perfect iishanten is when every possible wait leads to a ryanmen tenpai
    # (the check is different when you have headless waits involved)
    is_perfect_headless = shanten > 1 and check_headless_perfect_iishanten(starting_hand)
    is_perfect_complete = len(complete_taatsu_waits - waits) > 0 and check_complete_perfect_iishanten(starting_hand)
    is_perfect = is_perfect_complete or is_perfect_headless
    if len(complete_taatsu_waits - waits) > 0 or len(complete_shanpon_waits - shanpon_waits - waits) > 0: # check for complete iishanten
        shanten += 0.003 if is_perfect else 0.002
        # print(f"{ph(sorted_hand(starting_hand))} is complete iishanten with complex shapes {list(map(ph, complete_iishanten_shapes))}, adding extra waits {ph(complete_taatsu_waits - waits)}")
        waits |= complete_taatsu_waits
        shanpon_waits |= complete_shanpon_waits
    elif len(floating_waits - waits) > 0 or len(floating_shanpon_waits - shanpon_waits - waits) > 0: # check for floating iishanten
        shanten += 0.003 if is_perfect else 0.001
        # print(f"{ph(sorted_hand(starting_hand))} is floating iishanten with floating tiles {ph(floating_iishanten_tiles)}, adding extra waits {ph(floating_waits - waits)}")
        waits |= floating_waits
        shanpon_waits |= floating_shanpon_waits
    elif is_perfect:
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
            # check if, after removing the sequence, we still have headless/kutsuki iishanten
            removed_sequence = try_remove_all_tiles(starting_hand, seq)
            return len(removed_sequence) < len(starting_hand) and count_floating(next(iter(remove_all_groups({removed_sequence})))) <= 2
        for tile in waits.copy():
            if PRED[PRED[PRED[tile]]] != 0 and PRED[PRED[PRED[tile]]] not in waits and sequence_exists((PRED[PRED[tile]], PRED[tile], tile)):
                # print(f"  extended {pt(tile)} left to {pt(PRED[PRED[PRED[tile]]])}")
                waits.add(PRED[PRED[PRED[tile]]])
            if SUCC[SUCC[SUCC[tile]]] != 0 and SUCC[SUCC[SUCC[tile]]] not in waits and sequence_exists((SUCC[SUCC[tile]], SUCC[tile], tile)):
                # print(f"  extended {pt(tile)} right to {pt(SUCC[SUCC[SUCC[tile]]])}")
                waits.add(SUCC[SUCC[SUCC[tile]]])
        return waits
    waits = fix(extend_waits, waits)

    return round(shanten, 3), waits | shanpon_waits

@functools.cache
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
        shanten, waits = get_iishanten_type(starting_hand)
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
        shanten = 1.001
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
