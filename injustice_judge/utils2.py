import functools
from .constants import PRED, SUCC, YAOCHUUHAI
from .classes import Interpretation, CallInfo
from .display import ph, pt, round_name, shanten_name
from .utils import normalize_red_fives, sorted_hand, try_remove_all_tiles
from typing import *
from pprint import pprint

# this file (utils2.py) is dependent on classes.py, which depends on utils.py

def generate_hand_interpretations(initial_interpretation: Interpretation,
                                  yakuhai: Tuple[int, ...] = (),
                                  base_ron_fu: int = 20,
                                  base_tsumo_fu: int = 22,
                                  frozen_hand_calls: Tuple[CallInfo, ...] = ()) -> Set[Interpretation]:
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
                yakuhai_fu = 2 * yakuhai.count(tile)
                # print(f"add {yakuhai_fu} for yakuhai pair {pt(tile)}, {ph(unprocessed_part)}")
                removed_pair = try_remove_all_tiles(unprocessed_part, (tile, tile))
                if removed_pair != unprocessed_part: # removal was a success
                    to_update.add(Interpretation(removed_pair, fu + yakuhai_fu, fu + yakuhai_fu, sequences, triplets, (tile, tile), calls=frozen_hand_calls))
            
        if len(unprocessed_part) == 2:
            # now evaluate the remaining taatsu
            tile1, tile2 = sorted_hand(normalize_red_fives(unprocessed_part))
            is_shanpon = tile1 == tile2
            is_penchan = SUCC[tile1] == tile2 and 0 in {PRED[tile1], SUCC[tile2]}
            is_ryanmen = SUCC[tile1] == tile2 and 0 not in {PRED[tile1], SUCC[tile2]}
            is_kanchan = SUCC[SUCC[tile1]] == tile2
            single_wait_fu = 2 if is_penchan or is_kanchan else 0
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
            yakuhai_fu = 2 * yakuhai.count(tile)
            ron_fu = base_ron_fu + fu + yakuhai_fu + 2
            tsumo_fu = base_tsumo_fu + fu + yakuhai_fu + 2
            interpretations.add(Interpretation(unprocessed_part, ron_fu, tsumo_fu, sequences, triplets, calls=frozen_hand_calls))
            # then take care of the pinfu aryanmen possibility:
            if len(triplets) == 0: # all sequences
                # check that it's a tanki overlapping a sequence
                has_pair = False
                for i, (t1,t2,t3) in enumerate(sequences):
                    remaining_seqs = (*sequences[:i], *sequences[i+1:])

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
                    interpretations.add(Interpretation(ryanmen, 30, 22, remaining_seqs, triplets, (tanki, tanki), calls=frozen_hand_calls))
    return interpretations

@functools.lru_cache(maxsize=2048)
def get_tenpai_waits(hand: Tuple[int, ...]) -> Set[int]:
    return {wait for i in generate_hand_interpretations(Interpretation(hand)) for wait in i.get_waits()}
