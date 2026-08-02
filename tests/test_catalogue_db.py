"""Unit tests for the SQLite catalogue store-of-record (catalogue_db.py)."""
import json

from podcast_catalogue.catalogue_db import CatalogueDB


def test_roundtrip_upsert_and_get(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("Science Hour", {"title": "Science Hour", "primaryGenre": "Science"})
    got = db.get_show("science hour")  # case-insensitive key
    assert got["title"] == "Science Hour"
    assert got["primaryGenre"] == "Science"
    assert db.count() == 1


def test_upsert_replaces(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("S", {"title": "S", "v": 1})
    db.upsert_show("S", {"title": "S", "v": 2})
    assert db.count() == 1
    assert db.get_show("s")["v"] == 2


def test_replace_all_atomic_and_complete(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("Old", {"title": "Old"})
    shows = {"a": {"title": "A"}, "b": {"title": "B"}}
    db.replace_all(shows)
    titles = sorted(s["title"] for s in db.all_shows())
    assert titles == ["A", "B"]  # Old gone, both new present
    assert db.get_show("old") is None


def test_replace_all_rolls_back_on_error(tmp_path):
    """A mid-write failure must leave the prior state intact (the data-safety cure)."""
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("Keep", {"title": "Keep"})

    class Unserializable:
        pass

    # One row's data can't be JSON-encoded -> the whole replace_all must abort.
    bad = {"a": {"title": "A"}, "b": {"title": "B", "x": Unserializable()}}
    try:
        db.replace_all(bad)
    except TypeError:
        pass
    # Original catalogue untouched, no partial write of "A".
    assert db.count() == 1
    assert db.get_show("keep") is not None
    assert db.get_show("a") is None


def test_delete_show(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("X", {"title": "X"})
    db.delete_show("x")
    assert db.count() == 0


def test_meta_and_empty(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    assert db.is_empty()
    db.set_meta("source", "universe.jsonl")
    assert db.get_meta("source") == "universe.jsonl"
    assert db.is_empty()  # meta doesn't count as catalogue content


def test_persists_across_connections(tmp_path):
    path = str(tmp_path / "cat.db")
    db = CatalogueDB(path)
    db.upsert_show("Persist", {"title": "Persist"})
    db.close()
    db2 = CatalogueDB(path)
    assert db2.get_show("persist")["title"] == "Persist"


def test_unicode_preserved(tmp_path):
    db = CatalogueDB(str(tmp_path / "cat.db"))
    db.upsert_show("Café", {"title": "Café", "desc": "naïve résumé — 日本語"})
    assert db.get_show("café")["desc"] == "naïve résumé — 日本語"
