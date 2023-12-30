from dataclasses import dataclass, field
from collections import defaultdict
from typing import *

# This file contains every lookup table used in InjusticeJudge.
# A summary:
#   SHANTEN_NAMES: the printed name for each number internally representing of a type of shanten
#      PLACEMENTS: the printed name of a placement (1 -> "1st")
#     LIMIT_HANDS: maps han count to tenhou limit hand name (5 -> "満貫")
#   TENHOU_LIMITS: maps tenhou's limit field ID to limit hand name (5 -> "役満")
#    MAJSOUL_YAKU: maps mahjong soul yaku IDs to tenhou yaku names
#     TENHOU_YAKU: maps tenhou yaku IDs to tenhou yaku names
# RIICHICITY_YAKU: maps riichi city yaku IDs to tenhou yaku names
#         YAKUMAN: set of yakuman names. there's also DOUBLE_YAKUMAN
#       TRANSLATE: a big map from all Japanese terms to English terms
#       PRED/SUCC: get the predecessor/successor of a number tile, 0 if nonexistent
#  DORA_INDICATOR: map from a dora to its indicator
#            DORA: map from a dora indicator to its indicated dora
# TOGGLE_RED_FIVE: maps a five to its red equivalent and vice versa
#           MANZU: a set of all manzu tiles
#           PINZU: a set of all pinzu tiles
#           SOUZU: a set of all souzu tiles
#           JIHAI: a set of all honor tiles
#      YAOCHUUHAI: a set of all terminal and honor tiles
#       TANYAOHAI: a set of all 2-8 tiles
#    KO_RON_SCORE: nondealer ron score for a given han and fu
#   OYA_RON_SCORE: dealer ron score for a given han and fu
#  KO_TSUMO_SCORE: tsumo points paid by nondealers for a given han and fu
# OYA_TSUMO_SCORE: tsumo points paid by the dealer or to the dealer for a given han and fu

# Global types:
Event = Tuple[Any, ...]
Shanten = Tuple[float, Tuple[int, ...]]
YakuForWait = Dict[int, List[Tuple[str, int]]]

SHANTEN_NAMES = {
    0: "tenpai",
    1: "iishanten", # used when we round down iishanten
    1.010: "headless iishanten",
    1.020: "kuttsuki iishanten",
    1.030: "kuttsuki headless iishanten",
    1.100: "chiitoitsu iishanten",
    1.110: "chiitoi headless iishanten",
    1.120: "chiitoi kuttsuki iishanten",
    1.130: "chiitoi headless kuttsuki iishanten",
    1.001: "floating iishanten",
    1.011: "headless iishanten",
    1.021: "kuttsuki iishanten",
    1.031: "headless kuttsuki iishanten",
    1.101: "chiitoi iishanten",
    1.111: "chiitoi headless iishanten",
    1.121: "chiitoi kuttsuki iishanten",
    1.131: "chiitoi headless kuttsuki iishanten",
    1.002: "imperfect iishanten",
    1.012: "headless iishanten",
    1.022: "kuttsuki iishanten",
    1.032: "headless kuttsuki iishanten",
    1.102: "chiitoi iishanten",
    1.112: "chiitoi headless iishanten",
    1.122: "chiitoi kuttsuki iishanten",
    1.132: "chiitoi headless kuttsuki iishanten",
    1.003: "perfect iishanten",
    1.013: "headless iishanten",
    1.023: "kuttsuki iishanten",
    1.033: "headless kuttsuki iishanten",
    1.103: "chiitoi iishanten",
    1.113: "chiitoi headless iishanten",
    1.123: "chiitoi kuttsuki iishanten",
    1.133: "chiitoi headless kuttsuki iishanten",
    1.200: "kokushi musou iishanten",
    1.300: "tanki iishanten",
    2: "2-shanten",
    3: "3-shanten",
    4: "4-shanten",
    5: "5-shanten",
    6: "6-shanten"
}
PLACEMENTS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

LIMIT_HANDS = defaultdict(lambda: "役満", {
                0: "", 1: "", 2: "",
                3: "満貫", 4: "満貫", 5: "満貫",
                6: "跳満", 7: "跳満",
                8: "倍満", 9: "倍満", 10: "倍満",
                11: "三倍満", 12: "三倍満"})

TENHOU_LIMITS = ["", "満貫", "跳満", "倍満", "三倍満", "役満"]

MAJSOUL_YAKU = {
    1: "門前清自摸和",        # Fully Concealed Hand
    2: "立直",               # Riichi
    3: "槍槓",               # Robbing a Kan
    4: "嶺上開花",            # After a Kan
    5: "海底摸月",            # Under the Sea
    6: "河底撈魚",            # Under the River
    7: "役牌 白",            # White Dragon (Haku)
    8: "役牌 發",            # Green Dragon (Hatsu)
    9: "役牌 中",            # Red Dragon (Chun)
    10: "役牌:自風牌",        # Seat Wind
    11: "役牌:場風牌",        # Prevalent Wind
    12: "断幺九",            # All Simples
    13: "一盃口",            # Pure Double Sequence
    14: "平和",              # Pinfu
    15: "混全帯幺九",        # Half Outside Hand
    16: "一気通貫",          # Pure Straight
    17: "三色同順",           # Mixed Triple Sequence
    18: "ダブル立直",         # Double Riichi
    19: "三色同刻",           # Triple Triplets
    20: "三槓子",            # Three Quads
    21: "対々和",            # All Triplets
    22: "三暗刻",            # Three Concealed Triplets
    23: "小三元",            # Little Three Dragons
    24: "混老頭",            # All Terminals and Honours
    25: "七対子",            # Seven Pairs
    26: "純全帯幺九",        # Fully Outside Hand
    27: "混一色",            # Half Flush
    28: "二盃口",            # Twice Pure Double Sequence
    29: "清一色",            # Full Flush
    30: "一発",              # Ippatsu
    31: "ドラ",              # Dora
    32: "赤ドラ",            # Red Five
    33: "裏ドラ",            # Uradora
    34: "抜きドラ",          # Kita
    35: "天和",              # Blessing of Heaven
    36: "地和",              # Blessing of Earth
    37: "大三元",            # Big Three Dragons
    38: "四暗刻",            # Four Concealed Triplets
    39: "字一色",            # All Honors
    40: "緑一色",            # All Green
    41: "清老頭",            # All Terminals
    42: "国士無双",          # Thirteen Orphans
    43: "小四喜",            # Four Little Winds
    44: "四槓子",            # Four Quads
    45: "九蓮宝燈",          # Nine Gates
    46: "八連荘",            # Paarenchan
    47: "純正九蓮宝燈",       # True Nine Gates
    48: "四暗刻単騎",         # Single-wait Four Concealed Triplets
    49: "国士無双十三面待ち",  # Thirteen-wait Thirteen Orphans
    50: "大四喜",            # Four Big Winds
    51: "燕返し",            # Tsubame-gaeshi
    52: "槓振り",            # Kanburi
    53: "十二落抬",          # Shiiaruraotai
    54: "五門斉",            # Uumensai
    55: "三連刻",            # Three Chained Triplets
    56: "一色三順",           # Pure Triple Chow
    57: "一筒摸月",           # Iipinmoyue
    58: "九筒撈魚",           # Chuupinraoyui
    59: "人和",              # Hand of Man
    60: "大車輪",            # Big Wheels
    61: "大竹林",            # Bamboo Forest
    62: "大数隣",            # Numerous Neighbours
    63: "石の上にも三年",      # Ishinouenimosannen
    64: "大七星",            # Big Seven Stars
}
TENHOU_YAKU = {
    0: "門前清自摸和",        # Fully Concealed Hand
    1: "立直",               # Riichi
    2: "一発",               # Ippatsu
    3: "槍槓",               # Robbing a Kan
    4: "嶺上開花",            # After a Kan
    5: "海底摸月",            # Under the Sea
    6: "河底撈魚",            # Under the River
    7: "平和",               # Pinfu
    8: "断幺九",             # All Simples
    9: "一盃口",             # Pure Double Sequence
    10: "自風 東",           # Seat Wind
    11: "自風 南",           # Seat Wind
    12: "自風 西",           # Seat Wind
    13: "自風 北",           # Seat Wind
    14: "場風 東",           # Prevalent Wind
    15: "場風 南",           # Prevalent Wind
    16: "場風 西",           # Prevalent Wind
    17: "場風 北",           # Prevalent Wind
    18: "役牌 白",           # White Dragon (Haku)
    19: "役牌 發",           # Green Dragon (Hatsu)
    20: "役牌 中",           # Red Dragon (Chun)
    21: "ダブル立直",         # Double Riichi
    22: "七対子",            # Seven Pairs
    23: "混全帯幺九",        # Half Outside Hand
    24: "一気通貫",          # Pure Straight
    25: "三色同順",           # Mixed Triple Sequence
    26: "三色同刻",           # Triple Triplets
    27: "三槓子",            # Three Quads
    28: "対々和",            # All Triplets
    29: "三暗刻",            # Three Concealed Triplets
    30: "小三元",            # Little Three Dragons
    31: "混老頭",            # All Terminals and Honours
    32: "二盃口",            # Twice Pure Double Sequence
    33: "純全帯幺九",        # Fully Outside Hand
    34: "混一色",            # Half Flush
    35: "清一色",            # Full Flush
    36: "人和",              # Hand of Man
    37: "天和",              # Blessing of Heaven
    38: "地和",              # Blessing of Earth
    39: "大三元",            # Big Three Dragons
    40: "四暗刻",            # Four Concealed Triplets
    41: "四暗刻単騎",         # Single-wait Four Concealed Triplets
    42: "字一色",            # All Honors
    43: "緑一色",            # All Green
    44: "清老頭",            # All Terminals
    45: "九蓮宝燈",          # Nine Gates
    46: "純正九蓮宝燈",       # True Nine Gates
    47: "国士無双十三面待ち",  # Thirteen-wait Thirteen Orphans
    48: "国士無双",          # Thirteen Orphans
    49: "大四喜",            # Four Big Winds
    50: "小四喜",            # Four Little Winds
    51: "四槓子",            # Four Quads
    52: "ドラ",              # Dora/Kita
    53: "裏ドラ",            # Uradora
    54: "赤ドラ",            # Red Five
}
RIICHICITY_YAKU = {
    0: "立直",               # Riichi
    1: "門前清自摸和",        # Fully Concealed Hand
    2: "一発",               # Ippatsu
    7: "役牌 中",            # Red Dragon (Chun)
    8: "役牌 發",            # Green Dragon (Hatsu)
    9: "役牌 白",            # White Dragon (Haku)
    10: "役牌:場風牌",        # Prevalent Wind
    11: "役牌:自風牌",        # Seat Wind
    12: "一盃口",            # Pure Double Sequence
    13: "平和",              # Pinfu
    14: "断幺九",            # All Simples
    16: "対々和",            # All Triplets
    17: "七対子",            # Seven Pairs
    23: "三色同順",           # Mixed Triple Sequence
    27: "混一色",            # Half Flush
    49: "赤ドラ",            # Red Five
    50: "ドラ",              # Dora
    51: "裏ドラ",            # Uradora

    # below are unknowns
    900: "抜きドラ",          # Kita
    901: "槍槓",             # Robbing a Kan
    902: "嶺上開花",          # After a Kan
    903: "海底摸月",          # Under the Sea
    904: "河底撈魚",          # Under the River
    905: "ダブル立直",         # Double Riichi
    906: "混全帯幺九",        # Half Outside Hand
    907: "一気通貫",          # Pure Straight
    908: "三色同刻",           # Triple Triplets
    909: "三槓子",            # Three Quads
    910: "三暗刻",            # Three Concealed Triplets
    911: "小三元",            # Little Three Dragons
    912: "混老頭",            # All Terminals and Honours
    913: "二盃口",            # Twice Pure Double Sequence
    914: "純全帯幺九",        # Fully Outside Hand
    915: "清一色",            # Full Flush
    916: "人和",              # Hand of Man
    917: "天和",              # Blessing of Heaven
    918: "地和",              # Blessing of Earth
    919: "大三元",            # Big Three Dragons
    920: "四暗刻",            # Four Concealed Triplets
    921: "四暗刻単騎",         # Single-wait Four Concealed Triplets
    922: "字一色",            # All Honors
    923: "緑一色",            # All Green
    924: "清老頭",            # All Terminals
    925: "九蓮宝燈",          # Nine Gates
    926: "純正九蓮宝燈",       # True Nine Gates
    927: "国士無双十三面待ち",  # Thirteen-wait Thirteen Orphans
    928: "国士無双",          # Thirteen Orphans
    929: "大四喜",            # Four Big Winds
    930: "小四喜",            # Four Little Winds
    931: "四槓子",            # Four Quads
}
YAKUMAN = {
    'tenhou',
    'chiihou',
    'daisangen',
    'suuankou',
    'tsuuiisou',
    'ryuuiisou',
    'chinroutou',
    'kokushi musou',
    'shousuushi',
    'suukantsu',
    'chuurenpoutou',
    'paarenchan',
    'junsei chuurenpoutou',
    'suuankou tanki',
    'koushi musou 13-sided',
    'daisuushi',
    'renhou',
    'daisharin',
    'daichikurin',
    'daisuurin',
    'ishino uenimo sannan',
    'daichisei',
}
DOUBLE_YAKUMAN = {
    'junsei chuurenpoutou',
    'suuankou tanki',
    'koushi musou 13-sided',
    'daichisei',
}
TRANSLATE = {
    "流局": "ryuukyoku",
    "全員聴牌": "ryuukyoku",
    "全員不聴": "ryuukyoku",
    "流し満貫": "nagashi mangan",
    "九種九牌": "9 terminals draw",
    "四家立直": "4-riichi draw",
    "三家和了": "3-ron draw",
    "四槓散了": "4-kan draw",
    "四風連打": "4-wind draw",
    "満貫": "mangan",
    "跳満": "haneman",
    "倍満": "baiman",
    "三倍満": "sanbaiman",
    "役満": "yakuman",
    "門前清自摸和": "tsumo",
    "立直": "riichi",
    "槍槓": "chankan",
    "嶺上開花": "rinshan",
    "海底摸月": "haitei",
    "河底撈魚": "houtei",
    "役牌 白": "haku",
    "役牌 發": "hatsu",
    "役牌 中": "chun",
    "自風 東": "ton",
    "場風 東": "ton",
    "自風 南": "nan",
    "場風 南": "nan",
    "自風 西": "shaa",
    "場風 西": "shaa",
    "自風 北": "pei",
    "場風 北": "pei",
    "役牌:自風牌": "seat wind",
    "役牌:場風牌": "round wind",
    "断幺九": "tanyao",
    "一盃口": "iipeikou",
    "平和": "pinfu",
    "混全帯幺九": "chanta",
    "一気通貫": "iitsu",
    "三色同順": "sanshoku",
    "ダブル立直": "double riichi",
    "両立直": "double riichi",
    "三色同刻": "sanshoku doukou",
    "三槓子": "sankantsu",
    "対々和": "toitoi",
    "三暗刻": "sanankou",
    "小三元": "shousangen",
    "混老頭": "honroutou",
    "七対子": "chiitoitsu",
    "純全帯幺九": "junchan",
    "混一色": "honitsu",
    "二盃口": "ryanpeikou",
    "清一色": "chinitsu",
    "一発": "ippatsu",
    "ドラ": "dora",
    "赤ドラ": "aka",
    "裏ドラ": "ura",
    "抜きドラ": "kita",
    "天和": "tenhou",
    "地和": "chiihou",
    "大三元": "daisangen",
    "四暗刻": "suuankou",
    "字一色": "tsuuiisou",
    "緑一色": "ryuuiisou",
    "清老頭": "chinroutou",
    "国士無双": "kokushi musou",
    "小四喜": "shousuushi",
    "四槓子": "suukantsu",
    "九蓮宝燈": "chuurenpoutou",
    "八連荘": "paarenchan",
    "純正九蓮宝燈": "junsei chuurenpoutou",
    "四暗刻単騎": "suuankou tanki",
    "国士無双十三面待ち": "koushi musou 13-sided",
    "大四喜": "daisuushi",
    "燕返し": "tsubame gaeshi",
    "槓振り": "kanburi",
    "十二落抬": "shiiaruraotai",
    "五門斉": "uumensai",
    "三連刻": "sanrenkou",
    "一色三順": "isshokusanjun",
    "一筒摸月": "iipinmooyue",
    "九筒撈魚": "chuupinraoyui",
    "人和": "renhou",
    "大車輪": "daisharin",
    "大竹林": "daichikurin",
    "大数隣": "daisuurin",
    "石の上にも三年": "ishino uenimo sannan",
    "大七星": "daichisei",
}
PRED = {0:0,1:0,2:1,3:2,4:3,5:4,6:5,7:6,8:7,9:8, # get previous tile
        11:0,12:11,13:12,14:13,15:14,16:15,17:16,18:17,19:18, 
        21:0,22:21,23:22,24:23,25:24,26:25,27:26,28:27,29:28,
        31:0,32:31,33:32,34:33,35:34,36:35,37:36,38:37,39:38,
        41:0,42:0,43:0,44:0,45:0,46:0,47:0,51:14,52:24,53:34}
SUCC = {0:0,1:2,2:3,3:4,4:5,5:6,6:7,7:8,8:9,9:0, # get next tile
        11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19,19:0,
        21:22,22:23,23:24,24:25,25:26,26:27,27:28,28:29,29:0,
        31:32,32:33,33:34,34:35,35:36,36:37,37:38,38:39,39:0,
        41:0,42:0,43:0,44:0,45:0,46:0,47:0,51:16,52:26,53:36}
DORA_INDICATOR \
     = {0:0,11:19,12:11,13:12,14:13,15:14,16:15,17:16,18:17,19:18, # get dora indicator, given dora
            21:29,22:21,23:22,24:23,25:24,26:25,27:26,28:27,29:28,
            31:39,32:31,33:32,34:33,35:34,36:35,37:36,38:37,39:38,
            41:44,42:41,43:42,44:43,45:47,46:45,47:46,51:14,52:24,53:34}
DORA = {0:0,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19,19:11, # get dora, given dora indicator
            21:22,22:23,23:24,24:25,25:26,26:27,27:28,28:29,29:21,
            31:32,32:33,33:34,34:35,35:36,36:37,37:38,38:39,39:31,
            41:42,42:43,43:44,44:41,45:46,46:47,47:45,51:16,52:26,53:36}
TOGGLE_RED_FIVE = {15:51,25:52,35:53,51:15,52:25,53:35}
MANZU = {11,12,13,14,15,16,17,18,19,51}
PINZU = {21,22,23,24,25,26,27,28,29,52}
SOUZU = {31,32,33,34,35,36,37,38,39,53}
JIHAI = {41,42,43,44,45,46,47}
YAOCHUUHAI = {11,19,21,29,31,39,41,42,43,44,45,46,47}
TANYAOHAI = {12,13,14,15,16,17,18,22,23,24,25,26,27,28,32,33,34,35,36,37,38}

# SCORE[han][fu] = score
KO_RON_SCORE = defaultdict(lambda: defaultdict(lambda: 32000), {
    1: {30:1000,40:1300,50:1600,60:2000,70:2300,80:2600,90:2900,100:3200,110:3600},
    2: {20:1300,25:1600,30:2000,40:2600,50:3200,60:3900,70:4500,80:5200,90:5800,100:6400,110:7100},
    3: {20:2600,25:3200,30:3900,40:5200,50:6400,60:7700,70:8000,80:8000,90:8000,100:8000,110:8000},
    4: {20:5200,25:6400,30:7700,40:8000,50:8000,60:8000,70:8000,80:8000,90:8000,100:8000,110:8000},
    5: defaultdict(lambda: 8000),
    6: defaultdict(lambda: 12000),
    7: defaultdict(lambda: 12000),
    8: defaultdict(lambda: 16000),
    9: defaultdict(lambda: 16000),
    10: defaultdict(lambda: 16000),
    11: defaultdict(lambda: 24000),
    12: defaultdict(lambda: 24000),
    13: defaultdict(lambda: 32000),
})
OYA_RON_SCORE = defaultdict(lambda: defaultdict(lambda: 48000), {
    1: {30:1500,40:2000,50:2400,60:2900,70:3400,80:3900,90:4400,100:4800,110:5300},
    2: {20:2000,25:2400,30:2900,40:3900,50:4800,60:5800,70:6800,80:7700,90:8700,100:9600,110:10600},
    3: {20:3900,25:4800,30:5800,40:7700,50:9600,60:11600,70:12000,80:12000,90:12000,100:12000,110:12000},
    4: {20:5200,25:9600,30:11600,40:12000,50:12000,60:12000,70:12000,80:12000,90:12000,100:12000,110:12000},
    5: defaultdict(lambda: 12000),
    6: defaultdict(lambda: 18000),
    7: defaultdict(lambda: 18000),
    8: defaultdict(lambda: 24000),
    9: defaultdict(lambda: 24000),
    10: defaultdict(lambda: 24000),
    11: defaultdict(lambda: 36000),
    12: defaultdict(lambda: 36000),
    13: defaultdict(lambda: 48000),
})

KO_TSUMO_SCORE = defaultdict(lambda: defaultdict(lambda: 8000), {
    1: {30:300,40:400,50:400,60:500,70:600,80:700,90:800,100:800,110:900},
    2: {20:400,25:400,30:500,40:700,50:800,60:1000,70:1200,80:1300,90:1500,100:1600,110:1800},
    3: {20:700,25:800,30:1000,40:1300,50:1600,60:2000,70:2000,80:2000,90:2000,100:2000,110:2000},
    4: {20:1300,25:1600,30:2000,40:2000,50:2000,60:2000,70:2000,80:2000,90:2000,100:2000,110:2000},
    5: defaultdict(lambda: 2000),
    6: defaultdict(lambda: 3000),
    7: defaultdict(lambda: 3000),
    8: defaultdict(lambda: 4000),
    9: defaultdict(lambda: 4000),
    10: defaultdict(lambda: 4000),
    11: defaultdict(lambda: 6000),
    12: defaultdict(lambda: 6000),
    13: defaultdict(lambda: 8000),
})
OYA_TSUMO_SCORE = defaultdict(lambda: defaultdict(lambda: 16000), {
    1: {30:500,40:700,50:800,60:1000,70:1200,80:1300,90:1500,100:1600,110:1800},
    2: {20:700,25:800,30:1000,40:1300,50:1600,60:2000,70:2300,80:2600,90:2900,100:3200,110:3600},
    3: {20:1300,25:1600,30:2000,40:2600,50:3200,60:3900,70:4000,80:4000,90:4000,100:4000,110:4000},
    4: {20:2600,25:3200,30:3900,40:4000,50:4000,60:4000,70:4000,80:4000,90:4000,100:4000,110:4000},
    5: defaultdict(lambda: 4000),
    6: defaultdict(lambda: 6000),
    7: defaultdict(lambda: 6000),
    8: defaultdict(lambda: 8000),
    9: defaultdict(lambda: 8000),
    10: defaultdict(lambda: 8000),
    11: defaultdict(lambda: 12000),
    12: defaultdict(lambda: 12000),
    13: defaultdict(lambda: 16000),
})
