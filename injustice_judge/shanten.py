import functools
import itertools
from .constants import PRED, SUCC, YAOCHUUHAI
from typing import *
from .utils import pt, ph, remove_red_five, remove_red_fives, sorted_hand, try_remove_all_tiles, remove_some, remove_all, fix
from pprint import pprint

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

def get_waits(hand: Tuple[int, ...]) -> Set[int]:
    """Get all waits resulting from each pair of consecutive tiles, excluding pair waits"""
    hand = sorted_hand(hand)
    def get_taatsu_wait(taatsu: Tuple[int, int]) -> Set[int]:
        t1, t2 = remove_red_fives(taatsu)
        return {PRED[t1], SUCC[t2]} if SUCC[t1] == t2 else {SUCC[t1]} if SUCC[SUCC[t1]] == t2 else set()
    return set().union(*map(get_taatsu_wait, zip(hand[:-1], hand[1:]))) - {0}

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

@functools.cache
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Tuple[float, List[int]]:
    """
    Return the shanten of the hand plus its waits (if tenpai or iishanten).
    If the shanten is 2+, the waits returned are an empty list.
    If iishanten, the returned shanten is 1.1 to 1.6, based on the type of iishanten.
    - 1.05: "kokushi musou iishanten",
    - 1.1 kutsuki iishanten
    - 1.2 headless iishanten
    - 1.23 headless perfect iishanten
    - 1.23 headless (imperfect) iishanten
    - 1.24 headless floating iishanten
    - 1.32 perfect iishanten
    - 1.33 imperfect iishanten
    - 1.4 floating tile iishanten
    +0.5 is added to all iishanten if chiitoitsu iishanten is also present in the hand.
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
        def get_floating_waits(hands: Set[Tuple[int, ...]]) -> Set[int]:
            count_floating = lambda hand: len(next(iter(remove_all_pairs(remove_all_taatsus({hand})))))
            waits = set()
            for hand in [tuple(remove_red_fives(hand)) for hand  in hands]:
                # first count the floating tiles
                # then try removing each pair
                # if removing the pair increases the floating count, skip this pair
                # otherwise, get the wait for the result, and also add this pair to a list
                # if we have 1 pair, don't do anything
                # if we have 2+ pairs, add them all to the wait
                num_floating = count_floating(hand)
                pairs = set()
                for tile in hand:
                    nopair = try_remove_all_tiles(hand, (tile, tile))
                    if len(nopair) < len(hand): # we removed this pair
                        if count_floating(nopair) == num_floating: # didn't remove a taatsu
                            waits |= get_waits(nopair)
                            pairs.add(tile)
                if len(pairs) >= 2:
                    waits |= pairs
            return waits

        # handle kutsuki/headless iishanten
        headless_waits: Set[int] = set()
        if groups_needed == 1:
            kutsuki_iishanten_tiles: Set[int] = set()
            headless_iishanten_tiles: Set[int] = set()
            for hand in remove_some_taatsus(hands):
                pairless = next(iter(remove_all_pairs({hand})))
                if len(pairless) != len(hand):
                    # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten on {ph(pairless)}")
                    kutsuki_iishanten_tiles |= set(pairless)
                else:
                    # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten on {ph(hand)}")
                    headless_iishanten_tiles |= set(hand)
            if len(kutsuki_iishanten_tiles) > 0:
                shanten = 1.1
                waits = set()
                for tile in kutsuki_iishanten_tiles:
                    waits |= {PRED[PRED[tile]], PRED[tile], remove_red_five(tile), SUCC[tile], SUCC[SUCC[tile]]} - {0}
                # print(f"{ph(sorted_hand(starting_hand))} is kutsuki iishanten, with waits {ph(waits)}")
            elif len(headless_iishanten_tiles) > 0:
                shanten = 1.2
                floating_tiles = set(next(iter(remove_all_taatsus({tuple(headless_iishanten_tiles)}))))
                if len(floating_tiles) == 0:
                    headless_waits = get_waits(tuple(headless_iishanten_tiles)).union(headless_iishanten_tiles)
                else:
                    headless_waits = get_waits(tuple(headless_iishanten_tiles)).union(floating_tiles)

        # handle floating/complete iishanten
        if groups_needed == 2 or shanten == 1.2: # headless can also be interpreted as floating/complete iishanten
            subhands = remove_some_pairs(remove_some_taatsus(filter(lambda hand: len(hand) == 7, remove_some_groups({starting_hand}))))
            subhands = set(map(sorted_hand, subhands))

            # get waits for floating tile iishanten
            floating_iishanten_tiles = {tile for hand in subhands if len(hand) == 1 for tile in hand}
            floating_waits = get_floating_waits(subhands) if len(floating_iishanten_tiles) > 0 else set()

            # get waits for complete iishanten
            to_complex_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t5:=SUCC[SUCC[t3]], ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
            complete_iishanten_shapes = subhands & {shape for hand in subhands for shape in to_complex_shapes(hand[0])}
            complete_waits = set().union(*map(get_waits, complete_iishanten_shapes))
            if shanten == 1.2:
                if len(complete_waits | headless_waits) > len(headless_waits):
                    # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten, adding extra waits {ph(complete_waits - headless_waits)}")
                    shanten = 1.23
                elif len(floating_waits | headless_waits) > len(headless_waits):
                    # print(f"{ph(sorted_hand(starting_hand))} is headless floating iishanten, adding extra waits {ph(floating_waits - headless_waits)}")
                    shanten = 1.24
                else:
                    # print(f"{ph(sorted_hand(starting_hand))} is headless iishanten, with waits {ph(headless_waits)")
                    shanten = 1.23

                # check for headless perfect iishanten
                #   which is only true if both shapes are ryanmen and overlap with a group
                #   such that a pair+ryanmen can be formed by dropping one side of the ryanmen
                # e.g. 234 34 -> drop 3 -> 2344
                # e.g. 234 45 -> drop 5 -> 2344
                # e.g. 34 444 -> drop 4 -> 3444
                # e.g. 34 555 -> drop 3 -> 4555 
                # there are 8 possible shapes (the above 4 plus their reverse versions)
                # exclude shapes that result in penchan!
                # these are: 12233, 12222, 11112, 77889, 88889, 89999
                penchan_shapes = {(11,12,12,13,13),(11,12,12,12,12),(11,11,11,11,12),(17,17,18,18,19),(18,18,18,18,19),(18,19,19,19,19),
                                  (21,22,22,23,23),(21,22,22,22,22),(21,21,21,21,22),(27,27,28,28,29),(28,28,28,28,29),(28,29,29,29,29),
                                  (31,32,32,33,33),(31,32,32,32,32),(31,31,31,31,32),(37,37,38,38,39),(38,38,38,38,39),(38,39,39,39,39)}
                to_flexible_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t4:=SUCC[t3],
                   tuple({(t1,t2,t2,t3,t4), (t2,t2,t3,t3,t4), (t1,t2,t2,t3,t3), (t1,t2,t3,t3,t4),
                          (t1,t2,t3,t3,t3), (t1,t2,t2,t2,t2), (t1,t1,t1,t1,t2), (t1,t1,t1,t2,t3)} - penchan_shapes))[-1]
                flexible_shapes = set().union(*map(to_flexible_shapes, sorted_hand(starting_hand)))
                if len(flexible_shapes & subhands) >= 2:
                    shanten = 1.22

                waits = floating_waits | complete_waits | headless_waits
            elif len(complete_iishanten_shapes) > 0:
                # take out all ryanmen shapes (not penchan!)
                make_ryanmen = lambda tile: ((SUCC[tile], tile),) if tile not in {11,18,21,28,31,38} else {()}
                remove_all_ryanmen = lambda hands: fix(lambda hs: remove_all(hs, make_ryanmen), hands)
                # if the resulting length is 3 then it's a perfect iishanten
                # otherwise, it's imperfect iishanten
                if len(next(iter(remove_all_ryanmen(hands)))) == 3:
                    shanten = 1.35
                else:
                    shanten = 1.3
                waits = get_floating_waits(hands)
                # print(f"{ph(sorted_hand(starting_hand))} is complete iishanten, with complex shapes {list(map(ph, complete_iishanten_shapes))}")
            elif len(floating_waits) > 0:
                shanten = 1.4
                waits = get_floating_waits(hands)
                # print(f"{ph(sorted_hand(starting_hand))} is floating tile iishanten, with floating tile(s) {ph(floating_iishanten_tiles)}")

        assert groups_needed in {1,2}, f"{ph(sorted_hand(starting_hand))} is somehow iishanten with {4-groups_needed} groups"
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
        # take the min, unless we're iishanten in which case we add 0.5 to the shanten
        if c_shanten == 1 and shanten >= 1 and shanten < 2:
            shanten += 0.5
            waits |= set(c_waits)
        elif c_shanten < shanten:
            shanten = c_shanten
            waits = set(c_waits)
        if shanten == 1:
            shanten = 1.5
    if k_shanten < shanten:
        shanten = k_shanten
        if shanten == 1:
            shanten = 1.05
        waits = set(k_waits)

    # remove all ankan in hand from the waits
    ankan_tiles = {k for k, v in ctr.items() if v == 4}
    return shanten, list(sorted_hand(waits - ankan_tiles))

@functools.cache
def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    hand_copy = tuple(remove_red_fives(hand))
    possible_winning_tiles = {t for tile in hand_copy for t in (PRED[tile], tile, SUCC[tile])} - {0}
    is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
    makes_winning_hand = lambda tile: any(map(is_pair, remove_all_groups({(*hand_copy, tile)})))
    return set(filter(makes_winning_hand, possible_winning_tiles))

def calculate_shanten(starting_hand: Iterable[int]) -> Tuple[float, List[int]]:
    """This just converts the input to a sorted tuple so it can be serialized as a cache key"""
    return _calculate_shanten(tuple(sorted(starting_hand)))
