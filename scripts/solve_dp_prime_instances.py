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


INF_OBJ = (2**63 - 1) // 4


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
        prog="solve_dp_prime_instances",
        description="Batch-run DP-Prime solver on instance txt files.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--instances-dir",
        default=str(default_root / "results" / "benchmark_instances"),
    )
    parser.add_argument("--glob", default="instance_*.txt")
    parser.add_argument("--time-limit", type=float, default=1800.0)
    parser.add_argument("--recursion-limit", type=int, default=20000)
    parser.add_argument(
        "--raw-out",
        default=str(
            default_root
            / "results"
            / "detailed_results"
            / "dp_prime_detailed.csv"
        ),
    )
    parser.add_argument(
        "--summary-out",
        default=str(
            default_root
            / "results"
            / "summary_results"
            / "table_dp_prime_summary.csv"
        ),
    )
    parser.add_argument("--backfill-txt", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: List[str]) -> int:
    root = detect_algorithmdp_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.cpp.dp_prime_solver import DPPrimeSolver, Job

    args = build_parser(root).parse_args(argv)
    if args.recursion_limit > 0:
        sys.setrecursionlimit(max(sys.getrecursionlimit(), int(args.recursion_limit)))

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
        "dp_prime_obj",
        "dp_prime_time",
        "dp_prime_status",
    ]
    with raw_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        total = len(records)
        for idx, rec in enumerate(records, start=1):
            t0 = time.perf_counter()
            obj: float = float(INF_OBJ)
            status = "OPTIMAL"
            try:
                jobs = [Job(i + 1, p, rec.q) for i, p in enumerate(rec.p_list)]
                obj, _ = DPPrimeSolver(jobs, rec.b, rec.s, rec.q).solve()
            except Exception as exc:
                status = f"ERROR_{exc}"
            sec = time.perf_counter() - t0

            if args.time_limit > 0 and sec > args.time_limit and status == "OPTIMAL":
                status = "TIME_LIMIT"

            row: Dict[str, object] = {
                "instance_file": rec.file_name,
                "n": rec.n,
                "b": rec.b,
                "q": rec.q,
                "s": rec.s,
                "rep": rec.rep if rec.rep is not None else "",
                "seed": rec.seed if rec.seed is not None else "",
                "dp_prime_obj": int(round(obj)) if status == "OPTIMAL" else int(obj),
                "dp_prime_time": sec,
                "dp_prime_status": status,
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
                    row["dp_prime_obj"],
                    f"{sec:.6f}",
                    row["dp_prime_status"],
                ]
            )
            f.flush()

            if args.backfill_txt:
                update_txt_fields(
                    rec.path,
                    {
                        "obj_dp_prime:": f"obj_dp_prime: {row['dp_prime_obj']}",
                        "status_dp_prime:": f"status_dp_prime: {status}",
                        "time_dp_prime:": f"time_dp_prime: {sec:.6f}",
                    },
                )

            if not args.quiet:
                print(
                    f"[{idx}/{total}] {rec.file_name} "
                    f"(n={rec.n},b={rec.b},q={rec.q},s={rec.s}) "
                    f"-> obj={row['dp_prime_obj']}, time={sec:.4f}s, status={status}"
                )

    write_summary_csv(
        rows,
        summary_out,
        obj_key="dp_prime_obj",
        time_key="dp_prime_time",
        status_key="dp_prime_status",
    )

    if not args.quiet:
        print(f"bad_files={bad_files}")
        print(f"raw_out={raw_out}")
        print(f"summary_out={summary_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
