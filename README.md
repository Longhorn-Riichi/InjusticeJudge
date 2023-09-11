# InjusticeJudge

Analyzes your tenhou.net game to find instances of mahjong injustice. Currently, it checks for:

- Your tenpai was chased with a worse wait and you deal into it
- You experience iishanten hell (9+ draws)
- You start with 5+ shanten
- You lost points to someone's first-row ron or tsumo
- As dealer you lost points to a baiman+ tsumo
- Someone else had a bad wait ippatsu tsumo
- You just barely fail nagashi (due to the draw or a call)
- You deal into someone with your riichi tile (or tile that got you into tenpai)
- You draw a tile that would have completed a past tenpai wait
- You dealt in with what would have been the final discard of the round, while tenpai
- You dealt into any of: dama, ippatsu, houtei, double/triple ron, ura 3, or closed dora 3
- Your iishanten haipai got reset due to an abortive draw
- You reached yakuman tenpai and did not win
- You got head bumped
- You were haneman+ tenpai but someone else won with a below-mangan hand
- You dropped placement only because the winner got ura
- You had a (good) 4+ sided wait and didn't win
- You dealt into chankan while tenpai
- You had an early 8 outs ryanmen (or better) and never folded, but didn't win
- You keep drawing honor tiles that you discard immediately (6+ times)
- You draw and discard the same tile 6 times in a row (not in tenpai)
- You started with a shanten 2 worse than every other player
- You discarded dora and immediately drew dora after
- Your turn was skipped by pon/kan 3 or more times
- Your tenpai wait was damaged by someone calling ankan
- You are going for honitsu but drew 6+ off-suit tiles in a row
- You started with a 1-4-7 shape in more than one suit
- You're still 4-shanten or worse after the first row of discards
- You had to deal with a triple riichi in which you are the one not in riichi (and you dealt in)
- You started with 3+ dora while 4th place, but then someone else won
- Someone with a 5-shanten start (or worse) reaches tenpai before your 3-shanten start (or better)

__Note__: This program was explicitly written to

1) be funny
2) demonstrate how common some of these perceived injustices are.

What appears as an injustice to you may be well justified from another player's perspective!

## Usage (standalone)

Clone this repository and run with either:

- `python main.py '<tenhou url>'`
- `python main.py '<mahjong soul url>'`
- `python main.py '<tenhou url>' <seat number 0-3>`
- `python main.py '<mahjong soul url>' <seat number 0-3>`

where 0 = East, 1 = South, 2 = West, 3 = North

Outputs injustices to console.

## Usage (library)

```python
import asyncio
from injustice_judge import analyze_game

asyncio.run(analyze_game("tenhou link")) # Use player from link
asyncio.run(analyze_game("tenhou link", 2)) # West player
```

## Setup for mahjong soul links

This is only required if you want to analyze mahjong soul logs. Create a `config.env` file and choose one option below:

### Option 1: login to Chinese server with username and password

    ms_username = "<your username>"
    ms_password = "<your password>"

### Option 2: login to EN server with `uid` and `token`

    ms_uid = "<your uid>"
    ms_token = "<your token>"

Both your UID (not friend code!) and token can be found by capturing the login request.
To do this:

- Open up the Network tab in the developer tools of your browser and filter for XHR requests.
- Visit Mahjong Soul with the Network tab open.
- Once you see a request that says POST, click it.
- Check the request field, which should contain your UID and token: `{"uid":"<your uid>","token":"<your token>","deviceId":"..."}`

## High level TODOs

