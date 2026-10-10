"""
DP-Prime solver module.

This module is migrated from:
AlgorithmDP/src/pythonProject p+s(1)_ling/algorithm_a_oulamara.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Job:
    id: int
    p: float
    q: float = 0.0

    def __repr__(self) -> str:
        return f"J{self.id}(p={self.p})"


class DPPrimeSolver:
    """
    DP-Prime solver (formerly AlgorithmASolver in algorithm_a_oulamara.py).

    Inputs:
    - jobs: list[Job]
    - b: batch capacity
    - s: setup time on M2 per batch
    - q: per-job processing time on M2
    """

    def __init__(self, jobs: List[Job], b: int, s: float, q: float):
        if b <= 0:
            raise ValueError("b (batch capacity) must be positive.")
        self.jobs: List[Job] = sorted(jobs, key=lambda x: x.p)
        self.n: int = len(jobs)
        self.b: int = int(b)
        self.s: float = float(s)
        self.q: float = float(q)
        self.p_list: List[float] = [job.p for job in self.jobs]
        self.memo: Dict[Tuple[int, int], Tuple[float, List[Dict[str, Any]]]] = {}

    def solve(self) -> Tuple[float, List[Dict[str, Any]]]:
        if self.n == 0:
            return 0.0, []

        min_cmax = float("inf")
        best_schedule: List[Dict[str, Any]] = []

        limit_h = min(self.b, self.n)
        for h in range(1, limit_h + 1):
            first_batch_jobs = self.jobs[:h]
            p_h = first_batch_jobs[-1].p

            idle_cost, sched_tail = self._solve_dp(self.n - h, h)
            current_cmax = p_h + self.s + self.n * self.q + idle_cost

            if current_cmax < min_cmax:
                min_cmax = current_cmax
                first_batch = {
                    "p": p_h,
                    "size": h,
                    "jobs": first_batch_jobs,
                    "type": "AlgoA_Head",
                }
                best_schedule = [first_batch] + sched_tail

        return float(min_cmax), best_schedule

    def _solve_dp(self, remaining_jobs_count: int, last_batch_size: int) -> Tuple[float, List[Dict[str, Any]]]:
        state = (int(remaining_jobs_count), int(last_batch_size))
        if state in self.memo:
            return self.memo[state]

        if remaining_jobs_count == 0:
            self.memo[state] = (0.0, [])
            return 0.0, []

        best_val = float("inf")
        best_tail_sched: List[Dict[str, Any]] = []
        limit = min(self.b, remaining_jobs_count)

        for next_size in range(1, limit + 1):
            start_idx = self.n - remaining_jobs_count
            end_idx = start_idx + next_size

            p_next = self.p_list[end_idx - 1]
            gap = max(0.0, p_next - self.s - last_batch_size * self.q)

            res_val, res_sched = self._solve_dp(remaining_jobs_count - next_size, next_size)
            total_cost = gap + self.s + res_val

            if total_cost < best_val:
                best_val = total_cost
                current_batch = {
                    "p": p_next,
                    "size": next_size,
                    "jobs": self.jobs[start_idx:end_idx],
                    "type": "AlgoA_Body",
                }
                best_tail_sched = [current_batch] + res_sched

        self.memo[state] = (float(best_val), best_tail_sched)
        return self.memo[state]


# Backward-compatible alias
AlgorithmASolver = DPPrimeSolver


def schedule_to_simple_str(schedule: List[Dict[str, Any]]) -> str:
    parts = []
    for i, batch in enumerate(schedule, 1):
        ids = [j.id for j in batch["jobs"]]
        parts.append(f"B{i}(size={batch['size']}, p={batch['p']}): {ids}")
    return "\n".join(parts)


if __name__ == "__main__":
    jobs = [Job(i, p) for i, p in enumerate([1, 4, 5, 6, 7, 8])]
    b, s, q = 2, 1, 2
    solver = DPPrimeSolver(jobs, b=b, s=s, q=q)
    cmax, sched = solver.solve()
    print("DP-Prime result")
    print("Cmax =", cmax)
    print(schedule_to_simple_str(sched))

