#!/usr/bin/env python3
"""
Python port of AlgorithmDP/scripts/generate_instances.cpp.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


def parse_int_list(raw: str) -> List[int]:
    vals: List[int] = []
    for item in raw.split(","):
        t = item.strip()
        if not t:
            continue
        vals.append(int(t))
    return vals


def parse_int_range(raw: str) -> Tuple[int, int]:
    vals = parse_int_list(raw)
    if len(vals) != 2:
        raise ValueError(f"Range must contain two integers: {raw}")
    if vals[0] > vals[1]:
        raise ValueError(f"Invalid range (lo > hi): {raw}")
    return vals[0], vals[1]


def pad_int(value: int, width: int) -> str:
    return str(value).zfill(width)


def collect_files_by_glob_like(directory: Path, pattern: str) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def write_instance_txt(
    path: Path,
    instance_id: int,
    n: int,
    b: int,
    gamma: int,
    q: int,
    s_val: int,
    rep: int,
    seed: int,
    p_list: Iterable[int],
) -> None:
    lines = [
        "# Instance for AlgorithmDP (no-wait flowshop)",
        f"instance_id: {instance_id}",
        f"n: {n}",
        f"b: {b}",
        f"gamma: {gamma}",
        f"q: {q}",
        f"s: {s_val}",
        f"rep: {rep}",
        f"seed: {seed}",
        "",
        "# Jobs (id p)",
    ]

    for i, p in enumerate(p_list, 1):
        lines.append(f"{i} {p}")

    lines.extend(
        [
            "",
            "# Solver results (filled after solving)",
            "obj_dp: PENDING",
            "obj_gurobi: PENDING",
            "time_dp: PENDING",
            "time_gurobi: PENDING",
            "status_dp: PENDING",
            "status_gurobi: PENDING",
        ]
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_instances",
        description="Generate AlgorithmDP benchmark instances.",
        allow_abbrev=False,
    )

    parser.add_argument("--n-small-list", default="5,10,15,20,25")
    parser.add_argument("--n-medium-list", default="100,200,300,400,500")
    parser.add_argument("--n-large-list", default="1000,2000,3000,4000,5000")

    parser.add_argument("--b-small-list", default="2,3,4")
    parser.add_argument("--b-medium-list", default="7,9,11")
    parser.add_argument("--b-large-list", default="13,15,17")

    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--gamma-list", default="1,95,190")
    parser.add_argument("--p-upper", type=int, default=200)
    parser.add_argument("--q-range", default="1,5")
    parser.add_argument("--s-range", default="1,10")
    parser.add_argument("--seed-start", type=int, default=20260302)
    parser.add_argument(
        "--out-dir",
        default=str(
            Path(__file__).resolve().parents[1]
            / "results"
            / "benchmark_instances"
        ),
    )
    parser.add_argument("--clear-existing", action="store_true")

    return parser


def run(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    n_small = parse_int_list(args.n_small_list)
    n_medium = parse_int_list(args.n_medium_list)
    n_large = parse_int_list(args.n_large_list)
    b_small = parse_int_list(args.b_small_list)
    b_medium = parse_int_list(args.b_medium_list)
    b_large = parse_int_list(args.b_large_list)
    gamma_list = parse_int_list(args.gamma_list)

    p_hi = int(args.p_upper)
    if p_hi <= 0:
        raise ValueError("--p-upper must be positive.")
    if not gamma_list:
        raise ValueError("--gamma-list cannot be empty.")
    if any(g <= 0 for g in gamma_list):
        raise ValueError("--gamma-list must contain positive integers.")
    if any(g > p_hi for g in gamma_list):
        raise ValueError("--gamma-list values must be <= --p-upper.")

    q_lo, q_hi = parse_int_range(args.q_range)
    s_lo, s_hi = parse_int_range(args.s_range)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clear_existing:
        for p in collect_files_by_glob_like(out_dir, "instance_*.txt"):
            p.unlink()

    instance_id = 0
    small_cnt = 0
    medium_cnt = 0
    large_cnt = 0

    groups = [
        ("small", n_small, b_small),
        ("medium", n_medium, b_medium),
        ("large", n_large, b_large),
    ]

    for scale, n_list, b_list in groups:
        for n in n_list:
            for b in b_list:
                if b >= n:
                    continue
                for gamma in gamma_list:
                    for rep in range(1, args.repeats + 1):
                        seed = args.seed_start + instance_id
                        rng = random.Random(seed)

                        q = rng.randint(q_lo, q_hi)
                        s = rng.randint(s_lo, s_hi)
                        p_list = [rng.randint(gamma, p_hi) for _ in range(n)]

                        instance_id += 1
                        if scale == "small":
                            small_cnt += 1
                        elif scale == "medium":
                            medium_cnt += 1
                        else:
                            large_cnt += 1

                        file_name = (
                            f"instance_{pad_int(instance_id, 5)}_{scale}_n{n}_b{b}_g{gamma}_rep{rep}.txt"
                        )
                        out_path = out_dir / file_name

                        write_instance_txt(
                            out_path,
                            instance_id=instance_id,
                            n=n,
                            b=b,
                            gamma=gamma,
                            q=q,
                            s_val=s,
                            rep=rep,
                            seed=seed,
                            p_list=p_list,
                        )

                        print(f"[{instance_id}] {file_name} (gamma={gamma}, q={q}, s={s})")

    print(f"generated={instance_id}")
    print(f"generated_small={small_cnt}")
    print(f"generated_medium={medium_cnt}")
    print(f"generated_large={large_cnt}")
    print(f"output_dir={out_dir}")
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
