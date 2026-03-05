# AlgorithmDP

Python implementation of the algorithms for the two-machine no-wait flowshop scheduling problem:
$F2|\text{no-wait}, \text{p-batch}(1), \text{s-batch}(2), b<n, q_j=q|C_{\max}$

## Directory Layout

- `src/cpp/`
  - `DP_solver.py` — Exact Dynamic Programming (DP) core implementation.
  - `dp_prime_solver.py` — DP' ($DP^\prime$) heuristic core implementation.
- `src/gurobi/`
  - `gurobi_solver.py` — Gurobi MILP model implementation.
- `scripts/`
  - `generate_instances.py` — Script to generate benchmark instances.
  - `solve_dp_instances.py` — Batch runner for the DP solver.
  - `solve_dp_prime_instances.py` — Batch runner for the DP' heuristic solver.
  - `solve_gurobi_instances.py` — Batch runner for the Gurobi MILP solver.
- `results/Instance/` — Directory for generated benchmark instances (`.txt` files).
- `results/raw/` — Detailed CSV outputs for each solved instance.
- `results/summary/` — Summary CSV outputs aggregating the evaluation metrics across all instances.

## Requirements

- **Python 3.7+**
- **gurobipy** (Required only if you intend to run the Gurobi MILP solver)

To install Gurobi for Python, run:

```bash
pip install gurobipy
```

*Note: A valid Gurobi license is required to solve large MILP instances using `gurobipy`. The free trial or academic license is sufficient.*

## Recommended Workflow

It is highly recommended to execute all scripts from the **repository root** so that relative paths naturally map to the `results/` folder.

### 1. Generate Instances

Generate synthetic benchmark instances of different scales (small, medium, large).

```bash
python scripts/generate_instances.py --clear-existing
```

Generated instances will be saved into the folder `results/Instance/`.

### 2. Run the DP Solver

Solve the generated benchmark instances using the exact Dynamic Programming (DP) algorithm. The script applies the recursive logic to find optimal batching structures.

```bash
python scripts/solve_dp_instances.py --backfill-txt
```

**Outputs generated:**

- Detailed results: `results/raw/dp_py_detailed.csv`
- Aggregated summary: `results/summary/table_dp_py_summary.csv`

### 3. Run the DP' Heuristic Solver

Solve the instances using the faster DP' heuristic algorithm, specifically designed for computational efficiency while maintaining high solution quality.

```bash
python scripts/solve_dp_prime_instances.py --backfill-txt
```

**Outputs generated:**

- Detailed results: `results/raw/dp_prime_detailed.csv`
- Aggregated summary: `results/summary/table_dp_prime_summary.csv`

### 4. Run the Gurobi Solver

Solve the instances using the standard Gurobi Mixed Integer Linear Programming (MILP) mathematical formulation. 

```bash
python scripts/solve_gurobi_instances.py --backfill-txt
```

**Outputs generated:**

- Detailed results: `results/raw/gurobi_detailed_py.csv`
- Aggregated summary: `results/summary/table_gurobi_py_summary.csv`
