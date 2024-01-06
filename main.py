import asyncio
from pprint import pprint
from injustice_judge import analyze_game
from typing import *
import sys

if __name__ == "__main__":
    assert len(sys.argv) >= 2, "expected one or two arguments, the tenhou url/majsoul link/riichicity id, and then seat [0-3] (optional)"
    link = sys.argv[1]
    players: Set[int] = {int(i) for i in sys.argv[2:]}
    assert link != "", "expected one or two arguments, the tenhou url/majsoul link/riichicity id, and then seat [0-3] (optional)"
    assert all(player in {0,1,2,3} for player in players), "expected remaining arguments to include 0 1 2 3"
    print("\n".join(asyncio.run(analyze_game(link, players, look_for={"injustice"}))))
    # print("\n".join(asyncio.run(analyze_game(link, players, look_for={"skill"}))))
    # print("\n".join(asyncio.run(analyze_game(link, players))))

    # from injustice_judge.shanten import pair_shapes, complex_shapes
    # print(len(pair_shapes), len(complex_shapes))

    # from injustice_judge.yaku import test_get_yakuman_tenpais
    # test_get_yakuman_tenpais()
    
    # # shanten tests
    # from injustice_judge.display import ph, shanten_name
    # from injustice_judge.shanten import calculate_shanten
    # hand = (11,11,12,12,13,13,15,15,15,15,19,19,19)
    # shanten = calculate_shanten(hand)
    # print(ph(hand), shanten, shanten_name(shanten))

    # from injustice_judge.utils import get_waits
    # print(get_waits((11,11,13,13,15))) # 11335 could be 11 33 5, 13 13 5, 13 35 1, we want all of them
    # print(get_waits((11,13,13,15,25))) # 11335 could be 11 33 5, 13 13 5, 13 35 1, we want all of them

    # from injustice_judge.shanten import calculate_shanten
    # def test_shanten(hand, expected_shanten):
    #   shanten = calculate_shanten(hand)
    #   if shanten != expected_shanten:
    #       assert False, f"Hand {hand} expected shanten {expected_shanten} but got {shanten}"
    # print("tenpai:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,37,37])[0] == 0   # 11123m123567p77s  tenpai
    # test_shanten((16,17,18,24,25,26,32,32,33,34,34,53,36), (0, (32,35)))
    # test_shanten((16,18,23,24,25,31,32,33,37,38,39,39,39), (0, (17,)))
    # test_shanten((12,12,13,13,14,14,15,15,34,34,34,35,36), (0, (12,15,34,37)))
    # print("kuttsuki iishanten:")
    # test_shanten((11,11,11,12,13,21,22,23,25,26,27,28,38), (1.030, (11,14,23,24,25,26,27,28,29,36,37,38,39))) # 11123m1235678p8s  kuttsuki headless iishanten
    # test_shanten((24,24,52,27,28,29,33,34,35,53,37,38,39), (1.032, (23,24,25,26,27,32,33,34,35,36,37))) # 440789p3450789s kuttsuki headless iishanten
    # test_shanten((11,11,12,12,13,13,15,16,16,17,18,18,19), (1.130, (13,14,15,16,17,18,19))) # 1122335667889m kuttsuki headless chiitoi iishsanten
    # test_shanten((11,12,13,13,14,15,17,29,29,33,34,35,35), (1.021, (12,15,16,17,18,19,29,32,33,34,35,36,37))) # 1233457m99p3455s kuttsuki floating iishanten
    # test_shanten((11,12,13,23,24,25,52,33,37,38,39,42,42), (1.021, (22,23,24,25,26,27,31,32,33,34,35,42))) # 123m3450p3789s22z kuttsuki floating iishanten
    # test_shanten((23,24,25,25,26,27,27,32,32,32,36,41,41), (1.021, (22,24,25,26,27,28,29,34,35,36,37,38,41))) # 3455677p2226s11z 
    # test_shanten((13,14,14,15,16,17,18,25,25,34,35,36,36), (1.021, (12,13,14,15,16,19,25,33,34,35,36,37,38))) # 3445678m55p4566s
    # print("headless iishanten:")
    # test_shanten((11,11,12,13,13,21,22,23,25,26,27,37,38), (1.012, (11,12,13,14,36,37,38,39))) # 11233m123567p78s  headless iishanten
    # test_shanten((11,12,12,13,13,21,22,23,25,26,27,37,38), (1.010, (11,12,13,14,36,37,38,39))) # 12233m123567p78s  headless iishanten
    # test_shanten((11,11,12,13,16,21,22,23,25,26,27,37,38), (1.011, (11,14,16,36,39))) # 11236m123567p78s  headless floating iishanten
    # test_shanten((13,14,15,16,17,18,22,24,24,25,26,32,33), (1.011, (22,23,24,27,31,32,33,34))) # 345678m24456p23s  headless floating floating iishanten
    # test_shanten((12,12,12,13,15,17,19,27,28,29,31,31,31), (1.012, (11,13,14,15,16,17,18,19))) # 2223579m789p111s  headless imperfect iishanten
    # print("complete iishanten:")
    # test_shanten((11,11,11,12,13,13,21,22,23,25,26,37,37), (1.003, (11,12,13,14,24,27,37))) # 111233m12356p77s  perfect iishanten
    # test_shanten((12,12,13,14,14,15,23,24,29,29,31,32,33), (1.002, (12,13,16,22,25,29))) # 223445m3499p123s  imperfect iishanten
    # test_shanten((11,12,13,17,18,19,23,23,25,27,27,32,33), (1.002, (23,24,26,27,31,34))) # 123789m33577p23s  imperfect iishanten
    # test_shanten((12,12,13,13,14,15,15,16,16,16,18,19,19), (1.102, (11,12,14,15,17,18,19)))   # 2233455666899m  imperfect iishanten + chiitoitsu
    # print("floating tile iishanten:")
    # test_shanten((11,11,11,12,13,17,21,22,23,25,26,37,37), (1.001, (11,14,24,27,37))) # 111237m12356p77s  floating tile iishanten
    # test_shanten((11,13,13,51,21,21,27,28,29,31,32,33,41), (1.001, (12,14))) # 1330m11789p123s  floating tile iishanten
    # test_shanten((12,13,14,16,18,25,52,27,27,28,29,36,37), (1.001, (17,35,38))) # 23468m507789p67s  floating tile iishanten
    # test_shanten((12,13,14,16,16,16,16,26,26,26,36,37,38), (1.001, (11,12,13,14,15,17,18,19,21,22,23,24,25,26,27,28,29,31,32,33,34,35,36,37,38,39,41,42,43,44,45,46,47))) # 2346666m666p678s floating tile iishanten, just need to discard the ankan tanki
    # test_shanten((12,12,13,13,21,22,23,27,28,29,31,31,39), (1.001, (11,12,13,14,31))) # 2233m123789p119s floating tile iishanten
    # test_shanten((11,12,13,14,14,16,16,17,18,19,28,29,41), (1.001, (14,16,27))) # 1234466789m89p1z floating tile iishanten
    # test_shanten((16,17,18,22,23,23,25,27,27,28,37,38,39), (1.001, (21,24,26,29))) # 678m2335778p789s floating tile iishanten
    # print("chiitoitsu iishanten:")
    # assert calculate_shanten((15,15,16,16,24,24,52,27,27,35,53,37,37))[0] == 0   # 5566m44577p5077s  chiitoitsu tenpai
    # assert calculate_shanten((11,15,16,16,24,24,52,27,27,35,53,37,37))[0] == 1.1 # 1566m44577p5077s  chiitoitsu iishanten
    # assert calculate_shanten((15,16,16,17,24,24,52,27,27,35,53,37,37))[0] == 1.1
    # assert calculate_shanten((15,16,16,17,24,24,52,27,27,35,53,36,39))[0] == 2
    # assert calculate_shanten((15,15,16,16,17,17,23,23,24,24,25,37,37))[0] == 0 # ryanpeikou tenpai
    # assert calculate_shanten((11,13,13,15,15,17,17,19,19,21,21,21,21))[0] == 2
    # assert calculate_shanten((11,11,13,13,15,15,17,17,19,19,21,21,21))[0] == 1.1
    # assert calculate_shanten((11,11,11,13,13,13,15,15,17,17,19,19,21))[0] == 1.001
    # assert calculate_shanten((11,13,13,15,15,17,17,19,19,19,21,21,21))[0] == 1.002
    # test_shanten((15,15,16,16,17,17,23,23,24,24,25,31,39), (1.110, (22,25,31,39))) # 556677m33445p19s  ryanpeikou iishanten
    # print("kokushi musou iishanten:")
    # test_shanten((11,11,19,21,29,31,39,41,42,43,44,45,46), (0, (47,))) # kokushi musou tenpai
    # test_shanten((11,19,21,29,31,39,41,42,43,44,45,46,47), (0, (11,19,21,29,31,39,41,42,43,44,45,46,47))) # kokushi musou 13-sided tenpai
    # assert calculate_shanten((14,19,21,29,29,31,39,41,42,44,45,46,47))[0] == 1.2 # kokushi musou iishanten
    # assert calculate_shanten((19,19,21,29,29,31,39,41,42,44,46,46,47))[0] == 2
    # print("tanki iishanten:")
    # test_shanten((12,13,14,16,16,16,16,26,26,26,36,37,38), (1.3, (11,12,13,14,15,17,18,19,21,22,23,24,25,27,28,29,31,32,33,34,35,36,37,38,39,41,42,43,44,45,46,47))) # 2346666m666p678s tanki iishanten
    # test_shanten((11,11,12,12,13,13,15,15,15,15,19,19,19), (1.3, (11,12,13,14,16,17,18,21,22,23,24,25,26,27,28,29,31,32,33,34,35,36,37,38,39,41,42,43,44,45,46,47))) # 11223355559999m11z tanki iishanten
    # print("2+ shanten:")
    # assert calculate_shanten((12,13,14,22,23,52,27,28,28,34,35,38,38))[0] == 2   # 234m230788p4588s  2-shanten
    # assert calculate_shanten((11,19,23,24,25,31,32,35,36,37,38,43,43))[0] == 2   # 19m345p125678s33z  2-shanten
    # assert calculate_shanten((11,19,22,24,25,31,32,35,36,37,38,43,43))[0] == 3   # 19m245p125678s33z  3-shanten
    # assert calculate_shanten((11,19,22,24,25,31,32,35,36,37,38,43,47))[0] == 4   # 19m245p125678s37z  4-shanten
    # assert calculate_shanten((12,13,16,17,23,24,28,29,31,32,35,36,39))[0] == 4   # 2367m3489p12569s  4-shanten
    # assert calculate_shanten((11,12,16,18,22,26,27,34,41,42,44,45,46))[0] == 5   # 1268m267p4s12456z  5-shanten
    # assert calculate_shanten((13,16,18,19,27,28,31,35,38,42,44,45,46))[0] == 6   # 3689m78p158s2456z  6-shanten
    # assert calculate_shanten((12,15,51,23,25,33,39,41,42,44,45,45,46))[0] == 4   # 150m25p39s124556z  4-shanten for chiitoitsu

    # from injustice_judge.shanten import _calculate_shanten
    # print(_calculate_shanten.cache_info())
    # from injustice_judge.shanten import timers
    # pprint(timers)

    # unused:
    # this is perfect headless, but we don't rly count it as such
    # cause checking perfect headless hands is too expensive
    # test_shanten([13,14,14,15,15,27,28,29,33,34,34,35,35], (1.013, [12,13,14,15,16,32,33,34,35,36])) # 34455m789p34455s  headless perfect iishanten
