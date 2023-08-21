
# InjusticeJudge

Analyzes your tenhou.net game to find instances of mahjong injustice. Currently, it checks for:

- Your tenpai was chased with a worse wait and you deal into it
- You experience iishanten hell (9+ draws)
- You start with 5+ shanten
- You lost points to someone's first-row ron or tsumo
- You dealt into dama or ippatsu
- Someone else had a bad wait ippatsu tsumo
- You just barely fail nagashi (due to the draw or a call)
- You deal into someone with your riichi tile (or tile that got you into tenpai)
- You draw a tile that would have completed a past tenpai wait

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

- detect when your big tenpai hand is destroyed by a low value hand
