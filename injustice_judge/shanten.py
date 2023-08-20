import functools
import itertools
from .constants import PRED, SUCC, YAOCHUUHAI
from typing import *
from .utils import pt, ph, remove_red_fives, sorted_hand, try_remove_all_tiles


###
### ukeire and shanten calculations
###

@functools.cache
def _calculate_shanten(starting_hand: Tuple[int, ...]) -> Tuple[float, List[int]]:
    """
    Return the shanten of the hand plus some extra data.
    If the shanten is 2+, the extra data is just an empty list.
    If iishanten, the returned shanten is 1.1 to 1.6, based on the type of iishanten.
    If iishanten, some extra data is returned:
    - 1.1 kutsuki iishanten: all kutsuki tiles (e.g. 49m or 14m8s)
    - 1.2 headless iishanten: all taatsu (e.g. 24m89p, 3467p12s)
    - 1.3 complete iishanten: the complex group (e.g. 246m or 44688p)
    - 1.4 floating tile iishanten: the floating tile(s) (e.g. 8s or 14m)
    - 1.5 chiitoitsu/1.6 kokushi iishanten: the wait (e.g. 1p14z)
    If tenpai (shanten = 0), returns the waits as the extra data.
    """
    # 1. Remove all groups
    # 2. Count floating tiles
    # 3. Calculate shanten
    # 4. Check for iishanten/tenpai
    # 5. If iishanten, output the relevant tiles
    # 6. If tenpai, output the wait
    # 7. Do 3-6 for chiitoitsu and kokushi

    # helpers for removing tiles from hand
    remove_some = lambda hands, tile_to_groups: {cast(Tuple[int, ...], ())} if hands == {()} else set(try_remove_all_tiles(hand, group) for hand in hands for tile in set(hand) for group in tile_to_groups(tile))
    def remove_all(hands: Set[Tuple[int, ...]], tile_to_groups: Callable[[int], Tuple[Tuple[int, ...], ...]]):
        # Tries to remove the maximum number of groups in tile_to_groups(tile) from the hand.
        # Basically same as remove_some but filters the result for min length hands.
        assert isinstance(hands, set)
        result = remove_some(hands, tile_to_groups)
        min_length = min(map(len, result), default=0)
        ret = set(filter(lambda hand: len(hand) == min_length, result))
        assert len(ret) > 0
        # print(list(map(ph,hands)),"\n=>\n",list(map(ph,result)), "\n=>\n",list(map(ph,ret)),"\n")
        return ret
    make_groups = lambda tile: ((SUCC[SUCC[tile]], SUCC[tile], tile), (tile, tile, tile))
    remove_all_groups = lambda hands: functools.reduce(lambda hs, _: remove_all(hs, make_groups), range(4), hands)
    fix = lambda f, x: next(x for _ in itertools.cycle([None]) if x == (x := f(x)))
    make_taatsus = lambda tile: ((SUCC[tile], tile), (SUCC[SUCC[tile]], tile))
    remove_some_taatsus = lambda hands: fix(lambda hs: remove_some(hs, make_taatsus), hands)
    make_pairs = lambda tile: ((tile, tile),)
    remove_some_pairs = lambda hands: fix(lambda hs: remove_some(hs, make_pairs), hands)
    remove_all_pairs = lambda hands: fix(lambda hs: remove_all(hs, make_pairs), hands)

    # remove as many groups as possible
    hands = remove_all_groups({starting_hand})
    num_groups = (13 - len(next(iter(hands)))) // 3

    # calculate shanten for every combination of groups removed

    @functools.cache
    def get_hand_shanten(hand: Tuple[int, ...]) -> float:
        """Return the shanten of a hand with all of its groups, ryanmens, and kanchans removed"""
        floating_tiles = next(iter(remove_all_pairs({hand})))
        # needs_pair = 1 if the hand is missing a pair but is full of taatsus -- need to convert a taatsu to a pair
        # must_discard_taatsu = 1 if the hand is 6+ blocks -- one of the taatsu is actually 2 floating tiles
        # shanten = (3 + num_floating - num_groups) // 2, plus the above
        needs_pair = 1 if len(floating_tiles) == len(hand) and len(floating_tiles) + num_groups <= 3 else 0
        must_discard_taatsu = 1 if num_groups <= 1 and len(floating_tiles) <= 1 else 0
        return needs_pair + must_discard_taatsu + (3 + len(floating_tiles) - num_groups) // 2
    shanten: float = min(map(get_hand_shanten, remove_some_taatsus(hands)))
    assert shanten >= 0, f"somehow calculated negative shanten for {ph(sorted_hand(starting_hand))}"

    # if iishanten, get the type of iishanten based on tiles remaining after removing some number of taatsus
    extra_data: Tuple[int, ...] = ()
    if shanten == 1:
        kutsuki_iishanten_tiles: Set[int] = set()
        headless_iishanten_tiles: Set[int] = set()
        complete_iishanten_tiles: Set[Tuple[int, ...]] = set()
        floating_iishanten_tiles: Set[int] = set()
        for hand in remove_some_taatsus(hands):
            pairless = next(iter(remove_all_pairs({hand})))
            if num_groups == 3:
                if len(pairless) != len(hand):
                    # print(f"{ph(starting_hand)} is kutsuki iishanten on {ph(pairless)}")
                    kutsuki_iishanten_tiles |= set(pairless)
                else:
                    # print(f"{ph(starting_hand)} is headless iishanten on {ph(hand)}")
                    headless_iishanten_tiles |= set(hand)
            elif num_groups == 2:
                if len(hand) >= 3:
                    # check if the hand is a complex shape
                    to_complex_shapes = lambda t1: (t2:=SUCC[t1], t3:=SUCC[t2], t5:=SUCC[SUCC[t3]], ((t1,t1,t2),(t1,t2,t2),(t1,t1,t3),(t1,t3,t3),(t1,t3,t5)))[-1]
                    for potential_complex_shape in map(sorted_hand, filter(lambda hand: len(hand) == 3, remove_some_pairs({hand}))):
                        red_removed = tuple(remove_red_fives(potential_complex_shape))
                        if red_removed in to_complex_shapes(red_removed[0]):
                            # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(hand)}")
                            complete_iishanten_tiles.add(potential_complex_shape)
                if len(pairless) == 1:
                    # print(f"{ph(starting_hand)} is floating tile iishanten on {ph(hand)}")
                    floating_iishanten_tiles.add(next(iter(pairless)))
            else:
                assert False, f"{ph(sorted_hand(starting_hand))} is somehow iishanten with {num_groups} groups"

        if len(kutsuki_iishanten_tiles) > 0:
            shanten = 1.1
            extra_data = sorted_hand(kutsuki_iishanten_tiles)
            # print(f"{ph(starting_hand)} is kutsuki iishanten, with kutsuki tiles {ph(extra_data)}")
        elif len(headless_iishanten_tiles) > 0:
            shanten = 1.2
            extra_data = sorted_hand(headless_iishanten_tiles)
            # print(f"{ph(starting_hand)} is headless iishanten, with shapes {ph(extra_data)}")
        if len(complete_iishanten_tiles) > 0:
            shanten = 1.3
            intersect = lambda l1, l2: [l1.remove(x) or x for x in l2 if x in l1]
            flatten = lambda xss: [x for xs in xss for x in xs]
            extra_data = sorted_hand(intersect(list(starting_hand), flatten(complete_iishanten_tiles)))
            # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(extra_data)}")
        elif len(floating_iishanten_tiles) > 0:
            shanten = 1.4
            extra_data = sorted_hand(floating_iishanten_tiles)
            # print(f"{ph(starting_hand)} is floating tile iishanten, with floating tiles {ph(extra_data)}")

    # if tenpai, get the waits
    elif shanten == 0:
        hand_copy = tuple(remove_red_fives(starting_hand))
        possible_winning_tiles = {t for tile in hand_copy for t in (PRED[tile], tile, SUCC[tile])} - {0}
        is_pair = lambda hand: len(hand) == 2 and hand[0] == hand[1]
        makes_winning_hand = lambda tile: any(map(is_pair, remove_all_groups({(*hand_copy, tile)})))
        extra_data = sorted_hand(filter(makes_winning_hand, possible_winning_tiles))
        assert len(extra_data) > 0, f"tenpai hand {ph(sorted_hand(hand_copy))} has no waits?"

    # otherwise, check for chiitoitsu and kokushi musou
    else:
        # chiitoitsu shanten
        count_unique_pairs = lambda hand: len(list(filter(lambda ct: ct > 1, Counter(remove_red_fives(hand)).values())))
        num_unique_pairs = count_unique_pairs(starting_hand)
        shanten = min(shanten, 6 - num_unique_pairs)

        # get chiitoitsu waits (iishanten or tenpai) and label iishanten type
        if shanten <= 1:
            extra_data = sorted_hand(functools.reduce(lambda hand, tile: try_remove_all_tiles(hand, (tile, tile)), set(starting_hand), tuple(starting_hand)))
        if shanten == 1:
            shanten = 1.5

        # kokushi musou shanten
        if shanten >= 4:
            shanten = min(shanten, (12 if num_unique_pairs >= 1 else 13) - len(YAOCHUUHAI.intersection(starting_hand)))

            # get kokushi waits (iishanten or tenpai) and label iishanten type
            if shanten <= 1:
                if num_unique_pairs > 0:
                    extra_data = sorted_hand(YAOCHUUHAI.difference(starting_hand))
                else:
                    extra_data = sorted_hand(YAOCHUUHAI)
            if shanten == 1:
                shanten = 1.6
    return shanten, list(extra_data)

def calculate_shanten(starting_hand: Iterable[int]) -> Tuple[float, List[int]]:
    """This just converts the input to a sorted tuple so it can be serialized as a cache key"""
    return _calculate_shanten(tuple(sorted(starting_hand)))

def calculate_ukeire(hand: Tuple[int, ...], visible: Iterable[int]):
    """
    Return the ukeire of the hand, or 0 if the hand is not tenpai.
    Requires passing in the visible tiles on board (not including hand).
    """
    shanten, waits = calculate_shanten(hand)
    if shanten > 0:
        return 0
    relevant_tiles = set(remove_red_fives(waits))
    visible = list(remove_red_fives(list(hand) + list(visible)))
    return 4 * len(relevant_tiles) - sum(visible.count(wait) for wait in relevant_tiles)
