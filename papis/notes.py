"""
This module controls the notes for every Papis document.
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

import papis.config
import papis.logging

if TYPE_CHECKING:
    from papis.document import Document

logger = papis.logging.get_logger(__name__)

#: Regex to match YAML frontmatter delimited by ``---`` at the start of a file.
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\n(.*?\n)---[ \t]*\n?",
    re.DOTALL,
)


def has_notes(doc: Document) -> bool:
    """Checks if the document has notes."""
    return "notes" in doc


def notes_path(doc: Document) -> str:
    """Get the path to the notes file corresponding to *doc*.

    If the document does not have attached notes, a filename is constructed (using
    the :confval:`notes-name` setting) in the document's main folder.

    :returns: a absolute filename that corresponds to the attached notes for
        *doc* (this file does not necessarily exist).
    """
    if not has_notes(doc):
        from papis.format import format
        notes_name = format(
            papis.config.getformatpattern("notes-name"), doc,
            default="notes.tex")

        from papis.paths import normalize_path
        doc["notes"] = normalize_path(notes_name)

        from papis.api import save_doc
        save_doc(doc)

    return os.path.join(doc.get_main_folder() or "", doc["notes"])


def notes_path_ensured(doc: Document) -> str:
    """Get the path to the notes file corresponding to *doc* or create it if
    it does not exist.

    If the notes do not exist, a new file is created using :func:`notes_path`
    and filled with the contents of the template given by the
    :confval:`notes-template` configuration option.

    :returns: an absolute filename that corresponds to the attached notes for *doc*.
    """
    notespath = notes_path(doc)

    if not os.path.exists(notespath):
        templatepath = os.path.expanduser(papis.config.getstring("notes-template"))

        template = ""
        if os.path.exists(templatepath):
            from papis.format import FormatFailedError, format

            with open(templatepath, encoding="utf-8") as fd:
                try:
                    template = format(fd.read(), doc)
                except FormatFailedError as exc:
                    logger.error("Failed to format notes template at '%s'.",
                                 templatepath, exc_info=exc)

        with open(notespath, "w+", encoding="utf-8") as fd:
            fd.write(template)

    return notespath


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from note file content.

    Frontmatter is expected at the very start of the file, delimited by ``---``.

    :param content: the full text content of a note file.
    :returns: a tuple ``(metadata, body)`` where *metadata* is a dict of the
        parsed YAML frontmatter (empty dict if none found) and *body* is the
        remaining content after the frontmatter block.
    """
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return {}, content

    import yaml

    try:
        from papis.yaml import Loader
        metadata = yaml.load(match.group(1), Loader=Loader)
    except Exception as exc:
        logger.warning("Failed to parse YAML frontmatter in notes file.",
                       exc_info=exc)
        return {}, content

    if not isinstance(metadata, dict):
        return {}, content

    body = content[match.end():]
    return metadata, body


def dump_frontmatter(metadata: dict[str, Any], body: str) -> str:
    """Serialize a metadata dict as YAML frontmatter prepended to *body*.

    :param metadata: dict of key-value pairs to write as YAML frontmatter.
    :param body: the note body content to append after the frontmatter block.
    :returns: the combined string with ``---`` delimited frontmatter followed
        by the body.
    """
    if not metadata:
        return body

    import yaml

    from papis.yaml import Dumper

    fm = yaml.dump(metadata,
                   Dumper=Dumper,
                   allow_unicode=True,
                   default_flow_style=False)
    return f"---\n{fm}---\n{body}"


def get_frontmatter_update(doc: Document,
                           metadata: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Compute the synced frontmatter for the notes of *doc*.

    This applies the :confval:`notes-frontmatter-keys` (including any
    ``frontmatter_key=document_key`` mappings) and the
    :confval:`notes-frontmatter-tag-prefix` to the existing frontmatter
    *metadata* without modifying it.

    :param metadata: the current frontmatter of the notes file for *doc*.
    :returns: a tuple ``(new_metadata, changed)`` of the updated frontmatter
        and a flag denoting whether it differs from *metadata*.
    """
    keys = papis.config.getlist("notes-frontmatter-keys")
    tag_prefix = papis.config.getstring("notes-frontmatter-tag-prefix")

    new_metadata = dict(metadata)

    changed = False
    for key in keys:
        fm_key, _, doc_key = key.partition("=")
        doc_key = doc_key or fm_key

        value = doc.get(doc_key)
        if doc_key == "tags" and tag_prefix and isinstance(value, list):
            value = [f"{tag_prefix}{tag}" for tag in value]

        if value is not None:
            if new_metadata.get(fm_key) != value:
                new_metadata[fm_key] = value
                changed = True
        elif fm_key in new_metadata:
            del new_metadata[fm_key]
            changed = True

    return new_metadata, changed


def update_notes_frontmatter(doc: Document) -> bool:
    """Sync document metadata into the YAML frontmatter of its notes file.

    Only the keys listed in :confval:`notes-frontmatter-keys` are written into
    the frontmatter. Any other keys already present in the frontmatter are
    preserved. The sync is gated behind the :confval:`notes-frontmatter-sync`
    configuration option.

    Entries in :confval:`notes-frontmatter-keys` of the form
    ``frontmatter_key=document_key`` write the value of *document_key* under
    *frontmatter_key* (e.g. ``id=ref`` mirrors the document reference into an
    ``id`` frontmatter key). Tag values (taken from the ``tags`` document key)
    are prefixed with :confval:`notes-frontmatter-tag-prefix` when written.

    :param doc: the document whose notes should be updated.
    :returns: *True* if the notes file was modified, *False* otherwise.
    """
    if not papis.config.getboolean("notes-frontmatter-sync"):
        return False

    if not has_notes(doc):
        return False

    notespath = os.path.join(doc.get_main_folder() or "", doc["notes"])
    if not os.path.exists(notespath):
        return False

    keys = papis.config.getlist("notes-frontmatter-keys")
    if not keys:
        return False

    with open(notespath, encoding="utf-8") as fd:
        content = fd.read()

    metadata, body = parse_frontmatter(content)
    metadata, changed = get_frontmatter_update(doc, metadata)

    if not changed:
        return False

    new_content = dump_frontmatter(metadata, body)

    with open(notespath, "w", encoding="utf-8") as fd:
        fd.write(new_content)

    logger.debug("Updated frontmatter in notes file '%s'.", notespath)
    return True
