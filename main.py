import asyncio
from pprint import pprint
from injustice_judge import analyze_game
from typing import *
import sys
import dotenv

dotenv.load_dotenv("config.env")

if __name__ == "__main__":
    assert len(sys.argv) >= 2, "expected one or two arguments, the tenhou/majsoul url, and then seat [0-3] (optional)"
    link = sys.argv[1]
    player = int(sys.argv[2]) if len(sys.argv) == 3 else None
    assert link != "", "expected one or two arguments, the tenhou/majsoul url, and then seat [0-3] (optional)"
    assert player in {0,1,2,3,None}, "expected second argument to be 0,1,2,3"
    print("\n".join(asyncio.run(analyze_game(link, player))))

    # from injustice_judge.yaku import test_get_yakuman_tenpais
    # test_get_yakuman_tenpais()
    
    # from injustice_judge.yaku import test_get_stateless_yaku
    # test_get_stateless_yaku()
    
    # from injustice_judge.yaku import test_get_hand_interpretations
    # test_get_hand_interpretations()
    
    # # shanten tests
    # from injustice_judge.utils import ph
    # from injustice_judge.shanten import calculate_shanten
    # hand = [11,11,11,12,13,21,22,23,25,26,27,37,37]
    # print(ph(hand), calculate_shanten(hand))

    # from injustice_judge.shanten import calculate_shanten
    # print("tenpai:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,37,37])[0] == 0   # 11123m123567p77s  tenpai
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36]) == (0, [32,35])
    # assert calculate_shanten([16,18,23,24,25,31,32,33,37,38,39,39,39]) == (0, [17])
    # print("kutsuki iishanten:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,28,38])[0] == 1.1 # 11123m1235678p8s  kutsuki iishanten
    # assert calculate_shanten([11,12,13,23,24,25,52,33,37,38,39,42,42])[0] == 1.1
    # assert calculate_shanten([24,24,52,27,28,29,33,34,35,53,37,38,39]) == (1.1, [23,24,25,26,27,33,34,35,36,37])
    # assert calculate_shanten([11,11,12,12,13,13,15,16,16,17,18,18,19]) == (1.6, [13,14,15,16,17,18,19]) # 1122335667889m
    # print("headless iishanten:")
    # assert calculate_shanten([13,14,14,15,15,27,28,29,33,34,34,35,35]) == (1.22, [12,13,14,15,16,32,33,34,35,36]) # 34455m789p34455s  headless perfect iishanten
    # assert calculate_shanten([11,11,12,13,13,21,22,23,25,26,27,37,38]) == (1.23, [11,12,13,14,36,37,38,39]) # 11233m123567p78s  headless iishanten
    # assert calculate_shanten([11,12,12,13,13,21,22,23,25,26,27,37,38]) == (1.23, [11,12,13,14,36,37,38,39]) # 12233m123567p78s  headless iishanten
    # assert calculate_shanten([11,11,12,13,16,21,22,23,25,26,27,37,38]) == (1.24, [11,14,16,36,39]) # 11236m123567p78s  headless floating iishanten
    # print("complete iishanten:")
    # assert calculate_shanten([11,11,11,12,13,13,21,22,23,25,26,37,37]) == (1.35, [11,12,13,14,24,27,37]) # 111233m12356p77s  complete iishanten
    # assert calculate_shanten([11,12,13,17,18,19,23,23,25,27,27,32,33]) == (1.3, [23,24,26,27,31,34]) # 123789m33577p23s
    # assert calculate_shanten([12,12,13,14,14,15,23,24,29,29,31,32,33]) == (1.35, [12,13,16,22,25,29]) # 223445m3499p123s
    # print("floating tile iishanten:")
    # assert calculate_shanten([11,11,11,12,13,17,21,22,23,25,26,37,37]) == (1.4, [11,14,24,27,37]) # 111237m12356p77s  floating tile iishanten
    # assert calculate_shanten([11,13,13,51,21,21,27,28,29,31,32,33,41]) == (1.4, [12,14]) # 1330m11789p123s  floating tile iishanten
    # assert calculate_shanten([12,13,14,16,18,25,52,27,27,28,29,36,37]) == (1.4, [17,35,38]) # 23468m507789p67s  floating tile iishanten
    # print("chiitoitsu iishanten:")
    # assert calculate_shanten([15,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 0   # 5566m44577p5077s  chiitoitsu tenpai
    # assert calculate_shanten([11,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 1.5 # 1566m44577p5077s  chiitoitsu iishanten
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,37,37])[0] == 1.5
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,36,39])[0] == 2
    # assert calculate_shanten([15,15,16,16,17,17,23,23,24,24,25,37,37])[0] == 0 # ryanpeikou tenpai
    # assert calculate_shanten([15,15,16,16,17,17,23,23,24,24,25,31,39])[0] == 1.73 # ryanpeikou iishanten
    # print("kokushi musou iishanten:")
    # assert calculate_shanten([11,11,19,21,29,31,39,41,42,43,44,45,46]) == (0, [47]) # kokushi musou tenpai
    # assert calculate_shanten([11,19,21,29,31,39,41,42,43,44,45,46,47]) == (0, [11,19,21,29,31,39,41,42,43,44,45,46,47]) # kokushi musou 13-sided tenpai
    # assert calculate_shanten([14,19,21,29,29,31,39,41,42,44,45,46,47])[0] == 1.05 # kokushi musou iishanten
    # assert calculate_shanten([19,19,21,29,29,31,39,41,42,44,46,46,47])[0] == 2
    # print("2+ shanten:")
    # assert calculate_shanten([12,13,14,22,23,52,27,28,28,34,35,38,38])[0] == 2   # 234m230788p4588s  2-shanten
    # assert calculate_shanten([11,19,23,24,25,31,32,35,36,37,38,43,43])[0] == 2   # 19m345p125678s33z  2-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,43])[0] == 3   # 19m245p125678s33z  3-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,47])[0] == 4   # 19m245p125678s37z  4-shanten
    # assert calculate_shanten([12,13,16,17,23,24,28,29,31,32,35,36,39])[0] == 4   # 2367m3489p12569s  4-shanten
    # assert calculate_shanten([11,12,16,18,22,26,27,34,41,42,44,45,46])[0] == 5   # 1268m267p4s12456z  5-shanten
    # assert calculate_shanten([13,16,18,19,27,28,31,35,38,42,44,45,46])[0] == 6   # 3689m78p158s2456z  6-shanten
    # assert calculate_shanten([12,15,51,23,25,33,39,41,42,44,45,45,46])[0] == 4   # 150m25p39s124556z  4-shanten for chiitoitsu
    # assert calculate_shanten([12,12,13,13,14,15,15,16,16,16,18,19,19]) == (1.8, [11,12,14,15,17,18,19])   # 2233455666899m  imperfect iishanten + chiitoitsu
