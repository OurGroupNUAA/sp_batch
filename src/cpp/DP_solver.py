"""
DP solver extracted from:
AlgorithmDP/src/pythonProject p+s(1)_ling/DP+gurobi.py

This module keeps only the DP-related logic and removes Gurobi/experiment code.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class Job:
    def __init__(self, id: int, p: float, q: float = 0) -> None:
        self.id = id
        self.p = p
        self.q = q

    def __repr__(self) -> str:
        return f"J{self.id}(p={self.p})"


def calculate_schedule_makespan(batches: List[Dict[str, Any]], s: float, q: float) -> float:
    if not batches:
        return 0.0

    curr_e1 = 0.0
    curr_e2 = 0.0

    for batch in batches:
        p_batch = float(batch["p"])
        size = int(batch["size"])
        proc_m2 = s + size * q

        start_m1 = curr_e1
        end_m1 = start_m1 + p_batch
        start_m2 = end_m1

        if start_m2 < curr_e2:
            shift = curr_e2 - start_m2
            end_m1 += shift
            start_m2 += shift

        curr_e1 = end_m1
        curr_e2 = start_m2 + proc_m2

    return curr_e2


class ManuscriptDPSolver:
    """
    DP solver extracted from DP+gurobi.py.
    """

    def __init__(self, jobs: List[Job], b: int, s: float, q: float) -> None:
        self.jobs = sorted(jobs, key=lambda x: x.p)
        self.n = len(jobs)
        self.b = b
        self.s = s
        self.q = q
        self.p_list = [job.p for job in self.jobs]
        self._dp_cache: Dict[Tuple[int, float, int], Dict[str, Any]] = {}

    def solve(self) -> Tuple[float, List[Dict[str, Any]]]:
        min_cmax = float("inf")
        best_full_schedule: List[Dict[str, Any]] = []

        # Iterate last-batch end index j.
        for j in range(self.n - 1, -1, -self.b):
            limit_size_l = min(j + 1, self.b)

            for size_l in range(1, limit_size_l + 1):
                # Shared preparation.
                start_index_of_bl = j - size_l + 1
                p_bl = self.p_list[j]
                jobs_bl = self.jobs[start_index_of_bl : j + 1]

                tail_chain: List[Dict[str, Any]] = []
                tail_start = j + 1
                while tail_start < self.n:
                    tail_end = tail_start + self.b
                    p_val = self.p_list[tail_end - 1]
                    jobs_tail = self.jobs[tail_start:tail_end]
                    tail_chain.append(
                        {
                            "p": p_val,
                            "size": self.b,
                            "jobs": jobs_tail,
                            "type": "TailFull",
                        }
                    )
                    tail_start += self.b

                # Case A: B_l is full.
                if size_l == self.b:
                    batch_bl = {
                        "p": p_bl,
                        "size": size_l,
                        "jobs": jobs_bl,
                        "type": "Last(Full)",
                    }

                    curr_start_idx = start_index_of_bl
                    curr_p_limit = p_bl
                    chain_of_prev_full: List[Dict[str, Any]] = []

                    while True:
                        # DP linkage when next batch is full => size_limit = b.
                        res = self.solve_dp_recursive(curr_start_idx, curr_p_limit, self.b)

                        if res["cost"] != float("inf"):
                            full_sched = res["schedule"] + chain_of_prev_full + tail_chain + [batch_bl]
                            real_cmax = calculate_schedule_makespan(full_sched, self.s, self.q)
                            if real_cmax < min_cmax:
                                min_cmax = real_cmax
                                best_full_schedule = full_sched

                        # Trace back one more previous full batch.
                        if curr_start_idx < self.b:
                            break
                        p_new_prev = self.p_list[curr_start_idx - 1]
                        if p_new_prev > curr_p_limit:
                            break

                        jobs_new_prev = self.jobs[curr_start_idx - self.b : curr_start_idx]
                        batch_new_prev = {
                            "p": p_new_prev,
                            "size": self.b,
                            "jobs": jobs_new_prev,
                            "type": "PrevFull",
                        }
                        chain_of_prev_full.insert(0, batch_new_prev)
                        curr_start_idx -= self.b
                        curr_p_limit = p_new_prev

                # Case B: B_l is non-full.
                else:
                    batch_bl = {
                        "p": p_bl,
                        "size": size_l,
                        "jobs": jobs_bl,
                        "type": "Last(NonFull)",
                    }

                    # 1) Link DP directly.
                    res1 = self.solve_dp_recursive(start_index_of_bl, p_bl, self.b)
                    if res1["cost"] != float("inf"):
                        full_sched = res1["schedule"] + tail_chain + [batch_bl]
                        real_cmax = calculate_schedule_makespan(full_sched, self.s, self.q)
                        if real_cmax < min_cmax:
                            min_cmax = real_cmax
                            best_full_schedule = full_sched

                    # 2) Exactly one predecessor full batch.
                    if start_index_of_bl >= self.b:
                        p_one_full = self.p_list[start_index_of_bl - 1]
                        if p_one_full <= p_bl:
                            jobs_one_full = self.jobs[start_index_of_bl - self.b : start_index_of_bl]
                            batch_one_full = {
                                "p": p_one_full,
                                "size": self.b,
                                "jobs": jobs_one_full,
                                "type": "PrevFull(Single)",
                            }

                            rem_idx = start_index_of_bl - self.b
                            res2 = self.solve_dp_recursive(rem_idx, p_one_full, self.b)
                            if res2["cost"] != float("inf"):
                                full_sched = res2["schedule"] + [batch_one_full] + tail_chain + [batch_bl]
                                real_cmax = calculate_schedule_makespan(full_sched, self.s, self.q)
                                if real_cmax < min_cmax:
                                    min_cmax = real_cmax
                                    best_full_schedule = full_sched

        return min_cmax, best_full_schedule

    def solve_dp_recursive(
        self, rem_jobs: int, p_next_batch: float, size_limit: int
    ) -> Dict[str, Any]:
        """
        Iterative DP (stack-driven post-order) equivalent to the original
        recursion: generate non-full batches with non-decreasing sizes.
        """
        root = (int(rem_jobs), float(p_next_batch), int(size_limit))
        cached = self._dp_cache.get(root)
        if cached is not None:
            return cached

        stack: List[Tuple[int, float, int]] = [root]
        while stack:
            state = stack[-1]
            cached_state = self._dp_cache.get(state)
            if cached_state is not None:
                stack.pop()
                continue

            rem, p_next, limit = state

            if rem == 0:
                self._dp_cache[state] = {"cost": 0.0, "schedule": []}
                stack.pop()
                continue

            # Constraints: |B_curr| <= rem_jobs, |B_curr| <= |B_next|.
            current_limit = min(rem, limit)
            # DP handles non-full only, so force size < b.
            real_limit = min(current_limit, self.b - 1)
            if real_limit < 1:
                self._dp_cache[state] = {"cost": float("inf"), "schedule": []}
                stack.pop()
                continue

            p_curr = self.p_list[rem - 1]
            if p_curr > p_next:
                self._dp_cache[state] = {"cost": float("inf"), "schedule": []}
                stack.pop()
                continue

            deps_ready = True
            for size in range(1, real_limit + 1):
                dep_state = (rem - size, p_curr, size)
                if dep_state not in self._dp_cache:
                    stack.append(dep_state)
                    deps_ready = False

            if not deps_ready:
                continue

            best = {"cost": float("inf"), "schedule": []}
            for size in range(1, real_limit + 1):
                dep_state = (rem - size, p_curr, size)
                res = self._dp_cache[dep_state]
                if res["cost"] == float("inf"):
                    continue

                gap = max(0.0, p_next - (self.s + size * self.q))
                term_p = p_curr if (rem == size) else 0.0
                new_cost = res["cost"] + gap + term_p + self.s
                if new_cost < best["cost"]:
                    jobs_curr = self.jobs[rem - size : rem]
                    curr_batch = {
                        "p": p_curr,
                        "size": size,
                        "jobs": jobs_curr,
                        "type": "NonFull",
                    }
                    best = {"cost": new_cost, "schedule": res["schedule"] + [curr_batch]}

            self._dp_cache[state] = best
            stack.pop()

        return self._dp_cache[root]

    def calculate_single_batch_makespan(self) -> float:
        if self.n == 0:
            return 0.0
        p_batch = self.p_list[-1]
        return p_batch + self.s + self.n * self.q


def solve_dp(jobs: List[Job], b: int, s: float, q: float) -> Tuple[float, List[Dict[str, Any]]]:
    solver = ManuscriptDPSolver(jobs, b, s, q)
    return solver.solve()
