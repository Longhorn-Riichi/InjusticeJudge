# InjusticeJudge

Analyzes your `Mahjong Soul` or `tenhou.net` game to find instances of mahjong injustice. Currently, it checks for:

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
- You're still 4-shanten or worse after the first row of discards
- You had to deal with a triple riichi in which you are the one not in riichi (and you dealt in)
- You started with 3+ dora while 4th place, but then someone else won
- Your iishanten had 0 outs (at any point in time)
- You had no safe tiles after someone's riichi and drew at least 4 dangerous tiles afterwards
- Everyone immediately discarded a dangerous tile after your riichi
- You drew into tenpai but all the discards that give you tenpai will deal in
- You could have called chii into a 4+ han tenpai but were overridden by pon/kan

__Note__: This program was explicitly written to

1) be funny
2) demonstrate how common some of these perceived injustices are.

What appears as an injustice to you may be well justified from another player's perspective!

## Skills

Newest feature on the block is skill detection. Skills are instances of pure mahjong skill. Examples include:

- You started out with an iishanten hand
- You started out with 3+ dora
- You dealt 4 dangerous discards without dealing in
- Every tile you drew brought you closer to tenpai
- You called kan to get yourself 4 dora
- You called pon, pon, ron consecutively (or any two calls + win consecutively)
- You head bumped someone
- You won right after someone declared riichi, taking their riichi stick
- You won with a hell wait
- You changed wait and immediately won after
- Your very last draw brought you into tenpai (so you could get noten payments)
- You chased someone's tenpai and won with ippatsu
- You gained placement only because you had ura
- You won some silly yaku (ippatsu tsumo, rinshan, chankan, haitei, sankantsu, ryanpeikou, sanshoku doukou, double riichi, nagashi mangan)
- You got any yakuman (or sanbaiman)

Skills are pretty common. There's usually several in every game, and InjusticeJudge will recognize your skills for what they are.

## Usage (standalone)

Clone this repository and run with either:

- `python main.py '<tenhou url>'`
- `python main.py '<mahjong soul url>'`
- `python main.py '<tenhou url>' <seat number 0-3>`
- `python main.py '<mahjong soul url>' <seat number 0-3>`

where 0 = East, 1 = South, 2 = West, 3 = North.

Outputs injustices to console.

To output skills, open up `main.py` and change `{"injustice"}` to `{"skill"}`.

## Usage (library)

```python
import asyncio
from injustice_judge import analyze_game

# output injustices
asyncio.run(analyze_game("tenhou link")) # Use player from link
asyncio.run(analyze_game("tenhou link", {2})) # West player
asyncio.run(analyze_game("tenhou link", {0,1,2,3})) # All players

# output skills for each player
asyncio.run(analyze_game("tenhou link", look_for={"skill"})) # Use player from link
asyncio.run(analyze_game("tenhou link", {0,1,2,3}, look_for={"skill"})) # All players

# do both
asyncio.run(analyze_game("tenhou link", {0,1,2,3}, look_for={"injustice", "skill"}))
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

