from typing import *

###
### types
###

Kyoku = Dict[str, Any]

###
### lookup tables
###

SHANTEN_NAMES = {
    0: "tenpai",
    1: "iishanten", # unused
    1.1: "kutsuki iishanten",
    1.2: "headless iishanten",
    1.23: "headless complete iishanten",
    1.24: "headless floating iishanten",
    1.3: "complete iishanten",
    1.4: "floating tile iishanten",
    1.5: "chiitoitsu iishanten",
    1.6: "kokushi musou iishanten",
    2: "2-shanten",
    3: "3-shanten",
    4: "4-shanten",
    5: "5-shanten",
    6: "6-shanten"
}
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
               8: "倍满", 9: "倍满", 10: "倍满",
               11: "三倍满", 12: "三倍满",
               13: "役満", 14: "役満", 15: "役満", 16: "役満", 17: "役満", 18: "役満"}
TRANSLATE = {
    "流局": "ryuukyoku",
    "全員聴牌": "ryuukyoku",
    "流し満貫": "nagashi mangan",
    "九種九牌": "9 terminals draw",
    "四家立直": "4-riichi draw",
    "三家和了": "3-ron draw",
    "四槓散了": "4-kan draw",
    "四風連打": "4-wind draw",
    "満貫": "mangan",
    "跳満": "haneman",
    "倍满": "baiman",
    "三倍满": "sanbaiman",
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
    "三色同刻": "sanshoku doukou",
    "三槓子": "sankantsu",
    "対々和": "toitoi",
    "三暗刻": "sanankou",
    "小三元": "shousangen",
    "混老頭": "honroutou",
    "七対子": " chiitoitsu",
    "純全帯幺九": "junchan",
    "混一色": "honitsu",
    "二盃口": "ryanpeikou",
    "清一色": "chinitsu",
    "一発": "ippatsu",
    "ドラ": "dora",
    "赤ドラ": "akadora",
    "裏ドラ": "uradora",
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
            41:47,42:41,43:42,44:43,45:44,46:45,47:46}
TOGGLE_RED_FIVE = {15:51,25:52,35:53,51:15,52:25,53:35}
YAOCHUUHAI = {11,19,21,29,31,39,41,42,43,44,45,46,47}

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
    47: "<:7z:1142987164406259733>"
}
