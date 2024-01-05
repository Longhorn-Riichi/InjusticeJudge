import functools
import re
import google.protobuf as pb
import google.protobuf.reflection
from .proto import liqi_combined_pb2 as proto
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToDict
from typing import *
from .classes import CallInfo, GameRules, GameMetadata, Dir
from .classes2 import Draw, Hand, Kyoku, Ron, Score, Tsumo
from .constants import Event, Shanten, LIMIT_HANDS, MAJSOUL_YAKU, RIICHICITY_YAKU, TENHOU_LIMITS, TENHOU_YAKU, TRANSLATE, YAKUMAN, YAOCHUUHAI
from .display import ph, pt, round_name
from .utils import apply_delta_scores, calc_ko_oya_points, is_mangan, ix_to_tile, normalize_red_five, sorted_hand, to_dora, to_placement
from .wall import seed_wall, next_wall
from .yaku import debug_yaku
from pprint import pprint

# This file contains all the logic for fetching and parsing game logs into `Kyoku`s.
# 
# `__init__.py` calls the entry point `parse_game_link`, which takes a game log link
#    and returns a tuple: (kyokus, game metadata, player specified in the link).
#   
# `fetch_majsoul`/`fetch_tenhou` handle requesting and caching game logs, given a link.
# 
# `parse_majsoul`/`parse_tenhou` parse said game logs into a list of `Event`s
#   for each kyoku, as well as a `GameMetadata` object containing information about
#   the game across kyokus. After parsing, `postprocess_events` is called on each event
#   list, turning them into `Kyoku` objects. Returns the resulting list of `Kyoku`s,
#   plus the `GameMetadata` object.
#   
# The sole uses of the resulting `Kyoku` objects are:
# - `determine_flags` in `flags.py`, (used to calculate all the Flags)
# - `evaluate_injustices` in `injustices.py`. (used to fetch data for printing, e.g. dora)
# - in the Ronhorn bot, `parse_game` (used to fetch hand data, ukeire calculations)

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
MajsoulLog = List[Tuple[str, proto.Wrapper]]
RiichiCityLog = List[Any]

###
### postprocess events obtained from parsing
###

def postprocess_events(all_events: List[List[Event]],
                       metadata: GameMetadata,
                       all_dora_indicators: List[List[int]],
                       all_ura_indicators: List[List[int]],
                       all_walls: List[List[int]]) -> List[Kyoku]:
    """
    Go through a game (represented as a list of events) and add more events to it
    e.g. shanten changes, tenpai, ending nagashi discards
    Return a list of kyoku, which contains the new event list plus all data about the round
    """
    kyokus: List[Kyoku] = []
    for events, dora_indicators, ura_indicators, wall in zip(all_events, all_dora_indicators, all_ura_indicators, all_walls):
        assert len(events) > 0, "somehow got an empty events list"
        kyoku: Kyoku = Kyoku(rules=metadata.rules, wall=wall, num_dora_indicators_visible=metadata.rules.starting_doras)
        shanten_before_last_draw: List[Shanten] = []
        flip_kan_dora_next_discard = False
        def update_shanten(seat: int) -> None:
            old_shanten = shanten_before_last_draw[seat]
            new_shanten = kyoku.hands[seat].shanten
            if old_shanten != new_shanten:
                # calculate ukeire/furiten (if not tenpai, gives 0/False)
                ukeire = kyoku.get_ukeire(seat)
                kyoku.furiten[seat] = new_shanten[0] == 0 and any(w in kyoku.pond[seat] for w in new_shanten[1])
                kyoku.events.append((seat, "shanten_change", old_shanten, new_shanten, kyoku.hands[seat], ukeire, kyoku.furiten[seat]))
        for i, (seat, event_type, *event_data) in enumerate(events):
            kyoku.events.append(events[i]) # copy every event we process
            # if len(kyoku.hands) == metadata.num_players:
            #     print(seat, event_type, ph(kyoku.hands[seat].closed_part), "|", ph(kyoku.hands[seat].open_part), event_data)
            if event_type == "start_game":
                # initialize all the variables for this round to their starting value
                kyoku.round, kyoku.honba, kyoku.riichi_sticks, kyoku.start_scores = event_data
                kyoku.num_players = metadata.num_players
                kyoku.tiles_in_wall = 70 if kyoku.num_players == 4 else 55
                kyoku.doras = ([51, 52, 53] if metadata.rules.use_red_fives else []) + [to_dora(d, metadata.num_players) for d in dora_indicators]
                kyoku.uras = [to_dora(d, metadata.num_players) for d in ura_indicators]
            elif event_type == "haipai":
                # initialize every variable for this seat to its starting value
                hand = Hand(event_data[0])
                assert len(hand.tiles) == 13, f"haipai was length {len(hand.tiles)}, expected 13"
                kyoku.hands.append(hand)
                kyoku.pond.append([])
                kyoku.furiten.append(False)
                kyoku.haipai.append(hand)
                shanten_before_last_draw.append(hand.shanten)
                kyoku.final_draw_event_index.append(-1)
                kyoku.final_discard_event_index.append(-1)
            elif event_type == "draw":
                # process the draw of a tile (whether normal or after a kan)
                tile = event_data[0]
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                kyoku.hands[seat] = kyoku.hands[seat].add(tile)
                kyoku.final_draw = tile
                kyoku.final_draw_event_index[seat] = len(kyoku.events) - 1
                kyoku.tiles_in_wall -= 1
                assert len(kyoku.hands[seat].tiles) == 14
            elif event_type in {"discard", "riichi"}: # discards
                # process the discard of a tile (whether normal or riichi)
                tile, *_ = event_data
                old_shanten = kyoku.hands[seat].shanten
                kyoku.hands[seat] = kyoku.hands[seat].remove(tile)
                kyoku.final_discard = tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                kyoku.pond[seat].append(tile)
                update_shanten(seat)
            elif event_type in {"chii", "pon", "minkan"}: # calls
                # process a call (which is like a special draw)
                called_tile, call_tiles, call_dir = event_data
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                if event_type != "minkan":
                    kyoku.hands[seat] = kyoku.hands[seat].add(called_tile)
                    assert len(kyoku.hands[seat].tiles) == 14
                kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo(event_type, called_tile, call_dir, call_tiles))
            elif event_type in {"ankan", "kakan", "kita"}: # special discards
                # process a self call (which is like a special discard)
                called_tile, call_tiles, call_dir = event_data
                shanten_before_last_draw[seat] = kyoku.hands[seat].shanten
                # if kakan, replace the old pon call with kakan
                # and add the pon call to the kakan tiles
                if event_type == "kakan":
                    _, kyoku.hands[seat] = kyoku.hands[seat].kakan(called_tile)
                elif event_type == "ankan":
                    kyoku.hands[seat] = kyoku.hands[seat].add_call(CallInfo("ankan", called_tile, Dir.SELF, (called_tile,)*4))
                elif event_type == "kita":
                    kyoku.hands[seat] = kyoku.hands[seat].kita()
                kyoku.hands[seat] = kyoku.hands[seat].remove(called_tile)
                update_shanten(seat) # kans may change your wait
                kyoku.final_discard = called_tile
                kyoku.final_discard_event_index[seat] = len(kyoku.events) - 1
                assert len(kyoku.hands[seat].tiles) == 13
            elif event_type == "end_game":
                # process the result of a game; most of this is handled in parse_result
                unparsed_result = event_data[0]
                hand_is_hidden = [len(hand.open_part) == 0 for hand in kyoku.hands]
                kyoku.result = parse_result(unparsed_result, kyoku.round, metadata.num_players, hand_is_hidden, [h.kita_count for h in kyoku.hands], kyoku.rules)
                kyoku.events.append((0, "result", *kyoku.result))
                # if tsumo or kyuushu kyuuhai, pop the final tile from the winner's hand
                if kyoku.result[0] == "tsumo" or (kyoku.result[0] == "draw" and kyoku.result[1].name == "9 terminals draw"):
                    for seat in range(kyoku.num_players):
                        if len(kyoku.hands[seat].tiles) == 14:
                            kyoku.hands[seat] = kyoku.hands[seat].remove(kyoku.final_draw)
                            break
            # if the flag is set, we flip kan dora after processing a discard
            if flip_kan_dora_next_discard and event_type in {"discard", "riichi"}:
                flip_kan_dora_next_discard = False
                kyoku.num_dora_indicators_visible += 1
            # if this was a kan action, we set the dora flip flag for next discard
            if event_type in {"minkan", "ankan", "kakan"}:
                if metadata.rules.immediate_kan_dora:
                    kyoku.num_dora_indicators_visible += 1
                else:
                    flip_kan_dora_next_discard = True
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

def parse_result(result: List[Any], round: int, num_players: int, hand_is_hidden: List[bool], kita_counts: List[int], rules: GameRules) -> Tuple[Any, ...]:
    """
    Given a Tenhou game result list, parse it into a tuple where the first
    element is either "ron", "tsumo", or "draw"; the remainder of the tuple
    consists of "Ron" object(s), a "Tsumo" object, or a "Draw" object.
    These objects store all the relevant information about the win.
    (score changes, who won from who, was it dama, and yaku)
    """
    # the list consists of a string followed by all score info
    result_type, *score_info = result
    ret: List[Tuple[str, Any]] = []
    # score info is parsed in chunks of 2
    # score_info=[a, b, c, d] becomes scores=[[a,b],[c,d]]
    # score_info=[a] becomes scores=[[a]]
    scores = [score_info[i*2:i*2+2] for i in range((len(score_info)+1)//2)]
    # the result type is either "和了" (for ron/tsumo) or something else (for all draws)
    if result_type == "和了":
        rons: List[Ron] = []
        # each score info consists of a score delta list plus all info about the win
        for [score_delta, tenhou_result_list] in scores:
            # decompose the info about the win: winner, payer(s), points (ignored), and yaku names
            [winner, won_from, pao_seat, _, *yaku_strs] = tenhou_result_list
            # construct a Ron or Tsumo object
            # kwargs are common args to both objects
            kwargs = {
                "score_delta": score_delta,
                "winner": winner,
                "dama": hand_is_hidden[winner] and not any(y.startswith("立直") or y.startswith("ダブル立直") or y.startswith("両立直") for y in yaku_strs),
                "score": Score.from_tenhou_list(tenhou_result_list=tenhou_result_list,
                                                round=round,
                                                num_players=num_players,
                                                rules=rules,
                                                kita=kita_counts[winner]),
                "pao_from": None if winner == pao_seat else pao_seat,
            }
            if winner == won_from: # tsumo
                # return the single processed Tsumo object
                return ("tsumo", Tsumo(**kwargs))
            else:
                # append the processed Ron object to a list to be returned later
                rons.append(Ron(**kwargs, won_from=won_from))
        # return all the processed Ron objects
        return ("ron", *rons)
    elif result_type in ({"流局", "全員聴牌", "全員不聴", "流し満貫"} # exhaustive draws
                       | {"九種九牌", "四家立直", "三家和了", "四槓散了", "四風連打"}): # abortive draws
        # draws are either ryuukyoku or something else
        draw_type = "ryuukyoku" if result_type in {"流局", "全員聴牌", "全員不聴"} else "draw"
        # the score delta is usually given, except for abortive draws like 九種九牌
        #   in which case, we just set it to [0,0,0,0]
        score_delta = scores[0][0] if len(scores) > 0 else [0]*num_players
        # return the single processed Draw object
        return (draw_type, Draw(score_delta=score_delta, name=TRANSLATE[result_type]))
    else:
        assert False, f"unhandled Tenhou result type {result_type}"

###
### loading and parsing mahjong soul games
###

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
                                   final_score = [result_data[i][2] for i in range(num_players)],
                                   rules = GameRules.from_majsoul_detail_rule(num_players, metadata["config"]["mode"]["detailRule"], metadata["config"]["mode"]["mode"]))

    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat = nicknames.index(nickname) if nickname in nicknames else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat

###
### loading and parsing tenhou games
###

def parse_tenhou_link(link: str) -> Tuple[str, Optional[int]]:
    identifier_pattern = r'\?log=([0-9a-zA-Z-]+)'
    identifier_match = re.search(identifier_pattern, link)
    if identifier_match is None:
        raise Exception(f"Invalid Tenhou link: {link}")
    identifier = identifier_match.group(1)
    parts = identifier.split("-")
    assert len(parts) == 4, f"tenhou link id {identifier} should have 4 parts separated by dashes"
    if parts[3][0] == "x":
        # deanonymize the link
        f = [22136, 52719, 55146, 42104, 59591, 46934, 9248, 28891, 49597, 52974, 62844, 4015, 18311, 50730, 43056, 17939, 64838, 38145, 27008, 39128, 35652, 63407, 65535, 23473, 35164, 55230, 27536, 4386, 64920, 29075, 42617, 17294, 18868, 2081]
        padzero = lambda m: ("000" + m)[-4:]
        v = [int(val, 16) for val in (parts[3][1:5], parts[3][5:9], parts[3][9:13])]
        if "2010041111gm" <= parts[0]:
            x = int("3" + parts[0][4:10]) % (34 - int(parts[0][9]) - 1)
            parts[3] = padzero(hex(v[0] ^ v[1] ^ f[x]))
            parts[3] += padzero(hex(v[1] ^ v[2] ^ f[x] ^ f[x+1]))
    identifier = "-".join(parts)

    player_pattern = r'&tw=(\d)'
    player_match = re.search(player_pattern, link)
    if player_match is None:
        player_seat = 0
    else:
        player_seat = int(player_match.group(1))

    return identifier, player_seat

def fetch_tenhou(link: str, use_xml: bool = True) -> Tuple[TenhouLog, Dict[str, Any], Optional[int]]:
    """
    Fetch a raw tenhou log from a given link, returning a parsed log and the specified player's seat
    Example link: https://tenhou.net/0/?log=2023072712gm-0089-0000-eff781e1&tw=1&ts=4
    """
    import json
    identifier, player_seat = parse_tenhou_link(link)

    try:
        f = open(f"cached_games/game-{identifier}.json", 'r')
        game_data = json.load(f)
    except Exception:
        import requests
        USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/110.0"
        if use_xml:
            url = f"https://tenhou.net/0/log/?{identifier}"
        else:
            url = f"https://tenhou.net/5/mjlog2json.cgi?{identifier}"
        # print(f" Fetching game log at url {url}")
        r = requests.get(url=url, headers={"User-Agent": USER_AGENT})
        try:
            r.raise_for_status()
            game_data = r.json()
        except (requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ProxyError,
                requests.exceptions.SSLError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
                json.decoder.JSONDecodeError):
            use_xml = True
            url = f"https://tenhou.net/0/log/?{identifier}"
            r = requests.get(url=url, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
        if use_xml:
            log, game_data = tenhou_xml_to_log(identifier, r.text)
            game_data["log"] = log
        save_cache(filename=f"game-{identifier}.json", data=json.dumps(game_data, ensure_ascii=False).encode("utf-8"))
    log = game_data["log"]
    del game_data["log"]
    return log, game_data, (player_seat or None)

def tenhou_xml_to_log(identifier: str, xml: str) -> Tuple[TenhouLog, Dict[str, Any]]:
    """
    Turns a tenhou log obtained by https://tenhou.net/0/log/?{identifier}
     into a tenhou log obtained by https://tenhou.net/5/mjlog2json.cgi?{identifier}

    All the parsing code currently just works for the second log type,
      but we're unable to fetch it for games with special rules like shuugi
    The first log type exists for all rulesets and also specifies the wall seed,
      so it's better in all respects except that we don't have a parser for it
    The solution is this function, converting first log type -> second log type
      and also adds a key "wall_seed" to the second log type
    """
    # remove the start and close tags
    xml = xml.replace("<mjloggm ver=\"2.3\">", "")
    xml = xml.replace("</mjloggm>", "")
    # initialize the output, which is (log, game_data)
    log = []
    game_data: Dict[str, Any] = {"ver": 2.3, "ref": identifier}
    # some state variables used for parsing
    kyoku: Dict[str, Any] = {}
    last_draw = [-1,-1,-1,-1]
    just_drew = False
    calling_riichi = False
    doras: List[int] = []
    uras: List[int] = []
    # we actually have to parse the ruleset to see if kiriage mangan is enabled...
    rules: Optional[GameRules] = None
    num_players = 4
    def format_kyoku(kyoku, doras, uras):
        """Convert `kyoku` (a dict) into the correct output format (a json array)"""
        kyoku_obj = []
        kyoku_obj.append(kyoku["seed"][:3])
        kyoku_obj.append(kyoku["score"] + kyoku["shuugi"])
        kyoku_obj.append(doras)
        kyoku_obj.append(uras)
        for h in zip(kyoku["haipai"], kyoku["draws"], kyoku["discards"]):
            kyoku_obj.extend(list(h))
        kyoku_obj.append(kyoku["result"]) 
        return kyoku_obj

    # Go through all the tags and build each `kyoku` step-by-step
    for tag in xml.split("/>")[:-1]:
        # parse the tag into name and attributes
        tag = tag[1:] # remove "<"
        name, *attr_strs = tag.split(" ")
        attrs = dict(s.split("=") for s in attr_strs if s != "")
        attrs = {k: v[1:-1] for k, v in attrs.items()}

        if name == "SHUFFLE":
            # seed for generating the wall (used in wall.py)
            game_data["wall_seed"] = attrs["seed"]
        elif name == "GO":
            # ruleset
            game_data["lobby"] = int(attrs["lobby"])
            game_data["rule"] = attrs["rule"].split(",") if "rule" in attrs else [""] * 7
            game_data["csrule"] = attrs["csrule"].split(",") if "csrule" in attrs else [""] * 40
            rules = GameRules.from_tenhou_rules(num_players, game_data["rule"], game_data["csrule"])
        elif name == "UN":
            # usernames (plus some other info)
            if "name" in game_data:
                continue
            decodeURI = lambda str: str.replace("%","\\x").encode().decode("unicode_escape").encode("latin1").decode("utf-8")
            names = []
            names.append(decodeURI(attrs["n0"]))
            names.append(decodeURI(attrs["n1"]))
            names.append(decodeURI(attrs["n2"]))
            if "n3" in attrs:
                names.append(decodeURI(attrs["n3"]))
            game_data["name"] = names
            dans = "新人 ９級 ８級 ７級 ６級 ５級 ４級 ３級 ２級 １級 初段 二段 三段 四段 五段 六段 七段 八段 九段 十段 天鳳".split(" ")
            game_data["dan"] = [dans[int(v)] for v in attrs["dan"].split(",")]
            game_data["rate"] = [float(v) for v in attrs["rate"].split(",")]
            game_data["sx"] = attrs["sx"].split(",")
        elif name == "TAIKYOKU":
            # start of game tag; specifies starting dealer, but this is useless for us
            pass
        elif name == "INIT":
            # start of kyoku tag
            # push the kyoku we just processed (if we have one)
            if kyoku != {}:
                log.append(format_kyoku(kyoku, doras, uras))
            kyoku = {}
            kyoku["seed"] = [int(v) for v in attrs["seed"].split(",")]
            kyoku["score"] = [100 * int(v) for v in attrs["ten"].split(",")]
            if "chip" in attrs:
                kyoku["shuugi"] = [int(v) for v in attrs["chip"].split(",")]
            kyoku["oya"] = int(attrs["oya"])
            num_players = 3 if len(attrs["hai3"]) == 0 else 4
            assert rules is not None
            rules.num_players = num_players
            haipai0 = list(sorted_hand([ix_to_tile(int(v)) for v in attrs["hai0"].split(",")]))
            haipai1 = list(sorted_hand([ix_to_tile(int(v)) for v in attrs["hai1"].split(",")]))
            haipai2 = list(sorted_hand([ix_to_tile(int(v)) for v in attrs["hai2"].split(",")]))
            haipai3 = [] if num_players == 3 else list(sorted_hand([ix_to_tile(int(v)) for v in attrs["hai3"].split(",")]))
            kyoku["haipai"] = [haipai0, haipai1, haipai2, haipai3]
            kyoku["draws"] = [[],[],[],[]]
            kyoku["discards"] = [[],[],[],[]]
            last_draw = [-1,-1,-1,-1]
            calling_riichi = False
            doras = [ix_to_tile(kyoku["seed"][-1])]
            uras = []
        elif len(attrs) == 0: # draw or discard tag
            code, tile = name[0], ix_to_tile(int(name[1:]))
            if code in "TUVW": # draw
                seat = "TUVW".index(code)
                # print(seat, "<", tile)
                kyoku["draws"][seat].append(tile)
                last_draw[seat] = int(name[1:])
                just_drew = True
            elif code in "DEFG": # discard
                seat = "DEFG".index(code)
                # print(seat, ">", tile)
                if int(name[1:]) == last_draw[seat]:
                    tile = 60
                if calling_riichi:
                    tile = "r" + str(tile)
                kyoku["discards"][seat].append(tile)
                just_drew = False
        elif name == "N": # call
            # every call is completely specified by a 16 bit integer `m`
            # the format is detailed here: https://github.com/MahjongRepository/tenhou-log
            caller = int(attrs["who"])
            m = int(attrs["m"])
            # rightmost two bits specifies the call direction
            call_dir = m&3
            # the next three bits specify the call type
            # the call is stored as a base tile plus offsets for each tile;
            #   this is enough to determine all the tiles in the call
            # the base tile is stored in the leftmost bits
            # each call type stores it differently so we parse it out as `tile_info`
            # the offsets are stored in `rs`
            if m & 0x4: # chii
                call_type = "chii"
                tile_info = m>>10
                rs = [(m>>3)&3, 4+((m>>5)&3), 8+((m>>7)&3)]
            elif m & 0x8 or m & 0x10: # pon or kakan (which is a special pon)
                call_type = "pon" if m & 0x8 else "kakan"
                tile_info = m>>9
                rs = [0,1,2,3]
                if call_type == "pon":
                    rs.remove((m>>5)&3)
            else: # if none of those are set, it's ankan/daiminkan/kita
                call_type = "kita" if m & 0x20 else "ankan" if just_drew else "minkan"
                tile_info = m>>8
                rs = [0,1,2,3]
            # ankan/daiminkan specify 4 offsets, the others specify 3
            num_tiles = 4 if call_type in {"kita", "minkan", "ankan"} else 3
            # parse the base tile from `tile_info` = `tile_info//num_tiles`
            # it is given as an index `ix`. 0 is 1m, 1 is 2m, etc
            ix = tile_info//num_tiles
            # base tile for chii is the lowest of the three tiles
            # this lets them save some space since 8 and 9 cannot be base tiles
            # but this means we must parse it differently
            if call_type == "chii":
                ix = (ix//7)*9+ix%7
            # parse the called tile from `tile_info` = `tile_info%num_tiles`
            # this is an index into `rs` that specifies which of the `rs` was the called tile
            # exception: `rs` for kakan is a singleton array, which is the called tile
            called_tile = ix*4 + (rs[0] if call_type == "kakan" else rs[tile_info%num_tiles])
            # the tiles of the call are simply the base tile index * 4 + each offset
            # (tiles range from 0~135, representing all 136 tiles in a game)
            called_tiles: List[Any] = [(ix*4)+r for r in rs]

            # now output the parsed call into kyoku["draws"] or kyoku["discards"]
            # the format is:
            #   "c343536"   in draws    = chii 34 from kamicha
            #   "p353535"   in draws    = pon 35 from kamicha
            #   "35p3535"   in draws    = pon 35 from toimen
            #   "3535p35"   in draws    = pon 35 from shimocha
            #   "m12121212" in draws    = daiminkan 12 from kamicha
            #   "12m121212" in draws    = daiminkan 12 from toimen
            #   "121212m12" in draws    = daiminkan 12 from shimocha
            #   "414141a41" in discards = ankan 41
            #   "k17171717" in discards = kakan 17 where pon was from kamicha
            #   "17k171717" in discards = kakan 17 where pon was from toimen
            #   "1717k1717" in discards = kakan 17 where pon was from shimocha
            #   "f44"       in discards = kita
            pos = 3 - call_dir
            if call_type in {"minkan", "ankan"} and pos == 2:
                pos = 3
            called_tiles.remove(called_tile)
            called_tiles = called_tiles[:pos] + [call_type[0] + str(ix_to_tile(called_tile))] + called_tiles[pos:]
            call_str = "".join(str(ix_to_tile(t) if type(t) != str else t) for t in called_tiles)
            if call_type in {"ankan", "kakan"}:
                kyoku["discards"][caller].append(call_str)
            elif call_type == "kita":
                kyoku["discards"][caller].append("f44")
            else:
                kyoku["draws"][caller].append(call_str)
            # for daiminkan, we also push 0 to the discards to represent the lack of a discard
            if call_type == "minkan":
                kyoku["discards"][caller].append(0)
            last_draw[caller] = -1
        elif name == "REACH": # riichi
            # REACH tags always go: REACH step 1 > discard > REACH step 2
            # so we just toggle a flag that gets read during discard
            step = int(attrs["step"])
            if step == 1:
                calling_riichi = True
            elif step == 2:
                calling_riichi = False
        elif name == "DORA": # new dora
            # not needed because we get all dora at the end anyways
            pass
        elif name == "AGARI": # win
            # store all the provided dora/ura
            doras = [ix_to_tile(int(v)) for v in attrs["doraHai"].split(",")]
            if "doraHaiUra" in attrs:
                uras = [ix_to_tile(int(v)) for v in attrs["doraHaiUra"].split(",")]
            # the final round has an "owari" key storing the final scores
            if "owari" in attrs:
                final_scores = [int(v) * 100 for v in attrs["owari"].split(",")[0:8:2]]
                final_results = [float(v) for v in attrs["owari"].split(",")[1:8:2]]
                final_shuugi = [int(v) * 100 for v in attrs["owari"].split(",")[8::2]]
                final_scores += final_shuugi
                game_data["sc"] = [s for sc in zip(final_scores, final_results) for s in sc]
            # parse the score changes
            sc = attrs["sc"].split(",")
            # scores = [int(v) * 100 for v in sc[0:8:2]]
            deltas = [int(v) * 100 for v in sc[1:8:2]]
            kyoku["shuugi"] = [int(v) for v in sc[8::2]]
            shuugi_deltas = [int(v) for v in sc[9::2]]
            deltas += shuugi_deltas
            # parse the win details
            who, from_who, pao_who = int(attrs["who"]), int(attrs["fromWho"]), int(attrs["paoWho" if "paoWho" in attrs else "who"])
            fu, points, limit = [int(v) for v in attrs["ten"].split(",")]
            is_closed_hand = "m" not in attrs
            yaku = [int(v) for v in attrs["yaku"].split(",")[0::2]] if "yaku" in attrs else []
            yaku_vals = [int(v) for v in attrs["yaku"].split(",")[1::2]] if "yaku" in attrs else []
            yakuman = [int(v) for v in attrs["yakuman"].split(",")] if "yakuman" in attrs else []
            honba, riichis = [int(v) for v in attrs["ba"].split(",")]
            # calculate han, and apply kiriage mangan manually
            han = sum(yaku_vals)
            assert rules is not None
            if rules.kiriage_mangan and (han, fu) in ((4,30), (3,60)):
                limit = 1
            # format the yaku
            to_yaku_str = lambda id, val: f"{TENHOU_YAKU[id]}({val}飜)"
            to_yakuman_str = lambda id: f"{TENHOU_YAKU[id]}(役満)"
            yakus = [to_yaku_str(id, val) for id, val in zip(yaku, yaku_vals) if val > 0]
            yakumans = [to_yakuman_str(id) for id in yakuman]
            # format the point string
            if limit == 0:
                value_string = str(fu) + "符" + str(han) + "飜"
            else:
                value_string = TENHOU_LIMITS[limit]
            if who == from_who: # tsumo
                is_dealer = who == kyoku["seed"][0] % 4
                # reverse-calculate the ko and oya parts of the total points
                ko, oya = calc_ko_oya_points(points, num_players, is_dealer)
                if is_dealer: # dealer tsumo
                    point_string = f"{oya}点∀"
                else:
                    point_string = f"{ko}-{oya}点"
            else:
                point_string = f"{points}点"
            # store result or append to existing result
            if "result" not in kyoku:
                kyoku["result"] = ["和了"]
            kyoku["result"].append(deltas)
            kyoku["result"].append([who, from_who, pao_who, value_string + point_string, *yakus, *yakumans])
        elif name == "RYUUKYOKU": # draw
            type_to_name = {
                "nm":     "流し満貫",
                "yao9":   "九種九牌",
                "reach4": "四家立直",
                "ron3":   "三家和了",
                "kan4":   "四槓散了",
                "kaze4":  "四風連打",
            }
            # parse the score changes
            sc = attrs["sc"].split(",")
            # scores = [int(v) * 100 for v in sc[0:8:2]]
            deltas = [int(v) * 100 for v in sc[1:8:2]]
            kyoku["shuugi"] = [int(v) for v in sc[8::2]]
            shuugi_deltas = [int(v) for v in sc[9::2]]
            deltas += shuugi_deltas
            # output the appropriate name for the draw
            if "type" in attrs:
                kyoku["result"] = [type_to_name[attrs["type"]]]
            elif "hai0" in attrs and "hai1" in attrs and "hai2" in attrs and "hai3" in attrs:
                kyoku["result"] = ["全員聴牌"]
            elif "hai0" not in attrs and "hai1" not in attrs and "hai2" not in attrs and "hai3" not in attrs:
                kyoku["result"] = ["全員不聴"]
            else:
                kyoku["result"] = ["流局"]
            kyoku["result"].append(deltas)

    # done processing all tags, push the kyoku we just processed
    log.append(format_kyoku(kyoku, doras, uras))

    # if we set `game_data["log"] = log`
    #  then `game_data` should be exactly the right format, plus a "wall_seed" key
    return log, game_data

def parse_tenhou(raw_kyokus: TenhouLog, metadata: Dict[str, Any], nickname: Optional[str]) -> Tuple[List[Kyoku], GameMetadata, Optional[int]]:
    all_events: List[List[Event]] = []
    all_dora_indicators: List[List[int]] = []
    all_ura_indicators: List[List[int]] = []
    # check to see if the name of the fourth player is empty; Sanma if empty, Yonma if not empty.
    num_players: int = 3 if metadata["name"][3] == "" else 4
    rules = GameRules.from_tenhou_rules(num_players, metadata["rule"], metadata.get("csrule", ["0"]*3 + [""]*37))
    def get_call_dir(call: str) -> Dir:
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
        if not rules.use_red_fives:
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
        events.append((seat, "start_game", round, honba, riichi_sticks, tuple(scores)))

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
                call_tiles = extract_call_tiles(call, rules.use_red_fives)
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
                if not rules.use_red_fives:
                    draw = normalize_red_five(draw)
                events.append((curr_seat, "draw", draw))

            # if you tsumo, there's no next discard, so we jump out here
            if i[curr_seat] >= len(discards[curr_seat]):
                i[curr_seat] += 1
                if i[curr_seat] == len(draws[curr_seat]):
                    break
                else: # it's a kan into tsumo
                    continue

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
                elif not rules.use_red_fives:
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
                        same_tile = extract_call_tiles(next_draw, rules.use_red_fives)[0] == discard
                        if same_dir and same_tile:
                            curr_seat = seat
                            keep_curr_seat = True # don't increment turn after this
                            break

            # unless we keep_curr_seat, change turn to next player 
            curr_seat = curr_seat if keep_curr_seat else (curr_seat+1) % num_players

        assert all(i[seat] >= len(draws[seat]) for seat in range(num_players)), f"game ended prematurely in {round_name(round, honba)} on {curr_seat}'s turn; i = {i}, max i = {list(map(len, draws))}"
        events.append((curr_seat, "end_game", result))
        all_events.append(events)

    # parse metadata
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = metadata["name"],
                                   game_score = metadata["sc"][::2],
                                   final_score = list(map(lambda s: int(1000*s), metadata["sc"][1::2])),
                                   rules = rules)

    if "wall_seed" in metadata:
        seed_wall(metadata["wall_seed"][29:])
        all_walls = [next_wall() for _ in range(len(all_events))]
    else:
        all_walls = [[] for _ in all_events] # dummy
    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat = metadata["name"].index(nickname) if nickname in metadata["name"] else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat

async def parse_game_link(link: str, specified_players: Set[int] = set(), nickname: Optional[str]=None) -> Tuple[List[Kyoku], GameMetadata, Set[int]]:
    """Given a game link, fetch and parse the game into kyokus"""
    if "tenhou.net/" in link:
        tenhou_log, metadata, player = fetch_tenhou(link)
        if metadata["name"][3] == "":
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_tenhou(tenhou_log, metadata, nickname)
    elif "mahjongsoul" in link or "maj-soul" in link or "majsoul" in link:
        # EN: `mahjongsoul.game.yo-star.com`; CN: `maj-soul.com`; JP: `mahjongsoul.com`
        # Old CN (?): http://majsoul.union-game.com/0/?paipu=190303-335e8b25-7f5c-4bd1-9ac0-249a68529e8d_a93025901
        majsoul_log, metadata, player = await fetch_majsoul(link)
        if len(metadata["accounts"]) == 3:
            assert player != 3 or all(p != 3 for p in specified_players), "Can't specify North player in a sanma game"
        kyokus, parsed_metadata, parsed_player_seat = parse_majsoul(majsoul_log, metadata, nickname)
    elif len(link) == 20: # riichi city log id
        riichicity_log, metadata = fetch_riichicity(link)
        player = None
        kyokus, parsed_metadata, parsed_player_seat = parse_riichicity(riichicity_log, metadata, nickname)
    else:
        raise Exception("expected tenhou link similar to `tenhou.net/0/?log=`"
                        " or mahjong soul link similar to `mahjongsoul.game.yo-star.com/?paipu=`"
                        " or 20-character riichi city log id like `cjc3unuai08d9qvmstjg`")
    kyokus[-1].is_final_round = True
    if len(specified_players) == 0:
        if parsed_player_seat is not None:
            specified_players = {parsed_player_seat}
        elif player is not None:
            specified_players = {player}
    return kyokus, parsed_metadata, specified_players

def fetch_riichicity(identifier: str) -> Tuple[RiichiCityLog, Dict[str, Any]]:
    """
    Fetch a raw riichi city log given the log identifier.
    Example identifier: cm775fuai08d9bndf24g
    """
    import json
    try:
        f = open(f"cached_games/game-{identifier}.json", 'rb')
        game_data = json.load(f)
    except Exception:
        import os
        import dotenv
        import requests
        import urllib3
        dotenv.load_dotenv("config.env")
        SID = os.getenv("rc_sid")
        if SID is not None:
            game_data = requests.post(
                url="http://13.112.183.79/record/getRoomData",
                headers={
                    "Cookies": "{\"sid\":\"" + SID + "\"}",
                    "User-Agent": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                    "Accept-Encoding": urllib3.util.SKIP_HEADER,  # type: ignore[attr-defined]
                    "Connection": "close",
                },
                data="{\"keyValue\":\"" + identifier + "\"}").json()
            if game_data["code"] != 0:
                raise Exception(f"Error {game_data['code']}: {game_data['message']}")
        else:
            raise Exception("Need to set rc_sid in config.env!")
        save_cache(filename=f"game-{identifier}.json", data=json.dumps(game_data, ensure_ascii=False).encode("utf-8"))

    return game_data["data"]["handRecord"], game_data["data"]

def parse_riichicity(log: RiichiCityLog, metadata: Dict[str, Any], nickname: Optional[str]) -> Tuple[List[Kyoku], GameMetadata, Optional[int]]:
    import json
    num_players = metadata["playerCount"]
    player_ids: List[int] = []
    player_names: List[str] = []

    all_dora_indicators: List[List[int]] = []
    all_ura_indicators: List[List[int]] = []
    all_events: List[List[Event]] = []
    all_walls: List[List[int]] = []
    starting_dealer_pos = -1
    game_score: List[int] = []
    final_score: List[int] = []

    RC_TO_TENHOU_TILE = {
        # pinzu = 1-9
        1: 21, 2: 22, 3: 23, 4: 24, 5: 25, 6: 26, 7: 27, 8: 28, 9: 29,
        # souzu = 17-25
        17: 31, 18: 32, 19: 33, 20: 34, 21: 35, 22: 36, 23: 37, 24: 38, 25: 39,
        # manzu = 33-41
        33: 11, 34: 12, 35: 13, 36: 14, 37: 15, 38: 16, 39: 17, 40: 18, 41: 19,
        # jihai = 16n+1
        49: 41, 65: 42, 81: 43, 97: 44, 113: 45, 129: 46, 145: 47,
        # red fives = 256 + {5, 21, 37}
        261: 52, 277: 53, 293: 51
    }
    rc_to_tenhou_tiles = lambda tiles: tuple(RC_TO_TENHOU_TILE[tile] for tile in tiles)
    with_starting_dealer_0 = lambda lst: lst[starting_dealer_pos:] + lst[:starting_dealer_pos]

    def end_round(events: List[Event], result: List[Any]) -> None:
        nonlocal all_events
        all_events.append(events)
        # TODO dora
        # all_dora_indicators.append(dora_indicators)
        # all_ura_indicators.append(ura_indicators)

    for hand_record in log:
        tiles_in_wall = 70
        events: List[Event] = []
        starting_dora = -1
        last_seat = -1
        last_discard_index = -1
        round, honba = -1, -1
        haipai: List[Tuple[int, ...]] = [()] * num_players
        dora_indicators: List[int] = []
        ura_indicators: List[int] = []
        for ev in hand_record["handEventRecord"]:
            data = json.loads(ev["data"])
            ev["data"] = data
            seat = player_ids.index(ev["userId"]) if ev["userId"] in player_ids else 0
            if ev["eventType"] == 1: # haipai
                if starting_dealer_pos == -1:
                    starting_dealer_pos = data["dealer_pos"]
                    player_ids = with_starting_dealer_0([p["userId"] for p in hand_record["players"]])
                    player_names = with_starting_dealer_0([p["nickname"] for p in hand_record["players"]])
                    seat = player_ids.index(ev["userId"])

                haipai[seat] = rc_to_tenhou_tiles(data["hand_cards"])
                round, honba, riichi_sticks = data["chang_ci"] - 1, data["ben_chang_num"], data["li_zhi_bang_num"]
                scores = with_starting_dealer_0([p["hand_points"] for p in data["user_info_list"]])
                dora_indicators = [RC_TO_TENHOU_TILE[data["bao_pai_card"]]]
                if hand_record["quanFeng"] == 65: # south round wind
                    round += 4
                elif hand_record["quanFeng"] == 81: # west round wind
                    round += 8
            elif ev["eventType"] == 2: # start game or tenpai opportunity or draw
                if data["in_card"] == 0:
                    if data["is_first_xun_in"]: # start game
                        print("\n", round_name(round, honba))
                        starting_draw = haipai[round%4][-1]
                        haipai[round%4] = haipai[round%4][:-1]
                        for i, hand in enumerate(haipai):
                            events.append((i, "haipai", sorted_hand(hand)))
                        events.append((seat, "start_game", round, honba, riichi_sticks, tuple(scores)))
                        events.append((seat, "draw", starting_draw))
                    else: # tenpai opportunity
                        pass
                        # from pprint import pprint
                        # pprint(data)
                else: # draw
                    tile = RC_TO_TENHOU_TILE[data["in_card"]]
                    tiles_in_wall -= 1
                    events.append((seat, "draw", tile))
                    last_seat = seat
            elif ev["eventType"] == 3: # call opportunity
                tile = RC_TO_TENHOU_TILE[data["out_card"]]
            elif ev["eventType"] == 4: # discard or call
                tile = RC_TO_TENHOU_TILE[data["card"]] if data["card"] != 0 else 0
                # 2,3,4 are left/mid/right chii
                call_names = {2: "chii", 3: "chii", 4: "chii", 5: "pon", 6: "minkan", 8: "ankan", 9: "kakan", 13: "kita"}
                if data["action"] == 11: # discard
                    last_discard_index = len(events)
                    events.append((seat, "discard", tile))
                    last_seat = seat
                elif data["action"] in call_names.keys(): # chii/chii/chii/pon/daiminkan/ankan/kakan/kita
                    call_type = call_names[data["action"]]
                    if call_type in {"kakan", "kita"}:
                        call_tiles: Tuple[int, ...] = ()
                    else:
                        call_tiles = (*rc_to_tenhou_tiles(data["group_cards"]), tile)
                    call_dir = Dir((4 + last_seat - seat) % 4)
                    events.append((seat, call_type, tile, call_tiles, call_dir))
                    last_seat = seat
                elif data["action"] == 7: # ron
                    pass
                elif data["action"] == 10: # tsumo
                    pass
                elif data["action"] == 12: # kyuushu kyuuhai
                    pass
                else:
                    import os
                    if os.getenv("debug"):
                        raise Exception("unknown action " + str(data["action"]) + ", in " + round_name(round, honba) + " with " + str(tiles_in_wall) + " tiles left in wall")
            elif ev["eventType"] == 5: # ron, tsumo, ryuukyoku
                # game ended to ron or tsumo: construct a tenhou game result array
                result: List[Any] = ["和了"]
                if data["end_type"] in {0, 1}: # ron or tsumo
                    for win in data["win_info"]:
                        win_type = "tsumo" if data["end_type"] == 1 else "ron"
                        seat = player_ids.index(win["user_id"])
                        han = win["all_fang_num"]
                        fu = win["all_fu"]
                        score_string = f"{fu}符{han}飜"

                        # temporary stopgap since we don't know all yaku yet
                        import os
                        for yaku in win["fang_info"]:
                            if yaku["fang_type"] not in RIICHICITY_YAKU:
                                if not os.getenv("debug"):
                                    RIICHICITY_YAKU[yaku["fang_type"]] = "yaku#" + str(yaku["fang_type"])
                                else:
                                    raise Exception("unknown yaku " + str(yaku["fang_type"]) + ", in " + round_name(round, honba) + " with " + str(tiles_in_wall) + " tiles left in wall")

                        if any(TRANSLATE[RIICHICITY_YAKU[yaku["fang_type"]]] in YAKUMAN for yaku in win["fang_info"]):
                            score_string = "役満"
                        elif han >= 6 or is_mangan(han, fu):
                            score_string = LIMIT_HANDS[han]
                        points = win["all_point"]
                        point_string = f"{points}点"
                        pao_seat = seat # TODO: pao
                        if data["end_type"] == "1": # 
                            ko, oya = calc_ko_oya_points(points, num_players, is_dealer=(seat-round)%4==0)
                            if oya > 0:
                                point_string = f"{ko}-{oya}点"
                            else:
                                point_string = f"{ko}点∀"
                        fan_str = lambda yaku: f"{RIICHICITY_YAKU[yaku['fang_type']]}({'役満' if TRANSLATE[RIICHICITY_YAKU[yaku['fang_type']]] in YAKUMAN else str(yaku['fang_num'])+'飜'})"
                        yakus = [name for _, name in sorted((yaku['fang_type'], fan_str(yaku)) for yaku in win["fang_info"])]
                        delta_scores = with_starting_dealer_0([p["point_profit"] for p in data["user_profit"]])
                        # print("delta scores: ", delta_scores)
                        result.append(delta_scores)
                        result.append([seat, last_seat, pao_seat, score_string+point_string, *yakus])
                    if data["win_info"][0]["li_bao_card"] is not None:
                        ura_indicators = list(rc_to_tenhou_tiles(data["win_info"][0]["li_bao_card"]))
                    print("result: " + win_type)
                    print("yaku:", data["win_info"][0]["fang_info"])
                elif data["end_type"] == 6: # kyuushu kyuuhai
                    result = ["九種九牌"]
                    print("result: kyuushu kyuuhai")
                elif data["end_type"] == 7: # ryuukyoku
                    result = ["流局"]
                    delta_scores = with_starting_dealer_0([p["point_profit"] for p in data["user_profit"]])
                    # print("delta scores: ", delta_scores)
                    result.append(delta_scores)
                    print("result: ryuukyoku")
                else:
                    import os
                    if os.getenv("debug"):
                        raise Exception("unknown end_type " + str(data["end_type"]) + ", in " + round_name(round, honba) + " with " + str(tiles_in_wall) + " tiles left in wall")
                events.append((0, "end_game", result))
            elif ev["eventType"] == 6: # end game
                # these are unsorted, so we need to sort them
                user_data = sorted(data["user_data"], key=lambda p: player_ids.index(p["user_id"]))
                game_score = [p["point_num"] for p in user_data]
                final_score = [p["score"] * 100 for p in user_data]
                pass
            elif ev["eventType"] == 7: # new dora
                dora_indicators.append(RC_TO_TENHOU_TILE[data["cards"][-1]])
            elif ev["eventType"] == 8: # riichi
                # modify the previous discard
                assert events[last_discard_index][1] == "discard", events[last_discard_index]
                events[last_discard_index] = (events[last_discard_index][0], "riichi", *events[last_discard_index][2:])
            elif ev["eventType"] == 9: # ???
                pass
            elif ev["eventType"] == 11: # riichi tenpai info
                pass
            else:
                import os
                if os.getenv("debug"):
                    raise Exception("unknown eventType " + str(ev["eventType"]) + ", in " + round_name(round, honba) + " with " + str(tiles_in_wall) + " tiles left in wall")
        all_events.append(events)
        all_dora_indicators.append(dora_indicators)
        all_ura_indicators.append(ura_indicators)

    # parse metadata
    parsed_metadata = GameMetadata(num_players = num_players,
                                   name = player_names,
                                   game_score = game_score,
                                   final_score = final_score,
                                   rules = GameRules.from_riichicity_metadata(num_players, metadata))


    all_walls = [[] for _ in all_events] # dummy
    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat = player_names.index(nickname) if nickname in player_names else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat
