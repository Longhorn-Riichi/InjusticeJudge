from typing import *
from .constants import YAOCHUUHAI
from .utils import remove_red_fives

# all of these functions assume the passed-in hand is a 13-tile tenpai hand

# (tenpai hand, calls) -> is it yakuman?
CheckYakumanFunc = Callable[[List[int], List[int]], bool]

# daisangen tenpai if we have 8 tiles of dragons (counting each dragon at most 3 times)
is_daisangen: CheckYakumanFunc = lambda hand, calls: sum(min(3, hand.count(tile)) for tile in {45,46,47}) >= 8

# kokushi musou tenpai if we have at least 12 terminal/honors
is_kokushi: CheckYakumanFunc = lambda hand, calls: len(YAOCHUUHAI.intersection(hand)) >= 12

# suuankou tenpai if hand is closed and we have 4 triplets, or 3 triplets and two pairs
# which is to say, 3+ triplets + at most one unpaired tile
is_suuankou: CheckYakumanFunc = lambda hand, calls: len(calls) == 0 and (mults := list(Counter(hand).values()), mults.count(3) >= 3 and mults.count(1) <= 1)[1]

# shousuushi if we have exactly 10 winds (counting each wind at most 3 times)
# OR 11 tiles of winds + no pair (i.e. only 6 kinds of tiles in hand)
is_shousuushi: CheckYakumanFunc = lambda hand, calls: (count := sum(min(3, hand.count(tile)) for tile in {41,42,43,44}), count == 10 or count == 11 and len(set(remove_red_fives(hand))) == 6)[1]

# daisuushi if we have 12 tiles of winds (counting each wind at most 3 times)
# OR 11 tiles of winds + a pair (i.e. only 5 kinds of tiles in hand)
is_daisuushi: CheckYakumanFunc = lambda hand, calls: (count := sum(min(3, hand.count(tile)) for tile in {41,42,43,44}), count == 12 or count == 11 and len(set(remove_red_fives(hand))) == 5)[1]

# tsuuiisou tenpai if all the tiles are honor tiles
is_tsuuiisou: CheckYakumanFunc = lambda hand, calls: set(hand) - {41,42,43,44,45,46,47} == set()

# ryuuiisou tenpai if all the tiles are 23468s6z
is_ryuuiisou: CheckYakumanFunc = lambda hand, calls: set(hand) - {32,33,34,36,38,46} == set()

# chinroutou tenpai if all the tiles are 19m19p19s
is_chinroutou: CheckYakumanFunc = lambda hand, calls: set(hand) - {11,19,21,29,31,39} == set()

# chuuren poutou tenpai if hand is closed and we are missing at most one tile
#   out of the required 1112345678999
CHUUREN_TILES = Counter([1,1,1,2,3,4,5,6,7,8,9,9,9])
is_chuuren: CheckYakumanFunc = lambda hand, calls: len(calls) == 0 and all(tile < 40 for tile in hand) and (ctr := Counter([t % 10 for t in remove_red_fives(hand)]), sum((CHUUREN_TILES - (CHUUREN_TILES & ctr)).values()) <= 1)[1]

# note: evaluating {suukantsu, tenhou, chiihou, kazoe} requires information outside of the hand

CHECK_YAKUMAN = {"daisangen": is_daisangen,
                 "kokushi": is_kokushi,
                 "suuankou": is_suuankou,
                 "shousuushi": is_shousuushi,
                 "daisuushi": is_daisuushi,
                 "tsuuiisou": is_tsuuiisou,
                 "ryuuiisou": is_ryuuiisou,
                 "chinroutou": is_chinroutou,
                 "chuuren": is_chuuren}
get_yakuman_tenpais = lambda hand, calls: {name for name, func in CHECK_YAKUMAN.items() if func(hand, calls)}

def test_get_yakuman_tenpais():
    print("daisangen:")
    assert get_yakuman_tenpais([11,12,13,22,22,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,22,45,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,45,45,45,45,46,46,46,47,47,47], [47,47,47]) == {"daisangen"}
    assert get_yakuman_tenpais([11,12,13,45,45,45,45,46,46,46,47,11,11], []) == set()

    assert get_yakuman_tenpais([11,19,21,29,29,31,39,41,42,43,44,45,47], []) == {"kokushi"}
    assert get_yakuman_tenpais([11,19,21,29,29,29,39,41,42,43,44,45,46], []) == set()

    print("suuankou:")
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,13,14,14,15,15,15], []) == {"suuankou"}
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,14,14,14,15,15,15], []) == {"suuankou"}
    assert get_yakuman_tenpais([11,11,11,12,12,12,13,14,14,14,15,15,15], [15,15,15]) == set()

    print("shousuushi/daisuushi:")
    assert get_yakuman_tenpais([11,12,13,41,42,42,42,43,43,43,44,44,44], []) == {"shousuushi"}
    assert get_yakuman_tenpais([11,12,41,41,42,42,42,43,43,43,44,44,44], []) == {"shousuushi"}
    assert get_yakuman_tenpais([11,12,13,14,42,42,42,43,43,43,44,44,44], []) == set()
    assert get_yakuman_tenpais([11,11,41,41,42,42,42,43,43,43,44,44,44], []) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais([11,41,41,41,42,42,42,43,43,43,44,44,44], []) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais([11,41,41,41,42,42,42,43,43,43,44,44,44], [44,44,44]) == {"daisuushi"}

    print("tsuuiisou:")
    assert get_yakuman_tenpais([41,41,42,42,43,43,44,44,45,45,46,46,47], []) == {"tsuuiisou"}
    assert get_yakuman_tenpais([45,45,45,46,46,47,47,47,41,41,41,42,42], [41,41,41]) == {"daisangen", "tsuuiisou"}
    assert get_yakuman_tenpais([41,41,42,42,42,43,43,43,44,47,47,11,12], []) == set()
    assert get_yakuman_tenpais([41,41,41,42,42,42,43,43,43,44,44,44,45], []) == {"suuankou", "daisuushi", "tsuuiisou"}

    print("ryuuiisou:")
    assert get_yakuman_tenpais([32,32,33,33,34,34,36,36,36,38,38,46,46], []) == {"ryuuiisou"}
    assert get_yakuman_tenpais([22,22,23,23,24,24,26,26,26,28,28,46,46], []) == set()

    print("chinroutou:")
    assert get_yakuman_tenpais([11,11,11,19,19,21,21,21,29,29,29,31,31], []) == {"suuankou", "chinroutou"}
    assert get_yakuman_tenpais([11,11,11,19,19,21,21,21,29,29,29,31,31], [29,29,29]) == {"chinroutou"}

    print("chuurenpoutou:")
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,19], []) == {"chuuren"}
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,19], [19,19,19]) == set()
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,19,11], []) == {"chuuren"}
    assert get_yakuman_tenpais([11,11,11,12,13,14,15,16,17,18,19,11,11], []) == set()

