"""The opening repertoire practised on the Openings tab, split by line.

Edit ``REPERTOIRE`` to change what you practise. Each line is written as ordinary move text from the
starting position. ``tabiya`` is how many plies are common to every line before your own choices begin:
the stats only count positions from there on, so the start position (reached in every game) never counts.
``preview`` is how many plies of the first line the opening's thumbnail shows (default: the moves every line shares).
Lines are replayed with python-chess on import, so a typo fails loudly here and in the tests.
"""
from __future__ import annotations

import re
from functools import lru_cache

import chess

from collector.analysis import position_key

REPERTOIRE = [
    {"id": "london", "name": "London System", "colour": "white", "tabiya": 2, "preview": 3, "lines": [
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
        {"id": "london-greek-gift", "name": "Greek gift after …Be7 and …Nh5",
         "moves": "1.d4 d5 2.Bf4 Nf6 3.e3 e6 4.Nf3 c5 5.c3 Nc6 6.Nbd2 Be7 7.Bd3 O-O 8.Ne5 Bd6 9.Ndf3 Nh5 10.Bxh7+ Kxh7 11.Ng5+ Qxg5 12.Bxg5"},
        {"id": "london-greek-gift-mate", "name": "Greek gift, the king runs",
         "moves": "1.d4 d5 2.Bf4 Nf6 3.e3 e6 4.Nf3 c5 5.c3 Nc6 6.Nbd2 Be7 7.Bd3 O-O 8.Ne5 Bd6 9.Ndf3 Nh5 10.Bxh7+ Kxh7 11.Ng5+ Kh8 12.Qxh5+ Kg8 13.Qh7#"},
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
        {"id": "vienna-qg4", "name": "2…Nc6 3.Bc4 Bc5 4.Qg4",
         "moves": "1.e4 e5 2.Nc3 Nc6 3.Bc4 Bc5 4.Qg4 g6 5.Qf3 Nf6 6.Nge2 d6 7.d3"},
        {"id": "vienna-na5", "name": "2…Nc6 3.Bc4 Nf6 4.d3 Na5",
         "moves": "1.e4 e5 2.Nc3 Nc6 3.Bc4 Nf6 4.d3 Na5 5.Nge2 Nxc4 6.dxc4 Bc5 7.O-O d6 8.Bg5"},
    ]},
    {"id": "vienna-gambit", "name": "Vienna Gambit (2…Nf6 3.f4)", "colour": "white", "tabiya": 2, "preview": 5, "lines": [
        {"id": "gambit-exf4", "name": "Accepted: 3…exf4 4.e5",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 exf4 4.e5 Ng8 5.Nf3 d6 6.d4 dxe5 7.Qe2 Be7 8.dxe5"},
        {"id": "gambit-d5", "name": "Declined: 3…d5, the main line",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 d5 4.fxe5 Nxe4 5.Nf3 Be7 6.d4 O-O 7.Bd3 f5 8.exf6 Bxf6 9.O-O"},
        {"id": "gambit-d6", "name": "Declined: 3…d6",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 d6 4.Nf3 Nc6 5.Bb5 Bd7 6.d3"},
        {"id": "gambit-declined-nc6", "name": "Declined: 3…Nc6 4.fxe5",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.f4 Nc6 4.fxe5 Nxe5 5.d4 Ng6 6.e5 Ng8 7.Nf3 d6 8.Bc4"},
    ]},
    {"id": "grand-prix", "name": "Grand Prix Attack vs the Sicilian", "colour": "white", "tabiya": 2, "lines": [
        {"id": "gp-g6", "name": "2…Nc6 3.f4 g6",
         "moves": "1.e4 c5 2.Nc3 Nc6 3.f4 g6 4.Nf3 Bg7 5.Bb5 Nd4 6.O-O Nxb5 7.Nxb5 d6 8.d3"},
        {"id": "gp-e6", "name": "2…Nc6 3.f4 e6",
         "moves": "1.e4 c5 2.Nc3 Nc6 3.f4 e6 4.Nf3 d5 5.Bb5 Nf6 6.Bxc6+ bxc6 7.d3"},
        {"id": "gp-d6", "name": "2…d6 3.f4",
         "moves": "1.e4 c5 2.Nc3 d6 3.f4 Nc6 4.Nf3 g6 5.Bb5 Bd7 6.O-O Bg7 7.d3"},
        {"id": "gp-e6-d5", "name": "2…e6 3.f4 d5",
         "moves": "1.e4 c5 2.Nc3 e6 3.f4 d5 4.Nf3 dxe4 5.Nxe4 Nc6 6.Bb5 Bd7 7.O-O"},
    ]},
    {"id": "french-advance", "name": "French Advance", "colour": "white", "tabiya": 2, "preview": 5, "lines": [
        {"id": "fr-qb6", "name": "Main line 5…Qb6",
         "moves": "1.e4 e6 2.d4 d5 3.e5 c5 4.c3 Nc6 5.Nf3 Qb6 6.a3 c4 7.Nbd2 Na5 8.Be2"},
        {"id": "fr-bd7", "name": "5…Bd7 and …Nge7",
         "moves": "1.e4 e6 2.d4 d5 3.e5 c5 4.c3 Nc6 5.Nf3 Bd7 6.Be2 Nge7 7.Na3 cxd4 8.cxd4 Nf5 9.Nc2"},
        {"id": "fr-early-qb6", "name": "4…Qb6 and the bishop swap",
         "moves": "1.e4 e6 2.d4 d5 3.e5 c5 4.c3 Qb6 5.Nf3 Bd7 6.a3 Bb5 7.Bxb5+ Qxb5 8.Nbd2"},
    ]},
    {"id": "anti-caro", "name": "Caro-Kann Two Knights", "colour": "white", "tabiya": 2, "lines": [
        {"id": "ac-bg4", "name": "3…Bg4",
         "moves": "1.e4 c6 2.Nc3 d5 3.Nf3 Bg4 4.h3 Bxf3 5.Qxf3 e6 6.d4 Nf6 7.Bd3 dxe4 8.Nxe4 Nxe4 9.Qxe4 Nd7 10.O-O"},
        {"id": "ac-dxe4", "name": "3…dxe4 and …Bf5",
         "moves": "1.e4 c6 2.Nc3 d5 3.Nf3 dxe4 4.Nxe4 Bf5 5.Ng3 Bg6 6.h4 h6 7.Ne5 Bh7 8.Qh5 g6 9.Bc4 e6 10.Qe2"},
        {"id": "ac-nf6", "name": "3…Nf6 4.e5",
         "moves": "1.e4 c6 2.Nc3 d5 3.Nf3 Nf6 4.e5 Ne4 5.Ne2 Bf5 6.Ng3 Nxg3 7.hxg3 e6 8.d4"},
    ]},
    {"id": "scandinavian", "name": "Against the Scandinavian", "colour": "white", "tabiya": 2, "lines": [
        {"id": "sc-qa5", "name": "3…Qa5",
         "moves": "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qa5 4.d4 Nf6 5.Nf3 c6 6.Bc4 Bf5 7.Bd2 e6 8.O-O"},
        {"id": "sc-qd6", "name": "3…Qd6",
         "moves": "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qd6 4.d4 Nf6 5.Nf3 a6 6.g3 Bg4 7.Bg2 Nc6 8.O-O"},
        {"id": "sc-qd8", "name": "3…Qd8",
         "moves": "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qd8 4.d4 Nf6 5.Nf3 Bg4 6.h3 Bxf3 7.Qxf3 c6 8.Be3"},
        {"id": "sc-nf6", "name": "2…Nf6",
         "moves": "1.e4 d5 2.exd5 Nf6 3.d4 Nxd5 4.Nf3 g6 5.Be2 Bg7 6.O-O O-O 7.c4 Nb6 8.Nc3"},
    ]},
    {"id": "austrian", "name": "Austrian Attack vs Pirc and Modern", "colour": "white", "tabiya": 2, "preview": 7, "lines": [
        {"id": "au-na6", "name": "5…O-O 6.Bd3",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.f4 Bg7 5.Nf3 O-O 6.Bd3 Na6 7.O-O c5 8.d5"},
        {"id": "au-c5", "name": "5…c5 6.dxc5",
         "moves": "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.f4 Bg7 5.Nf3 c5 6.dxc5 Qa5 7.Bd3 Qxc5 8.Qe2 O-O 9.Be3 Qa5 10.O-O"},
        {"id": "au-modern", "name": "Modern 1…g6",
         "moves": "1.e4 g6 2.d4 Bg7 3.Nc3 d6 4.f4 Nc6 5.Be3 Nf6 6.Nf3 O-O 7.Be2"},
    ]},
    {"id": "kid", "name": "King's Indian Defence", "colour": "black", "tabiya": 1, "preview": 6, "lines": [
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
        {"id": "flank-english", "name": "Against 1.c4 with Nc3 and g3",
         "moves": "1.c4 Nf6 2.Nc3 g6 3.g3 Bg7 4.Bg2 O-O 5.Nf3 d6 6.O-O e5 7.d3 Nc6 8.Rb1 a5"},
        {"id": "flank-transpose", "name": "Against 1.c4 and 3.e4",
         "moves": "1.c4 Nf6 2.Nc3 g6 3.e4 d6 4.d4 Bg7 5.Nf3 O-O 6.Be2 e5"},
        {"id": "flank-reti", "name": "Against 1.Nf3 (Réti and King's Indian Attack)",
         "moves": "1.Nf3 Nf6 2.g3 g6 3.Bg2 Bg7 4.O-O O-O 5.d3 d6 6.c4 e5 7.Nc3 Nc6"},
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
        {"id": "caro-panov", "name": "Panov-Botvinnik Attack",
         "moves": "1.e4 c6 2.d4 d5 3.exd5 cxd5 4.c4 Nf6 5.Nc3 e6 6.Nf3 Bb4 7.cxd5 Nxd5 8.Bd2 Nc6 9.Bd3 O-O 10.O-O Be7"},
        {"id": "caro-bayonet", "name": "Advance, 4.Nc3 and 5.g4",
         "moves": "1.e4 c6 2.d4 d5 3.e5 Bf5 4.Nc3 e6 5.g4 Bg6 6.Nge2 c5 7.h4 h5 8.Nf4 Bh7 9.Nxh5 cxd4 10.Qxd4 Nc6"},
        {"id": "caro-fantasy", "name": "Fantasy 3.f3",
         "moves": "1.e4 c6 2.d4 d5 3.f3 e6 4.Nc3 Bb4 5.a3 Bxc3+ 6.bxc3 dxe4 7.fxe4 e5 8.Nf3 exd4 9.cxd4 Nf6"},
        {"id": "caro-kia", "name": "Against 2.d3 (King's Indian Attack)",
         "moves": "1.e4 c6 2.d3 d5 3.Nd2 e5 4.Ngf3 Bd6 5.g3 Nf6 6.Bg2 O-O 7.O-O Re8"},
    ]},
    {"id": "dutch", "name": "Leningrad Dutch", "colour": "black", "tabiya": 1, "lines": [
        {"id": "dutch-main", "name": "Main line with g3 and c4",
         "moves": "1.d4 f5 2.g3 Nf6 3.Bg2 g6 4.Nf3 Bg7 5.O-O O-O 6.c4 d6 7.Nc3 Qe8 8.d5 a5"},
        {"id": "dutch-c4", "name": "Against 2.c4 and 3.Nc3",
         "moves": "1.d4 f5 2.c4 Nf6 3.Nc3 g6 4.Nf3 Bg7 5.e3 O-O 6.Be2 d6 7.O-O Qe8"},
        {"id": "dutch-staunton", "name": "Staunton Gambit 2.e4",
         "moves": "1.d4 f5 2.e4 fxe4 3.Nc3 Nf6 4.Bg5 g6 5.f3 exf3 6.Nxf3 Bg7 7.Bd3 O-O 8.O-O d6"},
        {"id": "dutch-bg5", "name": "Against 2.Bg5",
         "moves": "1.d4 f5 2.Bg5 g6 3.Nd2 Bg7 4.c3 Nf6 5.Ngf3 O-O 6.e3 d6 7.Be2 Nbd7"},
        {"id": "dutch-london", "name": "Against the London",
         "moves": "1.d4 f5 2.Bf4 Nf6 3.e3 g6 4.Nf3 Bg7 5.Be2 O-O 6.O-O d6 7.c4 Nc6"},
    ]},
    {"id": "fun", "name": "Just for fun", "colour": "white", "tabiya": 2, "fun": True, "lines": [
        {"id": "fun-icbm", "name": "ICBM Gambit",
         "moves": "1.e4 d5 2.Nf3 dxe4 3.Ng5 Nf6 4.d3 exd3 5.Bxd3 h6 6.Nxf7 Kxf7 7.Bg6+ Kxg6 8.Qxd8"},
        {"id": "fun-alien", "name": "Alien Gambit",
         "moves": "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Nf6 5.Ng5 h6 6.Nxf7 Kxf7 7.Bc4+ e6 8.Nf3 Bd6 9.O-O"},
        {"id": "fun-dracula", "name": "Frankenstein-Dracula (Vienna 3.Bc4)",
         "moves": "1.e4 e5 2.Nc3 Nf6 3.Bc4 Nxe4 4.Qh5 Nd6 5.Bb3 Nc6 6.Nb5 g6 7.Qf3 f5 8.Qd5 Qe7 9.Nxc7+ Kd8 10.Nxa8"},
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


def _preview(opening: dict, lines: list[dict]) -> str:
    shared = 0
    while all(shared < len(ln["plies"]) and ln["plies"][shared]["uci"] == lines[0]["plies"][shared]["uci"] for ln in lines):
        shared += 1
    plies = lines[0]["plies"]
    at = min(opening.get("preview", max(shared, 2)), len(plies))
    return plies[at]["fen"] if at < len(plies) else lines[0]["end_fen"]


@lru_cache(maxsize=1)
def repertoire() -> list[dict]:
    book = []
    for o in REPERTOIRE:
        lines = [compile_line(o, line) for line in o["lines"]]
        book.append({"id": o["id"], "name": o["name"], "colour": o["colour"], "fun": o.get("fun", False),
                     "preview": _preview(o, lines), "lines": lines})
    return book


def book_moves() -> dict[str, set[str]]:
    """Every move your repertoire plays from each of your positions, across all openings."""
    moves: dict[str, set[str]] = {}
    for o in repertoire():
        for ln in o["lines"]:
            for p in ln["plies"]:
                if "key" in p:
                    moves.setdefault(p["key"], set()).add(p["san"])
    return moves


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

    book = book_moves()

    def slip(plies):
        """Your most common move off the line in these positions. Another opening's move from there is not a slip."""
        worst = None
        for p in plies:
            for san, m in positions[p["key"]]["moves"].items():
                if san not in book[p["key"]] and (worst is None or len(m["games"]) > worst["times"]):
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
