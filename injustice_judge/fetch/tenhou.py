import re
from ..constants import Event, TENHOU_LIMITS, TENHOU_YAKU
from ..classes import Dir, GameMetadata, GameRules
from ..classes2 import Kyoku
from ..utils import calc_ko_oya_points, ix_to_tile, normalize_red_five, save_cache, sorted_hand
from ..display import round_name
from ..wall import seed_wall, next_wall
from .postprocess import postprocess_events
from typing import *

###
### loading and parsing tenhou games
###

TenhouLog = List[List[List[Any]]]

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
                                   final_score = metadata["sc"][1::2],
                                   rules = rules)
    parsed_metadata.rules.calculate_placement_bonus(parsed_metadata.game_score, parsed_metadata.final_score)

    if "wall_seed" in metadata:
        seed_wall(metadata["wall_seed"][29:])
        all_walls = [next_wall() for _ in range(len(all_events))]
    else:
        all_walls = [[] for _ in all_events] # dummy
    assert len(all_events) == len(all_dora_indicators) == len(all_ura_indicators) == len(all_walls)
    player_seat = metadata["name"].index(nickname) if nickname in metadata["name"] else None
    return postprocess_events(all_events, parsed_metadata, all_dora_indicators, all_ura_indicators, all_walls), parsed_metadata, player_seat
