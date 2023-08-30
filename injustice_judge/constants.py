from dataclasses import dataclass, field
from collections import defaultdict
from typing import *

# This file contains every lookup table used in InjusticeJudge.
# A summary:
#   SHANTEN_NAMES: the printed name for each number internally representing of a type of shanten
#      PLACEMENTS: the printed name of a placement (1 -> "1st")
#      YAKU_NAMES: maps mahjong soul yaku IDs to tenhou yaku names
#         YAKUMAN: the yakuman subset of YAKU_NAMES
#     LIMIT_HANDS: a mapping from han to tenhou's limit hand name
#       TRANSLATE: a big maps from all Japanese terms to English terms
#       PRED/SUCC: get the predecessor/successor of a number tile, 0 if nonexistent
#  DORA_INDICATOR: map from a dora to its indicator
#            DORA: map from a dora indicator to its indicated dora
# TOGGLE_RED_FIVE: maps a five to its red equivalent and vice versa
#      YAOCHUUHAI: a set of all terminal and honor tiles
#    KO_RON_SCORE: nondealer ron score for a given han and fu
#   OYA_RON_SCORE: dealer ron score for a given han and fu
#  KO_TSUMO_SCORE: tsumo points paid by nondealers for a given han and fu
# OYA_TSUMO_SCORE: tsumo points paid by the dealer for a given han and fu
#   DISCORD_TILES: Discord emoji representation of each tile, used for the Discord bot
#                  There is also DISCORD_CALLED_TILES which is for sideways tiles

SHANTEN_NAMES = {
    0: "tenpai",
    1: "unknown iishanten", # unused
    1.05: "kokushi musou iishanten",
    1.1: "kutsuki iishanten",
    1.2: "headless iishanten",
    1.22: "perfect headless iishanten",
    1.23: "headless iishanten",
    1.24: "headless iishanten",
    1.32: "perfect iishanten",
    1.3: "imperfect iishanten",
    1.4: "floating iishanten",
    1.5: "chiitoitsu iishanten",
    1.6: "kutsuki chiitoi iishanten",
    1.7: "headless chiitoi iishanten",
    1.72: "headless chiitoi iishanten",
    1.73: "headless chiitoi iishanten",
    1.74: "headless chiitoi iishanten",
    1.82: "perfect chiitoi iishanten",
    1.83: "imperfect chiitoi iishanten",
    1.9: "floating chiitoi iishanten",
    2: "2-shanten",
    3: "3-shanten",
    4: "4-shanten",
    5: "5-shanten",
    6: "6-shanten"
}
PLACEMENTS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

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
LIMIT_HANDS = {2: "満貫", 3: "満貫", 4: "満貫", 5: "満貫",
               6: "跳満", 7: "跳満",
               8: "倍満", 9: "倍満", 10: "倍満",
               11: "三倍満", 12: "三倍満",
               13: "役満", 14: "役満", 15: "役満", 16: "役満", 17: "役満", 18: "役満"}
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

# SCORE[han][fu] = score
KO_RON_SCORE = {
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
}
OYA_RON_SCORE = {
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
}

KO_TSUMO_SCORE = {
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
}
OYA_TSUMO_SCORE = {
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
}

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
    11: "<:1M:1143300025863123046>",
    12: "<:2M:1143300036097220658>",
    13: "<:3M:1143300105886236682>",
    14: "<:4M:1143316151015850136>",
    15: "<:5M:1143316144183324683>",
    16: "<:6M:1143316186218627142>",
    17: "<:7M:1143316179818119251>",
    18: "<:8M:1143316207915778208>",
    19: "<:9M:1143316202161197198>",
    51: "<:0M:1143300021635268774>",

    21: "<:1P:1143300032213299290>",
    22: "<:2P:1143300038144045177>",
    23: "<:3P:1143300107702374511>",
    24: "<:4P:1143316158150344825>",
    25: "<:5P:1143316145257062490>",
    26: "<:6P:1143316187783110778>",
    27: "<:7P:1143316180778619013>",
    28: "<:8P:1143316199095156856>",
    29: "<:9P:1143316205021696000>",
    52: "<:0P:1143300023703048343>",

    31: "<:1S:1143300034486607872>",
    32: "<:2S:1143300104808313032>",
    33: "<:3S:1143316064613175488>",
    34: "<:4S:1143316159052128287>",
    35: "<:5S:1143316147488432148>",
    36: "<:6S:1143316190240972811>",
    37: "<:7S:1143316182351482920>",
    38: "<:8S:1143316200403783701>",
    39: "<:9S:1143316207001411694>",
    53: "<:0S:1143300024625795102>",

    41: "<:1Z:1143315859708850236>",
    42: "<:2Z:1143315875391361215>",
    43: "<:3Z:1143315890771853312>",
    44: "<:4Z:1143316160520134686>",
    45: "<:5Z:1143316148578947102>",
    46: "<:6Z:1143316177708400802>",
    47: "<:7Z:1143316185061015552>",

    50: "<:1X:1143315813588291606>",
}
