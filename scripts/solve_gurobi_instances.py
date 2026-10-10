#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fnmatch
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class InstanceRecord:
    path: Path
    file_name: str
    n: int
    b: int
    q: int
    s: int
    rep: Optional[int]
    seed: Optional[int]
    p_list: List[int]


def detect_algorithmdp_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "AlgorithmDP").is_dir():
        return cwd / "AlgorithmDP"
    if (cwd / "results").is_dir() and (cwd / "src").is_dir() and (cwd / "scripts").is_dir():
        return cwd
    return Path(__file__).resolve().parents[1]


def collect_files_by_glob_like(directory: Path, pattern: str) -> List[Path]:
    out: List[Path] = []
    if not directory.exists():
        return out
    for p in directory.iterdir():
        if p.is_file() and fnmatch.fnmatch(p.name, pattern):
            out.append(p)
    out.sort()
    return out


def _trim(s: str) -> str:
    return s.strip()


def _parse_key_int(lines: Sequence[str], key: str, default: Optional[int]) -> Optional[int]:
    prefix = f"{key}:"
    for line in lines:
        t = _trim(line)
        if not t.startswith(prefix):
            continue
        rhs = _trim(t[len(prefix) :])
        if rhs == "":
            return default
        return int(rhs)
    return default


def parse_instance_txt(path: Path) -> Optional[InstanceRecord]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    n = _parse_key_int(lines, "n", None)
    b = _parse_key_int(lines, "b", None)
    q = _parse_key_int(lines, "q", None)
    s = _parse_key_int(lines, "s", None)
    rep = _parse_key_int(lines, "rep", None)
    seed = _parse_key_int(lines, "seed", None)

    if n is None or b is None or q is None or s is None:
        return None
    if n <= 0 or b <= 0 or q < 0 or s < 0:
        return None

    p_list: List[int] = []
    in_jobs = False
    for raw in lines:
        t = _trim(raw)
        if not t:
            continue
        if t.startswith("# Jobs"):
            in_jobs = True
            continue
        if in_jobs and t.startswith("#"):
            break
        if not in_jobs:
            continue

        parts = t.split()
        if len(parts) < 2:
            continue
        try:
            p_val = int(parts[1])
        except ValueError:
            continue
        p_list.append(p_val)

    if len(p_list) != n:
        return None

    return InstanceRecord(
        path=path,
        file_name=path.name,
        n=n,
        b=b,
        q=q,
        s=s,
        rep=rep,
        seed=seed,
        p_list=p_list,
    )


def update_txt_fields(path: Path, updates: Dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    found = {k: False for k in updates}

    for i, line in enumerate(lines):
        for key_prefix, new_line in updates.items():
            if line.startswith(key_prefix):
                lines[i] = new_line
                found[key_prefix] = True

    for key_prefix, new_line in updates.items():
        if not found[key_prefix]:
            lines.append(new_line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_summary_csv(
    rows: Iterable[Dict[str, object]],
    summary_path: Path,
    obj_key: str,
    time_key: str,
    status_key: str,
) -> None:
    grouped: Dict[Tuple[int, int, int], List[Dict[str, object]]] = {}
    for row in rows:
        key = (int(row["n"]), int(row["b"]), int(row["q"]))
        grouped.setdefault(key, []).append(row)

    ensure_parent_dir(summary_path)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["n", "b", "q", "avg_obj", "avg_time", "solved", "total"])
        for (n, b, q) in sorted(grouped):
            vals = grouped[(n, b, q)]
            solved_rows = [r for r in vals if str(r[status_key]) == "OPTIMAL"]
            solved = len(solved_rows)
            total = len(vals)
            if solved > 0:
                avg_obj = sum(float(r[obj_key]) for r in solved_rows) / solved
                avg_time = sum(float(r[time_key]) for r in solved_rows) / solved
            else:
                avg_obj = math.inf
                avg_time = 0.0
            writer.writerow([n, b, q, avg_obj, f"{avg_time:.6f}", solved, total])


def build_parser(default_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solve_gurobi_instances",
        description="Batch-run Python Gurobi solver on instance txt files.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--instances-dir",
        default=str(default_root / "results" / "benchmark_instances"),
    )
    parser.add_argument("--glob", default="instance_*.txt")
    parser.add_argument("--time-limit", type=float, default=1800.0)
    parser.add_argument(
        "--raw-out",
        default=str(
            default_root
            / "results"
            / "detailed_results"
            / "gurobi_detailed_py.csv"
        ),
    )
    parser.add_argument(
        "--summary-out",
        default=str(
            default_root
            / "results"
            / "summary_results"
            / "table_gurobi_py_summary.csv"
        ),
    )
    parser.add_argument("--backfill-txt", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: List[str]) -> int:
    root = detect_algorithmdp_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.gurobi.gurobi_solver import solve_gurobi

    args = build_parser(root).parse_args(argv)

    instances_dir = Path(args.instances_dir)
    raw_out = Path(args.raw_out)
    summary_out = Path(args.summary_out)

    ensure_parent_dir(raw_out)
    ensure_parent_dir(summary_out)

    records = []
    bad_files = 0
    for p in collect_files_by_glob_like(instances_dir, args.glob):
        rec = parse_instance_txt(p)
        if rec is None:
            bad_files += 1
            continue
        records.append(rec)

    rows: List[Dict[str, object]] = []

    headers = [
        "instance_file",
        "n",
        "b",
        "q",
        "s",
        "rep",
        "seed",
        "gurobi_obj",
        "gurobi_time",
        "gurobi_status",
    ]
    with raw_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        total = len(records)
        for idx, rec in enumerate(records, start=1):
            t0 = time.perf_counter()
            result = solve_gurobi(
                n=rec.n,
                b=rec.b,
                s=rec.s,
                q=rec.q,
                p_list=rec.p_list,
                time_limit=args.time_limit if args.time_limit > 0 else -1.0,
            )
            sec = time.perf_counter() - t0

            row: Dict[str, object] = {
                "instance_file": rec.file_name,
                "n": rec.n,
                "b": rec.b,
                "q": rec.q,
                "s": rec.s,
                "rep": rec.rep if rec.rep is not None else "",
                "seed": rec.seed if rec.seed is not None else "",
                "gurobi_obj": int(result.obj),
                "gurobi_time": sec,
                "gurobi_status": result.status,
            }
            rows.append(row)

            writer.writerow(
                [
                    row["instance_file"],
                    row["n"],
                    row["b"],
                    row["q"],
                    row["s"],
                    row["rep"],
                    row["seed"],
                    row["gurobi_obj"],
                    f"{sec:.6f}",
                    row["gurobi_status"],
                ]
            )
            f.flush()

            if args.backfill_txt:
                update_txt_fields(
                    rec.path,
                    {
                        "obj_gurobi:": f"obj_gurobi: {row['gurobi_obj']}",
                        "status_gurobi:": f"status_gurobi: {result.status}",
                        "time_gurobi:": f"time_gurobi: {sec:.6f}",
                    },
                )

            if not args.quiet:
                print(
                    f"[{idx}/{total}] {rec.file_name} "
                    f"(n={rec.n},b={rec.b},q={rec.q},s={rec.s}) "
                    f"-> obj={row['gurobi_obj']}, time={sec:.4f}s, status={result.status}"
                )

    write_summary_csv(
        rows,
        summary_out,
        obj_key="gurobi_obj",
        time_key="gurobi_time",
        status_key="gurobi_status",
    )

    if not args.quiet:
        print(f"bad_files={bad_files}")
        print(f"raw_out={raw_out}")
        print(f"summary_out={summary_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
