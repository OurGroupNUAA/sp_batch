from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception:  # pragma: no cover
    gp = None
    GRB = None


INF_OBJ = (2**63 - 1) // 4


@dataclass
class GurobiResult:
    obj: int
    status: str


def solve_gurobi(
    n: int,
    b: int,
    s: int,
    q: int,
    p_list: Sequence[int],
    time_limit: float = -1.0,
) -> GurobiResult:
    """
    Python counterpart of `src/gurobi/gurobi_solver.cpp`.

    This function keeps the same status semantics:
    - OPTIMAL
    - TIME_LIMIT (with incumbent objective if available)
    - STATUS_<gurobi_status_code>
    - ERROR_<message>
    """
    if gp is None:
        return GurobiResult(obj=INF_OBJ, status="GUROBI_PY_NOT_ENABLED")

    if n <= 0:
        return GurobiResult(obj=INF_OBJ, status="ERROR_n_must_be_positive")
    if len(p_list) != n:
        return GurobiResult(obj=INF_OBJ, status="ERROR_len_p_list_mismatch")

    # Manuscript MILP assumes jobs are indexed by non-decreasing p_j.
    # Enforce this in-solver so callers cannot accidentally solve a different model.
    p_sorted = sorted(int(p) for p in p_list)

    try:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()

        m = gp.Model(env=env)
        if time_limit > 0.0:
            m.setParam("TimeLimit", float(time_limit))
        m.setParam("Threads", 1)

        K = n
        H = int(sum(p_sorted) + n * (s + q))

        x = m.addVars(n, K, vtype=GRB.BINARY, name="x")
        z = m.addVars(n, K, vtype=GRB.BINARY, name="z")
        y = m.addVars(K, vtype=GRB.BINARY, name="y")
        u = m.addVars(K, lb=0.0, ub=float(H), vtype=GRB.CONTINUOUS, name="u")
        S = m.addVars(K, lb=0.0, ub=float(H), vtype=GRB.CONTINUOUS, name="S")
        Cmax = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="Cmax")

        m.setObjective(Cmax, GRB.MINIMIZE)

        # (1) Assignment.
        for j in range(n):
            m.addConstr(gp.quicksum(x[j, k] for k in range(K)) == 1.0)

        # (2) Capacity.
        for k in range(K):
            sum_x = gp.quicksum(x[j, k] for j in range(n))
            m.addConstr(y[k] <= sum_x)
            m.addConstr(sum_x <= b * y[k])

        # (3) Contiguous positions.
        for k in range(K - 1):
            m.addConstr(y[k] >= y[k + 1])

        # (4) Max linearization.
        for k in range(K):
            m.addConstr(gp.quicksum(z[j, k] for j in range(n)) == y[k])
        for j in range(n):
            for k in range(K):
                m.addConstr(z[j, k] <= x[j, k])
                tail_z = gp.quicksum(z[i, k] for i in range(j, n))
                m.addConstr(x[j, k] <= tail_z)
        for k in range(K):
            m.addConstr(u[k] == gp.quicksum(float(p_sorted[j]) * z[j, k] for j in range(n)))

        # (5) S1 = 0.
        m.addConstr(S[0] == 0.0)

        # (6) M1 non-overlap.
        for k in range(K - 1):
            m.addConstr(
                S[k + 1] >= S[k] + u[k] - float(H) * (2.0 - y[k] - y[k + 1])
            )

        # (7) M2 no-wait / non-overlap.
        for k in range(K - 1):
            sum_x = gp.quicksum(x[j, k] for j in range(n))
            m.addConstr(
                S[k + 1] + u[k + 1]
                >= S[k] + u[k] + float(s) * y[k] + float(q) * sum_x - float(H) * (2.0 - y[k] - y[k + 1])
            )

        # (8) Makespan.
        for k in range(K):
            sum_x = gp.quicksum(x[j, k] for j in range(n))
            m.addConstr(Cmax >= S[k] + u[k] + float(s) * y[k] + float(q) * sum_x)

        # (9) Bounds.
        for k in range(K):
            m.addConstr(S[k] <= float(H) * y[k])
            m.addConstr(u[k] <= float(H) * y[k])

        m.optimize()

        st = int(m.Status)
        if st == GRB.OPTIMAL:
            return GurobiResult(obj=int(round(float(m.ObjVal))), status="OPTIMAL")
        if st == GRB.TIME_LIMIT:
            if int(m.SolCount) > 0:
                return GurobiResult(obj=int(round(float(m.ObjVal))), status="TIME_LIMIT")
            return GurobiResult(obj=INF_OBJ, status="TIME_LIMIT")
        return GurobiResult(obj=INF_OBJ, status=f"STATUS_{st}")

    except gp.GurobiError as e:
        return GurobiResult(obj=INF_OBJ, status=f"ERROR_{e}")
    except Exception as e:
        return GurobiResult(obj=INF_OBJ, status=f"ERROR_{e}")
