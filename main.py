import functools
from pprint import pprint
import re
import json
from typing import *
from enum import Enum


###
### types
###

Log = List[List[Any]]
Kyoku = Dict[str, Any]

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
flatmap = lambda f, xs: [y for x in xs for y in f(x)]

###
### hand related functions
###

RED_FIVE = {51: 15, 52: 25, 53: 35}
toggle_red = lambda tile: int(str(tile)[::-1])
def remove_red_five(tile: int) -> int:
    if tile in RED_FIVE.keys():
        return RED_FIVE[tile]
    else:
        return tile
def remove_red_fives(hand: List[int]) -> List[int]:
    # turn red 5s into their normal counterparts
    for k, v in RED_FIVE.items():
        if k in hand:
            hand.remove(k)
            hand.append(v)
    return hand

def sorted_hand(hand: Iterable[int]) -> List[int]:
    """Return a copy of the hand sorted (handles red fives accordingly)"""
    hand_copy: List[float] = cast(List[float], list(hand))
    for k, v in RED_FIVE.items():
        if k in hand_copy:
            hand_copy.remove(k)
            hand_copy.append(v+0.5)
    hand_copy.sort()
    for k, v in RED_FIVE.items():
        if v+0.5 in hand_copy:
            hand_copy[hand_copy.index(v+0.5)] = k
    return cast(List[int], hand_copy)

def won(orig_hand: List[int]) -> bool:
    """return True if the hand is winning, False otherwise"""
    assert len(orig_hand) == 14, f"won() needs a 14-tile hand, hand passed in has {len(orig_hand)} tiles"
    hand = sorted_hand(orig_hand)
    remove_red_fives(hand)
    # print(f"hand: {hand}")

    # for every pair in hand, add a copy of the hand with the pair removed to the queue
    check_queue = []
    for i, (t1, t2) in enumerate(zip(hand[:-1], hand[1:])):
        if t1 == t2:
            check_queue.append(hand[0:i] + hand[i+2:])
            # print(f"removed {ph([t1,t2])} from {ph(hand)} resulting in {ph(check_queue[-1])}")

    # the first tile must start either a sequence or triplet
    # in either case, remove the used tiles and add the resulting hand back to the queue
    # an empty hand signifies that every tile formed a sequence or triplet, i.e. we're done
    def remove_tiles(hand, t1, t2, t3):
        hand_copy = list(hand)
        hand_copy.remove(t1)
        hand_copy.remove(t2)
        hand_copy.remove(t3)
        # print(f"  removed {ph([t1,t2,t3])} from {ph(hand)}, resulting in {ph(hand_copy)}")
        return hand_copy

    gas = 10000 # prevent infinite loop from any potential bugs (it shouldn't happen)
    while len(check_queue) > 0 and gas >= 0:
        gas -= 1
        h = check_queue.pop()
        if len(h) == 0:
            # print(f"   {ph(hand)} is a winning hand")
            return True
        # find a triplet
        if h[0] == h[1] == h[2]:
            check_queue.append(remove_tiles(h, *h[0:3]))
        # find a sequence
        if h[0] not in [18,19,28,29,38,39,41,42,43,44,45,46,47]:
            if h[0]+1 in h and h[0]+2 in h:
                # print(f"  {pt(h[0])}{pt(h[0]+1)}{pt(h[0]+2)} is a sequence in {ph(h)}")
                check_queue.append(remove_tiles(h, h[0], h[0]+1, h[0]+2))
        # else:
            # print(f"  {pt(h[0])} does not start a sequence in {h}")
    assert gas >= 0, "ran out of gas in won()"

    # seven pairs
    # if first 2 tiles are a pair,
    # check every next 2 tiles are a pair different from the previous one
    if hand[0] == hand[1] and all(t2 == t3 and t2 != t1 for i, (t1, t2, t3) in enumerate(zip(hand[1::2], hand[2::2], hand[3::2]))):
        # print(f"   {ph(hand)} is a winning chiitoitsu hand")
        return True

    # kokushi musou
    if set(tile for tile in hand) == {11,19,21,29,31,39,41,42,43,44,45,46,47}:
        # print(f"   {ph(hand)} is a winning kokushi musou hand")
        return True

    return False

def get_waits(hand: List[int]):
    assert len(hand) == 13, f"get_waits() needs a 13-tile hand, hand passed in has {len(hand)} tiles"
    orig_hand = list(hand)
    remove_red_fives(orig_hand)
    def side_tiles(tile):
        ret = []
        if tile < 40:
            if tile not in [11, 21, 31]:
                ret.append(tile-1)
            if tile not in [19, 29, 39]:
                ret.append(tile+1)
        return ret
    possible_winning_tiles = set(orig_hand + flatmap(side_tiles, orig_hand))
    winning_tiles = []
    for tile in possible_winning_tiles:
        if won(list(orig_hand) + [tile]):
            winning_tiles.append(tile)
    return winning_tiles

def calculate_ukeire(hand: List[int], visible: List[int]):
    waits = get_waits(hand)
    ukeire = 4 * len(waits)
    visible_tiles = hand + visible
    remove_red_fives(waits)
    remove_red_fives(visible_tiles)
    for wait in waits:
        while wait in visible_tiles:
            visible_tiles.remove(wait)
            ukeire -= 1
    return ukeire

def calculate_shanten(starting_hand: List[int]) -> Tuple[float, List[int]]:
    assert len(starting_hand) == 13, f"calculate_shanten() needs a 13-tile hand, hand passed in has {len(starting_hand)} tiles"
    starting_hand = sorted_hand(starting_hand) # not necessary, but helpful

    # standard shanten
    def try_remove_tiles(hand: Iterable[int], tiles: Iterable[int]) -> List[int]:
        hand_copy = list(hand)
        for tile in tiles:
            if tile in hand_copy:
                hand_copy.remove(tile)
            elif tile in [15,25,35,51,52,53] and toggle_red(tile) in hand_copy:
                hand_copy.remove(toggle_red(tile))
            else:
                return list(hand)
        return hand_copy
    # remove = lambda hand, groups: set(tuple(try_remove_tiles(hand, group)) for tile in set(hand) for group in groups(tile))
    # remove_all = lambda hands, groups: set(flatmap(lambda hand: remove(hand, groups), hands))
    remove_all = lambda hands, groups: set(tuple(try_remove_tiles(hand, group)) for hand in hands for tile in set(hand) for group in groups(tile))
    # try to remove all groups first
    hands = {tuple(starting_hand)}
    # pprint(list(map(ph,hands)))

    succ = lambda tile: 0 if tile in {0,19,29,39,41,42,43,44,45,46,47} else (tile*10)-494 if tile in [51,52,53] else tile+1
    for i in range(4):
        hands = remove_all(hands, lambda tile: [[tile, tile, tile], [tile, succ(tile), succ(succ(tile))]])
    # pprint(list(map(ph,hands)))

    # only keep the hands with min length, since we want to have as many groups removed as possible
    min_length = min(len(hand) for hand in hands)
    hands = set(filter(lambda hand: len(hand) == min_length, hands))
    num_groups = (13 - min_length) // 3

    # remove all taatsu to find the number of floating tiles
    for i in range(7):
        hands = remove_all(hands, lambda tile: [[tile, tile], [tile, succ(tile)], [tile, succ(succ(tile))]])
    # pprint(list(map(ph,hands)))
    count_pairs = lambda hand: len(list(filter(lambda ct: ct > 1, Counter(hand).values())))
    num_pairs = map(count_pairs, hands)
    num_floating = map(len, hands)
    min_shanten: float = 99

    # calculate shanten based on remaining floating tiles
    for pairs, floating in zip(num_pairs, num_floating):
        if num_groups == 3 and pairs == 0 and floating == 0:
            min_shanten = min(min_shanten, 1) # headless requires a pair
        elif num_groups == 4:
            min_shanten = 0 # tanki wait
        else:
            min_shanten = min(min_shanten, (floating+1)//2 - pairs)

    # if iishanten, get the type of iishanten based on possible remaining tiles
    floating_iishanten_tiles: Set[int] = set()
    complete_iishanten_tiles: Set[Tuple[int, ...]] = set()
    headless_iishanten_tiles: Set[int] = set()
    kutsuki_iishanten_tiles: Set[int] = set()
    return_data: List[int] = []
    def removed_red_fives(hand: Iterable[int]) -> Tuple[int, ...]:
        return tuple(remove_red_fives(list(hand)))
    if min_shanten == 1:
        for hand in hands:
            if num_groups == 2 and len(hand) == 3:
                tile = sorted_hand(hand)[0]
                # check if each complex shape is in the hand
                for shape in [[tile, tile, succ(tile)],
                             [tile, succ(tile), succ(tile)],
                             [tile, tile, succ(succ(tile))],
                             [tile, succ(succ(tile)), succ(succ(tile))],
                             [tile, succ(succ(tile)), succ(succ(succ(succ(tile))))]]:
                    if len(try_remove_tiles(hand, shape)) == 0:
                        # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(hand)}")
                        complete_iishanten_tiles = complete_iishanten_tiles.union([hand, removed_red_fives(hand)])
            elif num_groups == 2 and len(hand) == 1:
                # print(f"{ph(starting_hand)} is floating tile iishanten, with floating tile {ph(hand)}")
                floating_iishanten_tiles = floating_iishanten_tiles.union(hand + removed_red_fives(hand))
            elif num_groups == 3 and len(hand) == 4:
                for tile in set(hand):
                    # ensure there is no pair
                    hand_copy = tuple(try_remove_tiles(hand, [tile, tile]))
                    if len(hand_copy) == 4:
                        # print(f"{ph(starting_hand)} is headless iishanten, with waits {ph(hand_copy)}")
                        headless_iishanten_tiles = headless_iishanten_tiles.union(hand_copy + removed_red_fives(hand))
            elif num_groups == 3 and len(hand) == 2:
                # check that the hand has floating tiles
                for tile in set(hand):
                    hand = tuple(try_remove_tiles(hand, [tile, succ(tile)]))
                    hand = tuple(try_remove_tiles(hand, [tile, succ(succ(tile))]))
                    hand = tuple(try_remove_tiles(hand, [tile, tile]))
                if len(hand) != 0:
                    # print(f"{ph(starting_hand)} is kutsuki iishanten, with kutsuki tiles {ph(hand)}")
                    kutsuki_iishanten_tiles = kutsuki_iishanten_tiles.union(hand + removed_red_fives(hand))

        if len(kutsuki_iishanten_tiles) > 0:
            min_shanten = 1.1
            return_data = sorted_hand(kutsuki_iishanten_tiles)
            # print(f"{ph(starting_hand)} is kutsuki iishanten, with kutsuki tiles {ph(return_data)}")
        elif len(headless_iishanten_tiles) > 0:
            min_shanten = 1.2
            return_data = sorted_hand(headless_iishanten_tiles)
            # print(f"{ph(starting_hand)} is headless iishanten, with shapes {ph(return_data)}")
        elif len(complete_iishanten_tiles) > 0:
            min_shanten = 1.3
            return_data = sorted_hand(flatmap(lambda x: x, complete_iishanten_tiles))
            # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(return_data)}")
        elif len(floating_iishanten_tiles) > 0:
            min_shanten = 1.4
            return_data = sorted_hand(floating_iishanten_tiles)
            # print(f"{ph(starting_hand)} is floating tile iishanten, with floating tiles {ph(return_data)}")
    else:
        # chiitoitsu shanten
        num_unique_pairs = count_pairs(starting_hand)
        min_shanten = min(min_shanten, 6 - num_unique_pairs)
        # kokushi musou shanten
        min_shanten = min(min_shanten, (12 if num_unique_pairs >= 1 else 13) - len({11,19,21,29,31,39,41,42,43,44,45,46,47}.intersection(starting_hand)))
    return min_shanten, return_data

def get_shanten_name(shanten):
    if shanten == 0:
        return "tenpai"
    elif shanten == 1.1:
        return "kutsuki iishanten"
    elif shanten == 1.2:
        return "headless iishanten"
    elif shanten == 1.3:
        return "complete iishanten"
    elif shanten == 1.4:
        return "floating tile iishanten"
    else:
        return f"{shanten}-shanten"

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " CHASING_PLAYER_HAS_WORSE_WAIT"
    " GAME_ENDED_WITH_RON"
    " GAME_NOT_ENDED_WITH_RYUUKYOKU"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_TENPAI_FIRST"

    # unused:
    " CHASER_LOST_POINTS"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " GAME_ENDED_WITH_TSUMO"
    " YOU_GAINED_POINTS"

    # TODO:
    " HAITEI_HAPPENED_WHILE_YOU_ARE_TENPAI"
    " OPPONENT_RIICHI_IPPATSU_TSUMO"
    " YOU_HAVE_FIRST_ROW_DISCARDS"
    " YOU_HAVE_SECOND_ROW_DISCARDS"
    " YOU_HAVE_THIRD_ROW_DISCARDS"
    " YOU_PAID_TSUMO_AS_DEALER"
    " YOUR_HAND_RUINED_BY_TANYAO"
    )

def determine_flags(kyoku, player: int) -> Tuple[List[Flags], List[Dict[str, Any]]]:
    """
    Analyze a parsed kyoku by spitting out an ordered list of all interesting facts about it (flags)
    Returns a pair of lists `(flags, data)`, where the nth entry in `data` is the data for the nth flag
    """
    flags = []
    data = []
    other_player = None
    other_chases = False
    other_hand = None
    other_wait = None
    other_ukeire = None
    draws_since_shanten_change = 0
    starting_player_shanten = None
    player_shanten: Tuple[float, List[int]] = (99, [])
    for event in kyoku["events"]:
        if event[0] == player:
            if event[1] == "shanten":
                starting_player_shanten = event[2]
                player_shanten = event[2]
            elif event[1] == "shanten_change":
                assert starting_player_shanten is not None
                player_shanten = event[3]
                draws_since_shanten_change = 0
            elif event[1] in ["draw", "chii", "pon", "minkan"]:
                draws_since_shanten_change += 1
                if player_shanten[0] > 0 and draws_since_shanten_change >= 9:
                    flags.append(Flags.NINE_DRAWS_NO_IMPROVEMENT)
                    data.append({"shanten": player_shanten[0],
                                 "iishanten_tiles": player_shanten[1],
                                 "turns": draws_since_shanten_change})
        if event[1] == "tenpai":
            if event[0] == player:
                flags.append(Flags.YOU_TENPAI_FIRST)
                data.append({"hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})
            elif Flags.YOU_TENPAI_FIRST in flags:
                flags.append(Flags.YOU_GOT_CHASED)
                data.append({"player": event[0],
                             "hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})

    if kyoku["result"][0] == "和了":
        if 0 in kyoku["result"][1]:
            flags.append(Flags.GAME_ENDED_WITH_RON)
            data.append({})
            flags.append(Flags.GAME_NOT_ENDED_WITH_RYUUKYOKU)
            data.append({})
        else:
            flags.append(Flags.GAME_ENDED_WITH_TSUMO)
            data.append({})
            flags.append(Flags.GAME_NOT_ENDED_WITH_RYUUKYOKU)
            data.append({})
        if kyoku["result"][1][player] < 0:
            flags.append(Flags.YOU_LOST_POINTS)
            data.append({"amount": kyoku["result"][1][player]})
        if kyoku["result"][1][player] > 0:
            flags.append(Flags.YOU_GAINED_POINTS)
            data.append({"amount": kyoku["result"][1][player]})

        if Flags.YOU_GOT_CHASED in flags:
            assert Flags.YOU_TENPAI_FIRST in flags, "somehow got YOU_GOT_CHASED without YOU_TENPAI_FIRST"
            for index in [i for i, f in enumerate(flags) if f == Flags.YOU_GOT_CHASED]:
                # for every chaser, check if they gained or lost points
                chaser_player_data = data[index]
                chaser_player = chaser_player_data["player"]
                if kyoku["result"][1][chaser_player] < 0:
                    flags.append(Flags.CHASER_LOST_POINTS)
                    data.append({"player": chaser_player,
                                 "amount": kyoku["result"][1][chaser_player]})
                if kyoku["result"][1][chaser_player] > 0:
                    flags.append(Flags.CHASER_GAINED_POINTS)
                    data.append({"player": chaser_player,
                                 "amount": kyoku["result"][1][chaser_player]})
                # for every chaser, check if their wait is worse than yours
                player_data = data[flags.index(Flags.YOU_TENPAI_FIRST)]
                player_ukeire = player_data["ukeire"]
                chaser_ukeire = chaser_player_data["ukeire"]
                if chaser_ukeire < player_ukeire: # type: ignore
                    flags.append(Flags.CHASING_PLAYER_HAS_WORSE_WAIT)
                    player_wait = data[flags.index(Flags.YOU_TENPAI_FIRST)]["wait"]
                    chaser_wait = chaser_player_data["wait"]
                    data.append({"your_wait": player_wait,
                                 "chaser_wait": chaser_wait,
                                 "your_ukeire": player_ukeire,
                                 "chaser_ukeire": chaser_ukeire})

    # TODO: other results, namely "流局" (draw with noten payments), "全員聴牌" (everyone is tenpai)

    return flags, data

###
### injustice definitions
###

injustices: List[Dict[str, Any]] = []
InjusticeFunc = Callable[[List[Flags], List[Dict[str, Any]], str], None]
def injustice(flags: List[Flags]) -> Callable[[InjusticeFunc], InjusticeFunc] :
    """decorator for DIY injustices, see below for usage"""
    global injustices
    def decorator(callback):
        injustices.append({"callback": callback, "flags": flags})
        return lambda f: f
    return decorator

# each injustice takes a list of flags
# if all flags are satisfied in a certain round, the decorated function is called

# Print if you dealt into someone
@injustice([Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS])
def dealt_into_someone(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    # print(f"No unluckiness detected in {round_name}, but you dealt into someone")
    pass

# Print if your tenpai got chased
@injustice([Flags.YOU_TENPAI_FIRST, Flags.YOU_GOT_CHASED])
def got_chased(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    your_data = data[flags.index(Flags.YOU_TENPAI_FIRST)]
    chaser_data = data[flags.index(Flags.YOU_GOT_CHASED)]
    your_wait = your_data["wait"]
    chaser_wait = chaser_data["wait"]
    your_ukeire = your_data["ukeire"]
    chaser_ukeire = chaser_data["ukeire"]
    # print(f"No unluckiness detected in {round_name}, but"
    #       f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
    #       f" was chased by wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), though you did not deal into it")

# Print if your tenpai got chased by a worse wait, and you dealt in
@injustice([Flags.YOU_TENPAI_FIRST, Flags.YOU_GOT_CHASED,
            Flags.GAME_NOT_ENDED_WITH_RYUUKYOKU, Flags.CHASER_GAINED_POINTS,
            Flags.CHASING_PLAYER_HAS_WORSE_WAIT])
def chaser_won_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    chase_data = data[flags.index(Flags.CHASING_PLAYER_HAS_WORSE_WAIT)]
    your_wait = chase_data["your_wait"]
    chaser_wait = chase_data["chaser_wait"]
    your_ukeire = chase_data["your_ukeire"]
    chaser_ukeire = chase_data["chaser_ukeire"]
    print(f"Unluckiness detected in {round_name}:"
          f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
          f" was chased by a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and they won")

# Print if your tenpai got chased by a worse wait, and you dealt in
@injustice([Flags.YOU_TENPAI_FIRST, Flags.YOU_GOT_CHASED,
            Flags.GAME_ENDED_WITH_RON,
            Flags.YOU_LOST_POINTS, Flags.CHASER_GAINED_POINTS,
            Flags.CHASING_PLAYER_HAS_WORSE_WAIT])
def dealt_into_chaser_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    chase_data = data[flags.index(Flags.CHASING_PLAYER_HAS_WORSE_WAIT)]
    your_wait = chase_data["your_wait"]
    chaser_wait = chase_data["chaser_wait"]
    your_ukeire = chase_data["your_ukeire"]
    chaser_ukeire = chase_data["chaser_ukeire"]
    print(f"Major unluckiness detected in {round_name}:"
          f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
          f" was chased by a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and you dealt into it")

# Print if you failed to improve your shanten for nine consecutive draws
@injustice([Flags.NINE_DRAWS_NO_IMPROVEMENT])
def nine_draws_no_improvement(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    turns = shanten_data["turns"]
    shanten = shanten_data["shanten"]
    iishanten_tiles = shanten_data["iishanten_tiles"]
    shanten_name = get_shanten_name(shanten)
    if len(iishanten_tiles) > 0:
        print(f"Unluckiness detected in {round_name}: you could not improve your {shanten_name} ({ph(iishanten_tiles)}) for {turns} turns")
    else:
        print(f"Unluckiness detected in {round_name}: you could not improve your {shanten_name} for {turns} turns")

# Default if none of the above applies
def no_injustice_detected(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    # print(f"No unluckiness detected in {round_name}")
    pass

def evaluate_unluckiness(kyoku: Kyoku, player: int) -> None:
    global injustices
    round_name = f"East {kyoku['round']+1}" if kyoku["round"] <= 3 else f"South {kyoku['round']-3}"
    round_name += f" ({kyoku['honba']} honba)"
    flags, data = determine_flags(kyoku, player)

    found_injustice = False
    for i in injustices:
        if all(flag in flags for flag in i["flags"]):
            found_injustice = True
            i["callback"](flags, data, round_name)
    if not found_injustice:
        no_injustice_detected(flags, data, round_name)

###
### loading and parsing games
###

@functools.cache
def get_call_name(draw: str) -> str:
    """Get the type of a call from tenhou's log format, e.g. "12p1212" -> "pon" """
    ret = "chii"   if "c" in draw else \
          "riichi" if "r" in draw else \
          "pon"    if "p" in draw else \
          "kakan"  if "k" in draw else \
          "ankan"  if "a" in draw else \
          "minkan" if "m" in draw else "" # minkan = daiminkan, but we want it to start with "m"
    assert ret != "", f"couldn't figure out call name of {draw}"
    return ret

@functools.cache
def extract_call_tile(draw: str) -> int:
    call_type = get_call_name(draw)
    # the position of the letter determines where it's called from
    # but we don't use this information, we just brute force check for calls
    if draw[0] == call_type[0]: # from kamicha
        return int(draw[1:3])
    elif draw[2] == call_type[0]: # from toimen
        return int(draw[3:5])
    elif draw[4] == call_type[0]: # from shimocha
        return int(draw[5:7])
    elif len(draw) > 7 and draw[6] == call_type[0]: # from shimocha
        return int(draw[7:9])
    assert False, f"failed to extract {call_type} tile from {draw}"

def read_kyoku(raw_kyoku: Log) -> Kyoku:
    [
        [current_round, current_honba, num_riichis],
        scores,
        dora_indicators,
        ura_indicators,
        haipai0,
        draws0,
        discards0,
        haipai1,
        draws1,
        discards1,
        haipai2,
        draws2,
        discards2,
        haipai3,
        draws3,
        discards3,
        result
    ] = raw_kyoku
    hand = [haipai0, haipai1, haipai2, haipai3]
    draws = [draws0, draws1, draws2, draws3]
    discards = [discards0, discards1, discards2, discards3]

    # assume we're player 1 (south)
    
    # get a sequence of events based on discards only
    turn = current_round
    if current_round >= 4:
        turn -= 4
    last_turn = None
    last_discard = None
    i = [0,0,0,0]
    visible_tiles = []
    events: List[Any] = []
    gas = 1000
    num_dora = 1
    shanten = list(map(calculate_shanten, hand))
    for t in range(4):
        events.append((t, "haipai", hand[t]))
        events.append((t, "shanten", shanten[t]))
    while gas >= 0:
        gas -= 1
        if i[turn] >= len(discards[turn]):
            break

        # pon / kan handling
        # we have to look at the next draw of every player first
        # if any of them pons or kans the previously discarded tile, control goes to them
        turn_changed = False
        if last_discard is not None:
            for t in range(4):
                if turn != t and i[t] < len(draws[t]):
                    draw = draws[t][i[t]]
                    if type(draw) is str:
                        called_tile = extract_call_tile(draw)
                        if remove_red_five(called_tile) == remove_red_five(last_discard):
                            turn = t
                            turn_changed = True
                            break
        if turn_changed:
            last_discard = None
            continue

        # first handle the draw
        # could be a regular draw, chii, pon, or daiminkan
        # then handle the discard
        # could be a regular discard, riichi, kakan, or ankan

        def handle_call(call: str):
            """called every time a call happens"""
            call_type = get_call_name(call)
            called_tile = extract_call_tile(call)
            events.append((turn, call_type, called_tile))
            nonlocal num_dora
            if call_type in ["minkan", "ankan", "kakan"]:
                num_dora += 1
                visible_tiles.append(called_tile) # account for visible kan tile
            return called_tile

        draw = draws[turn][i[turn]]
        if type(draw) is str:
            hand[turn].append(handle_call(draw))
        else:
            assert type(draw) == int, f"failed to handle unknown draw type: {draw}"
            hand[turn].append(draw)
            events.append((turn, "draw", draw))

        discard = discards[turn][i[turn]]
        if type(discard) is str:
            last_discard = handle_call(discard)
            last_discard = last_discard if last_discard != 60 else draw # 60 = tsumogiri
            hand[turn].remove(last_discard)
            visible_tiles.append(last_discard)
        elif discard == 0: # the draw earlier was daiminkan, so no discard happened
            pass
        else:
            assert type(discard) == int, f"failed to handle unknown discard type: {discard}"
            last_discard = discard if discard != 60 else draw # 60 = tsumogiri
            hand[turn].remove(last_discard)
            visible_tiles.append(last_discard)
            events.append((turn, "discard", last_discard))

        new_shanten = calculate_shanten(hand[turn])
        if new_shanten != shanten[turn]: # compare both the shanten number and the iishanten group
            events.append((turn, "shanten_change", shanten[turn], new_shanten))
            shanten[turn] = new_shanten


        i[turn] += 1 # done processing this draw/discard

        # check if the resulting hand is tenpai
        potential_waits = get_waits(hand[turn])
        if len(potential_waits) > 0:
            ukeire = calculate_ukeire(hand[turn], visible_tiles + dora_indicators[:num_dora])
            events.append((turn, "tenpai", sorted_hand(hand[turn]), potential_waits, ukeire))

        # change turn to next player
        turn += 1
        if turn == 4:
            turn = 0
    assert gas >= 0, "ran out of gas"
    assert len(dora_indicators) == num_dora, "there's a bug in counting dora"

    # get waits of final hands
    final_waits = [get_waits(h) for h in hand]
    final_ukeire = [calculate_ukeire(h, visible_tiles + dora_indicators) for h in hand]

    dora_indicators[:num_dora]
    return {
        "round": current_round,
        "honba": current_honba,
        "events": events,
        "result": result,
        "hands": hand,
        "final_waits": final_waits,
        "final_ukeire": final_ukeire,
    }

def fetch_game(link: str) -> Log:
    # expects a link like 'https://tenhou.net/0/?log=2023072712gm-0089-0000-eff781e1&tw=1'
    identifier = link.split("https://tenhou.net/0/?log=")[1].split("&")[0]
    player = link[-1]
    try:
        f = open(f"cached_games/game-{identifier}.json", 'r')
        return json.load(f)["log"]
    except Exception as e:
        import requests
        import os
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        url = f"https://tenhou.net/5/mjlog2json.cgi?{identifier}"
        print(f" Fetching game log at url {url}")
        r = requests.get(url=url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        log = r.json()
        if not os.path.isdir("cached_games"):
            os.mkdir("cached_games")
        with open(f"cached_games/game-{identifier}.json", "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False)
        return log["log"]

def load_game(filename: str, player: int) -> None:
    with open(filename, 'r') as file:
        log = json.loads(re.sub(r"//.*?\n", "", file.read()))["log"]
        return log

def analyze_game(link: str) -> None:
    print(f"Analyzing game {link}:")
    log = fetch_game(link)
    player = int(link[-1])
    for raw_kyoku in log:
        kyoku = read_kyoku(raw_kyoku)
        evaluate_unluckiness(kyoku, player)

import sys
if __name__ == "__main__":
    assert len(sys.argv) == 2, "expected one argument, the tenhou url"
    link = sys.argv[1]
    assert link != "", "expected one argument, the tenhou url"
    assert link.startswith("https://tenhou.net/0/?log="), "expected tenhou link starting with https://tenhou.net/0/?log="
    if not link[:-1].endswith("&tw="):
        print("Assuming you're the first east player, since tenhou link did not end with ?tw=<number>")
    analyze_game(link)


    # shanten tests

    # hand = [12,15,51,23,25,33,39,41,42,44,45,45,46]
    # print(ph(hand), calculate_shanten(hand))

    # print("tenpai:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,37,37])[0] == 0 # 11123m123567p77s  tenpai
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36])[0] == 0
    # print("kutsuki iishanten:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,28,38])[0] == 1.1 # 11123m1235678p8s  kutsuki iishanten
    # assert calculate_shanten([11,12,13,23,24,25,52,33,37,38,39,42,42])[0] == 1.1
    # print("headless iishanten:")
    # assert calculate_shanten([11,11,12,13,13,21,22,23,25,26,27,37,38])[0] == 1.2 # 11223m123567p78s  headless iishanten
    # print("complete iishanten:")
    # assert calculate_shanten([11,11,11,12,13,13,21,22,23,25,26,37,37])[0] == 1.3 # 111233m12356p77s  complete iishanten
    # print("floating tile iishanten:")
    # assert calculate_shanten([11,11,11,12,13,17,21,22,23,25,26,37,37])[0] == 1.4 # 111237m12356p77s  floating tile iishanten
    # print("2+ shanten:")
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,43])[0] == 2 # 19m245p125678s33z  2-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,47])[0] == 3 # 19m245p125678s37z  3-shanten
    # assert calculate_shanten([11,12,16,18,22,26,27,34,41,42,44,45,46])[0] == 4 # 1268m267p4s12456z  4-shanten
    # assert calculate_shanten([12,15,51,23,25,33,39,41,42,44,45,45,46])[0] == 4






# limit before we split this into multiple files: 1000 lines
