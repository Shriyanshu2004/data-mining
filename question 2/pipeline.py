from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import importlib
import json
import sqlite3
import time
from pathlib import Path

from dedupe_core import MinHasher, content_tokens, corpus_stopwords, lsh_buckets, shingles


PERMUTATIONS = 256
BANDS = 64
ROWS = 4
MATCH_THRESHOLD = 0.72


def load_notices(data_dir: Path) -> list[dict[str, str]]:
    notice_dir = data_dir / "notices"
    csv_paths = sorted(glob.glob(str(notice_dir / "*.csv")))
    parquet_paths = sorted(glob.glob(str(notice_dir / "*.parquet")))
    if parquet_paths:
        try:
            parquet = importlib.import_module("pyarrow.parquet")
        except ImportError as error:
            raise RuntimeError("Parquet input requires pyarrow; install it before running the pipeline") from error
        rows = [row for path in parquet_paths for row in parquet.read_table(path).to_pylist()]
    else:
        rows = []
        for path in csv_paths:
            with open(path, newline="", encoding="utf-8") as handle:
                rows.extend(csv.DictReader(handle))
    for row in rows:
        if "notice_id" not in row and "notice_is" in row:
            row["notice_id"] = row.pop("notice_is")
        if "estimated_value" not in row and "estimates_value" in row:
            row["estimated_value"] = row.pop("estimates_value")
    if not rows:
        raise FileNotFoundError(f"No notice CSV or Parquet files found under {notice_dir}")
    return rows


def stable_card_id(member_ids: list[str]) -> str:
    payload = "\n".join(sorted(member_ids)).encode("utf-8")
    return "CARD-" + hashlib.sha256(payload).hexdigest()[:24]


class UnionFind:
    def __init__(self, ids: list[str]):
        self.parent = {item: item for item in ids}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS notice (
            notice_id TEXT PRIMARY KEY,
            portal_id TEXT NOT NULL,
            published_at TEXT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            estimated_value INTEGER,
            closing_date TEXT,
            signature BLOB NOT NULL,
            card_id TEXT
        );
        CREATE TABLE IF NOT EXISTS lsh_bucket (
            band INTEGER NOT NULL,
            bucket TEXT NOT NULL,
            notice_id TEXT NOT NULL REFERENCES notice(notice_id),
            PRIMARY KEY (band, bucket, notice_id)
        );
        CREATE TABLE IF NOT EXISTS card_alias (
            old_card_id TEXT PRIMARY KEY,
            current_card_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS lsh_bucket_lookup ON lsh_bucket(band, bucket);
        CREATE INDEX IF NOT EXISTS notice_card_lookup ON notice(card_id);
        """
    )


def encode_signature(signature: tuple[int, ...]) -> bytes:
    return b"".join(value.to_bytes(8, "big") for value in signature)


def run(data_dir: Path, output: Path) -> dict[str, object]:
    notices = load_notices(data_dir)
    published_by_id = {row["notice_id"]: row["published_at"] for row in notices}
    portal_by_id = {row["notice_id"]: row["portal_id"] for row in notices}
    stopwords = corpus_stopwords((row["title"], row["body"]) for row in notices)
    hasher = MinHasher(PERMUTATIONS)
    signatures: dict[str, tuple[int, ...]] = {}
    feature_sets: dict[str, set[str]] = {}
    for row in notices:
        tokens = content_tokens(row["title"], row["body"], stopwords)
        features = shingles(tokens, 5)
        feature_sets[row["notice_id"]] = features
        signatures[row["notice_id"]] = hasher.signature(features)

    connection = sqlite3.connect(output)
    previous_cards = {}
    if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notice'").fetchone():
        previous_cards = dict(connection.execute("SELECT notice_id, card_id FROM notice WHERE card_id IS NOT NULL"))
    create_schema(connection)
    connection.execute("DELETE FROM lsh_bucket")
    connection.execute("DELETE FROM notice")
    connection.executemany(
        "INSERT INTO notice VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [
            (
                row["notice_id"], row["portal_id"], row["published_at"], row["title"],
                row["body"], int(row["estimated_value"] or 0), row["closing_date"],
                encode_signature(signatures[row["notice_id"]]),
            )
            for row in notices
        ],
    )
    bucket_rows = []
    for notice_id, signature in signatures.items():
        bucket_rows.extend((band, bucket, notice_id) for band, bucket in lsh_buckets(signature, BANDS, ROWS))
    connection.executemany("INSERT INTO lsh_bucket VALUES (?, ?, ?)", bucket_rows)
    connection.commit()

    union_find = UnionFind([row["notice_id"] for row in notices])
    candidate_counts = []
    portal_counts: dict[str, list[int]] = {}
    compared = 0
    started = time.perf_counter()
    for notice_id, signature in signatures.items():
        candidate_ids = {
            candidate
            for band, bucket in lsh_buckets(signature, BANDS, ROWS)
            for (candidate,) in connection.execute(
                "SELECT notice_id FROM lsh_bucket WHERE band = ? AND bucket = ?", (band, bucket)
            )
            if candidate != notice_id
        }
        candidate_counts.append(len(candidate_ids))
        portal_counts.setdefault(portal_by_id[notice_id], []).append(len(candidate_ids))
        for candidate_id in candidate_ids:
            if notice_id >= candidate_id:
                continue
            compared += 1
            left, right = feature_sets[notice_id], feature_sets[candidate_id]
            score = len(left & right) / len(left | right) if left or right else 0.0
            if score >= MATCH_THRESHOLD:
                union_find.union(notice_id, candidate_id)

    groups: dict[str, list[str]] = {}
    for notice_id in union_find.parent:
        groups.setdefault(union_find.find(notice_id), []).append(notice_id)
    assignments = []
    for members in groups.values():
        old_ids = sorted({previous_cards[member] for member in members if member in previous_cards})
        if old_ids:
            card_id = old_ids[0]
            connection.executemany(
                "INSERT OR REPLACE INTO card_alias VALUES (?, ?)",
                [(old_id, card_id) for old_id in old_ids],
            )
        else:
            card_id = stable_card_id(sorted(members, key=lambda member: (published_by_id[member], member))[:1])
        assignments.extend((card_id, member) for member in members)
    connection.executemany("UPDATE notice SET card_id = ? WHERE notice_id = ?", assignments)
    connection.commit()
    elapsed = time.perf_counter() - started
    sample_bucket = connection.execute("SELECT band, bucket FROM lsh_bucket LIMIT 1").fetchone()
    indexed_plan = connection.execute("EXPLAIN QUERY PLAN SELECT notice_id FROM lsh_bucket WHERE band = ? AND bucket = ?", sample_bucket).fetchall()
    scan_plan = connection.execute("EXPLAIN QUERY PLAN SELECT notice_id FROM lsh_bucket NOT INDEXED WHERE band = ? AND bucket = ?", sample_bucket).fetchall()
    def probe(sql: str) -> tuple[float, int]:
        probe_start = time.perf_counter()
        rows_examined = 0
        for _ in range(100):
            rows_examined += len(connection.execute(sql, sample_bucket).fetchall())
        return round(time.perf_counter() - probe_start, 6), rows_examined
    indexed_time, indexed_rows = probe("SELECT notice_id FROM lsh_bucket WHERE band = ? AND bucket = ?")
    scan_time, scan_rows = probe("SELECT notice_id FROM lsh_bucket NOT INDEXED WHERE band = ? AND bucket = ?")
    report = {
        "notices": len(notices), "stopwords": len(stopwords), "buckets": len(bucket_rows),
        "candidate_pairs": compared, "cards": len(groups), "elapsed_seconds": round(elapsed, 3),
        "candidate_mean": round(sum(candidate_counts) / len(candidate_counts), 2),
        "candidate_p95": sorted(candidate_counts)[int(len(candidate_counts) * 0.95)],
        "portal_hotspots": sorted(
            ({"portal_id": portal, "notices": len(counts), "mean_candidates": round(sum(counts) / len(counts), 2), "p95_candidates": sorted(counts)[int(len(counts) * 0.95)]} for portal, counts in portal_counts.items()),
            key=lambda item: item["mean_candidates"], reverse=True,
        )[:15],
        "database_access": {"indexed_plan": indexed_plan, "forced_scan_plan": scan_plan, "indexed_100_probe_seconds": indexed_time, "forced_scan_100_probe_seconds": scan_time, "indexed_rows_returned": indexed_rows, "forced_scan_rows_returned": scan_rows},
        "threshold": MATCH_THRESHOLD, "permutations": PERMUTATIONS, "bands": BANDS, "rows": ROWS,
    }
    (output.parent / "run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    connection.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("setubid.sqlite"))
    args = parser.parse_args()
    print(json.dumps(run(args.data_dir, args.output), indent=2))