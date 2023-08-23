import dataclasses
import functools
import google.protobuf as pb  # type: ignore[import]
from .proto import liqi_combined_pb2 as proto
from google.protobuf.message import Message  # type: ignore[import]
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from typing import *
from .constants import CallInfo, Kyoku, DORA, DORA_INDICATOR, LIMIT_HANDS, YAKU_NAMES, YAKUMAN, YAOCHUUHAI
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
GameMetadata = Dict[str, List[Any]]

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

def parse_majsoul(actions: MajsoulLog, metadata: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], GameMetadata]:
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
            haipais = [action.tiles0, action.tiles1, action.tiles2]
            num_players = 3
            if len(action.tiles3) > 0:
                haipais.append(action.tiles3)
                num_players = 4
            nagashi: List[int] = [True] * num_players
            kyoku = Kyoku(
                round = action.chang*4 + action.ju,
                honba = action.ben,
                num_players = num_players,
                final_tile = 0,
                dora = [DORA[convert_tile(dora)] for dora in action.doras],
                events = [],
                result = [],
                hands = [majsoul_hand_to_tenhou(h) for h in haipais],
                calls = [[] for _ in range(num_players)],
                call_info = [[] for _ in range(num_players)],
                pond = [[] for _ in range(num_players)],
                furiten = [False for _ in range(num_players)],
                final_waits = [],
                final_ukeire = [],
                starting_hands = [sorted_hand(majsoul_hand_to_tenhou(h)) for h in haipais],
                starting_shanten = []
                )
            dora_indicators = [convert_tile(dora) for dora in action.doras]
            visible_tiles = []
            first_tile: int = kyoku.hands[action.ju].pop() # dealer starts with 14, remove the last tile so we can calculate shanten
            kyoku.starting_hands[action.ju] = kyoku.starting_hands[action.ju][:-1] # also pop for the starting_hand
            shanten = list(map(calculate_shanten, kyoku.hands))
            kyoku.starting_shanten = list(shanten)
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
            if tile not in YAOCHUUHAI and nagashi[action.seat]:
                kyoku.events.append((action.seat, "end_nagashi", action.seat, "discard", tile))
                nagashi[action.seat] = False
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
            if nagashi[last_seat]:
                kyoku.events.append((action.seat, "end_nagashi", last_seat, call_type, called_tile))
                nagashi[last_seat] = False
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
    parsed_metadata: GameMetadata = {
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
    temp_dict_kyokus = list(map(dataclasses.asdict, kyokus))
    return list(map(dataclasses.asdict, kyokus)), parsed_metadata

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

def parse_tenhou(raw_kyokus: TenhouLog, metadata: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], GameMetadata]:
    kyokus = []
    for raw_kyoku in raw_kyokus:
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
        num_players = 4
        starting_hand = cast(List[Tuple[int, ...]], [tuple(haipai0), tuple(haipai1), tuple(haipai2), tuple(haipai3)])
        hand = cast(List[List[int]], [haipai0, haipai1, haipai2, haipai3])
        calls = cast(List[List[int]], [[], [], [], []])
        call_info = cast(List[List[CallInfo]], [[], [], [], []]) # call type, called tile, direction [1-3], call tiles
        draws = cast(List[List[Union[int, str]]], [draws0, draws1, draws2, draws3])
        discards = cast(List[List[Union[int, str]]], [discards0, discards1, discards2, discards3])
        pond = cast(List[List[int]], [[], [], [], []])
        dora_indicators = cast(List[int], list(map(DORA_INDICATOR.get, doras)))

        # get a sequence of events based on discards only
        turn = current_round
        if current_round >= 4:
            turn -= 4
        last_turn: int = 0
        last_discard: int = 0
        i = [0] * num_players
        nagashi = [True] * num_players
        furiten = [False] * num_players
        visible_tiles = []
        events: List[Any] = []
        gas = 1000
        num_dora = 1
        starting_shanten = list(map(calculate_shanten, hand))
        shanten = list(starting_shanten)
        final_tile = 0
        
        for t in range(num_players):
            events.append((t, "haipai", sorted_hand(hand[t])))
            events.append((t, "start_shanten", starting_shanten[t]))

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
        def extract_call_tiles(draw: str) -> List[int]:
            call_type = get_call_name(draw)
            # the position of the letter determines where it's called from
            # but we don't use this information, we just brute force check for calls
            call_tiles = "".join(c for c in draw if c.isdigit())
            return [int(call_tiles[i:i+2]) for i in range(0, len(call_tiles), 2)]
        # print("===", round_name(current_round, current_honba), "===")
        while gas >= 0:
            gas -= 1
            # print(last_turn, "=>", turn)
            if i[turn] >= len(draws[turn]):
                assert all(i[turn] >= len(draws[turn]) for turn in range(num_players)), f"game ended prematurely in {round_name(current_round, current_honba)} on {turn}'s turn; i = {i}, max i = {list(map(len, draws))}"
                final_tile = last_discard
                break

            # first handle the draw
            # could be a regular draw, chii, pon, or daiminkan
            # then handle the discard
            # could be a regular discard, riichi, kakan, or ankan
            called_kan = False
            def handle_call(call: str) -> int:
                """called every time a call happens, returns the called tile"""
                call_type = get_call_name(call)
                call_tiles = extract_call_tiles(call)
                call_direction = (last_turn - turn) % 4
                called_tile = call_tiles[0]
                events.append((turn, call_type, called_tile))
                if call_type in {"minkan", "ankan", "kakan"}:
                    nonlocal num_dora
                    nonlocal called_kan
                    num_dora += 1
                    called_kan = True
                    visible_tiles.append(called_tile) # account for visible kan tile
                # if kakan, replace the old pon call with kakan
                if call_type == "kakan":
                    kakan_index = next((i for i, callinfo in enumerate(call_info[turn]) if callinfo.type == "pon" and callinfo.tile == called_tile), None)
                    assert kakan_index is not None, f"called kakan on {called_tile} but there was no previous pon"
                    orig_direction = call_info[turn][kakan_index].dir
                    call_info[turn][kakan_index] = CallInfo(call_type, called_tile, orig_direction, [called_tile]*4)
                elif call_type == "ankan":
                    calls[turn].extend(call_tiles[:3]) # ignore fourth kan tile
                    call_info[turn].append(CallInfo(call_type, called_tile, call_direction, call_tiles))
                elif call_type in {"chii", "pon", "minkan"}:
                    calls[turn].extend(call_tiles[:3]) # ignore fourth kan tile
                    call_info[turn].append(CallInfo(call_type, called_tile, call_direction, call_tiles))
                    if nagashi[last_turn]:
                        events.append((turn, "end_nagashi", last_turn, call_type, called_tile))
                        nagashi[last_turn] = False
                    if call_type == "minkan":
                        hand[turn].remove(called_tile) # remove the extra kan tile
                return called_tile

            draw = draws[turn][i[turn]]
            if type(draw) is str:
                hand[turn].append(handle_call(draw))
                draw = hand[turn][-1]
            else:
                assert type(draw) == int, f"failed to handle unknown draw type: {draw}"
                # print(turn, i[turn], "drew", draw)
                hand[turn].append(draw)
                events.append((turn, "draw", draw))

            if i[turn] >= len(discards[turn]): # tsumo after draw means no discard after this
                hand[turn].remove(draw) # so we can calculate final shanten/wait
                final_tile = draw
                break

            discard = discards[turn][i[turn]]
            if type(discard) is str:
                last_discard = handle_call(discard)
                last_discard = last_discard if last_discard != 60 else draw # 60 = tsumogiri
                hand[turn].remove(last_discard)
                visible_tiles.append(last_discard)
                pond[turn].append(last_discard)
            elif discard == 0: # the draw earlier was daiminkan, so no discard happened
                pass
            else:
                assert type(discard) == int, f"failed to handle unknown discard type: {discard}"
                last_discard = discard if discard != 60 else draw # 60 = tsumogiri
                # print(turn, i[turn], "discarded", last_discard)
                if last_discard not in YAOCHUUHAI and nagashi[turn]:
                    events.append((turn, "end_nagashi", turn, "discard", last_discard))
                    nagashi[turn] = False
                hand[turn].remove(last_discard)
                visible_tiles.append(last_discard)
                pond[turn].append(last_discard)
                events.append((turn, "discard", last_discard))
            closed_hand = closed_part(tuple(hand[turn]), tuple(calls[turn]))
            new_shanten = calculate_shanten(closed_hand)
            if new_shanten != shanten[turn]: # compare both the shanten number and the iishanten group
                events.append((turn, "shanten_change", shanten[turn], new_shanten))
                shanten[turn] = new_shanten
                # check if the resulting hand is tenpai
                if new_shanten[0] == 0:
                    ukeire = calculate_ukeire(closed_hand, calls[turn] + visible_tiles + dora_indicators[:num_dora])
                    potential_waits = new_shanten[1]
                    events.append((turn, "tenpai", sorted_hand(hand[turn]), potential_waits, ukeire))
                    # check for furiten
                    if any(w in pond[turn] for w in potential_waits):
                        events.append((turn, "furiten"))
                        furiten[turn] = True
                    else:
                        furiten[turn] = False

            assert len(hand[turn]) == 13, f"got {len(hand[turn])} tiles in hand after events:\n" + "\n".join(map(str,events[-5:]))
            was_ankan = type(discard) is str and get_call_name(discard) == "ankan"
            was_kakan = type(discard) is str and get_call_name(discard) == "kakan"
            was_daiminkan = type(draws[turn][i[turn]]) is str and get_call_name(draws[turn][i[turn]]) == "minkan"
            i[turn] += 1 # done processing this draw/discard

            # pon / kan handling
            # we have to look at the next draw of every player before changing the turn
            # if any of them pons or kans the previously discarded tile, control goes to them
            called = False
            for t in range(num_players):
                if turn == t or i[t] >= len(draws[t]):
                    continue
                draw = draws[t][i[t]]
                if type(draw) is not str:
                    continue
                call_type = get_call_name(draw)
                called_tile = extract_call_tiles(draw)[0]
                # make sure it's the same tile as last discarded
                if remove_red_five(called_tile) != remove_red_five(last_discard):
                    continue
                # make sure it's coming from the right direction
                same_dir = (draw[0].isalpha() and turn == (t-1)%4) \
                        or (draw[2].isalpha() and turn == (t-2)%4) \
                        or (draw[4].isalpha() and turn == (t-3)%4)
                if not same_dir:
                    continue
                last_turn = turn
                turn = t
                last_discard = 0
                called = True
                break

            # change turn to next player
            if not called and not called_kan:
                last_turn = turn
                turn += 1
                if turn == num_players:
                    turn = 0
        assert gas >= 0, "ran out of gas"
        assert len(dora_indicators) == num_dora, "there's a bug in counting dora"

        # get waits of final hands
        final_waits = [w for _, w in shanten]
        final_ukeire = [calculate_ukeire(closed_part(tuple(hand[t]), tuple(calls[t])), calls[t] + visible_tiles + dora_indicators) for t in range(num_players)]
        kyokus.append(Kyoku(
            round = current_round,
            honba = current_honba,
            num_players = num_players,
            events = events,
            result = result,
            hands = hand,
            calls = calls,
            call_info = call_info,
            pond = pond,
            furiten = furiten,
            final_waits = final_waits,
            final_ukeire = final_ukeire,
            starting_hands = starting_hand,
            starting_shanten = starting_shanten,
            dora = list(map(lambda i: DORA[i], dora_indicators)),
            final_tile = final_tile))

    # parse metadata
    parsed_metadata: GameMetadata = {
        "name": metadata["name"],
        "game_score": metadata["sc"][::2],
        "final_score": list(map(lambda s: int(1000*s), metadata["sc"][1::2]))
    }
    temp_dict_kyokus = list(map(dataclasses.asdict, kyokus))
    return temp_dict_kyokus, parsed_metadata

async def parse_game_link(link: str, specified_player: int = 0) -> Tuple[List[Dict[str, Any]], GameMetadata, int]:
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
