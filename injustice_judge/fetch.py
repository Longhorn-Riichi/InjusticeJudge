from dataclasses import dataclass
import dataclasses
import functools
import google.protobuf as pb  # type: ignore[import]
from .proto import liqi_combined_pb2 as proto
from google.protobuf.message import Message  # type: ignore[import]
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from typing import *
from .constants import CallInfo, Kyoku, Game, GameMetadata, DORA, DORA_INDICATOR, LIMIT_HANDS, YAKU_NAMES, YAKUMAN, YAOCHUUHAI
from .utils import ph, pt, closed_part, remove_red_five, round_name, sorted_hand, try_remove_all_tiles
from .shanten import calculate_shanten, calculate_ukeire
from pprint import pprint

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
Event = Tuple[Any, ...]

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
    Fetch a raw majsoul log from a given link, returning a parsed log and the specified player's seat
    Example link: https://mahjongsoul.game.yo-star.com/?paipu=230814-90607dc4-3bfd-4241-a1dc-2c639b630db3_a878761203
    """
    assert link.startswith(("https://mahjongsoul.game.yo-star.com/?paipu=",
                            "http://mahjongsoul.game.yo-star.com/?paipu=")), "expected mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu="
    if not "_a" in link:
        print("Assuming you're the first east player, since mahjong soul link did not end with _a<number>")

    identifier, *player_string = link.split("?paipu=")[1].split("_a")
    ms_account_id = None if len(player_string) == 0 else int((((int(player_string[0])-1358437)^86216345)-1117113)/7)
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
    return actions, MessageToDict(record.head), next((acc.seat for acc in record.head.accounts if acc.account_id == ms_account_id), 0)

def parse_majsoul(actions: MajsoulLog, metadata: Dict[str, Any]) -> Tuple[List[Kyoku], Dict[str, Any]]:
    """
    Parse a Mahjong Soul log fetched with `fetch_majsoul`.
    """
    kyokus: List[Kyoku] = []
    visible_tiles: List[int] = []
    dora_indicators: List[int] = []
    shanten: List[Tuple[float, List[int]]] = []
    convert_tile = lambda tile: {"m": 51, "p": 52, "s": 53}[tile[1]] if tile[0] == "0" else {"m": 10, "p": 20, "s": 30, "z": 40}[tile[1]] + int(tile[0])
    majsoul_hand_to_tenhou = lambda hand: list(sorted_hand(map(convert_tile, hand)))
    last_seat = 0
    for name, action in actions:
        if name == "RecordNewRound":
            if "kyoku" in locals():
                kyokus.append(kyoku)  # type: ignore[has-type]
            num_players = 4 if len(action.tiles3) > 0 else 3
            raw_haipais = [action.tiles0, action.tiles1, action.tiles2] + ([action.tiles3] if num_players == 4 else [])
            kyoku = Kyoku(
                round = action.chang*4 + action.ju,
                honba = action.ben,
                num_players = num_players,
                final_tile = 0,
                doras = [DORA[convert_tile(dora)] for dora in action.doras],
                events = [],
                result = [],
                hands = [majsoul_hand_to_tenhou(h) for h in raw_haipais],
                calls = [[] for _ in range(num_players)],
                call_info = [[] for _ in range(num_players)],
                pond = [[] for _ in range(num_players)],
                furiten = [False for _ in range(num_players)],
                final_waits = [],
                final_ukeire = [],
                haipai = [sorted_hand(majsoul_hand_to_tenhou(h)) for h in raw_haipais],
                haipai_shanten = []
                )
            nagashi_eligible: List[int] = [True] * num_players
            dora_indicators = [convert_tile(dora) for dora in action.doras]
            visible_tiles = []
            first_tile: int = kyoku.hands[action.ju].pop() # dealer starts with 14, remove the last tile so we can calculate shanten
            kyoku.haipai[action.ju] = kyoku.haipai[action.ju][:-1] # also pop for the starting_hand
            shanten = list(map(calculate_shanten, kyoku.hands))
            kyoku.haipai_shanten = list(shanten)
            for t in range(num_players):
                kyoku.events.append((t, "haipai", sorted_hand(kyoku.hands[t])))
                kyoku.events.append((t, "start_shanten", shanten[t]))
            # pretend we drew the first tile
            kyoku.events.append((action.ju, "draw", first_tile))
            kyoku.hands[action.ju].append(first_tile)
        elif name == "RecordDealTile":
            tile = convert_tile(action.tile)
            kyoku.events.append((action.seat, "draw", tile))
            kyoku.hands[action.seat].append(tile)
        elif name == "RecordDiscardTile":
            tile = convert_tile(action.tile)
            hand = kyoku.hands[action.seat]
            kyoku.events.append((action.seat, "discard", tile))
            if action.is_liqi:
                kyoku.events.append((action.seat, "riichi", tile))
            hand.remove(tile)
            visible_tiles.append(tile)
            kyoku.pond[action.seat].append(tile)
            dora_indicators = [DORA_INDICATOR[convert_tile(dora)] for dora in action.doras]
            closed_hand = closed_part(tuple(kyoku.hands[action.seat]), tuple(kyoku.calls[action.seat]))
            new_shanten = calculate_shanten(closed_hand)
            if new_shanten != shanten[action.seat]:
                kyoku.events.append((action.seat, "shanten_change", shanten[action.seat], new_shanten))
                shanten[action.seat] = new_shanten
                # check if the resulting hand is tenpai
                if new_shanten[0] == 0:
                    ukeire = calculate_ukeire(closed_hand, kyoku.calls[action.seat] + visible_tiles + dora_indicators)
                    potential_waits = new_shanten[1]
                    kyoku.events.append((action.seat, "tenpai", sorted_hand(hand), potential_waits, ukeire))
                    # check for furiten
                    if any(w in kyoku.pond[action.seat] for w in potential_waits):
                        kyoku.events.append((action.seat, "furiten"))
                        kyoku.furiten[action.seat] = True
                    else:
                        kyoku.furiten[action.seat] = False
            if tile not in YAOCHUUHAI and nagashi_eligible[action.seat]:
                kyoku.events.append((action.seat, "end_nagashi", action.seat, "discard", tile))
                nagashi_eligible[action.seat] = False
            kyoku.final_tile = tile
        elif name == "RecordChiPengGang":
            call_tiles = list(map(convert_tile, action.tiles))
            called_tile = call_tiles[-1]
            if len(action.tiles) == 4:
                call_type = "minkan"
                kyoku.hands[action.seat].remove(called_tile) # remove the extra tile from hand
            elif action.tiles[0] == action.tiles[1]:
                call_type = "pon"
            else:
                call_type = "chii"
            kyoku.events.append((action.seat, call_type, called_tile))
            kyoku.hands[action.seat].append(called_tile)
            if nagashi_eligible[last_seat]:
                kyoku.events.append((action.seat, "end_nagashi", last_seat, call_type, called_tile))
                nagashi_eligible[last_seat] = False
            kyoku.calls[action.seat].extend(call_tiles[:3]) # ignore any kan tile
            call_direction = (last_seat - action.seat) % 4
            kyoku.call_info[action.seat].append((call_type, called_tile, call_direction, call_tiles))
        elif name == "RecordAnGangAddGang":
            tile = convert_tile(action.tiles)
            # if kakan, replace the old pon call with kakan
            kakan_index = next((i for i, (call_t, t, _, _) in enumerate(kyoku.call_info[action.seat]) if call_t == "pon" and t == tile), None)
            if kakan_index is not None:
                call_type = "kakan"
                orig_direction = kyoku.call_info[action.seat][kakan_index][2]
                kyoku.call_info[action.seat][kakan_index] = (call_type, tile, orig_direction, [tile]*4)
            else:
                call_type = "ankan"
                kyoku.call_info[action.seat].append((call_type, tile, 0, [tile]*4))
            kyoku.events.append((action.seat, call_type, tile))
            kyoku.hands[action.seat].remove(tile)
            visible_tiles.append(tile)
            dora_indicators = [DORA_INDICATOR[convert_tile(dora)] for dora in action.doras]
            kyoku.final_tile = tile
        elif name == "RecordHule":
            kyoku.result = ["和了"]
            for h in action.hules:
                han = sum(fan.val for fan in h.fans)
                score_string = f"{h.fu}符{han}飜"
                if any(fan.id in YAKUMAN.keys() for fan in h.fans):
                    score_string = "役満"
                elif h.point_rong >= 8000:
                    assert han in LIMIT_HANDS, f"limit hand with {han} han is not in LIMIT_HANDS"
                    score_string = LIMIT_HANDS[han]
                point_string = f"{h.point_rong}点"
                if h.zimo:
                    if h.point_zimo_qin > 0:
                        point_string = f"{h.point_zimo_xian}-{h.point_zimo_qin}点"
                    else:
                        point_string = f"{h.point_zimo_xian}点∀"
                    kyoku.hands[h.seat].pop() # remove that tile so we can calculate waits/ukeire
                yakus = [name for _, name in sorted((fan.id, f"{YAKU_NAMES[fan.id]}({fan.val}飜)") for fan in h.fans)]
                kyoku.result.append(list(action.delta_scores))
                kyoku.result.append([h.seat, last_seat, h.seat, score_string+point_string, *yakus])
                kyoku.final_tile = convert_tile(h.hu_tile)
            kyoku.final_waits = [w for _, w in shanten]
            get_closed_part = lambda seat: closed_part(tuple(kyoku.hands[seat]), tuple(kyoku.calls[seat]))
            kyoku.final_ukeire = [calculate_ukeire(get_closed_part(seat), kyoku.calls[seat] + visible_tiles + dora_indicators) for seat in range(num_players)]
        elif name == "RecordNoTile":
            kyoku.result = ["流局", *(score_info.delta_scores for score_info in action.scores)]
            kyoku.final_waits = [w for _, w in shanten]
            get_closed_part = lambda seat: closed_part(tuple(kyoku.hands[seat]), tuple(kyoku.calls[seat]))
            kyoku.final_ukeire = [calculate_ukeire(get_closed_part(seat), kyoku.calls[seat] + visible_tiles + dora_indicators) for seat in range(num_players)]
        elif name == "RecordBaBei": # kita
            hand = kyoku.hands[action.seat]
            kyoku.events.append((action.seat, "kita"))
            kyoku.hands[action.seat].remove(44)
            visible_tiles.append(44)
        elif name == "RecordLiuJu": # abortive draw
            if action.type == 1:
                kyoku.events.append((action.seat, "terminal_draw"))
                kyoku.result = ["九種九牌", [0]*num_players]
                kyoku.final_waits = [w for _, w in shanten]
                kyoku.final_ukeire = [0]*num_players
            else:
                print(f"unhandled type {action.type} abortive draw:", action)
        else:
            print("unhandled action:", name, action)
        if hasattr(action, "seat"):
            last_seat = action.seat

    # parse metadata
    parsed_metadata = {
        "name": [()] * num_players,
        "game_score": [()] * num_players,
        "final_score": [()] * num_players
    }
    acc_data = sorted((acc.get("seat", 0), acc["nickname"]) for acc in metadata["accounts"])
    result_data = sorted((res.get("seat", 0), res["partPoint1"], res["totalPoint"]) for res in metadata["result"]["players"])
    for i in range(num_players):
        parsed_metadata["name"][i] = acc_data[i][1]
        parsed_metadata["game_score"][i] = result_data[i][1]
        parsed_metadata["final_score"][i] = result_data[i][2]

    assert "kyoku" in locals(), "unable to read any kyoku"
    kyokus.append(kyoku)
    return kyokus, parsed_metadata

###
### postprocess events obtained from parsing
###

def postprocess_events(all_events: List[List[Event]], metadata: GameMetadata) -> Game:
    game = []
    for events in all_events:
        kyoku: Kyoku = Kyoku()
        nagashi_eligible: List[int] = [True] * metadata.num_players
        dora_indicators: List[int] = []
        ura_indicators: List[int] = []
        visible_tiles: List[int] = []
        num_doras = 1
        for i, (seat, event_type, *event_data) in enumerate(events):
            kyoku.events.append(events[i]) # copy every event we process
            if event_type == "haipai":
                hand = event_data[0]
                kyoku.hands.append(list(hand))
                kyoku.calls.append([])
                kyoku.call_info.append([])
                kyoku.pond.append([])
                kyoku.furiten.append(False)
                kyoku.haipai.append(sorted_hand(hand))
            elif event_type == "start_game":
                kyoku.round, kyoku.honba, dora_indicators, ura_indicators = event_data
                kyoku.num_players = metadata.num_players
                kyoku.doras = [DORA[d] for d in dora_indicators]
                kyoku.uras = [DORA[d] for d in ura_indicators]
                kyoku.shanten = [calculate_shanten(h) for h in kyoku.hands]
                kyoku.haipai_shanten = list(kyoku.shanten)
                kyoku.events.extend((t, "start_shanten", s) for t, s in enumerate(kyoku.shanten))
            elif event_type == "draw":
                tile = event_data[0]
                kyoku.hands[seat].append(tile)
                assert len(kyoku.hands[seat]) == 14
            elif event_type in {"discard", "riichi"}: # discards
                tile, *_ = event_data
                kyoku.hands[seat].remove(tile)
                assert len(kyoku.hands[seat]) == 13
                visible_tiles.append(tile)
                kyoku.pond[seat].append(tile)
                # calculate shanten
                closed_hand = closed_part(tuple(kyoku.hands[seat]), tuple(kyoku.calls[seat]))
                new_shanten = calculate_shanten(closed_hand)
                if new_shanten != kyoku.shanten[seat]:
                    kyoku.events.append((seat, "shanten_change", kyoku.shanten[seat], new_shanten))
                    kyoku.shanten[seat] = new_shanten
                    # calculate ukeire if tenpai
                    if new_shanten[0] == 0:
                        ukeire = calculate_ukeire(closed_hand, kyoku.calls[seat] + visible_tiles + dora_indicators[:num_doras])
                        waits = new_shanten[1]
                        kyoku.events.append((seat, "tenpai", sorted_hand(kyoku.hands[seat]), waits, ukeire))
                        # check for furiten
                        if any(w in kyoku.pond[seat] for w in waits):
                            kyoku.events.append((seat, "furiten"))
                            kyoku.furiten[seat] = True
                        else:
                            kyoku.furiten[seat] = False
                # check for nagashi
                if nagashi_eligible[seat] and tile not in YAOCHUUHAI:
                    kyoku.events.append((seat, "end_nagashi", seat, "discard", tile))
                    nagashi_eligible[seat] = False
                kyoku.final_tile = tile
            elif event_type in {"chii", "pon", "minkan"}: # calls
                called_tile, call_tiles, call_from = event_data
                if event_type != "minkan":
                    kyoku.hands[seat].append(called_tile)
                    assert len(kyoku.hands[seat]) == 14
                kyoku.calls[seat].extend(call_tiles[:3]) # ignore any kan tile
                call_direction = (call_from - seat) % 4
                kyoku.call_info[seat].append(CallInfo(event_type, called_tile, call_direction, call_tiles))
                # check for nagashi
                if nagashi_eligible[call_from]:
                    kyoku.events.append((seat, "end_nagashi", call_from, event_type, called_tile))
                    nagashi_eligible[call_from] = False
            elif event_type in {"ankan", "kakan", "kita"}: # special discards
                called_tile, call_tiles, call_from = event_data
                # if kakan, replace the old pon call with kakan
                if event_type == "kakan":
                    pon_index = next((i for i, call_info in enumerate(kyoku.call_info[seat]) if call_info.type == "pon" and call_info.tile == tile), None)
                    assert pon_index is not None
                    orig_direction = kyoku.call_info[seat][pon_index].dir
                    kyoku.call_info[seat][pon_index] = CallInfo(event_type, called_tile, orig_direction, call_tiles)
                else:
                    kyoku.call_info[seat].append(CallInfo(event_type, called_tile, 0, call_tiles))
                kyoku.hands[seat].remove(called_tile)
                assert len(kyoku.hands[seat]) == 13
                visible_tiles.append(called_tile)
                kyoku.final_tile = called_tile
            elif event_type == "end_game":
                kyoku.result = event_data[0]
                # TODO make a result dataclass
            # increment doras for kans
            if event_type in {"minkan", "ankan", "kakan"}:
                num_doras += 1
        game.append(kyoku)
    return game

###
### loading and parsing tenhou games
###

def fetch_tenhou(link: str) -> Tuple[TenhouLog, Dict[str, Any], int]:
    """
    Fetch a raw tenhou log from a given link, returning a parsed log and the specified player's seat
    Example link: https://tenhou.net/0/?log=2023072712gm-0089-0000-eff781e1&tw=1
    """
    import json
    assert link.startswith(("https://tenhou.net/0/?log=",
                            "http://tenhou.net/0/?log=",
                            "https://tenhou.net/3/?log=",
                            "http://tenhou.net/3/?log=",
                            "https://tenhou.net/4/?log=",
                            "http://tenhou.net/4/?log=")), "expected tenhou link starting with https://tenhou.net/0/?log="
    if link[:-1].endswith("&ts="): # round number (1-8) to start on; we ignore this
        link = link.split("&ts=")[0]
    if not link[:-1].endswith("&tw="):
        print("Assuming you're the first east player, since tenhou link did not end with ?tw=<number>")
        player = 0
    else:
        player = int(link[-1])

    identifier = link.split("?log=")[1].split("&")[0]
    try:
        f = open(f"cached_games/game-{identifier}.json", 'r')
        game_data = json.load(f)
    except Exception as e:
        import requests
        import os
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        url = f"https://tenhou.net/5/mjlog2json.cgi?{identifier}"
        print(f" Fetching game log at url {url}")
        r = requests.get(url=url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        game_data = r.json()
        save_cache(filename=f"game-{identifier}.json", data=json.dumps(game_data, ensure_ascii=False).encode("utf-8"))
    log = game_data["log"]
    del game_data["log"]
    return log, game_data, player

def parse_tenhou(raw_kyokus: TenhouLog, metadata: Dict[str, Any]) -> Tuple[Game, Dict[str, Any]]:
    all_events = []
    num_players = 4
    for [[round, honba, num_riichis], scores, doras, uras,
         haipai0, draws0, discards0,
         haipai1, draws1, discards1,
         haipai2, draws2, discards2,
         haipai3, draws3, discards3, result] in raw_kyokus:
        
        turn = round % 4
        haipai          = cast(List[List[int]],             [haipai0, haipai1, haipai2, haipai3])
        draws           = cast(List[List[Union[int, str]]], [draws0, draws1, draws2, draws3])
        discards        = cast(List[List[Union[int, str]]], [discards0, discards1, discards2, discards3])
        i = [0] * num_players

        events: List[Event] = []
        
        for t in range(num_players):
            events.append((t, "haipai", sorted_hand(haipai[t])))

        events.append((t, "start_game", round, honba, doras, uras))

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
        def extract_call_tiles(call: str) -> List[int]:
            call_type = get_call_name(call)
            # the position of the letter determines where it's called from
            # but we don't use this information, we just brute force check for calls
            call_tiles = "".join(c for c in call if c.isdigit())
            return [int(call_tiles[i:i+2]) for i in range(0, len(call_tiles), 2)]

        def get_call_direction(call: str):
            if call[0].isalpha():
                return 3
            elif call[2].isalpha():
                return 2
            elif call[4].isalpha():
                return 1
            elif call[6].isalpha():
                return 1
            else:
                assert False, f"got invalid call {call}"

        # print("===", round_name(round, honba), "===")
        while i[turn] < len(draws[turn]):
            keep_turn = False
            def handle_call(call: str) -> int:
                """Called every time a call happens. Returns the called tile"""
                call_type = get_call_name(call)
                call_tiles = extract_call_tiles(call)
                call_direction = get_call_direction(call)
                call_from = (turn+call_direction)%4
                called_tile = call_tiles[0]
                events.append((turn, call_type, called_tile, call_tiles, call_from))
                nonlocal keep_turn
                keep_turn = keep_turn or call_type in {"minkan", "ankan", "kakan"}
                return called_tile

            # first handle the draw
            # can be either a draw, [c]hii, [p]on, or dai[m]inkan event
            draw = draws[turn][i[turn]]
            if type(draw) is str:
                draw = handle_call(draw)
            else:
                assert type(draw) == int, f"failed to handle unknown draw type: {draw}"
                events.append((turn, "draw", draw))
            # print(i,events[-1])

            # you don't have a next discard if you tsumo
            if i[turn] >= len(discards[turn]):
                i[turn] += 1
                break

            # then handle the discard
            # can be either a discard, [r]iichi, [a]nkan, or [k]akan event
            discard = discards[turn][i[turn]]
            if type(discard) is str:
                discard = handle_call(discard)
                discard = discard if discard != 60 else draw # 60 = tsumogiri
            elif discard == 0: # the draw earlier was daiminkan, so no discard happened
                pass
            else:
                assert type(discard) == int, f"failed to handle unknown discard type: {discard}"
                discard = discard if discard != 60 else draw # 60 = tsumogiri
                events.append((turn, "discard", discard))
            # print(i,events[-1])

            i[turn] += 1 # done processing turn's ith draw/discard

            # pon / kan handling
            # we have to look at the next draw of every player before changing the turn
            # if any of them pons or kans the previously discarded tile, control goes to them
            for t in range(num_players):
                # check if a next draw exists on a turn other than ours
                if turn != t and i[t] < len(draws[t]):
                    # check that next draw is a call
                    if type(next_draw := draws[t][i[t]]) is str:
                        call_type = get_call_name(next_draw)
                        called_tile = extract_call_tiles(next_draw)[0]
                        # make sure it's the same tile we discarded
                        same_tile = remove_red_five(called_tile) == remove_red_five(discard)
                        # make sure it's coming from the right direction
                        same_dir = (next_draw[0].isalpha() and turn == (t-1)%4) \
                                or (next_draw[2].isalpha() and turn == (t-2)%4) \
                                or (next_draw[4].isalpha() and turn == (t-3)%4)
                        if same_tile and same_dir:
                            turn = t
                            keep_turn = True
                            break

            # change turn to next player
            turn = turn if keep_turn else (turn+1) % num_players

        assert all(i[turn] >= len(draws[turn]) for turn in range(num_players)), f"game ended prematurely in {round_name(round, honba)} on {turn}'s turn; i = {i}, max i = {list(map(len, draws))}"
        events.append((t, "end_game", result))
        all_events.append(events)

    # parse metadata
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = metadata["name"],
                                   game_score = metadata["sc"][::2],
                                   final_score = list(map(lambda s: int(1000*s), metadata["sc"][1::2])))

    game = postprocess_events(all_events, parsed_metadata)
    return game, dataclasses.asdict(parsed_metadata)

async def parse_game_link(link: str, specified_player: int = 0) -> Tuple[List[Kyoku], Dict[str, Any], int]:
    """Given a game link, fetch and parse the game into kyokus"""
    # print(f"Analyzing game {link}:")
    if "tenhou.net" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        kyokus, parsed_metadata = parse_tenhou(tenhou_log, metadata)
    elif "mahjongsoul.game.yo-star.com" in link:
        majsoul_log, metadata, player = await fetch_majsoul(link)
        kyokus, parsed_metadata = parse_majsoul(majsoul_log, metadata)
    else:
        raise Exception("expected tenhou link starting with https://tenhou.net/0/?log="
                        " or mahjong soul link starting with https://mahjongsoul.game.yo-star.com/?paipu=")
    if specified_player is not None:
        player = specified_player
    return kyokus, parsed_metadata, player
