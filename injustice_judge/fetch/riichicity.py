from ..classes import Dir, GameMetadata, GameRules
from ..classes2 import Kyoku
from ..constants import Event, RIICHICITY_YAKU, LIMIT_HANDS, TRANSLATE, YAKUMAN
from ..display import round_name
from ..utils import calc_ko_oya_points, is_mangan, save_cache, sorted_hand
from .postprocess import postprocess_events
from typing import *
import requests

###
### loading and parsing riichi city games
###

class RiichiCityAPI:
    """Helper class to interface with the Mahjong Soul API"""
    def __init__(self, domain: str, email: str, password: str) -> None:
        self.domain = domain
        self.email = email
        self.password = password
        self.headers = {
          "User-Agent": "UnityPlayer/2021.3.35f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
          "Content-Type": "application/json",
          "X-Unity-Version": "2021.3.35f1",
        }
        self.cookies = {"deviceid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
    async def __aenter__(self) -> "RiichiCityAPI":
        res1 = await self.call("/users/checkVersion", version="2.1.4")
        version = f"{res1['data']['Version']}.{res1['data']['MinVersion']}"
        self.cookies["version"] = version
        res2 = await self.call("/users/initSession")
        self.cookies["sid"] = res2["data"]
        res3 = await self.call("/users/emailLogin", adjustId="", email=self.email, passwd=self.password)
        if res3["code"] > 0:
            raise Exception("Unable to log into riichi city")
        print("riichi city login successful")
        self.cookies["uid"] = res3["data"]["user"]["id"]
        return self

    async def __aexit__(self, err_type: Optional[Type[BaseException]], 
                              err_value: Optional[BaseException], 
                              traceback: Optional[Any]) -> bool:
        return False

    async def call(self, endpoint: str, **data: Any) -> Dict:
        # "Cookies" is not a typo
        self.headers["Cookies"] = str(self.cookies).replace("'", "\"")
        formatted = str(data).replace("'", "\"")
        return requests.post(f"https://{self.domain}{endpoint}", headers=self.headers, data=formatted).json()

RiichiCityLog = List[Any]

async def fetch_riichicity(identifier: str) -> Tuple[RiichiCityLog, Dict[str, Any], Optional[int]]:
    """
    Fetch a raw riichi city log given the log identifier.
    Example identifier: cm775fuai08d9bndf24g@1
    """
    import json
    player = None
    username = None
    if "@" in identifier:
        identifier, username = identifier.split("@")
        if username in "0123":
            player = int(username)
            username = None
    try:
        f = open(f"cached_games/game-{identifier}.json", 'rb')
        game_data = json.load(f)
    except Exception:
        import os
        import dotenv
        import requests
        import urllib3
        dotenv.load_dotenv("config.env")
        EMAIL = os.getenv("rc_email")
        PASSWORD = os.getenv("rc_password")
        if EMAIL is not None and PASSWORD is not None:
            async with RiichiCityAPI("aga.mahjong-jp.net", EMAIL, PASSWORD) as api:
                game_data = await api.call("/record/getRoomData", keyValue=identifier)
                if game_data["code"] != 0:
                    raise Exception(f"Error {game_data['code']}: {game_data['message']}")
        else:
            raise Exception("Need to set rc_email and rc_password (MD5 hash) in config.env!")
        save_cache(filename=f"game-{identifier}.json", data=json.dumps(game_data, ensure_ascii=False).encode("utf-8"))
    if username is not None:
        for p in game_data["data"]["handRecord"][0]["players"]:
            if p["nickname"] == username:
                player_pos = p["position"]
                starting_dealer_pos = json.loads(game_data["data"]["handRecord"][0]["handEventRecord"][0]["data"])["dealer_pos"]
                player = (player_pos - starting_dealer_pos) % 4
                break
    return game_data["data"]["handRecord"], game_data["data"], player

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
    final_score: List[float] = []

    RC_TO_TENHOU_TILE = {
        # pinzu = 1-9
        0x01: 21, 0x02: 22, 0x03: 23, 0x04: 24, 0x05: 25,
        0x06: 26, 0x07: 27, 0x08: 28, 0x09: 29,
        # souzu = 17-25
        0x11: 31, 0x12: 32, 0x13: 33, 0x14: 34, 0x15: 35,
        0x16: 36, 0x17: 37, 0x18: 38, 0x19: 39,
        # manzu = 33-41
        0x21: 11, 0x22: 12, 0x23: 13, 0x24: 14, 0x25: 15,
        0x26: 16, 0x27: 17, 0x28: 18, 0x29: 19,
        # jihai = 16n+1
        0x31: 41, 0x41: 42, 0x51: 43, 0x61: 44, 0x71: 45,
        0x81: 46, 0x91: 47,
        # red fives = 256 + {5, 21, 37}
        0x105: 52, 0x115: 53, 0x125: 51
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
                        starting_draw = haipai[round%4][-1]
                        haipai[round%4] = haipai[round%4][:-1]
                        for i, hand in enumerate(haipai):
                            events.append((i, "haipai", sorted_hand(hand)))
                        events.append((seat, "start_game", round, honba, riichi_sticks, tuple(scores)))
                        events.append((seat, "draw", starting_draw))
                    else: # tenpai opportunity
                        pass
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
                        if any(TRANSLATE[RIICHICITY_YAKU[yaku["fang_type"]]] in YAKUMAN for yaku in win["fang_info"]):
                            score_string = "役満"
                        elif han >= 6 or is_mangan(han, fu):
                            score_string = LIMIT_HANDS[han]
                        points = win["all_point"]
                        point_string = f"{points}点"
                        pao_seat = seat
                        for player, p in enumerate(with_starting_dealer_0(data["user_profit"])):
                            if p["is_bao_pai"]:
                                if pao_seat != seat:
                                    raise Exception("2+ players paying pao is not implemented")
                                pao_seat = player
                        if data["end_type"] == "1": # 
                            ko, oya = calc_ko_oya_points(points, num_players, is_dealer=(seat-round)%4==0)
                            if oya > 0:
                                point_string = f"{ko}-{oya}点"
                            else:
                                point_string = f"{ko}点∀"
                        fan_str = lambda yaku: f"{RIICHICITY_YAKU[yaku['fang_type']]}({'役満' if TRANSLATE[RIICHICITY_YAKU[yaku['fang_type']]] in YAKUMAN else str(yaku['fang_num'])+'飜'})"
                        yakus = [name for _, name in sorted((yaku['fang_type'], fan_str(yaku)) for yaku in win["fang_info"])]
                        delta_scores = with_starting_dealer_0([p["point_profit"] for p in data["user_profit"]])
                        result.append(delta_scores)
                        result.append([seat, last_seat if win_type == "ron" else seat, pao_seat, score_string+point_string, *yakus])
                    if data["win_info"][0]["li_bao_card"] is not None:
                        ura_indicators = list(rc_to_tenhou_tiles(data["win_info"][0]["li_bao_card"]))
                elif data["end_type"] == 2: # four wind draw
                    result = ["四風連打"]
                elif data["end_type"] == 3: # four kan draw
                    result = ["四槓散了"]
                elif data["end_type"] == 4: # four riichi draw
                    result = ["四家立直"]
                elif data["end_type"] == 5: # triple ron draw
                    result = ["三家和了"]
                elif data["end_type"] == 6: # kyuushu kyuuhai
                    result = ["九種九牌"]
                elif data["end_type"] == 7: # ryuukyoku
                    result = ["流局"]
                    delta_scores = with_starting_dealer_0([p["point_profit"] for p in data["user_profit"]])
                    result.append(delta_scores)
                else:
                    import os
                    if os.getenv("debug"):
                        raise Exception("unknown end_type " + str(data["end_type"]) + ", in " + round_name(round, honba) + " with " + str(tiles_in_wall) + " tiles left in wall")
                events.append((0, "end_game", result))
            elif ev["eventType"] == 6: # end game
                # these are unsorted, so we need to sort them
                user_data = sorted(data["user_data"], key=lambda p: player_ids.index(p["user_id"]))
                game_score = [p["point_num"] for p in user_data]
                final_score = [p["score"] / 10.0 for p in user_data]
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
    parsed_metadata.rules.calculate_placement_bonus(game_score, final_score)

    all_walls = [[] for _ in all_events] # dummy
    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat: Optional[int]
    if nickname is not None and nickname in "0123":
        player_seat = int(nickname)
    else:
        player_seat = player_names.index(nickname) if nickname in player_names else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat
