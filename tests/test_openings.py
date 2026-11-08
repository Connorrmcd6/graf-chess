import chess

from collector import openings


def test_every_line_replays_legally_and_marks_your_moves():
    book = openings.repertoire()
    ids = [o["id"] for o in book] + [ln["id"] for o in book for ln in o["lines"]]
    assert len(ids) == len(set(ids))
    for o, src in zip(book, openings.REPERTOIRE):
        assert o["colour"] in ("white", "black") and len(o["lines"]) >= 3
        for ln in o["lines"]:
            board = chess.Board()
            for index, ply in enumerate(ln["plies"]):
                assert ply["fen"] == board.fen()
                mine = ply["mover"] == o["colour"]
                assert ("legal" in ply) == mine and ("key" in ply) == (mine and index >= src["tabiya"])
                if mine:
                    assert ply["legal"][ply["uci"]] == ply["san"]
                board.push_uci(ply["uci"])
            assert ln["end_fen"] == board.fen() and ln["plies"][-1]["mover"] == o["colour"]


def test_move_text_numbers_white_moves_only():
    o = {"colour": "black", "tabiya": 1}
    line = openings.compile_line(o, {"id": "x", "name": "x", "moves": "1.e4 d6 2.d4 Nf6"})
    assert line["moves"] == "1.e4 d6 2.d4 Nf6" and line["plies"][1]["label"] == "1…d6"


def test_bad_move_fails_loudly():
    try:
        openings.compile_line({"colour": "white", "tabiya": 0}, {"id": "bad", "name": "", "moves": "1.e4 e5 2.Ke3"})
    except ValueError as e:
        assert "bad" in str(e) and "Ke3" in str(e)
    else:
        raise AssertionError("illegal move accepted")


def test_stats_find_your_usual_slip():
    pirc = next(o for o in openings.repertoire() if o["id"] == "pirc")
    first, second = [p for p in pirc["lines"][0]["plies"] if "key" in p][:2]
    rows = {"black": [
        {"position_key": first["key"], "game_id": "g1", "san": "d6", "win_loss": 0},
        {"position_key": first["key"], "game_id": "g2", "san": "e5", "win_loss": 3},
        {"position_key": first["key"], "game_id": "g3", "san": "e5", "win_loss": 5},
        {"position_key": second["key"], "game_id": "g1", "san": "Nf6", "win_loss": 1},
    ]}
    s = openings.stats(lambda colour, keys: [r for r in rows.get(colour, []) if r["position_key"] in keys])
    assert s["positions"][first["key"]]["moves"][0] == {"san": "e5", "games": 2, "avg_loss": 4.0}
    # 1...d6 and 2...Nf6 are on every Pirc line, so slips there belong to the opening, not a line.
    assert s["openings"]["pirc"] == {"games": 1, "slip": {"label": "1…d6", "book": "d6", "san": "e5", "times": 2}}
    assert s["openings"]["london"] == {"games": 0, "slip": None}
    assert s["lines"]["pirc-austrian"] == {"games": 0, "deepest": "2…Nf6", "slip": None}
