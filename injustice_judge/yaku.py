from typing import *
from .classes import CallInfo, GameRules, Interpretation
from .classes2 import Kyoku, Hand, Score
from .constants import Event, Shanten, YakuForWait, LIMIT_HANDS, YAOCHUUHAI
from .display import ph, pt, round_name, shanten_name
from .utils import get_score, get_taatsu_wait, is_mangan, normalize_red_five, normalize_red_fives, sorted_hand
from pprint import pprint

# This file details some algorithms for checking the yaku of a given `Hand` object.
# It's used in `fetch.py` and `flags.py` to calculate some information that will be
#   included in their event list and flags list respectively.
# 
# Every single yaku is handled by get_yaku, but the logic is split up:
# 
# - get_stateless_yaku checks for all yaku which only require a look at hand
#   composition (tanyao, honroutou, toitoi, honitsu, chinitsu, pinfu, iitsu,
#   sanshoku, sanshoku doukou, iipeikou, ryanpeikou, chanta, junchan,
#   chiitoitsu, sanankou in hand, sankantsu, shousangen)
# - add_stateful_yaku adds all yaku which require game state to evaluate
#   (dora/aka/ura/kita, yakuhai, riichi, ippatsu, chankan, rinshan, houtei)
# - add_tsumo_yaku adds all yaku which are dependent on tsumo
#   (menzentsumo, sanankou shanpon wait, haitei)
# - finally, add_yakuman adds all yakuman. (kazoe yakuman, daisangen, kokushi,
#   suuankou, shousuushi, daisuushi, tsuuiisou, ryuuiisou, chinroutou,
#   chuurenpoutou, suukantsu, tenhou, chiihou, 13-sided kokushi, suuankou
#   tanki, junsei chuurenpoutou, and any valid combinations of yakuman,
#   and also renhou mangan if enabled)
# 
# This accounts for every standard yaku in the game plus renhou, except for
# nagashi mangan, which is handled as a draw instead of as a winning hand.

###
### yaku calculation
###

# checks for:
# - tanyao, honroutou, toitoi, chinitsu, honitsu, shousangen,
# - pinfu, iitsu, sanshoku, sanshoku doukou, 
# - iipeikou, ryanpeikou, junchan, chanta, chiitoitsu
# - sanankou, sankantsu
def get_stateless_yaku(interpretation: Interpretation, shanten: Shanten, is_closed_hand: bool) -> YakuForWait:
    if shanten[0] != 0:
        return {}
    waits = interpretation.get_waits()
    assert len(waits) > 0, "hand is tenpai, but has no waits?"

    # remove all red fives from the interpretation
    taatsu, ron_fu, tsumo_fu, sequences, triplets, pair = interpretation.unpack()
    taatsu = sorted_hand(normalize_red_fives(taatsu))
    sequences = tuple(tuple(normalize_red_fives(seq)) for seq in sequences)
    triplets = tuple(tuple(normalize_red_fives(tri)) for tri in triplets)
    pair_tile = None if pair is None else normalize_red_five(pair[0])

    # filter for only waits that satisfy this interpretation
    if len(taatsu) == 1: # tanki
        waits &= set(taatsu)
    elif len(taatsu) == 2:
        if taatsu[0] == taatsu[1] and pair_tile is not None: # shanpon
            waits &= {taatsu[0], pair_tile}
        else: # penchan, kanchan, ryanmen
            waits &= get_taatsu_wait(taatsu)
    if len(waits) == 0:
        return {}

    # get the full hand (for checking chiitoitsu)
    full_hand = (*taatsu,
                 *(tile for seq in sequences for tile in seq),
                 *(tile for tri in triplets for tile in tri),
                 *(() if pair is None else pair))
    assert len(full_hand) == 13, f"somehow got a length {len(full_hand)} hand"
    ctr = Counter(full_hand)
    count_of_counts = Counter(ctr.values())

    # now for each of the waits we calculate their possible yaku
    yaku_for_wait: YakuForWait = {wait: [] for wait in waits}

    # stateless closed hand yaku_for_wait
    if is_closed_hand:
        # iipeikou: see if any duplicates of sequences exist,
        #           or if adding a wait gives you that sequence
        # ryanpeikou: check how many times the above is true for a hand
        # chiitoitsu: check full_hand for 6 pairs
        seq_ctr = Counter(sequences)
        for wait in waits:
            # assume count >= 1 for all counts (since that's how Counter works)
            iipeikou_count = [count >= 2 or seq == sorted_hand((*taatsu, wait)) for seq, count in seq_ctr.items()].count(True)
            # priority list is: first ryanpeikou, then chiitoitsu, lastly iipeikou
            if iipeikou_count == 2:
                yaku_for_wait[wait].append(("ryanpeikou", 3))
            elif count_of_counts[2] == 6 and ctr[wait] == 1:
                yaku_for_wait[wait].append(("chiitoitsu", 2))
            elif iipeikou_count == 1:
                yaku_for_wait[wait].append(("iipeikou", 1))

        # pinfu: has 22 tsumo fu and 30 ron fu, and ryanmen wait
        if (tsumo_fu, ron_fu) == (22, 30) and len(interpretation.get_waits()) == 2:
            for wait in waits:
                yaku_for_wait[wait].append(("pinfu", 1))

    # iitsu: just check if all 3 sequences are there for every suit
    # or if adding each wait to the remaining hand gives the 3rd sequence
    IITSU = [{(11,12,13),(14,15,16),(17,18,19)},
             {(21,22,23),(24,25,26),(27,28,29)},
             {(31,32,33),(34,35,36),(37,38,39)}]
    for suit in IITSU:
        remaining = suit - set(sequences)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku_for_wait[wait].append(("iitsu", 2 if is_closed_hand else 1))

    # sanshoku: there's only 7 sanshoku groups, so do the same as before
    SANSHOKU = list(zip(zip(range(11,18),range(12,19),range(13,20)),
                        zip(range(21,28),range(22,29),range(23,30)),
                        zip(range(31,38),range(32,39),range(33,40))))
    for group in SANSHOKU:
        remaining = set(group) - set(sequences)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku_for_wait[wait].append(("sanshoku", 2 if is_closed_hand else 1))

    # sanshoku: there's only 9 sanshoku doukou groups, so do the same as before
    SANSHOKU_DOUKOU = list(zip(zip(range(11,20),range(11,20),range(11,20)),
                               zip(range(21,30),range(21,30),range(21,30)),
                               zip(range(31,40),range(31,40),range(31,40))))
    for group in SANSHOKU_DOUKOU:
        remaining = set(group) - set(triplets)
        if len(remaining) >= 2:
            continue
        for wait in waits:
            if remaining in [set(), {sorted_hand((*taatsu, wait))}]:
                yaku_for_wait[wait].append(("sanshoku doukou", 2))

    # honroutou: check that all of the hand is terminal/honors
    # then every terminal/honor wait gives honroutou
    non_honroutou_waits = set(waits)
    if set(full_hand).issubset(YAOCHUUHAI):
        non_honroutou_waits -= YAOCHUUHAI
        for wait in waits & YAOCHUUHAI:
            yaku_for_wait[wait].append(("honroutou", 2))
    # otherwise, we score junchan/chanta
    # junchan: if we remove all junchan groups and we're left with a terminal pair
    # chanta: if not junchan/honroutou and we remove all chanta groups and we're left with a terminal/honor pair
    TERMINAL_SEQS: Set[Tuple[int, ...]] \
        = set().union(set(zip(range(11,40,10),range(12,40,10),range(13,40,10))),
                      set(zip(range(21,40,10),range(22,40,10),range(23,40,10))),
                      set(zip(range(31,40,10),range(32,40,10),range(33,40,10))),
                      set(zip(range(17,40,10),range(18,40,10),range(19,40,10))),
                      set(zip(range(27,40,10),range(28,40,10),range(29,40,10))),
                      set(zip(range(37,40,10),range(38,40,10),range(39,40,10))))
    JUNCHAN_TRIS: Set[Tuple[int, ...]] = {(t,t,t) for t in {11,19,21,29,31,39}}
    JUNCHAN_PAIRS: Set[Tuple[int, ...]] = {(t,t) for t in {11,19,21,29,31,39}}
    CHANTA_TRIS: Set[Tuple[int, ...]] = {(t,t,t) for t in range(41,48)} | JUNCHAN_TRIS
    CHANTA_PAIRS: Set[Tuple[int, ...]] = {(t,t) for t in range(41,48)} | JUNCHAN_PAIRS
    # check that every existing group is junchan
    if set(sequences).issubset(TERMINAL_SEQS):
        if set(triplets).issubset(JUNCHAN_TRIS) and (pair_tile is None or pair_tile in {11,19,21,29,31,39}):
            for wait in non_honroutou_waits:
                if sorted_hand((*taatsu, wait)) in (JUNCHAN_TRIS | TERMINAL_SEQS | JUNCHAN_PAIRS):
                    yaku_for_wait[wait].append(("junchan", 3 if is_closed_hand else 2))
                elif sorted_hand((*taatsu, wait)) in CHANTA_TRIS | CHANTA_PAIRS:
                    yaku_for_wait[wait].append(("chanta", 2 if is_closed_hand else 1))
        elif set(triplets).issubset(CHANTA_TRIS) and (pair_tile is None or pair_tile in YAOCHUUHAI):
            for wait in non_honroutou_waits:
                if sorted_hand((*taatsu, wait)) in (CHANTA_TRIS | TERMINAL_SEQS | CHANTA_PAIRS):
                    yaku_for_wait[wait].append(("chanta", 2 if is_closed_hand else 1))

    # the following yaku_for_wait don't need to check the structure of the hand (sequences/triplets)

    # tanyao: check that none of the hand is terminal/honors
    # then every nonterminal/honor wait gives tanyao
    if set(full_hand).isdisjoint(YAOCHUUHAI):
        for wait in waits - YAOCHUUHAI:
            yaku_for_wait[wait].append(("tanyao", 1))

    # toitoi: take out all triplets.
    # if there's 4, the remaining tile gives toitoi.
    # if there's 3, and there are 2 pairs, the remaining pairs give toitoi
    if count_of_counts[3] == 4:
        for wait in waits:
            if ctr[wait] == 1:
                yaku_for_wait[wait].append(("toitoi", 2))
    if count_of_counts[3] == 3 and count_of_counts[2] == 2:
        for wait in waits:
            if ctr[wait] == 2:
                yaku_for_wait[wait].append(("toitoi", 2))

    # chinitsu: check that all of the hand is the suit
    # then every wait of that suit gives chinitsu
    # honitsu: same, but add honor tiles to the suit
    for chinitsu_suit in [set(range(11,20)) | {51}, set(range(21,30)) | {52}, set(range(31,40)) | {53}]:
        honitsu_suit = chinitsu_suit.union(range(41,48))
        if set(full_hand).issubset(honitsu_suit):
            if set(full_hand).issubset(chinitsu_suit):
                for wait in waits & chinitsu_suit:
                    yaku_for_wait[wait].append(("chinitsu", 6 if is_closed_hand else 5))
            else:
                for wait in waits & honitsu_suit:
                    if len(yaku_for_wait[wait]) == 0 or yaku_for_wait[wait][-1][0] != "chinitsu":
                        yaku_for_wait[wait].append(("honitsu", 3 if is_closed_hand else 2))

    # shousangen: if your tenpai hand has 8 of the 9 dragons, then you just have shousangen for any wait
    # alternatively if your tenpai hand has 7, then any wait matching a missing dragon gives shousangen
    shousangen_count = {tile: min(3, ctr[tile]) for tile in {45,46,47}}
    shousangen_sum = sum(shousangen_count.values())
    for wait in waits:
        if shousangen_sum == 8 or (shousangen_sum == 7 and shousangen_count[wait] in {1,2}):
            yaku_for_wait[wait].append(("shousangen", 2))

    # sanankou: check if there's three closed triplets
    # the case where there's two closed triplets and a pair waiting for a tsumo
    #   is handled in add_tsumo_yaku
    if len(triplets) >= 3:
        # check they are all closed
        called_triplets = {tuple(normalize_red_fives(call.tiles[:3])) for call in interpretation.calls}
        our_triplets = {tuple(normalize_red_fives(tri)) for tri in triplets}
        num_open_triplets = len(our_triplets & called_triplets)
        if len(triplets) - num_open_triplets >= 3:
            for wait in waits:
                yaku_for_wait[wait].append(("sanankou", 2))

    # sankantsu: check calls
    num_kans = list(map(lambda call: "kan" in call.type, interpretation.calls)).count(True)
    if num_kans == 3:
        for wait in waits:
            yaku_for_wait[wait].append(("sankantsu", 2))

    return yaku_for_wait

# pass in the stateless yakus + the whole state
# get back all the yakus (stateless + stateful)
# this will always output houtei for haitei hands; add_tsumo_yaku will make it haitei
def add_stateful_yaku(yaku_for_wait: YakuForWait,
                      hand: Hand,
                      events: List[Event],
                      doras: List[int],
                      uras: List[int],
                      round: int,
                      seat: int,
                      yakuhai: Tuple[int, ...],
                      is_last_tile: bool) -> YakuForWait:
    is_closed_hand = len(hand.closed_part) == 13
    ctr = Counter(hand.tiles)
    waits = set(yaku_for_wait.keys())
    # this is kind of a state machine over the events to figure out five yaku
    # first state machine checks for self-riichis, self-discards, and all calls
    # - riichi: check if there is a self-riichi event anywhere
    # - double riichi: check if no discard event before a self-riichi event
    # - ippatsu: check if there is are no call events or self-discard events after self-riichi
    # second state machine checks for kans and draws and discards
    # - chankan: check if there is any kakan and no draw after it
    # - rinshan: check if there is any kan, then a draw, and no discard after it
    double_riichi_eligible = True
    is_ippatsu = False
    is_chankan = False
    is_rinshan = False
    for event_seat, event_type, *event_data in events:
        if event_seat != seat and event_type == "draw": # someone draws
            if is_chankan:
                is_ippatsu = False # kakan call succeeded
            is_chankan = False
        elif event_seat == seat and event_type == "discard": # self discard
            double_riichi_eligible = False
            is_ippatsu = False
            is_rinshan = False
        elif is_closed_hand and event_seat == seat and event_type == "riichi": # self riichi
            is_ippatsu = True
            for wait in waits:
                if double_riichi_eligible:
                    yaku_for_wait[wait].append(("double riichi", 2))
                else:
                    yaku_for_wait[wait].append(("riichi", 1))
        elif event_seat != seat and event_type in {"kakan", "kita"}: # someone kakans or calls kita
            # ippatsu isn't cancelled yet; wait for a draw
            is_chankan = True
        elif event_seat != seat and event_type in {"chii", "pon", "minkan", "ankan", "kita"}: # any non-kakan call
            double_riichi_eligible = False
            is_ippatsu = False
        elif event_seat == seat and event_type in {"minkan", "ankan", "kakan", "kita"}: # self kan
            double_riichi_eligible = False
            is_rinshan = True
    if is_ippatsu:
        for wait in waits:
            yaku_for_wait[wait].append(("ippatsu", 1))
    if is_chankan:
        for wait in waits:
            yaku_for_wait[wait].append(("chankan", 1))
        is_last_tile = False
    if is_rinshan:
        for wait in waits:
            yaku_for_wait[wait].append(("rinshan", 1))
        is_last_tile = False

    # yakuhai: if your tenpai hand has three, then you just have yakuhai for any wait
    # alternatively if your tenpai hand has two, then any wait matching that has yakuhai
    YAKUHAI_NAMES = {41: "ton", 42: "nan", 43: "shaa", 44: "pei", 45: "haku", 46: "hatsu", 47: "chun"}
    for tile in yakuhai:
        for wait in waits:
            if ctr[tile] == 3 or (ctr[tile] == 2 and wait == tile):
                yaku_for_wait[wait].append((YAKUHAI_NAMES[tile], 1))

    # kita: just check the number of kita in hand
    if hand.kita_count > 0:
        for wait in waits:
            yaku_for_wait[wait].append((f"kita {hand.kita_count}" if hand.kita_count > 1 else "kita", hand.kita_count))

    # dora: count the dora of the hand, removing red fives (we'll count them next)
    full_hand = (*hand.hidden_part, *(tile for call in hand.calls for tile in call.tiles))
    hand_without_reds = tuple(normalize_red_fives(full_hand))
    non_red_dora = [dora for dora in doras if dora not in {51,52,53}]
    dora = sum(non_red_dora.count(tile) for tile in hand_without_reds)
    # now add dora to the yaku list
    for wait in waits:
        if wait in doras:
            wait_dora = dora + doras.count(wait)
            if wait_dora > 0:
                yaku_for_wait[wait].append((f"dora {wait_dora}" if wait_dora > 1 else "dora", wait_dora))
        else:
            if dora > 0:
                yaku_for_wait[wait].append((f"dora {dora}" if dora > 1 else "dora", dora))

    # aka: simply count the aka
    red_dora = set(doras) & {51,52,53} # might be empty if there's no red dora this game
    aka = len(set(full_hand) & red_dora)
    if aka > 0:
        for wait in waits:
            yaku_for_wait[wait].append((f"aka {aka}" if aka > 1 else "aka", aka))

    # ura: same as dora, except our hand has to have riichi in order to have ura
    ura = sum(uras.count(tile) for tile in hand_without_reds)
    for wait in waits:
        if ("riichi", 1) in yaku_for_wait[wait]:
            if wait in uras:
                wait_ura = ura + uras.count(wait)
                if wait_ura > 0:
                    yaku_for_wait[wait].append((f"ura {wait_ura}" if wait_ura > 1 else "ura", wait_ura))
            else:
                if ura > 0:
                    yaku_for_wait[wait].append((f"ura {ura}" if ura > 1 else "ura", ura))

    # haitei/houtei: just need is_last_tile passed in
    if is_last_tile:
        for wait in waits:
            yaku_for_wait[wait].append(("houtei", 1))
    assert [is_rinshan, is_chankan, is_last_tile].count(True) <= 1, f"rinshan, chankan, haitei, and houtei should be exclusive {[is_rinshan, is_chankan, is_last_tile]}"
    return yaku_for_wait

# add menzentsumo and sanankou
# convert houtei to haitei
# suuankou is checked in add_yakuman
def add_tsumo_yaku(yaku_for_wait: YakuForWait, interpretation: Interpretation, is_closed_hand: bool) -> YakuForWait:
    waits = set(yaku_for_wait.keys())

    # menzentsumo only requires a closed hand
    if is_closed_hand:
        for wait in waits:
            yaku_for_wait[wait].append(("tsumo", 1))

    # sanankou requires two closed triplets, and that the taatsu part is a shanpon wait
    taatsu, _, _, sequences, triplets, pair = interpretation.unpack()
    is_pair = lambda hand: len(hand) == 2 and normalize_red_five(hand[0]) == normalize_red_five(hand[1])
    if len(triplets) >= 2 and is_pair(taatsu) and pair is not None:
        # check they are all closed
        called_triplets = {tuple(normalize_red_fives(call.tiles[:3])) for call in interpretation.calls}
        our_triplets = {tuple(normalize_red_fives(tri)) for tri in triplets}
        num_open_triplets = len(our_triplets & called_triplets)
        if len(triplets) - num_open_triplets >= 2:
            for wait in waits & {taatsu[0], pair[0]}:
                if ("sanankou", 2) not in yaku_for_wait[wait]:
                    yaku_for_wait[wait].append(("sanankou", 2))

    # haitei: if houtei is there, make it haitei
    for wait in waits:
        if ("houtei", 1) in yaku_for_wait[wait]:
            yaku_for_wait[wait].remove(("houtei", 1))
            yaku_for_wait[wait].append(("haitei", 1))

    return yaku_for_wait

###
### yakuman checking functions
###

# All of these functions below assume the passed-in hand is a 13-tile tenpai hand

# (tenpai hand, calls) -> is it yakuman?
CheckYakumanFunc = Callable[[Hand], bool]

# daisangen tenpai if we have 8 tiles of dragons (counting each dragon at most 3 times)
is_daisangen: CheckYakumanFunc = lambda hand: sum(min(3, hand.tiles.count(tile)) for tile in {45,46,47}) >= 8

# kokushi musou tenpai if we have at least 12 terminal/honors
is_kokushi: CheckYakumanFunc = lambda hand: len(YAOCHUUHAI.intersection(hand.tiles)) >= 12

# suuankou tenpai if hand is closed and we have 4 triplets, or 3 triplets and two pairs
# which is to say, 3+ triplets + at most one unpaired tile
is_suuankou: CheckYakumanFunc = lambda hand: hand.closed_part == hand.tiles and (mults := list(Counter(hand.tiles).values()), mults.count(3) >= 3 and mults.count(1) <= 1)[1]

# shousuushi if we have exactly 10 winds (counting each wind at most 3 times)
# OR 11 tiles of winds + no pair (i.e. only 6 kinds of tiles in hand)
is_shousuushi: CheckYakumanFunc = lambda hand: (count := sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44}), count == 10 or count == 11 and len(set(normalize_red_fives(hand.tiles))) == 6)[1]

# daisuushi if we have 12 tiles of winds (counting each wind at most 3 times)
# OR 11 tiles of winds + a pair (i.e. only 5 kinds of tiles in hand)
is_daisuushi: CheckYakumanFunc = lambda hand: (count := sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44}), count == 12 or count == 11 and len(set(normalize_red_fives(hand.tiles))) == 5)[1]

# tsuuiisou tenpai if all the tiles are honor tiles
is_tsuuiisou: CheckYakumanFunc = lambda hand: set(hand.tiles).issubset({41,42,43,44,45,46,47})

# ryuuiisou tenpai if all the tiles are 23468s6z
is_ryuuiisou: CheckYakumanFunc = lambda hand: set(hand.tiles).issubset({32,33,34,36,38,46})

# chinroutou tenpai if all the tiles are 19m19p19s
is_chinroutou: CheckYakumanFunc = lambda hand: set(hand.tiles).issubset({11,19,21,29,31,39})

# chuuren poutou tenpai if hand is closed and we are missing at most one tile
#   out of the required 1112345678999
CHUUREN_TILES = Counter([1,1,1,2,3,4,5,6,7,8,9,9,9])
is_chuuren: CheckYakumanFunc = lambda hand: hand.closed_part == hand.tiles and max(hand.tiles) - min(hand.tiles) == 8 and max(hand.tiles) < 40 and (ctr := Counter([t % 10 for t in normalize_red_fives(hand.tiles)]), sum((CHUUREN_TILES - (CHUUREN_TILES & ctr)).values()) <= 1)[1]

# suukantsu tenpai if you have 4 kans
is_suukantsu = lambda hand: list(map(lambda call: "kan" in call.type, hand.calls)).count(True) == 4

# note: evaluating {suukantsu, tenhou, chiihou, kazoe} requires information outside of the hand

CHECK_YAKUMAN = {"daisangen": is_daisangen,
                 "kokushi musou": is_kokushi,
                 "suuankou": is_suuankou,
                 "shousuushi": is_shousuushi,
                 "daisuushi": is_daisuushi,
                 "tsuuiisou": is_tsuuiisou,
                 "ryuuiisou": is_ryuuiisou,
                 "chinroutou": is_chinroutou,
                 "chuurenpoutou": is_chuuren,
                 "suukantsu": is_suukantsu}
get_yakuman_tenpais = lambda hand: {name for name, func in CHECK_YAKUMAN.items() if func(hand)}
def get_yakuman_waits(hand: Hand, name: str) -> Set[int]:
    """
    Get all the waits that lead to a given yakuman hand.
    Assumes the given hand is yakuman tenpai for the given yakuman name
    """
    if name == "daisangen":
        return {45,46,47} & set(hand.shanten[1])
    elif name in {"shousuushi", "daisuushi"}:
        # if there are 11 winds you can have either shousuushi or daisuushi
        # get only the relevant wait
        shousuushi_waits = set()
        daisuushi_waits = set()
        num_winds = sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44})
        if num_winds == 10:
            shousuushi_waits = {41,42,43,44} & set(hand.shanten[1])
        elif num_winds == 11:
            shousuushi_waits = set(hand.shanten[1]) - {41,42,43,44}
            daisuushi_waits = {41,42,43,44} & set(hand.shanten[1])
        elif num_winds == 12:
            daisuushi_waits = set(hand.shanten[1])
        return shousuushi_waits if name == "shousuushi" else daisuushi_waits
    elif name == "ryuuiisou":
        return {32,33,34,36,38,46} & set(hand.shanten[1])
    elif name == "chuurenpoutou":
        ctr = Counter([t % 10 for t in normalize_red_fives(hand.tiles)])
        missing_digits = set((CHUUREN_TILES - (CHUUREN_TILES & ctr)).keys())
        return {wait for wait in hand.shanten[1] if wait % 10 in missing_digits}
    elif name in {"kokushi musou", "suuankou", "tsuuiisou", "chinroutou", "suukantsu"}:
        return set(hand.shanten[1])
    else:
        assert False, f"tried to get yakuman waits for {name}"

def test_get_yakuman_tenpais() -> None:
    print("daisangen:")
    from .classes import Dir
    pon = lambda tile: CallInfo(type="pon", tile=tile, tiles=(tile,tile,tile), dir=Dir.SHIMOCHA)
    assert get_yakuman_tenpais(Hand((11,12,13,22,22,45,45,46,46,46,47,47,47),calls=[pon(47)])) == {"daisangen"}
    assert get_yakuman_tenpais(Hand((11,12,13,22,45,45,45,46,46,46,47,47,47),calls=[pon(47)])) == {"daisangen"}
    assert get_yakuman_tenpais(Hand((11,12,13,45,45,45,45,46,46,46,47,47,47),calls=[pon(47)])) == {"daisangen"}
    assert get_yakuman_tenpais(Hand((11,12,13,45,45,45,45,46,46,46,47,11,11))) == set()

    assert get_yakuman_tenpais(Hand((11,19,21,29,29,31,39,41,42,43,44,45,47))) == {"kokushi musou"}
    assert get_yakuman_tenpais(Hand((11,19,21,29,29,29,39,41,42,43,44,45,46))) == set()

    print("suuankou:")
    assert get_yakuman_tenpais(Hand((11,11,11,12,12,12,13,13,14,14,15,15,15))) == {"suuankou"}
    assert get_yakuman_tenpais(Hand((11,11,11,12,12,12,13,14,14,14,15,15,15))) == {"suuankou"}
    assert get_yakuman_tenpais(Hand((11,11,11,12,12,12,13,14,14,14,15,15,15),calls=[pon(15)])) == set()

    print("shousuushi/daisuushi:")
    assert get_yakuman_tenpais(Hand((11,12,13,41,42,42,42,43,43,43,44,44,44))) == {"shousuushi"}
    assert get_yakuman_tenpais(Hand((11,12,41,41,42,42,42,43,43,43,44,44,44))) == {"shousuushi"}
    assert get_yakuman_tenpais(Hand((11,12,13,14,42,42,42,43,43,43,44,44,44))) == set()
    assert get_yakuman_tenpais(Hand((11,11,41,41,42,42,42,43,43,43,44,44,44))) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais(Hand((11,41,41,41,42,42,42,43,43,43,44,44,44))) == {"suuankou", "daisuushi"}
    assert get_yakuman_tenpais(Hand((11,41,41,41,42,42,42,43,43,43,44,44,44),calls=[pon(44)])) == {"daisuushi"}

    print("tsuuiisou:")
    assert get_yakuman_tenpais(Hand((41,41,42,42,43,43,44,44,45,45,46,46,47))) == {"tsuuiisou"}
    assert get_yakuman_tenpais(Hand((45,45,45,46,46,47,47,47,41,41,41,42,42),calls=[pon(41)])) == {"daisangen", "tsuuiisou"}
    assert get_yakuman_tenpais(Hand((41,41,42,42,42,43,43,43,44,47,47,11,12))) == set()
    assert get_yakuman_tenpais(Hand((41,41,41,42,42,42,43,43,43,44,44,44,45))) == {"suuankou", "daisuushi", "tsuuiisou"}

    print("ryuuiisou:")
    assert get_yakuman_tenpais(Hand((32,32,33,33,34,34,36,36,36,38,38,46,46))) == {"ryuuiisou"}
    assert get_yakuman_tenpais(Hand((22,22,23,23,24,24,26,26,26,28,28,46,46))) == set()

    print("chinroutou:")
    assert get_yakuman_tenpais(Hand((11,11,11,19,19,21,21,21,29,29,29,31,31))) == {"suuankou", "chinroutou"}
    assert get_yakuman_tenpais(Hand((11,11,11,19,19,21,21,21,29,29,29,31,31),calls=[pon(29)])) == {"chinroutou"}

    print("chuurenpoutou:")
    assert get_yakuman_tenpais(Hand((11,11,11,12,13,14,15,16,17,18,19,19,19))) == {"chuurenpoutou"}
    assert get_yakuman_tenpais(Hand((11,11,11,12,13,14,15,16,17,18,19,19,19),calls=[pon(19)])) == set()
    assert get_yakuman_tenpais(Hand((11,11,11,12,13,14,15,16,17,18,19,19,11))) == {"chuurenpoutou"}
    assert get_yakuman_tenpais(Hand((11,11,11,12,13,14,15,16,17,18,19,11,11))) == set()

def add_yakuman(yaku_for_wait: YakuForWait,
                hand: Hand,
                events: List[Event],
                round: int,
                seat: int,
                is_tsumo: bool,
                use_renhou: bool) -> YakuForWait:
    waits = set(hand.shanten[1])
    is_dealer = seat == round % 4

    yakumans = get_yakuman_tenpais(hand)

    # tenhou, chiihou: tsumo, and we never discarded + no calls happened
    # renhou: same, but not tsumo
    tenhou_eligible = True
    for event_seat, event_type, *event_data in events:
        if seat == event_seat and event_type == "discard":
            tenhou_eligible = False
            break
        elif event_type in {"chii", "pon", "minkan", "ankan", "kakan", "kita"}:
            tenhou_eligible = False
            break
    if tenhou_eligible:
        if is_tsumo: # tenhou/chiihou
            if is_dealer:
                yakumans.add("tenhou")
            elif not is_dealer:
                yakumans.add("chiihou")
            UPGRADES = {
                "kokushi musou": "kokushi musou 13-sided",
                "suuankou": "suuankou tanki",
                "chuurenpoutou": "junsei chuurenpoutou"
            }
            for k, v in UPGRADES.items():
                if k in yakumans:
                    yakumans.remove(k)
                    yakumans.add(v)
        elif use_renhou: # renhou
            # compare our current yaku to renhou
            # if renhou is equal or better, then we replace it with renhou
            for wait in waits:
                if sum(value for name, value in yaku_for_wait[wait]) <= 5:
                    yaku_for_wait[wait] = [("renhou", 5)]

    if len(yakumans) > 0:
        for wait in waits:
            actual_yakumans = yakumans.copy()

            # handle yasume possibilities

            # daisangen with 2 dragon triplets, you shanpon wait on the third but get the non-dragon wait
            num_dragons = sum(min(3, hand.tiles.count(tile)) for tile in {45,46,47})
            if "daisangen" in actual_yakumans and num_dragons == 8 and wait not in {45,46,47}:
                actual_yakumans.remove("daisangen")

            # daisuushi with 11 winds, you shanpon wait on the final wind but get the non-wind wait
            num_winds = sum(min(3, hand.tiles.count(tile)) for tile in {41,42,43,44})
            if "daisuushi" in actual_yakumans and num_winds == 11 and wait not in {41,42,43,44}:
                actual_yakumans.remove("daisuushi")
                actual_yakumans.add("shousuushi")

            # ryuuisou but you get a wait that is not a green tile
            if "ryuuisou" in actual_yakumans and wait not in {32,33,34,36,38,46}:
                actual_yakumans.remove("ryuuisou")

            # suuankou with 3 triplets, you shanpon wait on the fourth but did not tsumo
            if "suuankou" in actual_yakumans and not is_tsumo and list(Counter(hand.tiles).values()).count(3) == 3:
                actual_yakumans.remove("suuankou")

            # chuuren poutou but your final wait doesn't complete the set:
            if "chuurenpoutou" in actual_yakumans:
                CHUUREN_TILES = Counter([1,1,1,2,3,4,5,6,7,8,9,9,9])
                chuuren_repr = Counter([t % 10 for t in normalize_red_fives(hand.tiles)])
                [expected_wait] = (CHUUREN_TILES - (CHUUREN_TILES & chuuren_repr)).keys()
                if wait != expected_wait:
                    actual_yakumans.remove("chuurenpoutou")

            # finally, add all remaining yakuman to our wait
            if len(actual_yakumans) > 0:
                yaku_for_wait[wait] = [(y, 13) for y in actual_yakumans]

    return yaku_for_wait

###
### entry points
###

def get_yaku(hand: Hand,
             events: List[Event],
             doras: List[int],
             uras: List[int],
             round: int,
             seat: int,
             is_last_tile: bool,
             num_players: int,
             rules: GameRules,
             check_rons: bool = True,
             check_tsumos: bool = True) -> Dict[int, Score]:
    if hand.shanten[0] != 0:
        return {}

    waits = set(hand.shanten[1])
    assert len(waits) > 0, f"hand {hand!s} is tenpai, but has no waits?"

    # best_score[wait] = the Score value representing the best interpretation for that wait
    best_score: Dict[int, Score] = {}
    def add_best_score(wait: int, new_score: Score) -> None:
        nonlocal best_score
        assert (new_score.han, new_score.fu) != (0, 0), f"somehow got a zero score: {new_score})"
        if wait not in best_score:
            best_score[wait] = new_score
        else:
            best_score[wait] = max(best_score[wait], new_score)

    # we want to get the best yaku for each wait
    # each hand interpretation gives han and fu for some number of waits
    # get the best han and fu for each wait across all interpretations
    yakuhai: Tuple[int, ...] = (45,46,47,(round//4)+41,((seat-(round%4))%num_players)+41)
    if rules.double_round_wind:
        yakuhai = (*yakuhai, ((round//4)+2)+41)
    if not rules.double_wind_4_fu:
        yakuhai = tuple(set(yakuhai)) # remove duplicates
    is_closed_hand = len(hand.closed_part) == 13
    for interpretation in Interpretation(hand.hidden_part, calls=tuple(hand.calls)) \
            .generate_all_interpretations(yakuhai=yakuhai, is_closed_hand=is_closed_hand):
        # print("========")
        # for k, v in best_score.items():
        #     print(f"{pt(k)}, {v.hand!s}")
        yaku_for_wait: YakuForWait = get_stateless_yaku(interpretation, hand.shanten, is_closed_hand)
        # pprint(yaku_for_wait)
        yaku_for_wait = add_stateful_yaku(yaku_for_wait, hand, events, doras, uras, round, seat, yakuhai, is_last_tile)
        # print(round_name(round, 0), yaku_for_wait)
        # pprint([(a, b) for a, b, *_ in events])
        if check_tsumos:
            tsumo_yaku = add_tsumo_yaku(yaku_for_wait.copy(), interpretation, is_closed_hand)
            tsumo_yaku = add_yakuman(yaku_for_wait, hand, events, round, seat, is_tsumo=True, use_renhou=rules.renhou)
        yaku_for_wait = add_yakuman(yaku_for_wait, hand, events, round, seat, is_tsumo=False, use_renhou=rules.renhou)
        # pprint(yaku_for_wait)

        # if `interpretations.hand` is a pair, it's a shanpon wait
        # if it's a terminal pair then it's +4 fu for ron and +8 for tsumo
        # otherwise it's +2 fu for ron and +4 for tsumo
        is_pair = lambda hand: len(hand) == 2 and normalize_red_five(hand[0]) == normalize_red_five(hand[1])
        shanpon_fu = {wait: 0 for wait in yaku_for_wait.keys()} # times 2 for tsumo
        if is_pair(interpretation.hand):
            assert interpretation.pair is not None, "somehow got a shanpon tenpai hand without a pair"
            for tile in normalize_red_fives((interpretation.hand[0], interpretation.pair[0])):
                shanpon_fu[tile] = 4 if tile in YAOCHUUHAI else 2

        # now total up the fu for each wait
        round_fu = lambda fu: (((fu-1)//10)+1)*10
        for wait in yaku_for_wait.keys():
            fixed_fu = 25 if ("chiitoitsu", 2) in yaku_for_wait[wait] else None
            if check_rons:
                han = sum(b for _, b in yaku_for_wait[wait])
                ron_fu = interpretation.ron_fu + shanpon_fu[wait]
                fixed_fu = fixed_fu or (30 if ron_fu == 20 else None) # open pinfu ron = 30
                add_best_score(wait, Score(yaku_for_wait[wait], han, fixed_fu or round_fu(ron_fu), seat == round%4, False, num_players, rules, interpretation, hand))
            if check_tsumos:
                han = sum(b for _, b in tsumo_yaku[wait])
                if is_closed_hand:
                    tsumo_fu = interpretation.tsumo_fu + 2*shanpon_fu[wait]
                    fixed_fu = fixed_fu or (20 if ("pinfu", 1) in tsumo_yaku[wait] else None) # closed pinfu tsumo = 20
                    add_best_score(wait, Score(tsumo_yaku[wait], han, fixed_fu or round_fu(tsumo_fu), seat == round%4, True, num_players, rules, interpretation, hand))
                else:
                    tsumo_fu = interpretation.tsumo_fu + 2*shanpon_fu[wait]
                    add_best_score(wait, Score(tsumo_yaku[wait], han, fixed_fu or round_fu(tsumo_fu), seat == round%4, True, num_players, rules, interpretation, hand))
        # for k, v in best_score.items():
        #     print(f"{pt(k)}, {v!s}")
        # print("========")
    return best_score

def get_final_yaku(kyoku: Kyoku,
                   seat: int,
                   check_rons: bool = True,
                   check_tsumos: bool = True) -> Dict[int, Score]:
    assert kyoku.hands[seat].shanten[0] == 0, f"on {round_name(kyoku.round, kyoku.honba)}, get_seat_yaku was passed in seat {seat}'s non-tenpai hand {kyoku.hands[seat]!s} ({shanten_name(kyoku.hands[seat].shanten)})"
    ret = get_yaku(hand = kyoku.hands[seat],
                   events = kyoku.events,
                   doras = kyoku.doras,
                   uras = kyoku.uras,
                   round = kyoku.round,
                   seat = seat,
                   is_last_tile = kyoku.tiles_in_wall == 0,
                   num_players = kyoku.num_players,
                   rules = kyoku.rules,
                   check_rons = check_rons,
                   check_tsumos = check_tsumos)
    return ret

###
### for debug use
###

def debug_yaku(kyoku: Kyoku) -> None:
    def print_hand_details_given_seat(kyoku: Kyoku, seat: int, print_final_tile: bool = False) -> str:
        final_tile = None if not print_final_tile else kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
        return kyoku.hands[seat].print_hand_details(
                ukeire=kyoku.get_ukeire(seat),
                final_tile=final_tile,
                furiten=kyoku.furiten[seat])
    if kyoku.result[0] in {"ron", "tsumo"}:
        w = kyoku.result[1].winner
        is_dealer = w == kyoku.round % 4
        ron_score = get_final_yaku(kyoku, w, True, False)
        tsumo_score = get_final_yaku(kyoku, w, False, True)
        print(f"{round_name(kyoku.round, kyoku.honba)} | seat {w} {print_hand_details_given_seat(kyoku, w)} | dora {ph(kyoku.doras)} ura {ph(kyoku.uras)}")
        final_tile = kyoku.final_discard if kyoku.result[0] == "ron" else kyoku.final_draw
        print(f"actual    | {kyoku.result[0]} {pt(final_tile)} giving {kyoku.result[1].score.to_points()} with yaku {kyoku.result[1].yaku.yaku_strs}")
        if kyoku.result[0] == "ron":
            for t in ron_score.keys():
                assert (ron_score[t].han, ron_score[t].fu) != (0, 0), f"somehow got a 0/0 score: {ron_score}"
                score = get_score(ron_score[t].han, ron_score[t].fu, is_dealer, False, kyoku.num_players)
                han_fu_string = f"{ron_score[t].han}/{ron_score[t].fu}={score} (ron)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {ron_score[t].yaku}")
        else:
            for t in tsumo_score.keys():
                assert (tsumo_score[t].han, tsumo_score[t].fu) != (0, 0), f"somehow got a 0/0 score: {ron_score}"
                score = get_score(tsumo_score[t].han, tsumo_score[t].fu, is_dealer, True, kyoku.num_players)
                han_fu_string = f"{tsumo_score[t].han}/{tsumo_score[t].fu}={score} (tsumo)"
                print(f"predicted | {pt(t)} giving {han_fu_string} with yaku {tsumo_score[t].yaku}")
        print("")
