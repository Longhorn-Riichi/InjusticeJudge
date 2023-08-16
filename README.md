
# InjusticeJudge

Analyzes your tenhou.net game to find instances of mahjong injustice. Currently, it checks for:

- Getting chased and dealing into a worse wait
- You experience iishanten hell (9+ draws)
- You start with 5+ shanten
- You lost points to someone's first-row win

## Usage

Clone this and run with either:

- `python main.py '<tenhou url>'`
- `python main.py '<mahjong soul url> <seat number 0-3>'`

where 0 = East, 1 = South, 2 = West, 3 = North

Outputs injustices to console

## High level TODOs

- implement hand scoring
- detect when your big tenpai hand is destroyed by a dama low value hand
- detect riichi ippatsu tsumo
- detect when you're dealer and someone's tsumo flipped your placement
