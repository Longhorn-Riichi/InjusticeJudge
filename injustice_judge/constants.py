from dataclasses import dataclass, field
from collections import defaultdict
from typing import *

# This file contains every lookup table used in InjusticeJudge.
# A summary:
#   SHANTEN_NAMES: the printed name for each number internally representing of a type of shanten
#      PLACEMENTS: the printed name of a placement (1 -> "1st")
#     LIMIT_HANDS: maps han count to tenhou limit hand name
#      YAKU_NAMES: maps mahjong soul yaku IDs to tenhou yaku names
#         YAKUMAN: the yakuman subset of YAKU_NAMES
#       TRANSLATE: a big map from all Japanese terms to English terms
#       PRED/SUCC: get the predecessor/successor of a number tile, 0 if nonexistent
#  DORA_INDICATOR: map from a dora to its indicator
#            DORA: map from a dora indicator to its indicated dora
# TOGGLE_RED_FIVE: maps a five to its red equivalent and vice versa
#      YAOCHUUHAI: a set of all terminal and honor tiles
#       TANYAOHAI: a set of all 2-8 tiles
#    KO_RON_SCORE: nondealer ron score for a given han and fu
#   OYA_RON_SCORE: dealer ron score for a given han and fu
#  KO_TSUMO_SCORE: tsumo points paid by nondealers for a given han and fu
# OYA_TSUMO_SCORE: tsumo points paid by the dealer for a given han and fu
#   DISCORD_TILES: Discord emoji representation of each tile, used for the Discord bot
#                  There is also DISCORD_CALLED_TILES which is for sideways tiles
#                  as well as DISCORD_DORA_TILES and DISCORD_CALLED_DORA_TILES

SHANTEN_NAMES = {
    0: "tenpai",
    1: "unknown iishanten", # unused
    1.200: "kokushi musou iishanten",
    1.010: "headless iishanten",
    1.020: "kuttsuki iishanten",
    1.030: "kuttsuki headless iishanten",
    1.100: "chiitoitsu iishanten",
    1.110: "chiitoi headless iishanten",
    1.120: "chiitoi kuttsuki iishanten",
    1.130: "chiitoi kuttsuki headless iishanten",
    1.001: "floating iishanten",
    1.011: "floating headless iishanten",
    1.021: "floating kuttsuki iishanten",
    1.031: "floating headless kuttsuki iishanten",
    1.101: "floating chiitoi iishanten",
    1.111: "floating chiitoi headless iishanten",
    1.121: "floating chiitoi kuttsuki iishanten",
    1.131: "floating chiitoi headless kuttsuki iishanten",
    1.002: "imperfect iishanten",
    1.012: "imperfect headless iishanten",
    1.022: "imperfect kuttsuki iishanten",
    1.032: "imperfect headless kuttsuki iishanten",
    1.102: "imperfect chiitoi iishanten",
    1.112: "imperfect chiitoi headless iishanten",
    1.122: "imperfect chiitoi kuttsuki iishanten",
    1.132: "imperfect chiitoi headless kuttsuki iishanten",
    1.003: "perfect iishanten",
    1.013: "perfect headless iishanten",
    1.023: "perfect kuttsuki iishanten",
    1.033: "perfect headless kuttsuki iishanten",
    1.103: "perfect chiitoi iishanten",
    1.113: "perfect chiitoi headless iishanten",
    1.123: "perfect chiitoi kuttsuki iishanten",
    1.133: "perfect chiitoi headless kuttsuki iishanten",
    2: "2-shanten",
    3: "3-shanten",
    4: "4-shanten",
    5: "5-shanten",
    6: "6-shanten"
}
# SHANTEN_NAMES = {
#     0: "tenpai",
# # TODO make these all like 1.11111 where each one denotes a type of iishanten included
#     1: "unknown iishanten", # unused
#     1.05: "kokushi musou iishanten",
#     1.1: "kuttsuki iishanten",
#     1.12: "perfect kuttsuki iishanten",
#     1.13: "kuttsuki iishanten",
#     1.14: "floating kuttsuki iishanten",
#     1.15: "kuttsuki headless iishanten",
#     1.17: "kuttsuki headless iishanten",
#     1.18: "kuttsuki headless iishanten",
#     1.19: "kuttsuki headless iishanten",
#     1.2: "headless iishanten",
#     1.22: "perfect headless iishanten",
#     1.23: "headless iishanten",
#     1.24: "floating headless iishanten",
#     1.32: "perfect iishanten",
#     1.3: "imperfect iishanten",
#     1.4: "floating iishanten",
#     1.5: "chiitoitsu iishanten",
#     1.6: "kuttsuki chiitoi iishanten",
#     1.62: "kuttsuki chiitoi iishanten",
#     1.63: "kuttsuki chiitoi iishanten",
#     1.64: "kuttsuki chiitoi iishanten",
#     1.65: "kuttsuki chiitoi iishanten",
#     1.67: "kuttsuki chiitoi iishanten",
#     1.68: "kuttsuki chiitoi iishanten",
#     1.69: "kuttsuki chiitoi iishanten",
#     1.7: "headless chiitoi iishanten",
#     1.72: "headless chiitoi iishanten",
#     1.73: "headless chiitoi iishanten",
#     1.74: "headless chiitoi iishanten",
#     1.82: "perfect chiitoi iishanten",
#     1.83: "imperfect chiitoi iishanten",
#     1.9: "floating chiitoi iishanten",
#     2: "2-shanten",
#     3: "3-shanten",
#     4: "4-shanten",
#     5: "5-shanten",
#     6: "6-shanten"
# }
PLACEMENTS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

LIMIT_HANDS = defaultdict(lambda: "役満", {
                0: "", 1: "", 2: "",
                3: "満貫", 4: "満貫", 5: "満貫",
                6: "跳満", 7: "跳満",
                8: "倍満", 9: "倍満", 10: "倍満",
                11: "三倍満", 12: "三倍満"})
YAKU_NAMES = {
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
    18: "ダブル立直",         # Double riichi
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
    64: "大七星",            # Big Seven Star
}
YAKUMAN = {
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
    59: "人和",              # Hand of Man
    60: "大車輪",            # Big Wheels
    61: "大竹林",            # Bamboo Forest
    62: "大数隣",            # Numerous Neighbours
    63: "石の上にも三年",      # Ishinouenimosannen
    64: "大七星",            # Big Seven Star
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
    "自風 北": "pei",
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
    "石の上にも三年": "ishinouenimosannan",
    "大七星": "daishichisei",
}
PRED = {0:0,11:0,12:11,13:12,14:13,15:14,16:15,17:16,18:17,19:18, # get previous tile
            21:0,22:21,23:22,24:23,25:24,26:25,27:26,28:27,29:28,
            31:0,32:31,33:32,34:33,35:34,36:35,37:36,38:37,39:38,
            41:0,42:0,43:0,44:0,45:0,46:0,47:0,51:14,52:24,53:34}
SUCC = {0:0,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19,19:0, # get next tile
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

DISCORD_TILES = {
    11: "<:1m:1142707135021600830>",
    12: "<:2m:1142707491713593355>",
    13: "<:3m:1142707570251939880>",
    14: "<:4m:1142707571120160810>",
    15: "<:5m:1142707573192138792>",
    16: "<:6m:1142707574119079936>",
    17: "<:7m:1142707575108931665>",
    18: "<:8m:1142707576740520006>",
    19: "<:9m:1142707577357082655>",
    51: "<:0m:1142997164679770152>",

    21: "<:1p:1142707873802113044>",
    22: "<:2p:1142707875261726772>",
    23: "<:3p:1142707876159291512>",
    24: "<:4p:1142707877002358847>",
    25: "<:5p:1142707923605270590>",
    26: "<:6p:1142707925475930153>",
    27: "<:7p:1142707927292055562>",
    28: "<:8p:1142707928239964160>",
    29: "<:9p:1142707928885887040>",
    52: "<:0p:1142997170870550538>",

    31: "<:1s:1142707987526459455>",
    32: "<:2s:1142707989405519973>",
    33: "<:3s:1142707991351672982>",
    34: "<:4s:1142707992580603914>",
    35: "<:5s:1142707996460335155>",
    36: "<:6s:1142986859488751646>",
    37: "<:7s:1142986876144340992>",
    38: "<:8s:1142986885195640972>",
    39: "<:9s:1142986898017636382>",
    53: "<:0s:1142997176641929347>",

    41: "<:1z:1142986930422820996>",
    42: "<:2z:1142986936223531028>",
    43: "<:3z:1142987133599105065>",
    44: "<:4z:1142987139311734856>",
    45: "<:5z:1142987150984482989>",
    46: "<:6z:1142987158920106104>",
    47: "<:7z:1142987164406259733>",

    50: "<:1x:1142987199369986179>",
}

DISCORD_CALLED_TILES = {
    11: "<:1M:1147238374088917185>",
    12: "<:2M:1147238407597211768>",
    13: "<:3M:1147238414157095033>",
    14: "<:4M:1147238465247924225>",
    15: "<:5M:1147238469979095131>",
    16: "<:6M:1147238492120809472>",
    17: "<:7M:1147238496591954077>",
    18: "<:8M:1147238508839313540>",
    19: "<:9M:1147238545438818405>",
    51: "<:0M:1147238370435678228>",

    21: "<:1P:1147238375204593675>",
    22: "<:2P:1147238408595451906>",
    23: "<:3P:1147238415084027995>",
    24: "<:4P:1147238466766262332>",
    25: "<:5P:1147238472080445571>",
    26: "<:6P:1147238493714665472>",
    27: "<:7P:1147238498508738723>",
    28: "<:8P:1147238510600925337>",
    29: "<:9P:1147238544088240189>",
    52: "<:0P:1147238371161276477>",

    31: "<:1S:1147238377335300106>",
    32: "<:2S:1147238410877161483>",
    33: "<:3S:1147238416325558292>",
    34: "<:4S:1147238467735138394>",
    35: "<:5S:1147238473145794711>",
    36: "<:6S:1147238494620635136>",
    37: "<:7S:1147238499502788829>",
    38: "<:8S:1147238511720812614>",
    39: "<:9S:1147238562060828743>",
    53: "<:0S:1147238373099057172>",

    41: "<:1Z:1147238379499565088>",
    42: "<:2Z:1147238412374511776>",
    43: "<:3Z:1147238418477236346>",
    44: "<:4Z:1147238469140234260>",
    45: "<:5Z:1147238474282455100>",
    46: "<:6Z:1147238495723720776>",
    47: "<:7Z:1147238500727537774>",

    50: "<:1X:1147238378685861908>",
}

DISCORD_DORA_TILES = {
    11: "<:1md:1147275913319428216>",
    12: "<:2md:1147276023642210304>",
    13: "<:3md:1147276030151766037>",
    14: "<:4md:1147276133956591666>",
    15: "<:5md:1147276140088672417>",
    16: "<:6md:1147276278437773372>",
    17: "<:7md:1147276284318191687>",
    18: "<:8md:1147276427784355880>",
    19: "<:9md:1147276431957696632>",
    51: "<:0md:1147275908399509657>",

    21: "<:1pd:1147275914896494642>",
    22: "<:2pd:1147276025835835594>",
    23: "<:3pd:1147276031456202783>",
    24: "<:4pd:1147276135151980634>",
    25: "<:5pd:1147276141191778334>",
    26: "<:6pd:1147276280400711740>",
    27: "<:7pd:1147276285303853147>",
    28: "<:8pd:1147276428841341018>",
    29: "<:9pd:1147276433098559668>",
    52: "<:0pd:1147275909691346984>",

    31: "<:1sd:1147275915932467323>",
    32: "<:2sd:1147276027123482684>",
    33: "<:3sd:1147276032441860186>",
    34: "<:4sd:1147276136900993114>",
    35: "<:5sd:1147276142399717427>",
    36: "<:6sd:1147276281818398943>",
    37: "<:7sd:1147276286172090571>",
    38: "<:8sd:1147276430946865337>",
    39: "<:9sd:1147276434730139779>",
    53: "<:0sd:1147275911922729091>",

    41: "<:1zd:1147275919380185150>",
    42: "<:2zd:1147276027949764669>",
    43: "<:3zd:1147276033549152286>",
    44: "<:4zd:1147276138155089990>",
    45: "<:5zd:1147276143125352449>",
    46: "<:6zd:1147276282866966538>",
    47: "<:7zd:1147276287581372556>",

    50: "<:1xd:1147275917404680375>",
}

DISCORD_CALLED_DORA_TILES = {
    11: "<:1Md:1147277392931459156>",
    12: "<:2Md:1147277545868382328>",
    13: "<:3Md:1147277551765573735>",
    14: "<:4Md:1147277711652425788>",
    15: "<:5Md:1147277717113413632>",
    16: "<:6Md:1147277954922061945>",
    17: "<:7Md:1147277963688165406>",
    18: "<:8Md:1147278119145853038>",
    19: "<:9Md:1147278123046555781>",
    51: "<:0Md:1147277387747315782>",

    21: "<:1Pd:1147277394789539952>",
    22: "<:2Pd:1147277546929524797>",
    23: "<:3Pd:1147277552805748977>",
    24: "<:4Pd:1147277713141407825>",
    25: "<:5Pd:1147277719080542341>",
    26: "<:6Pd:1147277958592073801>",
    27: "<:7Pd:1147277965432987770>",
    28: "<:8Pd:1147278120248954890>",
    29: "<:9Pd:1147278124262887534>",
    52: "<:0Pd:1147277389622149355>",

    31: "<:1Sd:1147277396328845372>",
    32: "<:2Sd:1147277548733071440>",
    33: "<:3Sd:1147277554156306503>",
    34: "<:4Sd:1147277714735247543>",
    35: "<:5Sd:1147277720095572099>",
    36: "<:6Sd:1147277959716159649>",
    37: "<:7Sd:1147277967286861916>",
    38: "<:8Sd:1147278121926668348>",
    39: "<:9Sd:1147278126502653952>",
    53: "<:0Sd:1147277391660580954>",

    41: "<:1Zd:1147277398727991387>",
    42: "<:2Zd:1147277550029123654>",
    43: "<:3Zd:1147277555351687268>",
    44: "<:4Zd:1147277715968372747>",
    45: "<:5Zd:1147277721701986335>",
    46: "<:6Zd:1147277961196748853>",
    47: "<:7Zd:1147277968419344504>",

    50: "<:1Xd:1147277396878299148>",
}
