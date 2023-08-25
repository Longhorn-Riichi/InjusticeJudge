import functools
import re
import google.protobuf as pb  # type: ignore[import]
from .proto import liqi_combined_pb2 as proto
from google.protobuf.message import Message  # type: ignore[import]
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from typing import *
from .constants import CallInfo, Draw, Event, Kyoku, Ron, Tsumo, YakuList, GameMetadata, Dir, DORA, LIMIT_HANDS, TRANSLATE, YAKU_NAMES, YAKUMAN, YAOCHUUHAI
from .utils import hidden_part, round_name, sorted_hand
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
            #     print(seat, event_type, ph(kyoku.hands[seat]), "|", ph(kyoku.calls[seat]), event_data)
            if event_type == "haipai":
                hand = event_data[0]
                assert len(hand) == 13, f"haipai was length {len(hand)}, expected 13"
                kyoku.hands.append(list(hand))
                kyoku.calls.append([])
                kyoku.call_info.append([])
                kyoku.pond.append([])
                kyoku.furiten.append(False)
                kyoku.haipai.append(sorted_hand(hand))
                kyoku.final_draw_event_index.append(-1)
                kyoku.final_discard_event_index.append(-1)
                kyoku.kita_counts.append(0)
            elif event_type == "start_game":
                kyoku.round, kyoku.honba = event_data
                kyoku.num_players = metadata.num_players
                kyoku.doras = [DORA[d] for d in dora_indicators] + [51, 52, 53] # include red fives
                kyoku.uras = [DORA[d] for d in ura_indicators]
                kyoku.shanten = [calculate_shanten(h) for h in kyoku.hands]
                kyoku.haipai_shanten = list(kyoku.shanten)
                kyoku.haipai_ukeire = [calculate_ukeire(tuple(hand), dora_indicators[:num_doras]) for hand in kyoku.hands]
                kyoku.events.extend((t, "haipai_shanten", s) for t, s in enumerate(kyoku.shanten))
            elif event_type == "draw":
                tile = event_data[0]
                kyoku.hands[seat].append(tile)
                kyoku.final_draw = tile
                kyoku.final_draw_event_index[seat] = len(kyoku.events) - 1
                assert len(kyoku.hands[seat]) == 14
            elif event_type in {"discard", "riichi"}: # discards
                tile, *_ = event_data
                kyoku.hands[seat].remove(tile)
                kyoku.final_discard = tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                visible_tiles.append(tile)
                kyoku.pond[seat].append(tile)
                # calculate shanten
                hidden = hidden_part(kyoku.hands[seat], kyoku.calls[seat])
                new_shanten = calculate_shanten(hidden)
                if new_shanten != kyoku.shanten[seat]:
                    kyoku.events.append((seat, "shanten_change", kyoku.shanten[seat], new_shanten))
                    kyoku.shanten[seat] = new_shanten
                    # calculate ukeire if tenpai
                    if new_shanten[0] == 0:
                        ukeire = calculate_ukeire(hidden, kyoku.calls[seat] + visible_tiles + dora_indicators[:num_doras])
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
            elif event_type in {"chii", "pon", "minkan"}: # calls
                called_tile, call_tiles, call_dir = event_data
                if event_type != "minkan":
                    kyoku.hands[seat].append(called_tile)
                    assert len(kyoku.hands[seat]) == 14
                kyoku.calls[seat].extend(call_tiles[:3]) # keep only 3 tiles for shanten reasons
                kyoku.call_info[seat].append(CallInfo(event_type, called_tile, call_dir, call_tiles))
                # check for nagashi
                callee_seat = (seat + call_dir) % 4
                if nagashi_eligible[callee_seat]:
                    kyoku.events.append((seat, "end_nagashi", callee_seat, event_type, called_tile))
                    nagashi_eligible[callee_seat] = False
            elif event_type in {"ankan", "kakan", "kita"}: # special discards
                called_tile, call_tiles, call_dir = event_data
                # if kakan, replace the old pon call with kakan
                if event_type == "kakan":
                    pon_index = next((i for i, call_info in enumerate(kyoku.call_info[seat]) if call_info.type == "pon" and call_info.tile == called_tile), None)
                    assert pon_index is not None, f"unable to find previous pon for player {seat}'s kakan {event_data}: calls were {kyoku.call_info[seat]}"
                    orig_direction = kyoku.call_info[seat][pon_index].dir
                    kyoku.call_info[seat][pon_index] = CallInfo(event_type, called_tile, orig_direction, call_tiles)
                elif event_type == "ankan":
                    kyoku.call_info[seat].append(CallInfo(event_type, called_tile, 0, [called_tile]*4))
                    kyoku.calls[seat].extend([called_tile]*3) # keep only 3 tiles for shanten reasons
                elif event_type == "kita":
                    kyoku.kita_counts[seat] += 1
                kyoku.hands[seat].remove(called_tile)
                kyoku.final_discard = called_tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                assert len(kyoku.hands[seat]) == 13
                visible_tiles.append(called_tile)
            elif event_type == "end_game":
                unparsed_result = event_data[0]
                kyoku.result = parse_result(unparsed_result, metadata.num_players, kyoku.kita_counts)
                # if tsumo or kyuushu kyuuhai, pop the final tile from the winner's hand
                if kyoku.result[0] == "tsumo" or (kyoku.result[0] == "draw" and kyoku.result[1].name == "9 terminals draw"):
                    next(hand for hand in kyoku.hands if len(hand) == 14).pop()
                else: # otherwise we pop the deal-in tile from the visible tiles (so ukeire calculation won't count it)
                    assert kyoku.final_discard == visible_tiles.pop(), f"final discard of round {round_name(kyoku.round, kyoku.honba)} was not equal to the last visible tile"
                # save final waits and ukeire
                for seat in range(kyoku.num_players):
                    ukeire = 0
                    if kyoku.shanten[seat][0] <= 1:
                        hidden = hidden_part(kyoku.hands[seat][:13], kyoku.calls[seat])
                        ukeire = calculate_ukeire(hidden, kyoku.calls[seat] + visible_tiles + dora_indicators[:num_doras])
                    kyoku.final_waits.append(kyoku.shanten[seat][1])
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
            assert len(kyoku.hands[i]) == 13, f"on {round_name(kyoku.round, kyoku.honba)}, player {i}'s hand was length {len(kyoku.hands[i])} when the round ended, should be 13"
            assert (len(kyoku.calls[i]) % 3) == 0, f"on {round_name(kyoku.round, kyoku.honba)}, player {i}'s calls was length {len(kyoku.calls[i])} when the round ended, should be divisible by 3"
        kyokus.append(kyoku)
    return kyokus

def parse_result(result: List[Any], num_players: int, kita_counts: List[int]) -> Tuple[Any, ...]:
    """
    Given a Tenhou game result list, parse it into a list of tuples where the
    first element is either "ron", "tsumo", or "draw"; the remainder of the tuple
    consists of "Ron" object(s), a "Tsumo" object, or a "Draw" object.

    Mahjong Soul game result is converted into a Tenhou game result and parsed here.
    """
    result_type, *scoring = result
    ret: List[Tuple[str, Any]] = []
    scores = [scoring[i*2:i*2+2] for i in range((len(scoring)+1)//2)]
    def process_yaku(yaku: List[str],  kita_count: int) -> YakuList:
        # for subtracting kita count from dora count in Tenhou sanma
        dora_index: Optional[int] = None
        ret = YakuList(yaku_strs = yaku)
        for i, y in enumerate(yaku):
            if "役満" in y: # skip yakuman since they don't specify 飜
                continue
            name = TRANSLATE[y.split("(")[0]]
            value = int(y.split("(")[1].split("飜")[0])
            if name == "riichi":
                ret.riichi = True
            elif name == "ippatsu":
                ret.ippatsu = True
            elif name in "dora":
                dora_index = i
                ret.dora += value
            elif name == "aka":
                ret.dora += value
            elif name == "ura":
                ret.ura = value
            elif name == "kita":
                ret.kita = value
            elif name in {"haitei", "houtei"}:
                ret.haitei = True
        if kita_count > 0 and ret.kita == 0:
            # must be a Tenhou sanma game hand with kita because
            # it counts kita as regular dora (not "抜きドラ")
            non_kita_dora_count = ret.dora - kita_count
            assert non_kita_dora_count >= 0
            if non_kita_dora_count == 0:
                del ret.yaku_strs[dora_index]
            else:
                ret.yaku_strs[dora_index] = f"ドラ({non_kita_dora_count}飜)"
            ret.yaku_strs.append(f"抜きドラ({kita_count}飜)")
            ret.kita = kita_count
            ret.dora = non_kita_dora_count
        return ret
    if result_type == "和了":
        rons: List[Ron] = []
        for [score_delta, [w, won_from, _, score_string, *yaku]] in scores:
            below_mangan = "符" in score_string
            if below_mangan: # e.g. "30符1飜1000点", "50符3飜1600-3200点"
                [fu, rest] = score_string.split("符")
                [han, rest] = rest.split("飜")
                pts = "".join(rest.split("点"))
                fu = int(fu)
                han = int(han)
                limit_name = "" # not a limit hand
            else: # e.g. "倍満16000点", "満貫4000点∀"
                pts = "".join(c for c in score_string if c in "0123456789-∀")
                limit_name = score_string.split(pts[0])[0]
                han = 0
                for y in yaku:
                    if "役満" in y:
                        han = 13
                        break
                    else:
                        han += int(y.split("(")[1].split("飜")[0])
            assert han > 0, f"somehow got a {han} han win"
            if w == won_from: # tsumo
                if "-" in pts:
                    score_ko, score_oya = map(int, pts.split("-"))
                    score_total = score_oya + (num_players-2)*score_ko
                elif "∀" in pts:
                    score_ko = score_oya = int(pts.split("∀")[0])
                    score_total = score_oya + (num_players-2)*score_ko
                else:
                    assert False, f"unable to parse tsumo score {pts} from score string {score_string}"
                return ("tsumo", Tsumo(score_delta = score_delta,
                                       winner = w,
                                       han = han,
                                       fu = fu if below_mangan else 0,
                                       limit_name = limit_name,
                                       score_string = score_string,
                                       score = score_total,
                                       score_oya = score_oya,
                                       score_ko = score_ko,
                                       yaku = process_yaku(yaku, kita_counts[w])))
            else:
                score = int(pts)
                rons.append(Ron(score_delta = score_delta,
                                winner = w,
                                won_from = won_from,
                                han = han,
                                fu = fu if below_mangan else 0,
                                limit_name = limit_name,
                                score_string = score_string,
                                score = score,
                                yaku = process_yaku(yaku, kita_counts[w])))
        return ("ron", *rons)
    elif result_type in ({"流局", "全員聴牌", "全員不聴", "流し満貫"} # exhaustive draws
                       | {"九種九牌", "四家立直", "三家和了", "四槓散了", "四風連打"}): # abortive draws
        return ("draw", Draw(score_delta = scores[0][0] if len(scores) > 0 else [0]*num_players,
                                  name = TRANSLATE[result_type]))
    else:
        assert False, f"unhandled result type {result_type}"

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

    identifier_pattern = r'\?paipu=([^_]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Mahjong Soul link: {link}")
    identifier = identifier_match.group(1)
    
    player_pattern = r'_a(\d+)'
    player_match = re.search(player_pattern, link)
    if player_match is None:
        ms_account_id = None
    else:
        ms_account_id = int((((int(player_match.group(1))-1358437)^86216345)-1117113)/7)

    if not all(c in "0123456789abcdef-" for c in identifier):
        codex = "0123456789abcdefghijklmnopqrstuvwxyz"
        decoded = ""
        for i, c in enumerate(identifier):
            decoded += "-" if c == "-" else codex[(codex.index(c) - i + 55) % 36]
        identifier = decoded
        if link.count("_") == 2:
            player = int(link[-1])

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
    num_players: int = -1 # obtained in the main loop below
    
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
            events.append((t, "start_game", round, honba))
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
            elif action.tiles[0] == action.tiles[1]:
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
                elif h.point_rong >= 8000:
                    assert han in LIMIT_HANDS, f"limit hand with {han} han is not in LIMIT_HANDS"
                    score_string = LIMIT_HANDS[han]
                point_string = f"{h.point_rong}点"
                if h.zimo:
                    if h.point_zimo_qin > 0:
                        point_string = f"{h.point_zimo_xian}-{h.point_zimo_qin}点"
                    else:
                        point_string = f"{h.point_zimo_xian}点∀"
                yakus = [name for _, name in sorted((fan.id, f"{YAKU_NAMES[fan.id]}({fan.val}飜)") for fan in h.fans)]
                result.append(list(action.delta_scores))
                result.append([h.seat, last_seat, h.seat, score_string+point_string, *yakus])
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
            # TODO: abortive draw types
            if action.type == 1:
                end_round(["九種九牌", [0]*num_players])
            else:
                raise Exception(f"unhandled RecordLiuJu of type {action.type}: {action}")
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
                                   ura_indicators = all_ura_indicators)
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

    identifier_pattern = r'\?log=([^&]+)'
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
    # check to see if the haipai of the fourth player is empty; if so, it's sanma
    num_players: int = 3 if len(raw_kyokus[0][13]) == 0 else 4
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
    def extract_call_tiles(call: str) -> List[int]:
        """
        returns the called tile as the first tile;
        this matters when the call contains a red five.
        """
        for c in call:
            if c.isalpha():
                call_tiles = "".join(reversed(call.split(c)))
                return [int(call_tiles[i:i+2]) for i in range(0, len(call_tiles), 2)]

    for [[round, honba, num_riichis],
         scores, dora_indicators, ura_indicators,
         haipai0, draws0, discards0,
         haipai1, draws1, discards1,
         haipai2, draws2, discards2,
         haipai3, draws3, discards3, result] in raw_kyokus:
        # print("========", round_name(round, honba), "========")
        events: List[Event] = []
        # need to be 4, NOT num_players
        curr_seat = round % 4
        i = [0] * num_players
        haipai   = [haipai0,   haipai1,   haipai2,   haipai3][:num_players]
        draws    = [draws0,    draws1,    draws2,    draws3][:num_players]
        discards = [discards0, discards1, discards2, discards3][:num_players]
        all_dora_indicators.append(dora_indicators)
        all_ura_indicators.append(ura_indicators)

        for seat in range(num_players):
            events.append((seat, "haipai", sorted_hand(haipai[seat])))
        events.append((seat, "start_game", round, honba))

        # Emit events for draws and discards and calls, in order
        # stops when the current player has no more draws; remaining
        # draws handled after this loop
        while i[curr_seat] < len(draws[curr_seat]):
            keep_curr_seat = False
            def handle_call(call: str) -> int:
                """Called every time a call happens. Returns the called tile"""
                call_tiles = extract_call_tiles(call)
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
                # extract the called tile from the string
                draw = handle_call(draw)
            else:
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
                discard = handle_call(discard)
            elif discard == 0: # the draw earlier was daiminkan, so no discard happens
                pass
            else:
                discard = discard if discard != 60 else draw # 60 = tsumogiri
                events.append((curr_seat, "discard", discard))

            i[curr_seat] += 1 # done processing the ith draw/discard for this player

            # pon / kan handling
            # we have to look at the next draw of every player before changing curr_seat
            # if any of them pons or kans the previously discarded tile, control goes to them
            for seat in range(num_players):
                # check if a next draw exists for a player other than curr_seat
                if curr_seat != seat and i[seat] < len(draws[seat]):
                    # check that the next draw is a call
                    if type(next_draw := draws[seat][i[seat]]) is str:
                        # check that it's calling from us, and that it's the same tile we discarded
                        # TODO: if there is a pon and a chii waiting for us,
                        # the first player in `range(num_players)` takes precedence 
                        same_dir = get_call_dir(next_draw) == Dir((curr_seat - seat) % 4)
                        same_tile = extract_call_tiles(next_draw)[0] == discard
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
                                   ura_indicators = all_ura_indicators)

    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators)
    return postprocess_events(all_events, parsed_metadata), parsed_metadata

async def parse_game_link(link: str, specified_player: int = 0) -> Tuple[List[Kyoku], GameMetadata, int]:
    """Given a game link, fetch and parse the game into kyokus"""
    # print(f"Analyzing game {link}:")
    if "tenhou.net/" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        kyokus, parsed_metadata = parse_tenhou(tenhou_log, metadata)
    elif "mahjongsoul" in link or "maj-soul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        majsoul_log, metadata, player = await fetch_majsoul(link)
        assert (specified_player or player) < len(metadata["accounts"]), "Can't specify north player in a sanma game"
        kyokus, parsed_metadata = parse_majsoul(majsoul_log, metadata)
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`")
    if specified_player is not None:
        player = specified_player
    return kyokus, parsed_metadata, player
