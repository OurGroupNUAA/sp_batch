from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List


INSTANCE_RE = re.compile(
    r"^instance_\d+_(?P<scale>small|medium|large)_"
    r"n(?P<n>\d+)_b(?P<b>\d+)_g(?P<gamma>\d+)_rep(?P<rep>\d+)\.txt$"
)


def read_csv_by_instance(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    indexed: Dict[str, Dict[str, str]] = {}
    for row in rows:
        instance_file = row["instance_file"]
        if instance_file in indexed:
            raise ValueError(f"Duplicate instance_file in {path}: {instance_file}")
        indexed[instance_file] = row
    return indexed


def write_comparison(
    dp_rows: Dict[str, Dict[str, str]],
    dp_prime_rows: Dict[str, Dict[str, str]],
    output_path: Path,
    included_scales: Iterable[str],
) -> None:
    scales = set(included_scales)
    missing_in_prime = sorted(set(dp_rows) - set(dp_prime_rows))
    missing_in_dp = sorted(set(dp_prime_rows) - set(dp_rows))
    if missing_in_prime or missing_in_dp:
        raise ValueError(
            "DP and DP-prime results do not contain the same instances: "
            f"missing_in_prime={len(missing_in_prime)}, missing_in_dp={len(missing_in_dp)}"
        )

    grouped: Dict[tuple[int, int, int], List[Dict[str, float]]] = defaultdict(list)
    for instance_file, dp_row in dp_rows.items():
        match = INSTANCE_RE.match(instance_file)
        if match is None:
            raise ValueError(f"Unexpected instance filename: {instance_file}")
        if match.group("scale") not in scales:
            continue

        prime_row = dp_prime_rows[instance_file]
        if dp_row["dp_status"] != "OPTIMAL" or prime_row["dp_prime_status"] != "OPTIMAL":
            raise ValueError(f"Non-optimal DP result for included instance: {instance_file}")

        dp_obj = float(dp_row["dp_obj"])
        prime_obj = float(prime_row["dp_prime_obj"])
        if dp_obj <= 0:
            raise ValueError(f"RPD denominator must be positive: {instance_file}")

        gap = prime_obj - dp_obj
        grouped[
            (
                int(match.group("n")),
                int(match.group("b")),
                int(match.group("gamma")),
            )
        ].append(
            {
                "dp_time": float(dp_row["dp_time"]),
                "dp_prime_time": float(prime_row["dp_prime_time"]),
                "gap": gap,
                "rpd_pct": gap / dp_obj * 100.0,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "n",
                "b",
                "gamma",
                "T_DP",
                "T_DP_prime",
                "N_gap",
                "G_max",
                "RPD_max_pct",
                "instances",
            ]
        )
        for (n, b, gamma), rows in sorted(grouped.items()):
            count = len(rows)
            writer.writerow(
                [
                    n,
                    b,
                    gamma,
                    f"{sum(row['dp_time'] for row in rows) / count:.3f}",
                    f"{sum(row['dp_prime_time'] for row in rows) / count:.3f}",
                    sum(row["gap"] != 0 for row in rows),
                    f"{max(row['gap'] for row in rows):g}",
                    f"{max(row['rpd_pct'] for row in rows):.4f}",
                    count,
                ]
            )


def build_parser(root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the DP versus DP-prime comparison used by Table 4.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--dp-raw",
        default=str(
            root / "results" / "detailed_results" / "dp_py_detailed.csv"
        ),
    )
    parser.add_argument(
        "--dp-prime-raw",
        default=str(
            root / "results" / "detailed_results" / "dp_prime_detailed.csv"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            root
            / "results"
            / "summary_results"
            / "table_dp_comparison_medium_large.csv"
        ),
    )
    parser.add_argument(
        "--scales",
        default="medium,large",
        help="Comma-separated instance scales to include.",
    )
    return parser


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    args = build_parser(root).parse_args()
    scales = [value.strip() for value in args.scales.split(",") if value.strip()]
    unknown_scales = set(scales) - {"small", "medium", "large"}
    if not scales or unknown_scales:
        raise ValueError(f"Invalid --scales value: {args.scales}")

    write_comparison(
        read_csv_by_instance(Path(args.dp_raw)),
        read_csv_by_instance(Path(args.dp_prime_raw)),
        Path(args.output),
        scales,
    )


if __name__ == "__main__":
    main()
