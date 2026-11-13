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

# Why each move is played, keyed by the moves up to and including it. Written by hand and checked against
# Stockfish on the position; NOTES_TO_CHECK lists the ones worth a second opinion. A "white: " or "black: "
# prefix limits a note to that colour's openings, where both reach the same moves.
NOTES = {
    # London: the setup
    "d4 d5 Bf4": "The London move: get the dark-squared bishop out before e3 locks it inside your pawns.",
    "d4 d5 Bf4 Nf6 e3": "Supports d4 and opens a path for the light-squared bishop. Your pawns now form a solid wall on c3, d4 and e3.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3": "Natural development that also covers e5, the square your knight wants later.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5": "Black hits your centre. Next they often play ...Qb6 to attack b2.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3": "Completes the pyramid: d4 stays rock solid, and the queen can later defend b2 from b3 or c2.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2": "Keeps c3 supported and prepares Ne5 or e4. The knight on d2 can also come back to f3 if the other one moves.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Bd6": "Black offers to trade off your good bishop with ...Bxf4.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Bd6 Bg3": "Keep the bishop instead of trading. If Black takes with ...Bxg3, recapture hxg3 and your rook gets the open h-file.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Bd6 Bg3 O-O Bd3": "The bishop aims at h7, Black's castled king. Typical plans: Qe2 and castle, or Ne5 with f4 and a kingside attack.",
    # London: early ...c5 and ...Qb6
    "d4 d5 Bf4 c5": "The most testing reply: Black strikes at d4 straight away, and ...Qb6 against b2 is coming.",
    "d4 d5 Bf4 c5 e3": "Back up d4 with a pawn so ...cxd4 can be met by exd4.",
    "d4 d5 Bf4 c5 e3 Nc6 c3": "Same pyramid as the main line: d4 can't be won.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6": "Attacks b2. With your bishop gone from c1, nothing else defends it.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3": "Defends b2 and offers a queen trade, which suits you.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3 c4": "Black avoids the trade by hitting your queen.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3 c4 Qc2": "The queen stays near b2 and eyes the h7 square along the b1-h7 diagonal.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3 c4 Qc2 Nf6 Nd2": "Prepares e4 to break open the centre, and b3 to undermine Black's c4 pawn.",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3 c4 Qc2 Nf6 Nd2 Bg4 Ngf3": "Develops and finishes your setup. Stockfish prefers 8.b3 here, hitting the c4 pawn first.",
    # London: symmetrical ...Bf5
    "d4 d5 Bf4 Nf6 e3 Bf5": "Black copies you. The catch: with their bishop gone, b7 is weak.",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4": "Hits d5 and opens the way for Qb3 against b7.",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4 e6 Nc3": "More pressure on d5. Watch for ...Bb4 pinning this knight.",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4 e6 Nc3 Bb4": "The pin: Black's bishop holds your knight to the king.",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4 e6 Nc3 Bb4 Qb3": "Attacks b7 and the bishop on b4 together. Stockfish actually prefers 6.Nf3 or 6.Be2 here and rates this as slightly better for Black.",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4 e6 Nc3 Bb4 Qb3 Nc6 Nf3": "Develop and get ready to castle. Black's pin on c3 is the thing to deal with next, often with a3.",
    # London vs a King's Indian setup
    "white: d4 Nf6 Bf4 g6": "Black is going for a King's Indian setup with the bishop on g7.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2": "A quiet, safe square. Your bishop on f4 already covers the important diagonal.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3": "Gives your bishop a retreat on h2, so ...Nh5 can't trade it off, and stops ...Bg4 and ...Ng4.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3 c5 O-O": "King to safety before the centre opens.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3 c5 O-O Nc6 c3": "Holds d4 against ...c5 and the g7 bishop. Stockfish also likes the sharper 8.d5, chasing the knight.",
    # London vs a Caro-Kann setup
    "d4 d5 Bf4 c6 e3 Bf5": "Black's bishop leaves, and again b7 becomes a target.",
    "d4 d5 Bf4 c6 e3 Bf5 c4": "Strike at d5 and prepare Qb3, hitting b7.",
    "d4 d5 Bf4 c6 e3 Bf5 c4 e6 Nc3 Nf6 Qb3": "Attacks b7. Black has to defend it or offer a trade.",
    "d4 d5 Bf4 c6 e3 Bf5 c4 e6 Nc3 Nf6 Qb3 Qb6 c5": "The key trick: the pawn attacks Black's queen, so Black must trade on b3 and your pawns grab space on the queenside.",
    "d4 d5 Bf4 c6 e3 Bf5 c4 e6 Nc3 Nf6 Qb3 Qb6 c5 Qxb3 axb3": "Take towards the centre. The open a-file is ready for your rook, and Stockfish rates you about +1.",
    # London: the Greek gift
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7": "More passive than ...Bd6: this bishop doesn't challenge yours, so you keep it on f4.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3": "Aim the bishop at h7, Black's weak spot once they castle.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5": "A strong outpost backed by d4. From here the knight supports a kingside attack.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3": "Reinforce e5, which Black's bishop now attacks. This knight can also jump to g5.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5": "A blunder: chasing your bishop pulls the knight away from f6, the piece that defends h7.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+": "The Greek gift. It works because the f6 knight has left, your knight can check on g5, and your queen can reach h5.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+ Kxh7 Ng5+": "Knight check, and now your queen has a clear road to h5.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+ Kxh7 Ng5+ Qxg5": "Black's best: giving up the queen for a knight. Moving the king instead gets mated.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+ Kxh7 Ng5+ Qxg5 Bxg5": "You've won the queen for a bishop and knight. Stockfish rates this about +4.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+ Kxh7 Ng5+ Kh8 Qxh5+": "Takes the knight with check. The h-file is now a highway to Black's king.",
    "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Be7 Bd3 O-O Ne5 Bd6 Ndf3 Nh5 Bxh7+ Kxh7 Ng5+ Kh8 Qxh5+ Kg8 Qh7#": "Mate: the knight on g5 guards h7, and Black's own rook blocks f8.",
    # London vs the Englund Gambit
    "d4 e5": "The Englund Gambit: Black gives up a pawn for quick development and tricks. It's objectively bad, but full of traps.",
    "d4 e5 dxe5": "Take the pawn. Your job now is to develop sensibly and not fall for a trap.",
    "d4 e5 dxe5 Nc6 Nf3": "Defends the extra pawn on e5 and develops.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7": "Black piles up on e5 and sets the famous trap.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4": "Defends e5 a second time. Now be careful about ...Qb4+.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+": "Check, and the queen also attacks b2.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2": "Block with the bishop, which attacks the queen.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2": "Black grabs b2 and threatens ...Qxa1.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2 Nc3": "The safe move. Never play 6.Bc3?? here: ...Bb4! wins, because 7.Bxb4 Nxb4 and 7.Qd2 Bxc3 8.Qxc3 Qc1# both lose for you. That is the Englund trap.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2 Nc3 Bb4 Rb1": "Hunt the queen. It's running out of squares.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2 Nc3 Bb4 Rb1 Qa3 Rb3": "Chase it again and attack the bishop on b4.",
    "d4 e5 dxe5 Nc6 Nf3 Qe7 Bf4 Qb4+ Bd2 Qxb2 Nc3 Bb4 Rb1 Qa3 Rb3 Qa5 e4": "Grab the centre. You're about +2: an extra pawn and much better development.",
    "d4 e5 dxe5 d6 exd6": "Just take: Black is gambiting a second pawn.",
    "d4 e5 dxe5 d6 exd6 Bxd6 Nf3 Nf6 Bg5": "Pins the knight and develops. Stockfish prefers 5.Nc3, but either keeps you comfortably better.",
    "d4 e5 dxe5 d6 exd6 Bxd6 Nf3 Nf6 Bg5 Nc6 e3": "Solid: open the way for your other bishop and castle. You're a pawn up.",
    "d4 e5 dxe5 f6 exf6": "Take again. Black's ...f6 weakens their own king.",
    "d4 e5 dxe5 f6 exf6 Nxf6 Nf3 d5 Bf4": "Back to London-style development, but now with an extra pawn.",
    "d4 e5 dxe5 f6 exf6 Nxf6 Nf3 d5 Bf4 Bd6 e3": "Don't fear the trade on f4: after ...Bxf4 exf4 you're still a healthy pawn up.",
    "d4 Nf6": "Develops and controls e4 without committing your d-pawn. The plan: ...g6, ...Bg7, ...d6 and castle.",
    "d4 Nf6 c4 g6": "Prepare the fianchetto. You let White build a big centre, then attack it.",
    "d4 Nf6 c4 g6 Nc3 Bg7": "The heart of the King's Indian: this bishop on the long diagonal pressures d4 and, later, White's queenside.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6": "Stops e4-e5 kicking your knight and prepares ...e5.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O": "King to safety first. The fight in the centre comes next.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5": "The key King's Indian move: challenge the centre. After dxe5 dxe5 the queens come off, but you're fine.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6": "More pressure on d4, forcing White to decide what to do with the centre.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5": "White closes the centre. Rule of thumb: attack where your pawns point, so you go for the kingside while White attacks the queenside.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7": "Out of the way of the f-pawn, and heading for the kingside where your attack will be.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7 Ne1": "White's knight heads for d3 to support c4-c5, the queenside attack.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7 Ne1 Nd7": "Clears the way for the f-pawn. Stockfish rates ...Ne8 just as good.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7 Ne1 Nd7 f3 f5": "The thematic break. Next comes ...f4, then ...g5 and ...g4 to storm White's king. This is a race: be faster than White on the queenside.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3": "The Sämisch: f3 protects e4 and prepares Be3, Qd2 and maybe a kingside pawn storm.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 c5": "Hit the centre from the side while White's kingside pieces are still at home.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 c5 Nge2 Nc6": "Pile up on d4.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 c5 Nge2 Nc6 d5": "White closes the centre and gains space.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 c5 Nge2 Nc6 d5 Ne5": "A great central square. The knight eyes c4 and f3, and White can't easily kick it.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 c5 Nge2 Nc6 d5 Ne5 Ng3 e6": "Break open the centre with ...exd5 while White's king is still in the middle.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4": "The Four Pawns Attack: White grabs as much space as possible. A big centre like this can become a target.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4 O-O Nf3 c5": "Strike before White gets organised. The d4 pawn is undermined.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4 O-O Nf3 c5 d5": "White pushes past, which leaves e5 and the long diagonal for you.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4 O-O Nf3 c5 d5 e6": "Attack the head of White's pawn chain. ...exd5 opens the e-file towards White's king.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4 O-O Nf3 c5 d5 e6 Be2 exd5": "Open the e-file.",
    "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f4 O-O Nf3 c5 d5 e6 Be2 exd5 cxd5 Re8": "Your rook hits e4. White's pawns on e4 and f4 are now targets, and ...b5 is a typical follow-up.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3": "The Fianchetto variation: White's bishop on g2 blunts yours. Expect a calm, positional game.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6": "The standard King's Indian setup, whatever White does.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nc6": "The Panno plan: ...Nc6, ...a6 and ...Rb8, then ...b5 to fight on the queenside.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nc6 Nc3 a6": "Prepares ...Rb8 and ...b5.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nc6 Nc3 a6 d5": "Kicks your knight, but it has a good square on a5.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nc6 Nc3 a6 d5 Na5": "Attacks c4. White has to spend time defending it.",
    "d4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nc6 Nc3 a6 d5 Na5 Nd2 c5": "Supports the knight and gains space. Next: ...Rb8 and ...b5.",
    "d4 Nf6 Bf4": "The London. Your King's Indian setup works well here: the g7 bishop will aim at White's queenside.",
    "black: d4 Nf6 Bf4 g6": "Same setup as always: ...Bg7, ...O-O, ...d6.",
    "black: d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3": "Gives White's bishop a retreat on h2, so ...Nh5 can't trade it off.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3 Nbd7": "Flexible: supports ...e5 later, or backs up ...c5.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3 Nbd7 O-O c5": "Strike at d4 from the side. The London's weak spot is the queenside.",
    "d4 Nf6 Bf4 g6 e3 Bg7 Nf3 O-O Be2 d6 h3 Nbd7 O-O c5 c3 b6": "Prepares ...Bb7, a second bishop on a long diagonal.",
    "d4 Nf6 Nf3": "A quiet start. Stick to your King's Indian setup.",
    "d4 Nf6 Nf3 g6 e3": "White isn't challenging you, so just finish developing.",
    "d4 Nf6 Nf3 g6 e3 Bg7 Bd3 O-O O-O d6 c4 Nbd7": "Prepares ...e5.",
    "d4 Nf6 Nf3 g6 e3 Bg7 Bd3 O-O O-O d6 c4 Nbd7 Nc3 e5": "The standard King's Indian break. You've got equal play in the centre.",
    "c4": "The English. You can still play your King's Indian setup.",
    "c4 Nf6": "Flexible: you'll aim for the same ...g6, ...Bg7, ...d6 setup.",
    "c4 Nf6 Nc3 g6 g3": "White fianchettoes too, so this stays quieter than the main lines.",
    "c4 Nf6 Nc3 g6 g3 Bg7 Bg2 O-O Nf3 d6 O-O e5": "Claim the centre, since White hasn't.",
    "c4 Nf6 Nc3 g6 g3 Bg7 Bg2 O-O Nf3 d6 O-O e5 d3 Nc6 Rb1": "White prepares b4 and b5 to attack on the queenside.",
    "c4 Nf6 Nc3 g6 g3 Bg7 Bg2 O-O Nf3 d6 O-O e5 d3 Nc6 Rb1 a5": "Slows down White's b4 push.",
    "c4 Nf6 Nc3 g6 e4": "White builds a big centre after all.",
    "c4 Nf6 Nc3 g6 e4 d6": "Stops e5. This will turn into a main King's Indian.",
    "c4 Nf6 Nc3 g6 e4 d6 d4 Bg7 Nf3 O-O Be2 e5": "You're back in the Classical King's Indian, with the same plans as there.",
    "Nf3": "A quiet start that doesn't commit White's centre pawns.",
    "Nf3 Nf6": "Mirror White and stick to your setup.",
    "Nf3 Nf6 g3 g6 Bg2 Bg7 O-O O-O d3 d6 c4 e5": "Claim the centre, since White is playing slowly.",
    "Nf3 Nf6 g3 g6 Bg2 Bg7 O-O O-O d3 d6 c4 e5 Nc3 Nc6": "Natural development. You have a comfortable, equal position.",
    "e4 e5 Nc3": "The Vienna: develop the knight but keep the f-pawn free to push to f4, like a better-prepared King's Gambit.",
    "e4 e5 Nc3 Nc6": "Black defends e5 and keeps options open.",
    "e4 e5 Nc3 Nc6 Bc4": "Aims at f7, Black's weakest square. d3 and often f4 come next.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3": "Protects e4, so ...Nxe4 tricks don't work, and frees your other bishop.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Bc5": "Both sides' bishops aim at the other's f-pawn.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Bc5 f4": "The Vienna idea: open the f-file. Stockfish prefers the quieter 5.Nf3 and rates this slightly better for Black.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Bc5 f4 d6 Nf3": "Develop, add pressure on e5 and get ready to castle.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Na5": "Black wants to trade off your c4 bishop.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Na5 Nge2": "Develop and keep the f-pawn free. Let Black take the bishop.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Na5 Nge2 Nxc4 dxc4": "Recapture. The d-file is now open for your queen.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Na5 Nge2 Nxc4 dxc4 Bc5 O-O": "Get the king out of the centre.",
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Na5 Nge2 Nxc4 dxc4 Bc5 O-O d6 Bg5": "Pin the knight. Stockfish rates it equal, with Qd3 an alternative.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5": "Copycat: both bishops eye the f-pawns.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5 Qg4": "Hits g7, and with your bishop on c4 the f7 square too. Stockfish rates 4.Qh5 about the same.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5 Qg4 g6": "Defends g7 but weakens the dark squares around Black's king.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5 Qg4 g6 Qf3": "Now you threaten Qxf7 mate! Black must block with ...Nf6 or ...Qf6.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5 Qg4 g6 Qf3 Nf6 Nge2": "Develop and keep f3 for the queen.",
    "e4 e5 Nc3 Nc6 Bc4 Bc5 Qg4 g6 Qf3 Nf6 Nge2 d6 d3": "Solid: you're slightly better thanks to the active bishop on c4.",
    "e4 e5 Nc3 Bc5": "The bishop eyes f2.",
    "e4 e5 Nc3 Bc5 Nf3": "Attack e5 and develop.",
    "e4 e5 Nc3 Bc5 Nf3 d6 d4": "Strike the centre, gaining time on the c5 bishop.",
    "e4 e5 Nc3 Bc5 Nf3 d6 d4 exd4 Nxd4": "Recapture. Your knight sits strongly in the centre.",
    "e4 e5 Nc3 Bc5 Nf3 d6 d4 exd4 Nxd4 Nf6 Be2": "Prepare to castle. Stockfish slightly prefers 6.Bg5, pinning the knight.",
    "e4 e5 Nc3 Bc5 Nf3 d6 d4 exd4 Nxd4 Nf6 Be2 O-O O-O": "Both sides are developed, and you have more space in the centre.",
    "e4 e5 Nc3 Nf6": "Black attacks e4. This is where your gambit comes in.",
    "e4 e5 Nc3 Nf6 f4": "The Vienna Gambit: offer the f-pawn to rip open the centre and the f-file.",
    "e4 e5 Nc3 Nf6 f4 exf4": "Black takes, but now e5 kicks the knight.",
    "e4 e5 Nc3 Nf6 f4 exf4 e5": "Push with tempo: the knight has to move, usually back to g8.",
    "e4 e5 Nc3 Nf6 f4 exf4 e5 Ng8 Nf3": "Develop, cover h4 so ...Qh4+ is impossible, and prepare d4.",
    "e4 e5 Nc3 Nf6 f4 exf4 e5 Ng8 Nf3 d6 d4": "Grab the centre. You'll win back the f4 pawn later.",
    "e4 e5 Nc3 Nf6 f4 exf4 e5 Ng8 Nf3 d6 d4 dxe5 Qe2": "Pins Black's e5 pawn to the king, so it can't take on d4.",
    "e4 e5 Nc3 Nf6 f4 exf4 e5 Ng8 Nf3 d6 d4 dxe5 Qe2 Be7 dxe5": "Win back the pawn. Stockfish prefers 8.Qxe5, but either way you have the centre.",
    "e4 e5 Nc3 Nf6 f4 d5": "The main line: Black hits back in the centre instead of taking.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5": "Take. Your pawn on e5 cramps Black, and the f-file is open.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3": "Develop and stop ...Qh4+.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7 d4": "Build the centre. Stockfish rates d3 and d4 about the same.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7 d4 O-O Bd3": "Challenge the strong knight on e4.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7 d4 O-O Bd3 f5": "Black supports the knight.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7 d4 O-O Bd3 f5 exf6": "Take en passant, opening lines.",
    "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7 d4 O-O Bd3 f5 exf6 Bxf6 O-O": "Castle, and your rook joins in on the half-open f-file. Roughly equal.",
    "e4 e5 Nc3 Nf6 f4 d6": "Solid: Black supports e5.",
    "e4 e5 Nc3 Nf6 f4 d6 Nf3": "Develop and add pressure on e5.",
    "e4 e5 Nc3 Nf6 f4 d6 Nf3 Nc6 Bb5": "Pin the knight that defends e5.",
    "e4 e5 Nc3 Nf6 f4 d6 Nf3 Nc6 Bb5 Bd7 d3": "Solid. You're slightly better with more space.",
    "e4 e5 Nc3 Nf6 f4 Nc6": "A mistake: you can win space with fxe5, and Stockfish rates you about +1.5.",
    "e4 e5 Nc3 Nf6 f4 Nc6 fxe5": "Take, and the f6 knight is attacked.",
    "e4 e5 Nc3 Nf6 f4 Nc6 fxe5 Nxe5 d4": "Kick the knight with tempo and build a big centre.",
    "e4 e5 Nc3 Nf6 f4 Nc6 fxe5 Nxe5 d4 Ng6 e5": "Again with tempo: the f6 knight has to run back to g8.",
    "e4 e5 Nc3 Nf6 f4 Nc6 fxe5 Nxe5 d4 Ng6 e5 Ng8 Nf3 d6 Bc4": "Develop towards f7. You're clearly better.",
}
NOTES_TO_CHECK = {
    "e4 e5 Nc3 Nc6 Bc4 Nf6 d3 Bc5 f4",
    "e4 e5 Nc3 Nf6 f4 exf4 e5 Ng8 Nf3 d6 d4 dxe5 Qe2 Be7 dxe5",
    "d4 d5 Bf4 Nf6 e3 Bf5 c4 e6 Nc3 Bb4 Qb3",
    "d4 d5 Bf4 c5 e3 Nc6 c3 Qb6 Qb3 c4 Qc2 Nf6 Nd2 Bg4 Ngf3",
}


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
        path = " ".join(_sans(line["moves"])[:index + 1])
        path = next((k for k in (f"{opening['colour']}: {path}", path) if k in NOTES), None)
        if path:
            ply["note"] = NOTES[path]
            ply["check"] = path in NOTES_TO_CHECK
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
