import functools
import re
import google.protobuf as pb  # type: ignore[import]
from .proto import liqi_combined_pb2 as proto
from google.protobuf.message import Message  # type: ignore[import]
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from typing import *
from .classes import CallInfo, Draw, Event, Hand, Kyoku, Ron, Score, Tsumo, GameMetadata, Dir
from .constants import DORA, LIMIT_HANDS, TRANSLATE, YAKU_NAMES, YAKUMAN, YAOCHUUHAI
from .utils import is_mangan, ph, apply_delta_scores, normalize_red_five, round_name, sorted_hand, to_placement, translate_tenhou_yaku
from .yaku import get_yakuman_tenpais, get_yakuman_waits, debug_yaku
from pprint import pprint

# This file contains all the logic for fetching and parsing game logs into `Kyoku`s.
# 
# `__init__.py` calls the entry point `parse_game_link`, which takes a game log link
#    and returns a tuple (kyokus, game metadata, player specified in the link).
#   
# `fetch_majsoul`/`fetch_tenhou` handle requesting and caching game logs given a link.
# 
# `parse_majsoul`/`parse_tenhou` parse said game logs into a list of `Event`s
#   for each kyoku, as well as a `GameMetadata` object containing information about
#   the game across kyokus. They both use `postprocess_events` to turn each `Event` list
#   into a `Kyoku` object, and return the resulting list of `Kyoku`s, plus the
#   `GameMetadata` object.
#   
# The `GameMetadata` class is basically not used in InjusticeJudge, but other
#   callers of `parse_game_link` might take interest in it.
# NOTE: Currently working on removing the GameMetadata class, and putting all
#   the relevant information into the Kyoku class instead.
# 
# The sole uses of the resulting `Kyoku` objects are:
# - `determine_flags` in `flags.py`,
# - `evaluate_injustices` in `injustices.py`.

def save_cache(filename: str, data: bytes) -> None:
    """Save data to a cache file"""
    import os
    # make sure the cache directory exists
    if not os.path.isdir("cached_games"):
        os.mkdir("cached_games")
    # make sure we have enough space
    dir_size = sum(os.path.getsize(os.path.join(dirpath, f)) for dirpath, _, filenames in os.walk("cached_games") for f in filenames)
    if dir_size < (1024 ** 3): # 1GB
        with open(f"cached_games/{filename}", "wb") as file:
            file.write(data)

###
### parsing-related types
###

TenhouLog = List[List[List[Any]]]
MajsoulLog = List[Message]

###
### postprocess events obtained from parsing
###

def postprocess_events(all_events: List[List[Event]], metadata: GameMetadata) -> List[Kyoku]:
    """
    Go through a game (represented as a list of events) and add more events to it
    e.g. shanten changes, tenpai, ending nagashi discards
    Return a list of kyoku, which contains the new event list plus all data about the round
    """
    kyokus: List[Kyoku] = []
    for events, dora_indicators, ura_indicators in zip(all_events, metadata.dora_indicators, metadata.ura_indicators):
        assert len(events) > 0, "somehow got an empty events list"
        kyoku: Kyoku = Kyoku()
        nagashi_eligible: List[int] = [True] * metadata.num_players
        visible_tiles: List[int] = []
        num_doras = 1
        for i, (seat, event_type, *event_data) in enumerate(events):
            kyoku.events.append(events[i]) # copy every event we process
            # if len(kyoku.hands) == metadata.num_players:
            #     print(seat, event_type, ph(kyoku.hands[seat].closed_part), "|", ph(kyoku.hands[seat].open_part), event_data)
            if event_type == "haipai":
                hand = Hand(event_data[0])
                assert len(hand.tiles) == 13, f"haipai was length {len(hand.tiles)}, expected 13"
                kyoku.hands.append(hand)
                kyoku.pond.append([])
                kyoku.furiten.append(False)
                kyoku.haipai.append(hand)
                kyoku.final_draw_event_index.append(-1)
                kyoku.final_discard_event_index.append(-1)
            elif event_type == "start_game":
                kyoku.round, kyoku.honba, kyoku.riichi_sticks, kyoku.start_scores = event_data
                kyoku.num_players = metadata.num_players
                kyoku.tiles_in_wall = 70 if kyoku.num_players == 4 else 55
                kyoku.starting_doras = [DORA[d] for d in dora_indicators] + ([51, 52, 53] if metadata.use_red_fives else [])
                kyoku.doras = kyoku.starting_doras.copy()
                kyoku.uras = [DORA[d] for d in ura_indicators]
                kyoku.haipai_ukeire = [hand.ukeire(dora_indicators[:num_doras]) for hand in kyoku.hands]
            elif event_type == "draw":
                tile = event_data[0]
                kyoku.hands[seat] = kyoku.hands[seat].add(tile)
                kyoku.final_draw = tile
                kyoku.final_draw_event_index[seat] = len(kyoku.events) - 1
                kyoku.tiles_in_wall -= 1
                assert len(kyoku.hands[seat].tiles) == 14
            elif event_type in {"discard", "riichi"}: # discards
                tile, *_ = event_data
                old_shanten = kyoku.hands[seat].shanten
                kyoku.hands[seat] = kyoku.hands[seat].remove(tile)
                kyoku.final_discard = tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                visible_tiles.append(tile)
                kyoku.pond[seat].append(tile)
                # check if shanten changed
                new_shanten = kyoku.hands[seat].shanten
                if old_shanten != new_shanten:
                    # calculate ukeire/furiten (if not tenpai, gives 0/False)
                    ukeire = kyoku.hands[seat].ukeire(visible_tiles + dora_indicators[:num_doras])
                    kyoku.furiten[seat] = new_shanten[0] == 0 and any(w in kyoku.pond[seat] for w in new_shanten[1])
                    kyoku.events.append((seat, "shanten_change", old_shanten, new_shanten, kyoku.hands[seat], ukeire, kyoku.furiten[seat]))
                    if new_shanten[0] == 0:
                        # check for yakuman tenpai, excluding kazoe yakuman
                        yakuman_waits: List[Tuple[str, Set[int]]] = [(y, get_yakuman_waits(kyoku.hands[seat], y)) for y in get_yakuman_tenpais(kyoku.hands[seat])]
                        # only report the yakuman if the waits are not dead
                        visible = visible_tiles + dora_indicators[:num_doras] + list(kyoku.hands[seat].tiles)
                        yakuman_types: Set[str] = {t for t, waits in yakuman_waits if not all(visible.count(wait) == 4 for wait in waits)}
                        if len(yakuman_types) > 0:
                            kyoku.events.append((seat, "yakuman_tenpai", yakuman_types, yakuman_waits))
                # check for nagashi
                if nagashi_eligible[seat] and tile not in YAOCHUUHAI:
                    kyoku.events.append((seat, "end_nagashi", seat, "discard", tile))
                    nagashi_eligible[seat] = False
            elif event_type in {"chii", "pon", "minkan"}: # calls
                called_tile, call_tiles, call_dir = event_data
                if event_type != "minkan":
                    kyoku.hands[seat] = kyoku.hands[seat].add(called_tile)
                    assert len(kyoku.hands[seat].tiles) == 14
                kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo(event_type, called_tile, call_dir, call_tiles))
                # check for nagashi
                callee_seat = (seat + call_dir) % 4
                if nagashi_eligible[callee_seat]:
                    kyoku.events.append((seat, "end_nagashi", callee_seat, event_type, called_tile))
                    nagashi_eligible[callee_seat] = False
            elif event_type in {"ankan", "kakan", "kita"}: # special discards
                called_tile, call_tiles, call_dir = event_data
                # if kakan, replace the old pon call with kakan
                # and add the pon call to the kakan tiles
                if event_type == "kakan":
                    kyoku.hands[seat] = kyoku.hands[seat].kakan(called_tile)
                elif event_type == "ankan":
                    kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo("ankan", called_tile, Dir.SELF, [called_tile]*4))
                elif event_type == "kita":
                    kyoku.hands[seat] = kyoku.hands[seat].kita()
                kyoku.hands[seat] = kyoku.hands[seat].remove(called_tile)
                kyoku.final_discard = called_tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                assert len(kyoku.hands[seat].tiles) == 13
                visible_tiles.append(called_tile)
            elif event_type == "end_game":
                unparsed_result = event_data[0]
                hand_is_hidden = [len(hand.open_part) == 0 for hand in kyoku.hands]
                kyoku.result = parse_result(unparsed_result, kyoku.round, metadata.num_players, hand_is_hidden, [h.kita_count for h in kyoku.hands])
                # emit events for placement changes
                placement_before = to_placement(kyoku.start_scores)
                new_scores = apply_delta_scores(kyoku.start_scores, kyoku.result[1].score_delta)
                placement_after = to_placement(new_scores)
                for old, new in set(zip(placement_before, placement_after)) - {(x,x) for x in range(4)}:
                    kyoku.events.append((placement_before.index(old), "placement_change", old+1, new+1, kyoku.start_scores, kyoku.result[1].score_delta))
                # if tsumo or kyuushu kyuuhai, pop the final tile from the winner's hand
                if kyoku.result[0] == "tsumo" or (kyoku.result[0] == "draw" and kyoku.result[1].name == "9 terminals draw"):
                    for seat in range(kyoku.num_players):
                        if len(kyoku.hands[seat].tiles) == 14:
                            kyoku.hands[seat] = kyoku.hands[seat].remove(kyoku.final_draw)
                            break
                else: # otherwise we pop the deal-in tile from the visible tiles (so ukeire calculation won't count it)
                    assert kyoku.final_discard == visible_tiles.pop(), f"final discard of round {round_name(kyoku.round, kyoku.honba)} was not equal to the last visible tile"
                # save final waits and ukeire
                for seat in range(kyoku.num_players):
                    ukeire = kyoku.hands[seat].ukeire(visible_tiles + dora_indicators[:num_doras])
                    kyoku.final_ukeire.append(ukeire)
            # emit dora event, and increment doras for kans
            if event_type in {"minkan", "ankan", "kakan"}:
                called_tile, call_tiles, call_dir = event_data
                # might not have another dora if we get rinshan right after this
                if num_doras < len(dora_indicators):
                    kyoku.events.append((seat, "dora_indicator", dora_indicators[num_doras], called_tile))
                num_doras += 1

        assert len(kyoku.hands) > 0, f"somehow we never initialized the kyoku at index {len(kyokus)}"
        if len(kyokus) == 0:
            assert (kyoku.round, kyoku.honba) == (0, 0), f"kyoku numbering didn't start with East 1: instead it's {round_name(kyoku.round, kyoku.honba)}"
        else:
            assert (kyoku.round, kyoku.honba) != (kyokus[-1].round, kyokus[-1].honba), f"duplicate kyoku entered: {round_name(kyoku.round, kyoku.honba)}"
        for i in range(metadata.num_players):
            assert len(kyoku.hands[i].tiles) == 13, f"on {round_name(kyoku.round, kyoku.honba)}, player {i}'s hand was length {len(kyoku.hands[i].tiles)} when the round ended, should be 13"
        kyokus.append(kyoku)
        # debug_yaku(kyoku)
    return kyokus

def parse_result(result: List[Any], round: int, num_players: int, hand_is_hidden: List[bool], kita_counts: List[int]) -> Tuple[Any, ...]:
    """
    Given a Tenhou game result list, parse it into a tuple where the first
    element is either "ron", "tsumo", or "draw"; the remainder of the tuple
    consists of "Ron" object(s), a "Tsumo" object, or a "Draw" object.
    These objects store all the relevant information about the win.
    (score changes, who won from who, was it dama, and yaku)
    """
    result_type, *scoring = result
    ret: List[Tuple[str, Any]] = []
    scores = [scoring[i*2:i*2+2] for i in range((len(scoring)+1)//2)]
    if result_type == "和了":
        rons: List[Ron] = []
        for [score_delta, tenhou_result_list] in scores:
            [winner, won_from, pao_seat, _, *yaku_strs] = tenhou_result_list
            kwargs = {
                "score_delta": score_delta,
                "winner": winner,
                "dama": hand_is_hidden[winner] and not any(y.startswith("立直") for y in yaku_strs),
                "score": Score.from_tenhou_list(tenhou_result_list=tenhou_result_list,
                                                round=round,
                                                num_players=num_players,
                                                kita=kita_counts[winner]),
                "pao_from": None if winner == pao_seat else pao_seat,
            }
            if winner == won_from: # tsumo
                return ("tsumo", Tsumo(**kwargs))
            else:
                rons.append(Ron(**kwargs, won_from=won_from))
        return ("ron", *rons)
    elif result_type in ({"流局", "全員聴牌", "全員不聴", "流し満貫"} # exhaustive draws
                       | {"九種九牌", "四家立直", "三家和了", "四槓散了", "四風連打"}): # abortive draws
        return ("draw", Draw(score_delta = scores[0][0] if len(scores) > 0 else [0]*num_players,
                             name = TRANSLATE[result_type]))
    else:
        assert False, f"unhandled Tenhou result type {result_type}"

###
### loading and parsing mahjong soul games
###

class MahjongSoulAPI:
    """Helper class to interface with the Mahjong Soul API"""
    def __init__(self, endpoint):
        self.endpoint = endpoint
    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(self.endpoint)
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
        assert not res.error.code, f"{method.full_name} request received error {res.error.code}"
        return res

@functools.cache
def parse_wrapped_bytes(data):
    """Used to unwrap Mahjong Soul messages"""
    wrapper = proto.Wrapper()
    wrapper.ParseFromString(data)
    name = wrapper.name.strip(f'.{proto.DESCRIPTOR.package}')
    try:
        msg = pb.reflection.MakeClass(proto.DESCRIPTOR.message_types_by_name[name])()
        msg.ParseFromString(wrapper.data)
    except KeyError as e:
        raise Exception(f"Failed to find message name {name}")
    return name, msg

async def fetch_majsoul(link: str) -> Tuple[MajsoulLog, Dict[str, Any], int]:
    """
    Fetch a raw majsoul log from a given link, returning a parsed log and the seat of the player specified through `_a...` or `_a..._[0-3]`
    Example link: https://mahjongsoul.game.yo-star.com/?paipu=230814-90607dc4-3bfd-4241-a1dc-2c639b630db3_a878761203
    """
    identifier_pattern = r'\?paipu=([0-9a-zA-Z-]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Mahjong Soul link: {link}")
    identifier = identifier_match.group(1)

    if not all(c in "0123456789abcdef-" for c in identifier):
        # deanonymize the link
        codex = "0123456789abcdefghijklmnopqrstuvwxyz"
        decoded = ""
        for i, c in enumerate(identifier):
            decoded += "-" if c == "-" else codex[(codex.index(c) - i + 55) % 36]
        identifier = decoded

    try:
        f = open(f"cached_games/game-{identifier}.log", 'rb')
        record = proto.ResGameRecord()  # type: ignore[attr-defined]
        record.ParseFromString(f.read())
    except Exception:
        import os
        import dotenv
        import requests
        import uuid

        dotenv.load_dotenv("config.env")
        USERNAME = os.getenv("ms_username")
        PASSWORD = os.getenv("ms_password")
        
        if USERNAME is not None and PASSWORD is not None:
            import hmac
            import hashlib
            # login to the Chinese server with USERNAME and PASSWORD
            MS_VERSION = requests.get(url="https://game.maj-soul.com/1/version.json").json()["version"][:-2]

            async with MahjongSoulAPI("wss://gateway-hw.maj-soul.com:443/gateway") as api:
                client_version_string = f"web-{MS_VERSION}"
                client_device_info = {"is_browser": True}
                print("Calling login...")
                await api.call(
                    "login",
                    account=USERNAME,
                    password=hmac.new(b"lailai", PASSWORD.encode(), hashlib.sha256).hexdigest(),
                    device=client_device_info,
                    random_key=str(uuid.uuid1()),
                    client_version_string=client_version_string)
                print("Calling fetchGameRecord...")
                record = await api.call("fetchGameRecord", game_uuid=identifier, client_version_string=client_version_string)
        else:
            # login to the EN server with UID and TOKEN
            UID = os.getenv("ms_uid")
            TOKEN = os.getenv("ms_token")
            MS_VERSION = requests.get(url="https://mahjongsoul.game.yo-star.com/version.json").json()["version"][:-2]
            async with MahjongSoulAPI("wss://mjusgs.mahjongsoul.com:9663/") as api:
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
                client_device_info = {"platform": "pc", "hardware": "pc", "os": "mac", "is_browser": True, "software": "Firefox", "sale_platform": "web"}  # type: ignore[dict-item]
                await api.call("oauth2Login", type=7, access_token=oauth_token, reconnect=False, device=client_device_info, random_key=str(uuid.uuid1()), client_version={"resource": f"{MS_VERSION}.w"}, currency_platforms=[], client_version_string=f"web-{MS_VERSION}", tag="en")
                print("Calling fetchGameRecord...")
                record = await api.call("fetchGameRecord", game_uuid=identifier, client_version_string=f"web-{MS_VERSION}")
        save_cache(filename=f"game-{identifier}.log", data=record.SerializeToString())
    parsed = parse_wrapped_bytes(record.data)[1]
    if parsed.actions != []:
        actions = [parse_wrapped_bytes(action.result) for action in parsed.actions if len(action.result) > 0]
    else:
        actions = [parse_wrapped_bytes(record) for record in parsed.records]
    
    player = 0
    if link.count("_") == 2:
        player = int(link[-1])
    else:
        player_pattern = r'_a(\d+)'
        player_match = re.search(player_pattern, link)
        if player_match is not None:
            ms_account_id = int((((int(player_match.group(1))-1358437)^86216345)-1117113)/7)
            for acc in record.head.accounts:
                if acc.account_id == ms_account_id:
                    player = acc.seat
                    break
    return actions, MessageToDict(record.head), player

def parse_majsoul(actions: MajsoulLog, metadata: Dict[str, Any]) -> Tuple[List[Kyoku], GameMetadata]:
    """
    Parse a Mahjong Soul log fetched with `fetch_majsoul`.
    """
    all_dora_indicators: List[List[int]] = []
    all_ura_indicators: List[List[int]] = []
    dora_indicators: List[int] = []
    ura_indicators: List[int] = []
    convert_tile = lambda tile: {"m": 51, "p": 52, "s": 53}[tile[1]] if tile[0] == "0" else {"m": 10, "p": 20, "s": 30, "z": 40}[tile[1]] + int(tile[0])
    majsoul_hand_to_tenhou = lambda hand: list(sorted_hand(map(convert_tile, hand)))
    last_seat = 0
    all_events: List[List[Event]] = []
    events: List[Event] = []
    # constants obtained in the main loop below
    num_players: int = -1
    
    def end_round(result):
        nonlocal events
        nonlocal all_events
        nonlocal dora_indicators
        nonlocal ura_indicators
        events.append((t, "end_game", result))
        all_events.append(events)
        all_dora_indicators.append(dora_indicators)
        all_ura_indicators.append(ura_indicators)
        events = []
    
    def same_tile(tile1: str, tile2: str):
        # check if two tiles are equal, counting red
        # five as equal to regular fives
        if tile1[1] == tile2[1]:
            number1, number2 = tile1[0], tile2[0]
            if number1 == number2: return True
            if number1 == '0': return number2 == '5'
            if number1 == '5': return number2 == '0'
        return False

    for name, action in actions:
        if name == "RecordNewRound":
            haipai = [sorted_hand(majsoul_hand_to_tenhou(h)) for h in [action.tiles0, action.tiles1, action.tiles2, action.tiles3] if len(h) > 0]
            num_players = len(haipai)
            # dealer starts with 14, remove one tile and turn it into a draw
            *haipai[action.ju], first_tile = haipai[action.ju]
            for t in range(num_players):
                events.append((t, "haipai", haipai[t]))
            # `round` can jump from `2` to `4` for sanma, and this is okay because
            # the round printer is agnostic (0 -> East 1, 4 -> South 1).
            # this is actually how Tenhou logs store the round counter
            round = action.chang*4 + action.ju
            honba = action.ben
            riichi_sticks = action.liqibang
            events.append((t, "start_game", round, honba, riichi_sticks, list(action.scores)))
            # pretend we drew the first tile
            events.append((action.ju, "draw", first_tile))
            dora_indicators = [convert_tile(dora) for dora in action.doras]
        elif name == "RecordDealTile":
            events.append((action.seat, "draw", convert_tile(action.tile)))
            dora_indicators.extend(convert_tile(dora) for dora in action.doras)
        elif name == "RecordDiscardTile":
            tile = convert_tile(action.tile)
            events.append((action.seat, "riichi" if action.is_liqi else "discard", tile))
        elif name == "RecordChiPengGang":
            call_tiles = list(map(convert_tile, action.tiles))
            called_tile = call_tiles[-1]
            if len(action.tiles) == 4:
                call_type = "minkan"
            elif same_tile(action.tiles[0], action.tiles[1]):
                call_type = "pon"
            else:
                call_type = "chii"
            call_dir = Dir((last_seat - action.seat) % 4)
            events.append((action.seat, call_type, called_tile, call_tiles, call_dir))
        elif name == "RecordAnGangAddGang":
            tile = convert_tile(action.tiles)
            if action.type == 2:
                call_type = "kakan"
            elif action.type == 3:
                call_type = "ankan"
            else:
                raise Exception(f"unhandled RecordAnGangAddGang of type {action.type}: {action}")
            events.append((action.seat, call_type, tile, [tile], 0))
            dora_indicators.extend(convert_tile(dora) for dora in action.doras)
        elif name == "RecordHule":
            # construct a tenhou game result array
            result: List[Any] = ["和了"]
            for h in action.hules:
                han = sum(fan.val for fan in h.fans)
                score_string = f"{h.fu}符{han}飜"
                if any(fan.id in YAKUMAN.keys() for fan in h.fans):
                    score_string = "役満"
                elif han >= 6 or is_mangan(han, h.fu):
                    score_string = LIMIT_HANDS[han]
                point_string = f"{h.point_rong}点"
                pao_seat = h.seat
                if h.baopai > 0:
                    pao_seat = h.baopai - 1
                else:
                    if h.zimo:
                        if h.point_zimo_qin > 0:
                            point_string = f"{h.point_zimo_xian}-{h.point_zimo_qin}点"
                        else:
                            point_string = f"{h.point_zimo_xian}点∀"
                yakus = [name for _, name in sorted((fan.id, f"{YAKU_NAMES[fan.id]}({'役満' if fan.id in YAKUMAN.keys() else str(fan.val)+'飜'})") for fan in h.fans if fan.val)]
                result.append(list(action.delta_scores))
                result.append([h.seat, last_seat, pao_seat, score_string+point_string, *yakus])
                dora_indicators = majsoul_hand_to_tenhou(h.doras)
                ura_indicators = majsoul_hand_to_tenhou(h.li_doras)
            end_round(result)
        elif name == "RecordNoTile":
            if len(action.scores[0].delta_scores) == 0: # everybody/nobody is tenpai, so no score change
                end_round(["流局", [0]*num_players])
            else:
                end_round(["流局", *(score_info.delta_scores for score_info in action.scores)])
        elif name == "RecordBaBei": # kita
            events.append((action.seat, "kita", 44, [44], 0))
        elif name == "RecordLiuJu": # abortive draw
            # TODO: `action,.type` for 三家和了
            if action.type == 1:
                end_round(["九種九牌", [0]*num_players])
            elif action.type == 2:
                end_round(["四風連打", [0]*num_players])
            elif action.type == 3:
                end_round(["四槓散了", [0]*num_players])
            elif action.type == 4:
                end_round(["四家立直", [0]*num_players])
            else:
                raise Exception(f"unhandled RecordLiuJu of type {action.type}: {action}. Is this triple-ron draw?")
        else:
            raise Exception(f"unhandled action {name}: {action}")
        if hasattr(action, "seat"):
            last_seat = action.seat
    assert len(all_events) > 0, "unable to read any kyoku"

    # parse metadata
    acc_data = sorted((acc.get("seat", 0), acc["nickname"]) for acc in metadata["accounts"])
    result_data = sorted((res.get("seat", 0), res["partPoint1"], res["totalPoint"]) for res in metadata["result"]["players"])
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = [acc_data[i][1] for i in range(num_players)],
                                   game_score = [result_data[i][1] for i in range(num_players)],
                                   final_score = [result_data[i][2] for i in range(num_players)],
                                   dora_indicators = all_dora_indicators,
                                   ura_indicators = all_ura_indicators,
                                   use_red_fives = True)
    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators)
    return postprocess_events(all_events, parsed_metadata), parsed_metadata

###
### loading and parsing tenhou games
###

def fetch_tenhou(link: str) -> Tuple[TenhouLog, Dict[str, Any], int]:
    """
    Fetch a raw tenhou log from a given link, returning a parsed log and the specified player's seat
    Example link: https://tenhou.net/0/?log=2023072712gm-0089-0000-eff781e1&tw=1&ts=4
    """
    import json
    identifier_pattern = r'\?log=([0-9a-zA-Z-]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Tenhou link: {link}")
    identifier = identifier_match.group(1)
    
    player_pattern = r'&tw=(\d)'
    player_match = re.search(player_pattern, link)
    if player_match is None:
        player = 0
    else:
        player = int(player_match.group(1))

    try:
        f = open(f"cached_games/game-{identifier}.json", 'r')
        game_data = json.load(f)
    except Exception:
        import requests
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        url = f"https://tenhou.net/5/mjlog2json.cgi?{identifier}"
        # print(f" Fetching game log at url {url}")
        r = requests.get(url=url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        game_data = r.json()
        save_cache(filename=f"game-{identifier}.json", data=json.dumps(game_data, ensure_ascii=False).encode("utf-8"))
    log = game_data["log"]
    del game_data["log"]
    return log, game_data, player

def parse_tenhou(raw_kyokus: TenhouLog, metadata: Dict[str, Any]) -> Tuple[List[Kyoku], GameMetadata]:
    all_events: List[List[Event]] = []
    all_dora_indicators: List[List[int]] = []
    all_ura_indicators: List[List[int]] = []
    use_red_fives = "aka51" in metadata["rule"] and metadata["rule"]["aka51"]
    # check to see if the name of the fourth player is empty; Sanma if empty, Yonma if not empty.
    num_players: int = 3 if metadata["name"][3] == "" else 4
    @functools.cache
    def get_call_dir(call: str):
        """
        Returns the number of seats "away" from the current
        player, in a yonma setting
        """
        ret = Dir.KAMICHA if call[0].isalpha() else \
              Dir.TOIMEN if call[2].isalpha() else \
              Dir.SHIMOCHA if call[4].isalpha() else \
              Dir.SHIMOCHA if call[6].isalpha() else None # call[6] is for kans from shimocha
        assert ret is not None, f"couldn't figure out direction of {draw}"
        return ret
    @functools.cache
    def extract_call_tiles(call: str, use_red_fives: bool) -> List[int]:
        """
        returns the called tile as the first tile;
        this matters when the call contains a red five.
        Will also normalize red five if necessary.
        """
        for c in call:
            if c.isalpha():
                call_tiles_str = "".join(reversed(call.split(c)))
                call_tiles = []
                for i in range(0, len(call_tiles_str), 2):
                    call_tile = int(call_tiles_str[i:i+2])
                    if not use_red_fives:
                        call_tile = normalize_red_five(call_tile)
                    call_tiles.append(call_tile)
                return call_tiles
        assert False, f"unable to extract the call tiles from call {call}"

    for raw_kyoku in raw_kyokus:
        [[round, honba, riichi_sticks],
         scores, dora_indicators, ura_indicators,
         haipai0, draws0, discards0,
         haipai1, draws1, discards1,
         haipai2, draws2, discards2,
         haipai3, draws3, discards3, result] = raw_kyoku
        # if we don't use red fives, turn all red fives to non red fives in haipai
        # (tenhou keeps 51,52,53 in these lists and just displays them as normal fives)
        # note that draws and discards can have strings, in which the red fives are handled
        # later
        if not use_red_fives:
            lists: List[List[int]] = \
                [haipai0, haipai1, haipai2, haipai3, dora_indicators, ura_indicators]
            for lst in lists:
                for j, value in enumerate(lst):
                    lst[j] = normalize_red_five(value)
        # setup lists for number of players
        haipai   = [haipai0,   haipai1,   haipai2,   haipai3][:num_players]
        draws    = [draws0,    draws1,    draws2,    draws3][:num_players]
        discards = [discards0, discards1, discards2, discards3][:num_players]
        all_dora_indicators.append(dora_indicators)
        all_ura_indicators.append(ura_indicators)
        # print("========", round_name(round, honba), "========")
        
        events: List[Event] = []
        # need to be 4, NOT num_players
        curr_seat = round % 4
        i = [0] * num_players
        for seat in range(num_players):
            events.append((seat, "haipai", sorted_hand(haipai[seat])))
        events.append((seat, "start_game", round, honba, riichi_sticks, scores))

        # Emit events for draws and discards and calls, in order
        # stops when the current player has no more draws; remaining
        # draws handled after this loop
        while i[curr_seat] < len(draws[curr_seat]):
            keep_curr_seat = False
            def handle_call(call: str) -> int:
                """
                Called every time a call happens. Returns the called tile.
                Removes red fives when they are not in the ruleset
                (through `extract_call_tiles()`)
                """
                call_tiles = extract_call_tiles(call, use_red_fives)
                called_tile = call_tiles[0]

                call_type = "chii"   if "c" in call else \
                            "riichi" if "r" in call else \
                            "pon"    if "p" in call else \
                            "kita"   if "f" in call else \
                            "kakan"  if "k" in call else \
                            "ankan"  if "a" in call else \
                            "minkan" if "m" in call else "" # minkan = daiminkan, but we want it to start with "m"
                assert call_type != "", f"couldn't figure out call name of {call}"

                if call_type in {"riichi", "kita", "ankan", "kakan"}:
                    call_dir = Dir.SELF
                else:
                    call_dir = get_call_dir(call)
                    assert call_dir != Dir.SELF, f"somehow called {call_type} on ourselves"
                
                events.append((curr_seat, call_type, called_tile, call_tiles, call_dir))

                if call_type in {"minkan", "ankan", "kakan", "kita"}:
                    nonlocal keep_curr_seat
                    keep_curr_seat = True # we get another turn after any kan/kita
                
                return called_tile

            # first handle the draw
            # can be either a draw, [c]hii, [p]on, or dai[m]inkan event
            draw = draws[curr_seat][i[curr_seat]]
            if type(draw) is str:
                # extract the called tile from the string, removing red five
                # if necessary inside handle_call()
                draw = handle_call(draw)
            elif draw == 0:
                # skip this draw/discard
                assert discards[curr_seat][i[curr_seat]] == 0
                i[curr_seat] += 1
                continue
            else:
                if not use_red_fives:
                    draw = normalize_red_five(draw)
                events.append((curr_seat, "draw", draw))

            # if you tsumo, there's no next discard, so we jump out here
            if i[curr_seat] >= len(discards[curr_seat]):
                i[curr_seat] += 1 # to satisfy the assert check later
                break

            # then handle the discard
            # can be either a discard, [r]iichi, [a]nkan, [k]akan, or kita(f).
            discard = discards[curr_seat][i[curr_seat]]
            if discard == "r60": # tsumogiri riichi
                events.append((curr_seat, "riichi", draw, [draw], 0))
            elif type(discard) is str:
                # `handle_call()` removes the red five if necessary
                discard = handle_call(discard)
            elif discard == 0: # the draw earlier was daiminkan, so no discard happens
                pass
            else:
                if discard == 60:
                    # tsumogiri
                    discard = draw
                elif not use_red_fives:
                    # tedashi -- removes the five if necessary
                    discard = normalize_red_five(discard)
                events.append((curr_seat, "discard", discard))

            i[curr_seat] += 1 # done processing the ith draw/discard for this player

            # pon / kan handling
            # we have to look at the next draw of every player before changing curr_seat
            # if any of them pons or kans the previously discarded tile, control goes to them
            # NOTE: in tenhou format, if there's both a chii and a pon waiting for us,
            #       pon always takes precedence over the chii
            for seat in range(num_players):
                # check if a next draw exists for a player other than curr_seat
                if curr_seat != seat and i[seat] < len(draws[seat]):
                    # check that the next draw is a pon or daiminkan
                    if type(next_draw := draws[seat][i[seat]]) is str and ("p" in next_draw or "m" in next_draw):
                        # check that it's calling from us, and that it's the same tile we discarded
                        same_dir = get_call_dir(next_draw) == Dir((curr_seat - seat) % 4)
                        same_tile = extract_call_tiles(next_draw, use_red_fives)[0] == discard
                        if same_dir and same_tile:
                            curr_seat = seat
                            keep_curr_seat = True # don't increment turn after this
                            break

            # unless we keep_curr_seat, change turn to next player 
            curr_seat = curr_seat if keep_curr_seat else (curr_seat+1) % num_players

        assert all(i[seat] >= len(draws[seat]) for seat in range(num_players)), f"game ended prematurely in {round_name(round, honba)} on {curr_seat}'s turn; i = {i}, max i = {list(map(len, draws))}"
        events.append((seat, "end_game", result))
        all_events.append(events)

    # parse metadata
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = metadata["name"],
                                   game_score = metadata["sc"][::2],
                                   final_score = list(map(lambda s: int(1000*s), metadata["sc"][1::2])),
                                   dora_indicators = all_dora_indicators,
                                   ura_indicators = all_ura_indicators,
                                   use_red_fives = use_red_fives)

    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators)
    return postprocess_events(all_events, parsed_metadata), parsed_metadata

async def parse_game_link(link: str, specified_player: int = 0) -> Tuple[List[Kyoku], GameMetadata, int]:
    """Given a game link, fetch and parse the game into kyokus"""
    # print(f"Analyzing game {link}:")
    if "tenhou.net/" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        if metadata["name"][3] == "":
            assert (specified_player or player) < 3, "Can't specify North player in a sanma game"
        kyokus, parsed_metadata = parse_tenhou(tenhou_log, metadata)
    elif "mahjongsoul" in link or "maj-soul" or "majsoul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        # Old CN (?): http://majsoul.union-game.com/0/?paipu=190303-335e8b25-7f5c-4bd1-9ac0-249a68529e8d_a93025901
        majsoul_log, metadata, player = await fetch_majsoul(link)
        assert (specified_player or player) < len(metadata["accounts"]), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata = parse_majsoul(majsoul_log, metadata)
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`")
    kyokus[-1].is_final_round = True
    if specified_player is not None:
        player = specified_player
    return kyokus, parsed_metadata, player
