from base64 import b64decode
from .classes import mt19937
from hashlib import sha512
import struct
from typing import *
from .utils import sorted_hand

def ints_to_bytes(ints: List[int]) -> bytearray:
    return bytearray(b for i in ints for b in struct.pack("<I", i))
# assert ints_to_bytes([1, 1]) == bytearray([0, 0, 0, 1, 0, 0, 0, 1])

def bytes_to_ints(bytes: bytes) -> List[int]:
    ints = []
    for i in range(0, len(bytes), 4):
        ints.append(struct.unpack("<I", bytes[i:i+4])[0])
    return ints
# assert bytes_to_ints(bytearray([0, 0, 0, 1, 0, 0, 0, 1])) == [1, 1]

mt = mt19937()
def seed_wall(seed):
    mt.init_by_array(bytes_to_ints(bytearray(b64decode(seed))))
sha512_bytes = lambda x: bytes_to_ints(sha512(ints_to_bytes(x)).digest())
def next_wall() -> List[int]:
    r: List[int] = []
    for i in range(9):
        r += sha512_bytes([mt.int32() for _ in range(32)])
    wall = list(range(136))
    # Fisher-Yates using r to supply random values
    for i in range(135):
        j = i + (r[i] % (136-i))
        wall[i], wall[j] = wall[j], wall[i]
    # dice0 = rnd[135] % 6;
    # dice1 = rnd[136] % 6;
    tiles = [*range(11,20), *range(21,30), *range(31,40), *range(41,48)]
    reds = {tiles.index(15): 51, tiles.index(25): 52, tiles.index(35): 53}
    to_tile = lambda t: reds[t//4] if t//4 in reds and t%4==0 else tiles[t//4]
    return list(reversed([to_tile(t) for t in wall]))

def print_wall(wall: List[int]) -> None:
    haipai: List[List[int]] = [
        list(sorted_hand(wall[0:64:16]+wall[1:48:16]+wall[2:48:16]+wall[3:48:16]+[wall[52]])),
        list(sorted_hand(wall[4:64:16]+wall[5:48:16]+wall[6:48:16]+wall[7:48:16])),
        list(sorted_hand(wall[8:64:16]+wall[9:48:16]+wall[10:48:16]+wall[11:48:16])),
        list(sorted_hand(wall[12:64:16]+wall[13:48:16]+wall[14:48:16]+wall[15:48:16]))]
    draws: List[List[int]] = [wall[56:124:4],wall[53:125:4],wall[54:122:4],wall[55:123:4]]
    dead_wall = [t for t in wall[-14:]]
    dora_indicators = wall[-6:-16:-2]
    ura_indicators = wall[-5:-15:-2]

    for i, hand in enumerate(haipai):
        print(f"Player {i} haipai: {hand}")
    for i, draw in enumerate(draws):
        print(f"Player {i} draws: {draw}")
    print(f"Haitei: {haipai[1][-1]}")
    print(f"Dead wall: {dead_wall}")
    print(f"Hidden part of dead wall: {get_hidden_dead_wall(wall, 0, False)}")
    print(f"Dora indicator: {dora_indicators[0]}")
    print(f"Potential dora indicators: {dora_indicators}")
    print(f"Potential ura indicators: {ura_indicators}")

def get_hidden_dead_wall(wall: List[int], num_kans: int, sanma: bool, num_kitas: int = 0) -> List[int]:
    # Get the hidden part of the dead wall (i.e. not the visible dora indicators)
    kan_kita_tiles = wall[-(8 if sanma else 4):]
    # kan/kita replacement tiles are drawn kind of weird: [6 7 4 5 2 3 0 1]
    ixs = [6,7,4,5,2,3,0,1] if sanma else [2,3,0,1]
    for i in ixs[:num_kans+num_kitas]:
        kan_kita_tiles.remove(wall[i-(8 if sanma else 4)])
    dora_indicators = wall[-10:-20:-2] if sanma else wall[-6:-16:-2]
    ura_indicators = wall[-9:-19:-2] if sanma else wall[-5:-15:-2]
    later_tiles = wall[-14-num_kans-num_kitas:-14]
    return kan_kita_tiles + [0] + dora_indicators[1+num_kans:] + [0] + ura_indicators + [0] + later_tiles

def get_remaining_wall(wall: List[int], tiles_in_wall: int, sanma: bool, num_kans_kitas: int = 0) -> List[int]:
    offset = (55 if sanma else 70) - tiles_in_wall
    return wall[52+offset:-14-num_kans_kitas]

def get_remaining_draws(wall: List[int], tiles_in_wall: int, sanma: bool, num_kans_kitas: int = 0) -> List[int]:
    return get_remaining_wall(wall, tiles_in_wall, sanma, num_kans_kitas)[::(3 if sanma else 4)]
