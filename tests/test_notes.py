from __future__ import annotations

import os

import papis.config
import papis.database
from papis.notes import (
    dump_frontmatter,
    parse_frontmatter,
    update_notes_frontmatter,
)
from papis.testing import PapisRunner, TemporaryLibrary


def test_parse_frontmatter_with_frontmatter() -> None:
    content = "---\ntitle: Test\ntags:\n- a\n- b\n---\nBody text here.\n"
    metadata, body = parse_frontmatter(content)
    assert metadata == {"title": "Test", "tags": ["a", "b"]}
    assert body == "Body text here.\n"


def test_parse_frontmatter_without_frontmatter() -> None:
    content = "Just some plain notes.\nNo frontmatter.\n"
    metadata, body = parse_frontmatter(content)
    assert metadata == {}
    assert body == content


def test_parse_frontmatter_empty() -> None:
    metadata, body = parse_frontmatter("")
    assert metadata == {}
    assert body == ""


def test_parse_frontmatter_empty_frontmatter() -> None:
    content = "---\n---\nBody after empty frontmatter.\n"
    metadata, body = parse_frontmatter(content)
    # Empty YAML parses as None, so we return {} and treat it as no frontmatter
    assert metadata == {}
    assert body == content


def test_parse_frontmatter_preserves_extra_keys() -> None:
    content = "---\ntitle: Test\ncustom_key: custom_value\n---\nBody.\n"
    metadata, body = parse_frontmatter(content)
    assert metadata["title"] == "Test"
    assert metadata["custom_key"] == "custom_value"
    assert body == "Body.\n"


def test_dump_frontmatter() -> None:
    metadata = {"title": "My Title", "tags": ["physics", "quantum"]}
    body = "Some notes content.\n"
    result = dump_frontmatter(metadata, body)
    assert result.startswith("---\n")
    assert "---\n" in result[4:]
    assert result.endswith("Some notes content.\n")
    assert "title: My Title" in result
    # Re-parse to verify round-trip
    parsed_meta, parsed_body = parse_frontmatter(result)
    assert parsed_meta == metadata
    assert parsed_body == body


def test_dump_frontmatter_empty_metadata() -> None:
    body = "Just the body.\n"
    result = dump_frontmatter({}, body)
    assert result == body


def test_update_notes_frontmatter_disabled(tmp_library: TemporaryLibrary) -> None:
    papis.config.set("notes-frontmatter-sync", "False")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    # Create a notes file
    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("Some notes.\n")

    result = update_notes_frontmatter(doc)
    assert result is False

    with open(notespath, encoding="utf-8") as fd:
        assert fd.read() == "Some notes.\n"


def test_update_notes_frontmatter_no_notes(tmp_library: TemporaryLibrary) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "doc without files"})
    # Ensure no notes key
    doc.pop("notes", None)

    result = update_notes_frontmatter(doc)
    assert result is False


def test_update_notes_frontmatter_no_file(tmp_library: TemporaryLibrary) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})
    doc["notes"] = "nonexistent.md"

    result = update_notes_frontmatter(doc)
    assert result is False


def test_update_notes_frontmatter_basic(tmp_library: TemporaryLibrary) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("My research notes.\n")

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, body = parse_frontmatter(content)
    assert metadata["title"] == doc["title"]
    assert metadata["author"] == doc["author"]
    assert metadata["year"] == doc["year"]
    assert metadata["tags"] == doc["tags"]
    assert body == "My research notes.\n"


def test_update_notes_frontmatter_preserves_extra_keys(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("---\ncustom_key: my_value\nstatus: draft\n---\nBody.\n")

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, body = parse_frontmatter(content)
    # Synced keys are present
    assert metadata["title"] == doc["title"]
    assert metadata["tags"] == doc["tags"]
    # User's extra keys are preserved
    assert metadata["custom_key"] == "my_value"
    assert metadata["status"] == "draft"
    assert body == "Body.\n"


def test_update_notes_frontmatter_updates_existing(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    # Write initial frontmatter with old tags
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("---\ntags:\n- old_tag\ntitle: Old Title\n---\nNotes.\n")

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, body = parse_frontmatter(content)
    assert metadata["tags"] == doc["tags"]
    assert metadata["title"] == doc["title"]
    assert body == "Notes.\n"


def test_update_notes_frontmatter_preserves_body(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    body_text = "# Chapter 1\n\nSome detailed notes.\n\n## Section A\n\nMore text.\n"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write(body_text)

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    _, body = parse_frontmatter(content)
    assert body == body_text


def test_update_notes_frontmatter_no_change(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("Notes.\n")

    # First sync
    update_notes_frontmatter(doc)

    with open(notespath, encoding="utf-8") as fd:
        content_after_first = fd.read()

    # Second sync should be a no-op
    result = update_notes_frontmatter(doc)
    assert result is False

    with open(notespath, encoding="utf-8") as fd:
        content_after_second = fd.read()

    assert content_after_first == content_after_second


def test_update_notes_frontmatter_custom_keys(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")
    papis.config.set("notes-frontmatter-keys", '["tags", "year"]')

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("Notes.\n")

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, _ = parse_frontmatter(content)
    # Only the configured keys should be synced
    assert "tags" in metadata
    assert "year" in metadata
    assert "title" not in metadata
    assert "author" not in metadata


def test_tag_command_triggers_sync(tmp_library: TemporaryLibrary) -> None:
    from papis.commands.tag import cli

    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("---\ntags:\n- old\n---\nNotes.\n")

    from papis.api import save_doc
    save_doc(doc)

    cli_runner = PapisRunner()
    result = cli_runner.invoke(
        cli, ["--add", "newtag", "--all", "krishnamurti"])
    assert result.exit_code == 0

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, body = parse_frontmatter(content)
    assert "newtag" in metadata["tags"]
    assert body == "Notes.\n"


def test_update_notes_frontmatter_removes_cleared_key(
    tmp_library: TemporaryLibrary,
) -> None:
    papis.config.set("notes-frontmatter-sync", "True")

    db = papis.database.get()
    (doc,) = db.query_dict({"author": "Krishnamurti"})

    notespath = os.path.join(doc.get_main_folder() or "", "notes.md")
    doc["notes"] = "notes.md"
    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write("---\nref: old_ref\n---\nNotes.\n")

    # doc does not have 'ref' key, so it should be removed from frontmatter
    doc.pop("ref", None)

    result = update_notes_frontmatter(doc)
    assert result is True

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, _ = parse_frontmatter(content)
    assert "ref" not in metadata
