"""The opening repertoire practised on the Openings tab, split by line.

Edit ``REPERTOIRE`` to change what you practise. Each line is written as ordinary move text from the
starting position. ``tabiya`` is how many plies are common to every line before your own choices begin:
the stats only count positions from there on, so the start position (reached in every game) never counts.
Lines are replayed with python-chess on import, so a typo fails loudly here and in the tests.
"""
from __future__ import annotations

import re
from functools import lru_cache

import chess

from collector.analysis import position_key

REPERTOIRE = [
    {"id": "london", "name": "London System", "colour": "white", "tabiya": 2, "lines": [
        {"id": "london-main", "name": "Main line vs …d5 and …c5",
         "moves": "1.d4 d5 2.Bf4 Nf6 3.e3 e6 4.Nf3 c5 5.c3 Nc6 6.Nbd2 Bd6 7.Bg3 O-O 8.Bd3"},
        {"id": "london-qb6", "name": "Early …c5 and …Qb6",
         "moves": "1.d4 d5 2.Bf4 c5 3.e3 Nc6 4.c3 Qb6 5.Qb3 c4 6.Qc2 Nf6 7.Nd2 Bg4 8.Ngf3"},
        {"id": "london-bf5", "name": "Symmetrical …Bf5",
         "moves": "1.d4 d5 2.Bf4 Nf6 3.e3 Bf5 4.c4 e6 5.Nc3 Bb4 6.Qb3 Nc6 7.Nf3"},
        {"id": "london-kid", "name": "Against a King's Indian setup",
         "moves": "1.d4 Nf6 2.Bf4 g6 3.e3 Bg7 4.Nf3 O-O 5.Be2 d6 6.h3 c5 7.O-O Nc6 8.c3"},
        {"id": "london-caro", "name": "Caro-Kann setup, …c6 and …Bf5",
         "moves": "1.d4 d5 2.Bf4 c6 3.e3 Bf5 4.c4 e6 5.Nc3 Nf6 6.Qb3 Qb6 7.c5 Qxb3 8.axb3"},
        {"id": "london-englund", "name": "Englund Gambit 3…Qe7",
         "moves": "1.d4 e5 2.dxe5 Nc6 3.Nf3 Qe7 4.Bf4 Qb4+ 5.Bd2 Qxb2 6.Nc3 Bb4 7.Rb1 Qa3 8.Rb3 Qa5 9.e4"},
        {"id": "london-englund-d6", "name": "Englund with 2…d6",
         "moves": "1.d4 e5 2.dxe5 d6 3.exd6 Bxd6 4.Nf3 Nf6 5.Bg5 Nc6 6.e3"},
        {"id": "london-englund-f6", "name": "Englund with 2…f6",
         "moves": "1.d4 e5 2.dxe5 f6 3.exf6 Nxf6 4.Nf3 d5 5.Bf4 Bd6 6.e3"},
    ]},
    {"id": "vienna", "name": "Vienna Game", "colour": "white", "tabiya": 2, "lines": [
        {"id": "vienna-nc6", "name": "2…Nc6 3.Bc4",
         "moves": "1.e4 e5 2.Nc3 Nc6 3.Bc4 Nf6 4.d3 Bc5 5.f4 d6 6.Nf3"},
        {"id": "vienna-bc5", "name": "2…Bc5",
         "moves": "1.e4 e5 2.Nc3 Bc5 3.Nf3 d6 4.d4 exd4 5.Nxd4 Nf6 6.Be2 O-O 7.O-O"},
        {"id": "vienna-dracula", "name": "Frankenstein–Dracula",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.Bc4 Nxe4 4.Qh5 Nd6 5.Bb3 Nc6 6.Nb5 g6 7.Qf3 f5 8.Qd5 Qe7 9.Nxc7+ Kd8 10.Nxa8"},
    ]},
    {"id": "vienna-gambit", "name": "Vienna Gambit", "colour": "white", "tabiya": 2, "lines": [
        {"id": "gambit-exf4", "name": "Accepted: 3…exf4 4.e5",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 exf4 4.e5 Ng8 5.Nf3 d6 6.d4 dxe5 7.Qe2 Be7 8.dxe5"},
        {"id": "gambit-nc6", "name": "Accepted: 2…Nc6 3.f4 exf4",
         "moves": "1.e4 e5 2.Nc3 Nc6 3.f4 exf4 4.Nf3 Nf6 5.d4 d5 6.exd5 Nxd5 7.Nxd5 Qxd5 8.Bxf4"},
        {"id": "gambit-d5", "name": "Declined: 3…d5, the main line",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 d5 4.fxe5 Nxe4 5.Nf3 Be7 6.d4 O-O 7.Bd3 f5 8.exf6 Bxf6 9.O-O"},
        {"id": "gambit-d6", "name": "Declined: 3…d6",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 d6 4.Nf3 Nc6 5.Bb5 Bd7 6.d3"},
        {"id": "gambit-declined-nc6", "name": "Declined: 3…Nc6 4.fxe5",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 Nc6 4.fxe5 Nxe5 5.d4 Ng6 6.e5 Ng8 7.Nf3 d6 8.Bc4"},
        {"id": "gambit-declined-bc5", "name": "Declined: 2…Nc6 3.f4 Bc5",
         "moves": "1.e4 e5 2.Nc3 Nc6 3.f4 Bc5 4.Nf3 d6 5.Bc4 Nf6 6.d3"},
    ]},
    {"id": "grand-prix", "name": "Grand Prix Attack", "colour": "white", "tabiya": 2, "lines": [
        {"id": "gp-g6", "name": "2…Nc6 3.f4 g6",
         "moves": "1.e4 c5 2.Nc3 Nc6 3.f4 g6 4.Nf3 Bg7 5.Bb5 Nd4 6.O-O Nxb5 7.Nxb5 d6 8.d3"},
        {"id": "gp-e6", "name": "2…Nc6 3.f4 e6",
         "moves": "1.e4 c5 2.Nc3 Nc6 3.f4 e6 4.Nf3 d5 5.Bb5 Nf6 6.Bxc6+ bxc6 7.d3"},
        {"id": "gp-d6", "name": "2…d6 3.f4",
         "moves": "1.e4 c5 2.Nc3 d6 3.f4 Nc6 4.Nf3 g6 5.Bb5 Bd7 6.O-O Bg7 7.d3"},
    ]},
    {"id": "kid", "name": "King's Indian Defence", "colour": "black", "tabiya": 1, "lines": [
        {"id": "kid-classical", "name": "Classical",
         "moves": "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6 8.d5 Ne7 9.Ne1 Nd7 10.f3 f5"},
        {"id": "kid-samisch", "name": "Sämisch",
         "moves": "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f3 O-O 6.Be3 c5 7.Nge2 Nc6 8.d5 Ne5 9.Ng3 e6"},
        {"id": "kid-four-pawns", "name": "Four Pawns Attack",
         "moves": "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f4 O-O 6.Nf3 c5 7.d5 e6 8.Be2 exd5 9.cxd5 Re8"},
        {"id": "kid-fianchetto", "name": "Fianchetto",
         "moves": "1.d4 Nf6 2.c4 g6 3.Nf3 Bg7 4.g3 O-O 5.Bg2 d6 6.O-O Nc6 7.Nc3 a6 8.d5 Na5 9.Nd2 c5"},
        {"id": "kid-london", "name": "Against the London",
         "moves": "1.d4 Nf6 2.Bf4 g6 3.e3 Bg7 4.Nf3 O-O 5.Be2 d6 6.h3 Nbd7 7.O-O c5 8.c3 b6"},
        {"id": "kid-colle", "name": "Against 2.Nf3 and 3.e3",
         "moves": "1.d4 Nf6 2.Nf3 g6 3.e3 Bg7 4.Bd3 O-O 5.O-O d6 6.c4 Nbd7 7.Nc3 e5"},
    ]},
    {"id": "pirc", "name": "Pirc Defence", "colour": "black", "tabiya": 1, "lines": [
        {"id": "pirc-austrian", "name": "Austrian Attack",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.f4 Bg7 5.Nf3 O-O 6.Bd3 Nc6 7.O-O e5 8.fxe5 dxe5 9.d5 Nd4"},
        {"id": "pirc-150", "name": "150 Attack",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Be3 c6 5.Qd2 b5 6.Bd3 Nbd7 7.Nf3 e5"},
        {"id": "pirc-classical", "name": "Classical",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Nf3 Bg7 5.Be2 O-O 6.O-O Bg4 7.Be3 Nc6 8.Qd2 e5 9.d5 Ne7"},
        {"id": "pirc-bd3", "name": "Against 3.Bd3",
         "moves": "1.e4 d6 2.d4 Nf6 3.Bd3 e5 4.c3 d5 5.dxe5 Nxe4 6.Nf3 Be7 7.O-O O-O"},
        {"id": "pirc-bc4", "name": "Against 4.Bc4",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Bc4 Bg7 5.Nf3 O-O 6.O-O Nxe4 7.Nxe4 d5 8.Bd3 dxe4 9.Bxe4 c5"},
    ]},
    {"id": "caro", "name": "Caro-Kann Defence", "colour": "black", "tabiya": 1, "lines": [
        {"id": "caro-advance", "name": "Advance",
         "moves": "1.e4 c6 2.d4 d5 3.e5 Bf5 4.Nf3 e6 5.Be2 c5 6.Be3 Nd7 7.O-O Ne7"},
        {"id": "caro-exchange", "name": "Exchange",
         "moves": "1.e4 c6 2.d4 d5 3.exd5 cxd5 4.Bd3 Nc6 5.c3 Nf6 6.Bf4 Bg4 7.Qb3 Qd7"},
        {"id": "caro-classical", "name": "Classical 3.Nc3",
         "moves": "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Bf5 5.Ng3 Bg6 6.h4 h6 7.Nf3 Nd7 8.h5 Bh7 9.Bd3 Bxd3 10.Qxd3 e6"},
        {"id": "caro-two-knights", "name": "Two Knights",
         "moves": "1.e4 c6 2.Nc3 d5 3.Nf3 Bg4 4.h3 Bxf3 5.Qxf3 e6 6.d4 Nf6 7.Bd3 dxe4 8.Nxe4 Nxe4 9.Qxe4 Nd7"},
    ]},
    {"id": "kid-flank", "name": "King's Indian vs 1.c4 and 1.Nf3", "colour": "black", "tabiya": 1, "lines": [
        {"id": "flank-english", "name": "English with Nc3 and g3",
         "moves": "1.c4 Nf6 2.Nc3 g6 3.g3 Bg7 4.Bg2 O-O 5.Nf3 d6 6.O-O e5 7.d3 Nc6 8.Rb1 a5"},
        {"id": "flank-reti", "name": "Réti and King's Indian Attack",
         "moves": "1.Nf3 Nf6 2.g3 g6 3.Bg2 Bg7 4.O-O O-O 5.d3 d6 6.c4 e5 7.Nc3 Nc6"},
        {"id": "flank-transpose", "name": "English into the King's Indian",
         "moves": "1.c4 Nf6 2.Nc3 g6 3.e4 d6 4.d4 Bg7 5.Nf3 O-O 6.Be2 e5"},
    ]},
    {"id": "fun", "name": "Just for fun", "colour": "white", "tabiya": 2, "fun": True, "lines": [
        {"id": "fun-icbm", "name": "ICBM Gambit",
         "moves": "1.e4 d5 2.Nf3 dxe4 3.Ng5 Nf6 4.d3 exd3 5.Bxd3 h6 6.Nxf7 Kxf7 7.Bg6+ Kxg6 8.Qxd8"},
        {"id": "fun-alien", "name": "Alien Gambit",
         "moves": "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Nf6 5.Ng5 h6 6.Nxf7 Kxf7 7.Bc4+ e6 8.Nf3 Bd6 9.O-O"},
    ]},
]

MOVE_NUMBER = re.compile(r"^\d+\.+")


def _sans(moves: str) -> list[str]:
    return [t for t in (MOVE_NUMBER.sub("", tok) for tok in moves.split()) if t]


def compile_line(opening: dict, line: dict) -> dict:
    """Replays a line into plies: the position before each move, the move, and on your moves the legal moves."""
    board = chess.Board()
    plies = []
    for index, san in enumerate(_sans(line["moves"])):
        try:
            move = board.parse_san(san)
        except ValueError as e:
            raise ValueError(f"{line['id']}: {san} is not legal at ply {index + 1}") from e
        mover = "white" if board.turn == chess.WHITE else "black"
        ply = {"san": board.san(move), "uci": move.uci(), "fen": board.fen(), "mover": mover,
               "label": f"{board.fullmove_number}{'.' if mover == 'white' else '…'}{board.san(move)}"}
        if mover == opening["colour"]:
            ply["legal"] = {m.uci(): board.san(m) for m in board.legal_moves}
            if index >= opening["tabiya"]:
                ply["key"] = position_key(board)
        plies.append(ply)
        board.push(move)
    text = " ".join(p["label"] if p["mover"] == "white" or i == 0 else p["san"] for i, p in enumerate(plies))
    return {"id": line["id"], "name": line["name"], "moves": text,
            "plies": plies, "end_fen": board.fen()}


@lru_cache(maxsize=1)
def repertoire() -> list[dict]:
    return [{"id": o["id"], "name": o["name"], "colour": o["colour"], "fun": o.get("fun", False),
             "lines": [compile_line(o, line) for line in o["lines"]]} for o in REPERTOIRE]


STATS_SQL = """
SELECT position_key, game_id, san, win_loss FROM dashboard.player_moves
WHERE username = %(player)s AND mode = ANY(%(modes)s) AND colour = %(colour)s AND position_key = ANY(%(keys)s)"""


def stats(fetch) -> dict:
    """Your analysed games against the repertoire. ``fetch(colour, keys)`` returns player_moves rows for those positions."""
    positions: dict[str, dict] = {}
    for colour in ("white", "black"):
        keys = sorted({p["key"] for o in repertoire() if o["colour"] == colour for ln in o["lines"] for p in ln["plies"] if "key" in p})
        for row in fetch(colour, keys):
            pos = positions.setdefault(row["position_key"], {"games": set(), "moves": {}})
            pos["games"].add(row["game_id"])
            move = pos["moves"].setdefault(row["san"], {"games": set(), "loss": []})
            move["games"].add(row["game_id"])
            if row["win_loss"] is not None:
                move["loss"].append(float(row["win_loss"]))

    out_positions = {key: {"games": len(p["games"]), "moves": sorted(
        ({"san": san, "games": len(m["games"]), "avg_loss": round(sum(m["loss"]) / len(m["loss"]), 1) if m["loss"] else None}
         for san, m in p["moves"].items()), key=lambda m: -m["games"])} for key, p in positions.items()}

    def slip(plies):
        """Your most common move off the line in these positions."""
        worst = None
        for p in plies:
            for san, m in positions[p["key"]]["moves"].items():
                if san != p["san"] and (worst is None or len(m["games"]) > worst["times"]):
                    worst = {"label": p["label"], "book": p["san"], "san": san, "times": len(m["games"])}
        return worst

    def games(plies):
        return len(set().union(*(positions[p["key"]]["games"] for p in plies)))

    lines, openings = {}, {}
    for o in repertoire():
        own = [[p for p in ln["plies"] if "key" in p] for ln in o["lines"]]
        # Your first choice in each line, and positions every line passes through, belong to the opening.
        common = set.intersection(*({p["key"] for p in plies} for plies in own))
        opening_level = {p["key"]: p for plies in own for i, p in enumerate(plies) if i == 0 or p["key"] in common}
        for ln, plies in zip(o["lines"], own):
            others = {p["key"] for other in own if other is not plies for p in other}
            reached = [p for p in plies if p["key"] in positions]
            # Games in the line are those reaching a position no other line has; slips count anywhere past the opening.
            lines[ln["id"]] = {"games": games([p for p in reached if p["key"] not in others]),
                               "deepest": reached[-1]["label"] if reached else None,
                               "slip": slip([p for p in reached if p["key"] not in opening_level])}
        # A game is in the opening once you've played its first move: it reached one of your later positions.
        later = {p["key"]: p for plies in own for p in plies[1:] if p["key"] in positions}
        openings[o["id"]] = {"games": games(later.values()),
                             "slip": slip([p for p in opening_level.values() if p["key"] in positions])}
    return {"positions": out_positions, "lines": lines, "openings": openings}
