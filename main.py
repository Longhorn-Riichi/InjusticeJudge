import asyncio
import functools
from pprint import pprint
from enum import Enum
from typing import *

###
### types
###

from google.protobuf.message import Message  # type: ignore[import]
TenhouLog = List[List[Any]]
MajsoulLog = Tuple[Message, bytes]
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
RED_FIVE = {51: 15, 52: 25, 53: 35}
toggle_red = lambda tile: int(str(tile)[::-1])
remove_red_five = lambda tile: RED_FIVE[tile] if tile in RED_FIVE.keys() else tile
remove_red_fives = lambda hand: list(map(remove_red_five, hand))
sorted_hand = lambda hand: sorted(hand, key=remove_red_five)

###
### ukeire and shanten calculations
###

@functools.cache
def _calculate_shanten(_starting_hand: Tuple[int]) -> Tuple[float, List[int]]:
    assert len(_starting_hand) == 13, f"calculate_shanten() needs a 13-tile hand, hand passed in has {len(_starting_hand)} tiles"
    starting_hand = list(sorted_hand(_starting_hand)) # not necessary, but helpful when debugging

    # standard shanten
    def try_remove_all_tiles(hand: Iterable[int], tiles: Iterable[int]) -> List[int]:
        hand_copy = list(hand)
        for tile in tiles:
            if tile in hand_copy:
                hand_copy.remove(tile)
            elif tile in [15,25,35,51,52,53] and toggle_red(tile) in hand_copy:
                hand_copy.remove(toggle_red(tile))
            else:
                return list(hand)
        return hand_copy
    remove_all = lambda hands, to_groups: set(tuple(try_remove_all_tiles(hand, group)) for hand in hands for tile in set(hand) for group in to_groups(tile))
    hands = {tuple(starting_hand)}

    # try to remove all groups first
    succ = lambda tile: 0 if tile in {0,19,29,39,41,42,43,44,45,46,47} else (tile*10)-494 if tile in {51,52,53} else tile+1
    make_groups = lambda tile: [[tile, tile, tile], [tile, succ(tile), succ(succ(tile))]]
    remove_groups = lambda hands: functools.reduce(lambda hs, _: remove_all(hs, make_groups), range(4), hands)
    hands = remove_groups(hands)

    # only keep the hands with min length, since we want to have as many groups removed as possible
    min_length = min(len(hand) for hand in hands)
    taatsus = set(filter(lambda hand: len(hand) == min_length, hands))
    hands = set(taatsus)
    num_groups = (13 - min_length) // 3

    make_taatsus = lambda tile: [[tile, tile], [tile, succ(tile)], [tile, succ(succ(tile))]]
    remove_taatsus = lambda hands: functools.reduce(lambda hs, _: remove_all(hs, make_taatsus), range(6), hands)
    count_floating = lambda hand: min(len(hand) for hand in remove_taatsus({hand}))
    count_pairs = lambda hand: len(list(filter(lambda ct: ct > 1, Counter(remove_red_fives(hand)).values())))

    shanten: float = 99
    if num_groups == 4:
        shanten = 0 # tanki wait
    else:
        for pairs, floating in zip(map(count_pairs, hands), map(count_floating, hands)):
            # print(shanten, ph(hand), num_groups, "groups", pairs, "pairs", floating, "floating")
            needs_pair = 1 if floating <= (3-num_groups) and pairs == 0 else 0
            shanten = min(shanten, needs_pair + (3 + floating - num_groups) // 2)

    assert shanten >= 0, "somehow got negative shanten"

    # if iishanten, get the type of iishanten based on possible remaining tiles
    floating_iishanten_tiles: Set[int] = set()
    complete_iishanten_tiles: Set[Tuple[int, ...]] = set()
    headless_iishanten_tiles: Set[int] = set()
    kutsuki_iishanten_tiles: Set[int] = set()
    return_data: List[int] = []
    def removed_red_fives(hand: Iterable[int]) -> Tuple[int, ...]:
        return tuple(remove_red_fives(list(hand)))
    if shanten == 1:
        for hand in remove_taatsus(hands):
            if num_groups == 2 and len(hand) == 3:
                tile = sorted_hand(hand)[0]
                # check if the hand is a complex shape
                t1, t2, t3, t5 = tile, succ(tile), succ(succ(tile)), succ(succ(succ(succ(tile))))
                for shape in [[t1,t1,t2],[t1,t2,t2],[t1,t1,t3],[t1,t3,t3],[t1,t3,t5]]:
                    if len(try_remove_all_tiles(remove_red_fives(hand), shape)) == 0:
                        # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(hand)}")
                        complete_iishanten_tiles = complete_iishanten_tiles.union([hand])
            elif num_groups == 2 and len(hand) == 1:
                # print(f"{ph(starting_hand)} is floating tile iishanten on {ph(hand)}")
                floating_iishanten_tiles = floating_iishanten_tiles.union(hand)
            elif num_groups == 3 and len(hand) in [2,4]:
                for tile in set(hand):
                    hand_copy = tuple(try_remove_all_tiles(hand, [tile, tile]))
                    if len(hand_copy) == 4:
                        # print(f"{ph(starting_hand)} is headless iishanten on {ph(hand_copy)}")
                        headless_iishanten_tiles = headless_iishanten_tiles.union(hand_copy)
                    elif len(hand) == 4:
                        # print(f"{ph(starting_hand)} is kutsuki iishanten on {ph(hand_copy)}")
                        kutsuki_iishanten_tiles = kutsuki_iishanten_tiles.union(hand_copy)

        if len(kutsuki_iishanten_tiles) > 0:
            shanten = 1.1
            return_data = sorted_hand(kutsuki_iishanten_tiles)
            # print(f"{ph(starting_hand)} is kutsuki iishanten, with kutsuki tiles {ph(return_data)}")
        elif len(headless_iishanten_tiles) > 0:
            shanten = 1.2
            return_data = sorted_hand(headless_iishanten_tiles)
            # print(f"{ph(starting_hand)} is headless iishanten, with shapes {ph(return_data)}")
        elif len(complete_iishanten_tiles) > 0:
            shanten = 1.3
            return_data = sorted_hand(flatmap(lambda x: x, complete_iishanten_tiles))
            # print(f"{ph(starting_hand)} is complete iishanten, with complex shape {ph(return_data)}")
        elif len(floating_iishanten_tiles) > 0:
            shanten = 1.4
            return_data = sorted_hand(floating_iishanten_tiles)
            # print(f"{ph(starting_hand)} is floating tile iishanten, with floating tiles {ph(return_data)}")
    elif shanten == 0: # standard tenpai, get waits (excluding red fives)
        hand = tuple(remove_red_fives(starting_hand))
        side_tiles = lambda tile: [] if tile >= 40 else ([] if tile in [11,21,31] else [tile-1]) + ([] if tile in [19,29,39] else [tile+1])
        possible_winning_tiles = set(hand).union(flatmap(side_tiles, hand))
        makes_winning_hand = lambda tile: () in remove_all(remove_groups([(*starting_hand, tile)]), lambda tile: [[tile, tile]])
        return_data = sorted_hand(filter(makes_winning_hand, possible_winning_tiles))
    else:
        # chiitoitsu shanten
        num_unique_pairs = count_pairs(starting_hand)
        shanten = min(shanten, 6 - num_unique_pairs)
        if shanten <= 1:
            hand = tuple(starting_hand)
            for tile in set(hand):
                hand = tuple(try_remove_all_tiles(hand, [tile, tile]))
            return_data = sorted_hand(hand)
        if shanten == 1:
            shanten = 1.5

        # kokushi musou shanten
        shanten = min(shanten, (12 if num_unique_pairs >= 1 else 13) - len({11,19,21,29,31,39,41,42,43,44,45,46,47}.intersection(starting_hand)))
        if shanten <= 1 and return_data == []:
            if num_unique_pairs > 0:
                return_data = list({11,19,21,29,31,39,41,42,43,44,45,46,47}.difference(starting_hand))
            else:
                return_data = [11,19,21,29,31,39,41,42,43,44,45,46,47]
        if shanten == 1:
            shanten = 1.6
    return shanten, return_data

def calculate_shanten(starting_hand: Iterable[int]) -> Tuple[float, List[int]]:
    # this just converts the input to a tuple so it can be serialized as a cache key
    return _calculate_shanten(tuple(starting_hand))

def calculate_ukeire(hand: List[int], visible: List[int]):
    shanten, waits = calculate_shanten(hand)
    if shanten != 0:
        return 0
    waits = remove_red_fives(waits)
    ukeire = 4 * len(waits)
    visible_tiles = remove_red_fives(hand + visible)
    for wait in waits:
        while wait in visible_tiles:
            visible_tiles.remove(wait)
            ukeire -= 1
    return ukeire

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

###
### round flags used to determine injustices
###

Flags = Enum("Flags", "_SENTINEL"
    " CHASER_GAINED_POINTS"
    " CHASING_PLAYER_HAS_WORSE_WAIT"
    " FIVE_SHANTEN_START"
    " YOU_FOLDED_FROM_TENPAI"
    " GAME_ENDED_WITH_RON"
    " GAME_ENDED_WITH_RYUUKYOKU"
    " NINE_DRAWS_NO_IMPROVEMENT"
    " YOU_GAINED_POINTS"
    " YOU_GOT_CHASED"
    " YOU_LOST_POINTS"
    " YOU_REACHED_TENPAI"
    " YOU_TENPAI_FIRST"

    # unused:
    " CHASER_LOST_POINTS"
    " GAME_ENDED_WITH_TSUMO"

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
    someone_is_tenpai = False
    for event in kyoku["events"]:
        if event[0] == player:
            if event[1] == "shanten":
                starting_player_shanten = event[2]
                player_shanten = event[2]
                if player_shanten[0] >= 5:
                    flags.append(Flags.FIVE_SHANTEN_START)
                    data.append({"shanten": player_shanten[0]})
            elif event[1] == "shanten_change":
                assert starting_player_shanten is not None
                player_shanten = event[3]
                draws_since_shanten_change = 0
                if event[2][0] == 0 and event[3][0] > 0:
                    flags.append(Flags.YOU_FOLDED_FROM_TENPAI)
                    data.append({})
            elif event[1] in ["draw", "minkan"]:
                draws_since_shanten_change += 1
                if player_shanten[0] > 0 and draws_since_shanten_change >= 9:
                    flags.append(Flags.NINE_DRAWS_NO_IMPROVEMENT)
                    data.append({"shanten": player_shanten[0],
                                 "iishanten_tiles": player_shanten[1],  # type: ignore[dict-item]
                                 "turns": draws_since_shanten_change})
        if event[1] == "tenpai":
            if event[0] == player:
                if Flags.YOU_FOLDED_FROM_TENPAI in flags:
                    ix = flags.index(Flags.YOU_FOLDED_FROM_TENPAI)
                    del flags[ix]
                    del data[ix]
                flags.append(Flags.YOU_REACHED_TENPAI)
                data.append({"hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})
                if not someone_is_tenpai:
                    flags.append(Flags.YOU_TENPAI_FIRST)
                    data.append({})
            elif Flags.YOU_TENPAI_FIRST in flags:
                flags.append(Flags.YOU_GOT_CHASED)
                data.append({"player": event[0],
                             "hand": event[2],
                             "wait": event[3],
                             "ukeire": event[4]})
            someone_is_tenpai = True

    if kyoku["result"][0] == "和了":
        if 0 in kyoku["result"][1]:
            flags.append(Flags.GAME_ENDED_WITH_RON)
            data.append({})
        else:
            flags.append(Flags.GAME_ENDED_WITH_TSUMO)
            data.append({})
        if kyoku["result"][1][player] < 0:
            flags.append(Flags.YOU_LOST_POINTS)
            data.append({"amount": kyoku["result"][1][player]})
        elif kyoku["result"][1][player] > 0:
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
                player_data = data[flags.index(Flags.YOU_REACHED_TENPAI)]
                player_ukeire = player_data["ukeire"]
                chaser_ukeire = chaser_player_data["ukeire"]
                if chaser_ukeire < player_ukeire: # type: ignore
                    flags.append(Flags.CHASING_PLAYER_HAS_WORSE_WAIT)
                    player_wait = player_data["wait"]
                    chaser_wait = chaser_player_data["wait"]
                    data.append({"your_wait": player_wait,
                                 "chaser_wait": chaser_wait,
                                 "your_ukeire": player_ukeire,
                                 "chaser_ukeire": chaser_ukeire})
    elif kyoku["result"][0] in ["流局", "全員聴牌"] :
        flags.append(Flags.GAME_ENDED_WITH_RYUUKYOKU)
        data.append({})

    # TODO: other results?

    return flags, data

def evaluate_unluckiness(kyoku: Kyoku, player: int) -> None:
    global injustices
    round_name = f"East {kyoku['round']+1}" if kyoku["round"] <= 3 else f"South {kyoku['round']-3}"
    round_name += f" ({kyoku['honba']} honba)"
    flags, data = determine_flags(kyoku, player)
    for i in injustices:
        if all(flag in flags for flag in i["required_flags"]) and all(flag not in flags for flag in i["forbidden_flags"]):
            i["callback"](flags, data, round_name)

###
### injustice definitions
###

injustices: List[Dict[str, Any]] = []
InjusticeFunc = Callable[[List[Flags], List[Dict[str, Any]], str], None]
def injustice(require: List[Flags] = [], forbid: List[Flags] = []) -> Callable[[InjusticeFunc], InjusticeFunc] :
    """decorator for DIY injustices, see below for usage"""
    global injustices
    def decorator(callback):
        injustices.append({"callback": callback, "required_flags": require, "forbidden_flags": forbid})
        return lambda f: f
    return decorator

# each injustice takes a list of flags
# if all flags are satisfied in a certain round, the decorated function is called

# Print if you dealt into someone
@injustice(require=[Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS])
def dealt_into_someone(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    # print(f"No unluckiness detected in {round_name}, but you dealt into someone")
    pass

# Print if your tenpai got chased by a worse wait, and they won
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.YOU_TENPAI_FIRST, Flags.YOU_GOT_CHASED,
                    Flags.CHASER_GAINED_POINTS, Flags.CHASING_PLAYER_HAS_WORSE_WAIT],
            forbid=[Flags.GAME_ENDED_WITH_RYUUKYOKU, Flags.YOU_GAINED_POINTS, Flags.YOU_LOST_POINTS,
                    Flags.YOU_FOLDED_FROM_TENPAI])
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
@injustice(require=[Flags.YOU_REACHED_TENPAI, Flags.YOU_TENPAI_FIRST,
                    Flags.YOU_GOT_CHASED, Flags.CHASING_PLAYER_HAS_WORSE_WAIT,
                    Flags.GAME_ENDED_WITH_RON, Flags.YOU_LOST_POINTS, Flags.CHASER_GAINED_POINTS],
            forbid=[Flags.YOU_FOLDED_FROM_TENPAI])
def dealt_into_chaser_with_worse_wait(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    chase_data = data[flags.index(Flags.CHASING_PLAYER_HAS_WORSE_WAIT)]
    your_wait = chase_data["your_wait"]
    chaser_wait = chase_data["chaser_wait"]
    your_ukeire = chase_data["your_ukeire"]
    chaser_ukeire = chase_data["chaser_ukeire"]
    print(f"Major unluckiness detected in {round_name}:"
          f" your wait {ph(your_wait)} ({your_ukeire} ukeire)"
          f" was chased by a worse wait {ph(chaser_wait)} ({chaser_ukeire} ukeire), and you dealt into it")

# Print if you failed to improve your shanten for at least nine consecutive draws
@injustice(require=[Flags.NINE_DRAWS_NO_IMPROVEMENT],
            forbid=[Flags.YOU_REACHED_TENPAI])
def shanten_hell(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    shanten_data = data[len(flags) - 1 - flags[::-1].index(Flags.NINE_DRAWS_NO_IMPROVEMENT)]
    turns = shanten_data["turns"]
    shanten = shanten_data["shanten"]
    iishanten_tiles = shanten_data["iishanten_tiles"]
    if len(iishanten_tiles) > 0:
        print(f"Unluckiness detected in {round_name}: you were stuck at {SHANTEN_NAMES[shanten]} ({ph(iishanten_tiles)}) for {turns} turns")
    else:
        print(f"Unluckiness detected in {round_name}: you were stuck at {SHANTEN_NAMES[shanten]} for {turns} turns")

# Print if you started with atrocious shanten and never got to tenpai
@injustice(require=[Flags.FIVE_SHANTEN_START],
            forbid=[Flags.YOU_REACHED_TENPAI])
def five_shanten_start(flags: List[Flags], data: List[Dict[str, Any]], round_name: str) -> None:
    shanten = data[flags.index(Flags.FIVE_SHANTEN_START)]["shanten"]
    print(f"Unluckiness detected in {round_name}: you started at {shanten}-shanten")

###
### loading and parsing mahjong soul games
###

import google.protobuf as pb  # type: ignore[import]
import proto.liqi_combined_pb2 as proto
class MahjongSoulAPI:
    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect("wss://mjusgs.mahjongsoul.com:9663/")
        self.ix = 0
        return self
    async def __aexit__(self, err_type, err_value, traceback):
        await self.ws.close()

    async def call(self, name, **fields: Dict[str, Any]) -> Message:
        method = next((svc.FindMethodByName(name) for svc in proto.DESCRIPTOR.services_by_name.values() if name in [method.name for method in svc.methods]), None)
        assert method is not None, f"couldn't find method {name}"

        req: Message = pb.reflection.MakeClass(method.input_type)(**fields)
        res: Message = pb.reflection.MakeClass(method.output_type)()

        tx: bytes = b'\x02' + self.ix.to_bytes(2, "little") + proto.Wrapper(name=f".{method.full_name}", data=req.SerializeToString()).SerializeToString()  # type: ignore[attr-defined]
        await self.ws.send(tx)
        rx: bytes = await self.ws.recv()
        assert rx[0] == 3, f"Expected response message, got message of type {rx[0]}"
        assert self.ix == int.from_bytes(rx[1:3], "little"), f"Expected response index {self.ix}, got index {int.from_bytes(rx[1:3], 'little')}"
        self.ix += 1

        wrapper: Message = proto.Wrapper()  # type: ignore[attr-defined]
        wrapper.ParseFromString(rx[3:])
        res.ParseFromString(wrapper.data)
        assert not res.error.code, f"{method.full_name} request recieved error {res.error.code}"
        return res

@functools.cache
def parse_wrapped_bytes(data):
    wrapper = proto.Wrapper()
    wrapper.ParseFromString(data)
    name = wrapper.name.strip(f'.{proto.DESCRIPTOR.package}')
    try:
        msg = pb.reflection.MakeClass(proto.DESCRIPTOR.message_types_by_name[name])()
        msg.ParseFromString(wrapper.data)
    except KeyError as e:
        raise Exception(f"Failed to find message name {name}")
    return name, msg

def parse_majsoul(log: MajsoulLog) -> List[Kyoku]:
    metadata, raw_actions = log
    kyokus: List[Kyoku] = []
    kyoku: Kyoku = {}
    visible_tiles: List[int] = []
    dora_indicators: List[int] = []
    shanten: List[Tuple[float, List[int]]] = []
    convert_tile = lambda tile: {"m": 51, "p": 52, "s": 53}[tile[1]] if tile[0] == "0" else {"m": 10, "p": 20, "s": 30, "z": 40}[tile[1]] + int(tile[0])
    majsoul_hand_to_tenhou = lambda hand: sorted_hand(list(map(convert_tile, hand)))
    pred = lambda tile: tile+8 if tile in {11,21,31} else 47 if tile == 41 else (tile*10)-496 if tile in {51,52,53} else tile-1
    for name, action in [parse_wrapped_bytes(action.result) for action in parse_wrapped_bytes(raw_actions)[1].actions if len(action.result) > 0]:
        if name == "RecordNewRound":
            if "events" in kyoku:
                kyokus.append(kyoku)
            kyoku = {
                "round": action.chang*4 + action.ju,
                "honba": action.ben,
                "events": [],
                "result": None,
                "hands": list(map(majsoul_hand_to_tenhou, [action.tiles0, action.tiles1, action.tiles2, action.tiles3])),
                "final_waits": None,
                "final_ukeire": None
            }
            dora_indicators = [pred(convert_tile(dora)) for dora in action.doras]
            visible_tiles = []
            first_tile: int = kyoku["hands"][action.ju].pop() # dealer starts with 14, remove the last tile so we can calculate shanten
            shanten = list(map(calculate_shanten, kyoku["hands"]))
            for t in range(4):
                kyoku["events"].append((t, "haipai", sorted_hand(kyoku["hands"][t])))
                kyoku["events"].append((t, "shanten", shanten[t]))
            # pretend we drew the first tile
            kyoku["events"].append((action.ju, "draw", first_tile))
            kyoku["hands"][action.ju].append(first_tile)
        elif name == "RecordDealTile":
            tile = convert_tile(action.tile)
            kyoku["events"].append((action.seat, "draw", tile))
            kyoku["hands"][action.seat].append(tile)
        elif name == "RecordDiscardTile":
            tile = convert_tile(action.tile)
            hand = kyoku["hands"][action.seat]
            kyoku["events"].append((action.seat, "discard", tile))
            hand.remove(tile)
            visible_tiles.append(tile)
            new_shanten = calculate_shanten(hand)
            if new_shanten != shanten[action.seat]:
                kyoku["events"].append((action.seat, "shanten_change", shanten[action.seat], new_shanten))
                shanten[action.seat] = new_shanten

            # check if the resulting hand is tenpai
            if new_shanten[0] == 0:
                ukeire = calculate_ukeire(hand, visible_tiles + dora_indicators)
                potential_waits = new_shanten[1]
                kyoku["events"].append((action.seat, "tenpai", sorted_hand(hand), potential_waits, ukeire))

            # TODO check shanten and tenpai waits
        elif name == "RecordChiPengGang":
            tile = convert_tile(action.tiles[-1])
            if action.tiles[0] == action.tiles[1]:
                kyoku["events"].append((action.seat, "pon", tile))
            elif len(action.tiles) == 4:
                kyoku["events"].append((action.seat, "minkan", tile))
                dora_indicators = [pred(convert_tile(dora)) for dora in action.doras]
            else:
                kyoku["events"].append((action.seat, "chii", tile))
            kyoku["hands"][action.seat].append(tile)
        elif name == "RecordAnGangAddGang":
            tile = convert_tile(action.tiles)
            kyoku["events"].append((action.seat, "ankan", tile))
            kyoku["hands"][action.seat].remove(tile)
            visible_tiles.append(tile)
            dora_indicators = [pred(convert_tile(dora)) for dora in action.doras]
        elif name == "RecordHule":
            if len(action.hules) > 1:
                print("don't know how tenhou represents multi ron")
            h = action.hules[0]
            if h.zimo:
                kyoku["hands"][h.seat].pop() # remove that tile so we can calculate waits/ukeire
            kyoku["result"] = ["和了", list(action.delta_scores), h.fans]
            kyoku["final_waits"] = [w for _, w in shanten]
            kyoku["final_ukeire"] = [calculate_ukeire(h, visible_tiles + dora_indicators) for h in kyoku["hands"]]
        elif name == "RecordNoTile":
            kyoku["result"] = ["流局", [score_info.delta_scores for score_info in action.scores]]
            kyoku["final_waits"] = [w for _, w in shanten]
            kyoku["final_ukeire"] = [calculate_ukeire(h, visible_tiles + dora_indicators) for h in kyoku["hands"]]
        else:
            print("unhandled action:", name, action)
    return kyokus

async def fetch_majsoul(link: str) -> Tuple[MajsoulLog, int]:    # expects a link like 'https://mahjongsoul.game.yo-star.com/?paipu=230814-90607dc4-3bfd-4241-a1dc-2c639b630db3_a878761203'
    assert link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="), "expected mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu="
    print("Assuming you're the first east player")
    player = 0

    identifier = link.split("https://mahjongsoul.game.yo-star.com/?paipu=")[1].split("_")[0]

    try:
        f = open(f"cached_games/game-{identifier}.json", 'rb')
        record = proto.ResGameRecord()  # type: ignore[attr-defined]
        record.ParseFromString(f.read())
        data = record.data
        return (record.head, record.data), player
    except Exception as e:
        import os
        from os.path import join, dirname
        import dotenv
        import requests
        import uuid
        env_path = join(dirname(__file__), "config.env")
        dotenv.load_dotenv("config.env")
        UID = os.environ.get("ms_uid")
        TOKEN = os.environ.get("ms_token")
        MS_VERSION = "0.10.259" # from https://mahjongsoul.game.yo-star.com/version.json

        async with MahjongSoulAPI() as api:
            print("Calling heatbeat...")
            await api.call("heatbeat")
            print("Requesting initial access token...")
            USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
            access_token = requests.post(url="https://passport.mahjongsoul.com/user/login", headers={"User-Agent": USER_AGENT, "Referer": "https://mahjongsoul.game.yo-star.com/"}, data={"uid":UID,"token":TOKEN,"deviceId":f"web|{UID}"}).json()["accessToken"]
            print("Requesting oauth access token...")
            oauth_token = (await api.call("oauth2Auth", type=7, code=access_token, uid=UID, client_version_string=f"web-{MS_VERSION}")).access_token
            print("Calling heatbeat...")
            await api.call("heatbeat")
            print("Calling oauth2Check...")
            assert (await api.call("oauth2Check", type=7, access_token=oauth_token)).has_account, "couldn't find account with oauth2Check"
            print("Calling oauth2Login...")
            client_device_info = {"platform": "pc", "hardware": "pc", "os": "mac", "is_browser": True, "software": "Firefox", "sale_platform": "web"}
            await api.call("oauth2Login", type=7, access_token=oauth_token, reconnect=False, device=client_device_info, random_key=str(uuid.uuid1()), client_version={"resource": f"{MS_VERSION}.w"}, currency_platforms=[], client_version_string=f"web-{MS_VERSION}", tag="en")
            print("Calling fetchGameRecord...")
            res3 = await api.call("fetchGameRecord", game_uuid=identifier, client_version_string=f"web-{MS_VERSION}")

        if not os.path.isdir("cached_games"):
            os.mkdir("cached_games")
        with open(f"cached_games/game-{identifier}.json", "wb") as f2:
            f2.write(res3.SerializeToString())

        return (res3.head, res3.data), player

###
### loading and parsing tenhou games
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

def parse_tenhou(raw_kyoku: TenhouLog) -> Kyoku:
    [
        [current_round, current_honba, num_riichis],
        scores,
        doras,
        uras,
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
    pred = lambda tile: tile+8 if tile in {11,21,31} else 47 if tile == 41 else (tile*10)-496 if tile in {51,52,53} else tile-1
    dora_indicators = list(map(pred, doras))

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
        events.append((t, "haipai", sorted_hand(hand[t])))
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
        if new_shanten[0] == 0:
            ukeire = calculate_ukeire(hand[turn], visible_tiles + dora_indicators[:num_dora])
            potential_waits = new_shanten[1]
            events.append((turn, "tenpai", sorted_hand(hand[turn]), potential_waits, ukeire))

        # change turn to next player
        turn += 1
        if turn == 4:
            turn = 0
    assert gas >= 0, "ran out of gas"
    assert len(dora_indicators) == num_dora, "there's a bug in counting dora"

    # get waits of final hands
    final_waits = [w for _, w in shanten]
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

def fetch_tenhou(link: str) -> Tuple[TenhouLog, int]:
    import json
    # expects a link like 'https://tenhou.net/0/?log=2023072712gm-0089-0000-eff781e1&tw=1'
    assert link.startswith("https://tenhou.net/0/?log="), "expected tenhou link starting with https://tenhou.net/0/?log="
    if not link[:-1].endswith("&tw="):
        print("Assuming you're the first east player, since tenhou link did not end with ?tw=<number>")

    identifier = link.split("https://tenhou.net/0/?log=")[1].split("&")[0]
    player = int(link[-1])
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
        return log["log"], player

def analyze_game(link: str) -> None:
    print(f"Analyzing game {link}:")
    kyokus = []
    if link.startswith("https://tenhou.net/0/?log="):
        tenhou_log, player = fetch_tenhou(link)
        for raw_kyoku in tenhou_log:
            kyoku = parse_tenhou(raw_kyoku)
            kyokus.append(kyoku)
    elif link.startswith("https://mahjongsoul.game.yo-star.com/?paipu="):
        majsoul_log, player = asyncio.run(fetch_majsoul(link))
        kyokus = parse_majsoul(majsoul_log)
    else:
        raise Exception("expected tenhou link starting with https://tenhou.net/0/?log="
                        "or mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu=")
    for kyoku in kyokus:
        evaluate_unluckiness(kyoku, player)

import sys
if __name__ == "__main__":
    assert len(sys.argv) == 2, "expected one argument, the tenhou/majsoul url"
    link = sys.argv[1]
    assert link != "", "expected one argument, the tenhou/majsoul url"
    analyze_game(link)

    # # shanten tests
    # hand = [24, 24, 52, 27, 28, 29, 33, 34, 35, 53, 37, 38, 39]
    # print(ph(hand), calculate_shanten(hand))

    # print("tenpai:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,37,37])[0] == 0   # 11123m123567p77s  tenpai
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36])[0] == 0
    # assert calculate_shanten([16,17,18,24,25,26,32,32,33,34,34,53,36])[1] == [32,35]
    # print("kutsuki iishanten:")
    # assert calculate_shanten([11,11,11,12,13,21,22,23,25,26,27,28,38])[0] == 1.1 # 11123m1235678p8s  kutsuki iishanten
    # assert calculate_shanten([11,12,13,23,24,25,52,33,37,38,39,42,42])[0] == 1.1
    # assert calculate_shanten([24,24,52,27,28,29,33,34,35,53,37,38,39])[0] == 1.1
    # assert calculate_shanten([24,24,52,27,28,29,33,34,35,53,37,38,39])[1] == [52,53]
    # print("headless iishanten:")
    # assert calculate_shanten([11,11,12,13,13,21,22,23,25,26,27,37,38])[0] == 1.2 # 11223m123567p78s  headless iishanten
    # print("complete iishanten:")
    # assert calculate_shanten([11,11,11,12,13,13,21,22,23,25,26,37,37])[0] == 1.3 # 111233m12356p77s  complete iishanten
    # print("floating tile iishanten:")
    # assert calculate_shanten([11,11,11,12,13,17,21,22,23,25,26,37,37])[0] == 1.4 # 111237m12356p77s  floating tile iishanten
    # print("chiitoitsu iishanten:")
    # assert calculate_shanten([15,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 0   # 5566m44577p5077s  chiitoitsu tenpai
    # assert calculate_shanten([11,15,16,16,24,24,52,27,27,35,53,37,37])[0] == 1.5 # 1566m44577p5077s  chiitoitsu iishanten
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,37,37])[0] == 1.5
    # assert calculate_shanten([15,16,16,17,24,24,52,27,27,35,53,36,39])[0] == 2
    # print("kokushi musou iishanten:")
    # assert calculate_shanten([14,19,21,29,29,31,39,41,42,44,45,46,47])[0] == 1.6 # 5667m44577p5577s  kokushi musou iishanten
    # assert calculate_shanten([19,19,21,29,29,31,39,41,42,44,46,46,47])[0] == 2
    # print("2+ shanten:")
    # assert calculate_shanten([11,19,23,24,25,31,32,35,36,37,38,43,43])[0] == 2   # 19m345p125678s33z  2-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,43])[0] == 3   # 19m245p125678s33z  3-shanten
    # assert calculate_shanten([11,19,22,24,25,31,32,35,36,37,38,43,47])[0] == 4   # 19m245p125678s37z  4-shanten
    # assert calculate_shanten([11,12,16,18,22,26,27,34,41,42,44,45,46])[0] == 5   # 1268m267p4s12456z  5-shanten
    # assert calculate_shanten([13,16,18,19,27,28,31,35,38,42,44,45,46])[0] == 6   # 3689m78p158s2456z  6-shanten
    # assert calculate_shanten([12,15,51,23,25,33,39,41,42,44,45,45,46])[0] == 4   # 150m25p39s124556z  4-shanten for chiitoitsu








# limit before we split this into multiple files: 1000 lines
