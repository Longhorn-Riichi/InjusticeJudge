from base64 import b64decode
from hashlib import sha512
import struct
from typing import *
from .utils import ix_to_tile, sorted_hand

def ints_to_bytes(ints: List[int]) -> bytearray:
    return bytearray(b for i in ints for b in struct.pack("<I", i))
# assert ints_to_bytes([1, 1]) == bytearray([0, 0, 0, 1, 0, 0, 0, 1])

def bytes_to_ints(bytes: bytes) -> List[int]:
    ints = []
    for i in range(0, len(bytes), 4):
        ints.append(struct.unpack("<I", bytes[i:i+4])[0])
    return ints
# assert bytes_to_ints(bytearray([0, 0, 0, 1, 0, 0, 0, 1])) == [1, 1]

# The following is an implementation of the Mersenne Twister
# Fixed a bug in the `init_by_array` function:
#   `for ki in range(624):` should be `for ki in range(623):`
#   otherwise one of the initial values gets twisted twice

"""

Copyright (c) 2014-2016 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

This is a python implementation of mt19937ar from
http://www.math.sci.hiroshima-u.ac.jp/~m-mat/MT/MT2002/emt19937ar.html
http://www.math.sci.hiroshima-u.ac.jp/~m-mat/MT/MT2002/CODES/mt19937ar.c

"""

class mt19937(object):
    def __init__(self):
        self.mt = [0]*624
        self.mti = 625

    def seed(self, seed):
        self.mt[0] = seed & 0xffffffff
        for i in range(1,624):
            self.mt[i] = (1812433253 * (self.mt[i-1] ^ (self.mt[i-1] >> 30)) + i) & 0xffffffff
        self.mti = 624

    def init_by_array(self, key):
        self.seed(19650218)
        i = 1
        j = 0
        k = max(624, len(key))
        for ki in range(k):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i-1] ^ (self.mt[i-1] >> 30)) * 1664525)) + key[j] + j) & 0xffffffff
            i += 1
            j += 1
            if i >= 624:
                self.mt[0] = self.mt[623]
                i = 1
            if j >= len(key):
                j = 0
        for ki in range(623): # edited
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i-1] ^ (self.mt[i-1] >> 30)) * 1566083941)) - i) & 0xffffffff
            i += 1
            if i >= 624:
                self.mt[0] = self.mt[623]
                i = 1
        self.mt[0] = 0x80000000

    def int32(self):
        if self.mti >= 624:
            if self.mti == 625:
                self.seed(5489)

            for k in range(623):
                y = (self.mt[k] & 0x80000000) | (self.mt[k+1] & 0x7fffffff)
                if k < 624 - 397:
                    self.mt[k] = self.mt[k+397] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
                else:
                    self.mt[k] = self.mt[k+397-624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)

            y = (self.mt[623] & 0x80000000) | (self.mt[0] & 0x7fffffff)
            self.mt[623] = self.mt[396] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
            self.mti = 0

        y = self.mt[self.mti]
        self.mti += 1

        y ^= (y >> 11)
        y ^= (y << 7) & 0x9d2c5680
        y ^= (y << 15) & 0xefc60000
        y ^= (y >> 18)

        return y

    def int32b(self):
        print("mt2:", mt)
        if self.mti == 625:
            self.seed(5489)

        k = self.mti

        if k == 624:
            k = 0
            self.mti = 0

        if k == 623:
            y = (self.mt[623] & 0x80000000) | (self.mt[0] & 0x7fffffff)
            self.mt[623] = self.mt[396] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
        else:
            y = (self.mt[k] & 0x80000000) | (self.mt[k+1] & 0x7fffffff)
            if k < 624 - 397:
                self.mt[k] = self.mt[k+397] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
            else:
                self.mt[k] = self.mt[k+397-624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)

        y = self.mt[self.mti]
        self.mti += 1

        y ^= (y >> 11)
        y ^= (y << 7) & 0x9d2c5680
        y ^= (y << 15) & 0xefc60000
        y ^= (y >> 18)

        return y

mt = mt19937()
def seed_wall(seed):
    # the seed parsed from the log goes here
    mt.init_by_array(bytes_to_ints(bytearray(b64decode(seed))))
sha512_ints = lambda x: bytes_to_ints(sha512(ints_to_bytes(x)).digest())
def next_wall() -> List[int]:
    # generate a list of 32*9=288 random values the way their wall algorithm does it
    r: List[int] = []
    for i in range(9):
        r += sha512_ints([mt.int32() for _ in range(32)])
    wall = list(range(136))
    # Fisher-Yates using r to supply random values
    for i in range(135):
        j = i + (r[i] % (136-i))
        wall[i], wall[j] = wall[j], wall[i]
    # the final item of `wall` is the first tile drawn, so reverse it
    return list(reversed([ix_to_tile(t) for t in wall]))

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
