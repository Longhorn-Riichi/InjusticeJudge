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
LIMIT_HANDS = {2: "満貫", 3: "満貫", 4: "満貫", 5: "満貫",
               6: "跳満", 7: "跳満",
               8: "倍满", 9: "倍满", 10: "倍满",
               11: "三倍满", 12: "三倍满",
               13: "役満", 14: "役満", 15: "役満", 16: "役満", 17: "役満", 18: "役満"}
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

###
### utility functions
###

def pt(tile: int) -> str:
    """print tile (2-char representation)"""
    TILE_REPRS = "🀇🀈🀉🀊🀋🀌🀍🀎🀏🀙🀚🀛🀜🀝🀞🀟🀠🀡🀐🀑🀒🀓🀔🀕🀖🀗🀘🀀🀁🀂🀃🀆🀅🀄︎"
    if tile < 20:
        return TILE_REPRS[tile - 11] + " "
    elif tile < 30:
        return TILE_REPRS[tile - 21 + 9] + " "
    elif tile < 40:
        return TILE_REPRS[tile - 31 + 18] + " "
    elif tile < 47:
        return TILE_REPRS[tile - 41 + 27] + " "
    elif tile == 47:
        # need to specially output 🀄︎ so it's not an emoji
        return TILE_REPRS[-2:]
    elif tile == 51:
        return "🀋·"
    elif tile == 52:
        return "🀝·"
    elif tile == 53:
        return "🀔·"
    else:
        return "??"
ph = lambda hand: "".join(map(pt, hand)) # print hand
remove_red_five = lambda tile: TOGGLE_RED_FIVE[tile] if tile in {51,52,53} else tile
remove_red_fives = lambda hand: map(remove_red_five, hand)
sorted_hand = lambda hand: tuple(sorted(hand, key=remove_red_five))
round_name = lambda rnd, honba: (f"East {rnd+1}" if rnd <= 3 else f"South {rnd-3}") + ("" if honba == 0 else f"-{honba}")
relative_seat_name = lambda you, other: {0: "self", 1: "shimocha", 2: "toimen", 3: "kamicha"}[(other-you)%4]
