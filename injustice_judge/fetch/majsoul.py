import re
import google.protobuf as pb
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict
from ..proto import liqi_combined_pb2 as proto
from ..utils import is_mangan, save_cache, sorted_hand
from ..constants import Event, LIMIT_HANDS, MAJSOUL_YAKU, TRANSLATE, YAKUMAN
from ..classes import Dir, GameMetadata, GameRules
from ..classes2 import Kyoku
from .postprocess import postprocess_events
from typing import *

###
### loading and parsing mahjong soul games
###

MajsoulLog = List[Tuple[str, proto.Wrapper]]

class MahjongSoulAPI:
    """Helper class to interface with the Mahjong Soul API"""
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
    async def __aenter__(self) -> "MahjongSoulAPI":
        import websockets
        self.ws = await websockets.connect(self.endpoint)  # type: ignore[attr-defined]
        self.ix = 0
        return self
    async def __aexit__(self, err_type: Optional[Type[BaseException]], 
                              err_value: Optional[BaseException], 
                              traceback: Optional[Any]) -> bool:
        await self.ws.close()
        return False

    async def call(self, name: str, **fields: Any) -> Message:
        method = next((svc.FindMethodByName(name) for svc in proto.DESCRIPTOR.services_by_name.values() if name in [method.name for method in svc.methods]), None)
        assert method is not None, f"couldn't find method {name}"

        # prepare the payload (req) and a place to store the response (res)
        req: Message = pb.reflection.MakeClass(method.input_type)(**fields)
        res: Message = pb.reflection.MakeClass(method.output_type)()
        # the Res* response must have an error field
        assert hasattr(res, "error"), f"Got non-Res object: {res}\n\nfrom request: {req}"

        # wrap req in a Wrapper object and send it according to majsoul's protocol
        tx: bytes = b'\x02' + self.ix.to_bytes(2, "little") + proto.Wrapper(name=f".{method.full_name}", data=req.SerializeToString()).SerializeToString()
        await self.ws.send(tx)
        # get the raw request back and validate that it has the same index as our request
        rx: bytes = await self.ws.recv()
        assert rx[0] == 3, f"Expected response message, got message of type {rx[0]}"
        assert self.ix == int.from_bytes(rx[1:3], "little"), f"Expected response index {self.ix}, got index {int.from_bytes(rx[1:3], 'little')}"
        self.ix += 1

        # parse the raw request from the Wrapper object
        wrapper = proto.Wrapper()
        wrapper.ParseFromString(rx[3:])
        res.ParseFromString(wrapper.data)
        assert not res.error.code, f"{method.full_name} request received error {res.error.code}"
        return res

def parse_wrapped_bytes(data: bytes) -> Tuple[str, Message]:
    """Used to unwrap Mahjong Soul messages in fetch_majsoul() below"""
    wrapper = proto.Wrapper()
    wrapper.ParseFromString(data)
    name = wrapper.name.strip(f'.{proto.DESCRIPTOR.package}')
    try:
        msg = pb.reflection.MakeClass(proto.DESCRIPTOR.message_types_by_name[name])()
        msg.ParseFromString(wrapper.data)
    except KeyError as e:
        raise Exception(f"Failed to find message name {name}")
    return name, msg

def parse_majsoul_link(link: str) -> Tuple[str, Optional[int], Optional[int]]:
    identifier_pattern = r'\?paipu=([0-9a-zA-Z-]+)(_a)?(\d+)?_?(\d)?'
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
    account_string = identifier_match.group(3)
    if account_string is not None:
        ms_account_id = int((((int(account_string)-1358437)^86216345)-1117113)/7)
    else:
        ms_account_id = 0
    player_seat = identifier_match.group(4)
    if player_seat is not None:
        player_seat = int(player_seat)
    return identifier, ms_account_id, player_seat

async def fetch_majsoul(link: str) -> Tuple[MajsoulLog, Dict[str, Any], Optional[int]]:
    """
    Fetch a raw majsoul log from a given link, returning a parsed log and the seat of the player specified through `_a...` or `_a..._[0-3]`
    Example link: https://mahjongsoul.game.yo-star.com/?paipu=230814-90607dc4-3bfd-4241-a1dc-2c639b630db3_a878761203
    """
    identifier, ms_account_id, player_seat = parse_majsoul_link(link)

    try:
        f = open(f"cached_games/game-{identifier}.log", 'rb')
        record = proto.ResGameRecord()
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

            # url is the __MJ_GAME_INFO_API__ key of https://www.maj-soul.com/dhs/js/config.js
            async with MahjongSoulAPI("wss://common-v2.maj-soul.com:443/gateway") as api:
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
                record = cast(proto.ResGameRecord, await api.call("fetchGameRecord", game_uuid=identifier, client_version_string=client_version_string))
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
                oauth_token = cast(proto.ResOauth2Auth, await api.call("oauth2Auth", type=7, code=access_token, uid=UID, client_version_string=f"web-{MS_VERSION}")).access_token
                print("Calling heatbeat...")
                await api.call("heatbeat")
                print("Calling oauth2Check...")
                assert cast(proto.ResOauth2Check, await api.call("oauth2Check", type=7, access_token=oauth_token)).has_account, "couldn't find account with oauth2Check"
                print("Calling oauth2Login...")
                client_device_info = {"platform": "pc", "hardware": "pc", "os": "mac", "is_browser": True, "software": "Firefox", "sale_platform": "web"}  # type: ignore[dict-item]
                await api.call("oauth2Login", type=7, access_token=oauth_token, reconnect=False, device=client_device_info, random_key=str(uuid.uuid1()), client_version={"resource": f"{MS_VERSION}.w"}, currency_platforms=[], client_version_string=f"web-{MS_VERSION}", tag="en")
                print("Calling fetchGameRecord...")
                record = cast(proto.ResGameRecord, await api.call("fetchGameRecord", game_uuid=identifier, client_version_string=f"web-{MS_VERSION}"))
        save_cache(filename=f"game-{identifier}.log", data=record.SerializeToString())

    parsed = cast(proto.GameDetailRecords, parse_wrapped_bytes(record.data)[1])
    if parsed.actions != []:
        actions = [cast(Tuple[str, proto.Wrapper], parse_wrapped_bytes(action.result)) for action in parsed.actions if len(action.result) > 0]
    else:
        actions = [cast(Tuple[str, proto.Wrapper], parse_wrapped_bytes(record)) for record in parsed.records]
    
    player = None
    if player_seat is not None:
        player = player_seat
    elif ms_account_id is not None:
        for acc in record.head.accounts:
            if acc.account_id == ms_account_id:
                player = acc.seat
                break
    return actions, MessageToDict(record.head), player

def parse_majsoul(actions: MajsoulLog, metadata: Dict[str, Any], nickname: Optional[str]) -> Tuple[List[Kyoku], GameMetadata, Optional[int]]:
    """
    Parse a Mahjong Soul log fetched with `fetch_majsoul`.
    """
    all_dora_indicators: List[List[int]] = []
    all_ura_indicators: List[List[int]] = []
    dora_indicators: List[int] = []
    ura_indicators: List[int] = []
    convert_tile = lambda tile: {"m": 51, "p": 52, "s": 53}[tile[1]] if tile[0] == "0" else {"m": 10, "p": 20, "s": 30, "z": 40}[tile[1]] + int(tile[0])
    majsoul_hand_to_tenhou = lambda hand: list(sorted_hand(map(convert_tile, hand)))
    majsoul_hand_to_tenhou_unsorted = lambda hand: list(map(convert_tile, hand))
    last_seat = 0
    all_events: List[List[Event]] = []
    all_walls: List[List[int]] = []
    events: List[Event] = []
    # constants obtained in the main loop below
    num_players: int = -1
    
    def end_round(result: List[Any]) -> None:
        nonlocal events
        nonlocal all_events
        nonlocal dora_indicators
        nonlocal ura_indicators
        events.append((0, "end_game", result))
        all_events.append(events)
        all_dora_indicators.append(dora_indicators)
        all_ura_indicators.append(ura_indicators)
        events = []
    
    def same_tile(tile1: str, tile2: str) -> bool:
        # check if two tiles are equal, counting red
        # five as equal to regular fives
        if tile1[1] == tile2[1]:
            number1, number2 = tile1[0], tile2[0]
            if number1 == number2: return True
            if number1 == '0': return number2 == '5'
            if number1 == '5': return number2 == '0'
        return False

    # for every action in the log, turn it into an event in `events`
    # the format of the events list will match the one produced by `parse_tenhou`
    for name, action in actions:
        if isinstance(action, proto.RecordNewRound):
            # new round started: initialize round vars and push "start_game" event
            haipai: List[Tuple[int, ...]] = [sorted_hand(majsoul_hand_to_tenhou(h)) for h in [action.tiles0, action.tiles1, action.tiles2, action.tiles3] if len(h) > 0]
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
            all_walls.append([convert_tile(a+b) for a, b in zip(action.paishan[::2], action.paishan[1::2])])
            riichi_sticks = action.liqibang
            events.append((t, "start_game", round, honba, riichi_sticks, tuple(action.scores)))
            # pretend we drew the first tile
            events.append((action.ju, "draw", first_tile))
            dora_indicators = [convert_tile(dora) for dora in action.doras]
        elif isinstance(action, proto.RecordDealTile):
            # tile drawn: push "draw" event
            events.append((action.seat, "draw", convert_tile(action.tile)))
            if len(action.doras) > 0:
                dora_indicators = [convert_tile(dora) for dora in action.doras]
        elif isinstance(action, proto.RecordDiscardTile):
            # tile discarded: push "discard" or "riichi" event
            tile = convert_tile(action.tile)
            events.append((action.seat, "riichi" if action.is_liqi else "discard", tile))
        elif isinstance(action, proto.RecordChiPengGang):
            # chii/pon/daiminkan call made: push the corresponding call event
            assert isinstance(action, proto.RecordChiPengGang)
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
        elif isinstance(action, proto.RecordAnGangAddGang):
            # kakan/ankan call made: push the corresponding call event
            tile = convert_tile(action.tiles)
            if action.type == 2:
                call_type = "kakan"
            elif action.type == 3:
                call_type = "ankan"
            else:
                raise Exception(f"unhandled RecordAnGangAddGang of type {action.type}: {action}")
            events.append((action.seat, call_type, tile, (tile,)*4, Dir.SELF))
            dora_indicators.extend(convert_tile(dora) for dora in action.doras)
        elif isinstance(action, proto.RecordBaBei): # kita
            # kita call made: push "kita" call event
            events.append((action.seat, "kita", 44, [44], 0))
        elif isinstance(action, proto.RecordHule):
            # game ended to ron or tsumo: construct a tenhou game result array
            # call `end_round()` afterwards to push "end_game" event and cleanup
            result: List[Any] = ["和了"]
            for h in action.hules:
                han = sum(fan.val for fan in h.fans)
                score_string = f"{h.fu}符{han}飜"
                if any(TRANSLATE[MAJSOUL_YAKU[fan.id]] in YAKUMAN for fan in h.fans):
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
                fan_str = lambda fan: f"{MAJSOUL_YAKU[fan.id]}({'役満' if TRANSLATE[MAJSOUL_YAKU[fan.id]] in YAKUMAN else str(fan.val)+'飜'})"
                yakus = [name for _, name in sorted((fan.id, fan_str(fan)) for fan in h.fans if fan.val)]
                result.append(list(action.delta_scores))
                result.append([h.seat, last_seat, pao_seat, score_string+point_string, *yakus])
                dora_indicators = majsoul_hand_to_tenhou_unsorted(h.doras)
                ura_indicators = majsoul_hand_to_tenhou_unsorted(h.li_doras)
            end_round(result)
        elif isinstance(action, proto.RecordNoTile):
            # game ended to ryuukyoku: call `end_round()` to push "end_game" event and cleanup
            if len(action.scores[0].delta_scores) == 0: # everybody/nobody is tenpai, so no score change
                end_round(["流局", [0]*num_players])
            else:
                end_round(["流局", *(score_info.delta_scores for score_info in action.scores)])
        elif isinstance(action, proto.RecordLiuJu): # abortive draw
            # game ended to abortive draw: call `end_round()` to push "end_game" event and cleanup
            if action.type == 1:
                end_round(["九種九牌", [0]*num_players])
            elif action.type == 2:
                end_round(["四風連打", [0]*num_players])
            elif action.type == 3:
                end_round(["四槓散了", [0]*num_players])
            elif action.type == 4:
                end_round(["四家立直", [0]*num_players])
            # need to discover `action.type` for 三家和了 (it's probably 5)
            #   this requires getting triple ron with triple ron draw turned on
            #   which is not the default in majsoul, so we can probably ignore this
            else:
                raise Exception(f"unhandled RecordLiuJu of type {action.type}: {action}. Is this triple-ron draw?")
        else:
            raise Exception(f"unhandled action {name}: {action}")
        # set the last seat if the current action specifies a seat
        if hasattr(action, "seat"):
            last_seat = action.seat
    assert len(all_events) > 0, "unable to read any kyoku"

    # parse metadata (nicknames, score, rules)
    nicknames = ["AI"] * num_players
    for acc in metadata["accounts"]:
        nicknames[acc.get("seat", 0)] = acc["nickname"]
    result_data = sorted((res.get("seat", 0), res.get("partPoint1", 0), res.get("totalPoint", 0)) for res in metadata["result"]["players"])
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = nicknames,
                                   game_score = [result_data[i][1] for i in range(num_players)],
                                   final_score = [result_data[i][2]/1000.0 for i in range(num_players)],
                                   rules = GameRules.from_majsoul_detail_rule(num_players, metadata["config"]["mode"]["detailRule"], metadata["config"]["mode"]["mode"]))
    parsed_metadata.rules.calculate_placement_bonus(parsed_metadata.game_score, parsed_metadata.final_score)

    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat = nicknames.index(nickname) if nickname in nicknames else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat
