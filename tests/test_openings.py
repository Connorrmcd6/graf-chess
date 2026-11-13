import chess

from collector import openings


def test_every_line_replays_legally_and_marks_your_moves():
    book = openings.repertoire()
    ids = [o["id"] for o in book] + [ln["id"] for o in book for ln in o["lines"]]
    assert len(ids) == len(set(ids))
    for o, src in zip(book, openings.REPERTOIRE):
        assert o["colour"] in ("white", "black") and len(o["lines"]) >= (2 if o["fun"] else 3)
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
        {"position_key": first["key"], "game_id": "g4", "san": "c6", "win_loss": 0},
        {"position_key": first["key"], "game_id": "g5", "san": "c6", "win_loss": 0},
        {"position_key": first["key"], "game_id": "g6", "san": "c6", "win_loss": 0},
        {"position_key": second["key"], "game_id": "g1", "san": "Nf6", "win_loss": 1},
    ]}
    s = openings.stats(lambda colour, keys: [r for r in rows.get(colour, []) if r["position_key"] in keys])
    assert {"san": "e5", "games": 2, "avg_loss": 4.0} in s["positions"][first["key"]]["moves"]
    # 1...d6 and 2...Nf6 are on every Pirc line, so slips there belong to the opening, not a line.
    # 1...c6 is the Caro-Kann, also your repertoire, so it is never a Pirc slip however often you play it.
    assert s["openings"]["pirc"] == {"games": 1, "slip": {"label": "1…d6", "book": "d6", "san": "e5", "times": 2}}
    assert s["openings"]["london"] == {"games": 0, "slip": None}
    assert s["lines"]["pirc-austrian"] == {"games": 0, "deepest": "2…Nf6", "slip": None}


def test_london_meets_the_englund_and_the_icbm_wins_the_queen():
    book = {o["id"]: o for o in openings.repertoire()}
    assert any(ln["moves"].startswith("1.d4 e5") for ln in book["london"]["lines"])
    assert book["fun"]["fun"] and not book["london"]["fun"]
    icbm = next(ln for ln in book["fun"]["lines"] if ln["id"] == "fun-icbm")
    board = chess.Board(icbm["end_fen"])
    assert not board.pieces(chess.QUEEN, chess.BLACK) and board.pieces(chess.QUEEN, chess.WHITE)


def test_repertoire_changes_and_previews():
    book = {o["id"]: o for o in openings.repertoire()}
    assert "kid-flank" not in book
    replies = {o["lines"][0]["plies"][1]["san"] for o in book.values() if o["colour"] == "white" and not o["fun"]}
    assert {"e5", "c5", "e6", "c6", "d5", "d6"} <= replies
    assert {"flank-english", "flank-reti"} <= {ln["id"] for ln in book["kid"]["lines"]}
    assert book["dutch"]["colour"] == "black" and all(ln["moves"].startswith("1.d4 f5") for ln in book["dutch"]["lines"])
    assert len(book["caro"]["lines"]) >= 8
    assert book["caro"]["preview"] == chess.Board("rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2").fen()
    for o in book.values():
        chess.Board(o["preview"])


def test_one_move_of_yours_per_position():
    """Black picks a defence on move one; after that the repertoire never has two answers to the same position."""
    seen = {}
    for o in openings.repertoire():
        if o["fun"]:
            continue
        for ln in o["lines"]:
            for index, p in enumerate(ln["plies"]):
                if "key" in p and index > 1:
                    first = seen.setdefault(p["key"], (p["san"], ln["id"]))
                    assert first[0] == p["san"], f"{p['label']} in {ln['id']} but {first[0]} in {first[1]}"


def test_every_note_belongs_to_a_line():
    paths = {" ".join(openings._sans(ln["moves"])[:k]) for o in openings.REPERTOIRE for ln in o["lines"]
             for k in range(1, len(openings._sans(ln["moves"])) + 1)}
    assert set(openings.NOTES) <= paths, set(openings.NOTES) - paths
    assert openings.NOTES_TO_CHECK <= set(openings.NOTES)
    london = next(o for o in openings.repertoire() if o["id"] == "london")
    assert all(any("note" in p for p in ln["plies"] if p["mover"] == "white") for ln in london["lines"])
