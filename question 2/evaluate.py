from __future__ import annotations

import argparse
import csv
import glob
import importlib
import json
from pathlib import Path

from dedupe_core import MinHasher, content_tokens, corpus_stopwords, estimated_jaccard, lsh_buckets, shingles, tokenize
from pipeline import BANDS, ROWS, PERMUTATIONS


def notices(data_dir: Path) -> dict[str, dict[str, str]]:
    result = {}
    parquet_paths = sorted(glob.glob(str(data_dir / "notices" / "*.parquet")))
    if parquet_paths:
        try:
            parquet = importlib.import_module("pyarrow.parquet")
        except ImportError as error:
            raise RuntimeError("Parquet input requires pyarrow; install it before evaluating") from error
        rows = [row for path in parquet_paths for row in parquet.read_table(path).to_pylist()]
    else:
        rows = []
        for path in glob.glob(str(data_dir / "notices" / "*.csv")):
            with open(path, newline="", encoding="utf-8") as handle:
                rows.extend(csv.DictReader(handle))
    for row in rows:
        if "notice_id" not in row and "notice_is" in row:
            row["notice_id"] = row.pop("notice_is")
        result[row["notice_id"]] = row
    return result


def labels(data_dir: Path) -> list[dict[str, str]]:
    path = data_dir / "labelled_pairs.csv"
    if not path.exists():
        path = data_dir / "Labelled_paies.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def score_pairs(rows, pair_rows, stopwords, width, remove_common=True):
    features = {}
    signatures = {}
    hasher = MinHasher(PERMUTATIONS)
    for notice_id, row in rows.items():
        chosen_stopwords = stopwords if remove_common else set()
        features[notice_id] = shingles(content_tokens(row["title"], row["body"], chosen_stopwords), width)
        signatures[notice_id] = hasher.signature(features[notice_id])
    scores = []
    for pair in pair_rows:
        left, right = features[pair["notice_id_a"]], features[pair["notice_id_b"]]
        exact = len(left & right) / len(left | right) if left or right else 0.0
        left_buckets = set(lsh_buckets(signatures[pair["notice_id_a"]], BANDS, ROWS))
        right_buckets = set(lsh_buckets(signatures[pair["notice_id_b"]], BANDS, ROWS))
        scores.append((pair["label"] == "same", exact, estimated_jaccard(signatures[pair["notice_id_a"]], signatures[pair["notice_id_b"]]), bool(left_buckets & right_buckets)))
    return scores, features


def metrics(scores, threshold):
    tp = sum(actual and score >= threshold for actual, score, _, _ in scores)
    fp = sum(not actual and score >= threshold for actual, score, _, _ in scores)
    fn = sum(actual and score < threshold for actual, score, _, _ in scores)
    return {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "precision": tp / (tp + fp) if tp + fp else 0, "recall": tp / (tp + fn) if tp + fn else 0}


def run(data_dir: Path) -> dict[str, object]:
    rows = notices(data_dir)
    pair_rows = labels(data_dir)
    stopwords = corpus_stopwords((row["title"], row["body"]) for row in rows.values())
    label_counts = {label: sum(pair["label"] == label for pair in pair_rows) for label in ("same", "different")}
    results = {"label_counts": label_counts, "label_negative_fraction": label_counts["different"] / len(pair_rows)}
    for width in (3, 5):
        scores, features = score_pairs(rows, pair_rows, stopwords, width)
        results[f"width_{width}"] = {str(t): metrics(scores, t) for t in (0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.80, 0.85)}
        results[f"width_{width}"]["estimator_mae"] = sum(abs(exact - estimate) for _, exact, estimate, _ in scores) / len(scores)
        results[f"width_{width}"]["estimator_max_error"] = max(abs(exact - estimate) for _, exact, estimate, _ in scores)
        results[f"width_{width}"]["candidate_recall"] = sum(actual and survived for actual, _, _, survived in scores) / sum(actual for actual, _, _, _ in scores)
        results[f"width_{width}"]["raw_candidate_recall"] = sum(
            actual and survived for actual, _, _, survived in score_pairs(rows, pair_rows, stopwords, width, remove_common=False)[0]
        ) / sum(actual for actual, _, _, _ in scores)
        results[f"width_{width}"]["survival_curve"] = {
            str(bucket): {
                "pairs": sum(bucket <= exact < bucket + 0.1 for _, exact, _, _ in scores),
                "survived": sum(bucket <= exact < bucket + 0.1 and survived for _, exact, _, survived in scores),
            }
            for bucket in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
        }
        cost_table = {str(t): metrics(scores, t) | {"weighted_cost": 20 * metrics(scores, t)["fp"] + metrics(scores, t)["fn"]} for t in (0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.80, 0.85)}
        results[f"width_{width}"]["weighted_threshold_cost"] = cost_table
        results[f"width_{width}"]["false_merge_cost"] = 20
        results[f"width_{width}"]["missed_merge_cost"] = 1
        results[f"width_{width}"]["selected_threshold"] = min(cost_table, key=lambda threshold: cost_table[threshold]["weighted_cost"])
        results[f"width_{width}"]["examples"] = {
            label: next(
                {"notice_id_a": pair["notice_id_a"], "notice_id_b": pair["notice_id_b"], "scores": {"3gram_clean": score_pairs(rows, [pair], stopwords, 3)[0][0][1], "5gram_clean": score_pairs(rows, [pair], stopwords, 5)[0][0][1], "5gram_raw": score_pairs(rows, [pair], stopwords, 5, False)[0][0][1]}}
                for pair in pair_rows if pair["label"] == label
            )
            for label in ("same", "different")
        }
    selected = float(results["width_5"]["selected_threshold"])
    results["width_5"]["operating_point"] = {
        "threshold": selected,
        "candidate_recall": results["width_5"]["candidate_recall"],
        "weighted_cost": results["width_5"]["weighted_threshold_cost"][str(selected)]["weighted_cost"],
    }
    (Path("evaluation.json")).write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_survival_svg(results["width_5"]["survival_curve"], selected)
    return results


def write_survival_svg(curve: dict[str, dict[str, int]], threshold: float) -> None:
    points = []
    for bucket, values in curve.items():
        if values["pairs"]:
            x = float(bucket) * 900
            y = 300 - (values["survived"] / values["pairs"]) * 260
            points.append(f"{x + 60:.1f},{y:.1f}")
    polyline = " ".join(points)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="380" viewBox="0 0 1020 380">
<rect width="100%" height="100%" fill="white"/><line x1="60" y1="300" x2="960" y2="300" stroke="black"/><line x1="60" y1="40" x2="60" y2="300" stroke="black"/>
<polyline points="{polyline}" fill="none" stroke="#1565c0" stroke-width="3"/><line x1="{60 + threshold * 900:.1f}" y1="40" x2="{60 + threshold * 900:.1f}" y2="300" stroke="#c62828" stroke-dasharray="6 4"/><text x="420" y="355">exact Jaccard similarity</text><text x="10" y="35">candidate survival</text>
<text x="55" y="320">0.0</text><text x="505" y="320">0.5</text><text x="905" y="320">1.0</text><text x="765" y="70" fill="#1565c0">64 bands x 4 rows</text><text x="{60 + threshold * 900:.1f}" y="35" fill="#c62828">threshold {threshold:.2f}</text></svg>'''
    Path("survival_curve.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path)
    print(json.dumps(run(parser.parse_args().data_dir), indent=2))