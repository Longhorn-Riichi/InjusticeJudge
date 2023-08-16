
# InjusticeJudge

Analyzes your tenhou.net game to find instances of mahjong injustice. Currently, it checks for:

- Getting chased and dealing into a worse wait
- You experience iishanten hell (9+ draws)
- You start with 5+ shanten
- You lost points to someone's first-row win

## Usage

Clone this repository and run with either:

- `python main.py '<tenhou url>'`
- `python main.py '<mahjong soul url> <seat number 0-3>'`

where 0 = East, 1 = South, 2 = West, 3 = North

Outputs injustices to console

## Setup for mahjong soul links

This is only required if you want to analyze mahjong soul logs

Create a `config.env` file containing the following:

    ms_uid = "<your uid>"
    ms_token = "<your token>"

Both your UID (not friend code!) and token can be found by capturing the login request.

To do this, open up the Network tab in the developer tools of your browser and filter for XHR requests.
Visit Mahjong Soul. Once you see a request that says POST, click it.
Check the request field, which should look like:

    {"uid":"<your uid>","token":"<your token>","deviceId":"..."}

## High level TODOs

- implement hand scoring
- detect when your big tenpai hand is destroyed by a dama low value hand
- detect riichi ippatsu tsumo
- detect when you're dealer and someone's tsumo flipped your placement
