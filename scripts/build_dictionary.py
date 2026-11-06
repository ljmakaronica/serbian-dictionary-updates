#!/usr/bin/env python3
"""Build the bundled SQLite dictionary and the identical remote JSON snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("cyrillic", "latin", "english")
FIELDS = ("word", "part_of_speech", "definition", "example_sentence")
SUFFIXES = ("word", "part", "def", "example")


def read_content(source):
    entries, hashes = [], {}
    for path in sorted((source / "entries").glob("*.json")):
        raw = path.read_bytes()
        entry = json.loads(raw)
        identifier = entry["id"]
        if type(identifier) is not int or not 0 < identifier <= 2**63 - 1:
            raise ValueError(f"{path.name}: invalid ID")
        if str(identifier) in hashes:
            raise ValueError(f"Duplicate ID {identifier}")
        for language in LANGUAGES:
            for field in FIELDS:
                value = entry["translation"][language][field]
                if not isinstance(value, str) or not value.strip() or "\0" in value:
                    raise ValueError(f"{identifier}: missing/invalid {language}.{field}")
                if value != value.strip() or value != unicodedata.normalize("NFC", value):
                    raise ValueError(f"{identifier}: normalize {language}.{field}")
                if len(value.encode()) > 16_384:
                    raise ValueError(f"{identifier}: field too large")
                for char in value:
                    script = unicodedata.name(char, "")
                    if language == "cyrillic" and "LATIN" in script:
                        raise ValueError(f"{identifier}: Latin letter in Cyrillic {field}")
                    if language == "latin" and "CYRILLIC" in script:
                        raise ValueError(f"{identifier}: Cyrillic letter in Latin {field}")
        hashes[str(identifier)] = hashlib.sha256(raw).hexdigest()
        entries.append(entry)
    if not 1 <= len(entries) <= 50_000:
        raise ValueError("Invalid entry count")
    return entries, hashes


def build(source, output, seed=None, release=False, snapshot_url=None):
    entries, hashes = read_content(source)
    review = json.loads((source / "review.json").read_text())
    revision = review["revision"]
    if type(revision) is not int or revision < 1:
        raise ValueError("Revision must be a positive integer")
    approvals = review.get("approvedEntries", {})
    pending = [key for key, digest in hashes.items() if approvals.get(key) != digest]
    baseline_path = source / "launch-baseline.json"
    baseline = json.loads(baseline_path.read_text()).get("entryHashes", {}) if baseline_path.exists() else {}
    blocked = [key for key in pending if baseline.get(key) != hashes[key]]
    if release and blocked:
        raise ValueError(f"Publication blocked: {len(blocked)} changed/new entries need editorial approval")
    if release and not snapshot_url:
        raise ValueError("A release requires its immutable --snapshot-url")
    snapshot = {"schemaVersion": 1, "revision": revision, "entries": entries}
    data = (json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(data) > 8_000_000:
        raise ValueError("Snapshot exceeds the app download limit")
    output.mkdir(parents=True, exist_ok=True)
    (output / "dictionary.json").write_bytes(data)
    (output / "review-status.json").write_text(json.dumps({
        "pendingEntryIDs": pending, "currentEntryHashes": hashes,
        "publicationBlockedEntryIDs": blocked
    }, indent=2) + "\n")
    if snapshot_url:
        if not snapshot_url.startswith("https://"):
            raise ValueError("Snapshot URL must use HTTPS")
        manifest = {"schemaVersion": 1, "revision": revision, "snapshotURL": snapshot_url,
                    "byteCount": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "entryCount": len(entries)}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if seed:
        seed.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=seed.parent, suffix=".db")
        os.close(handle)
        try:
            with sqlite3.connect(temporary) as connection:
                columns = [f"{language}_{suffix}" for language in LANGUAGES for suffix in SUFFIXES]
                connection.execute("CREATE TABLE words (id INTEGER PRIMARY KEY," +
                                   ",".join(f"{column} TEXT NOT NULL" for column in columns) + ")")
                connection.execute("CREATE TABLE dictionary_metadata (singleton INTEGER PRIMARY KEY CHECK(singleton = 1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL)")
                for entry in entries:
                    values = [entry["id"]] + [entry["translation"][language][field]
                                              for language in LANGUAGES for field in FIELDS]
                    connection.execute("INSERT INTO words VALUES (" + ",".join("?" * 13) + ")", values)
                connection.execute("INSERT INTO dictionary_metadata VALUES (1, 1, ?)", (revision,))
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            os.replace(temporary, seed)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return len(entries), len(pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "dictionary-content")
    parser.add_argument("--output", type=Path, default=ROOT / "build/dictionary")
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--snapshot-url")
    args = parser.parse_args()
    count, pending = build(args.source, args.output, args.seed, args.release, args.snapshot_url)
    print(f"Built {count} entries; {pending} still need editorial approval.")
