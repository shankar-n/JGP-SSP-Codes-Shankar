# Branch-and-Benders-Cut for Job Sequencing Problem

## Overview

This is an exact implementation of the **Branch-and-Benders-Cut algorithm** for the Job Sequencing and Tool Switching Problem (SSP), implemented according to `plan-from-gemma.md`.

## Algorithm

### Master Problem
The Master Problem solves a **Traveling Salesman Problem (TSP)** with a surrogate cost variable:

$$\min \theta$$

**Subject to:**
- Degree constraints: Each job has exactly one predecessor and successor
- Lower bound: $\theta \ge \sum_{i,j} w_{ij} x_{ij}$ where $w_{ij} = \max(0, |T_i \cup T_j| - c)$
- Subtour elimination (via lazy constraints)
- Benders optimality cuts (via lazy constraints)

### Subproblem
For each integer solution (sequence), we solve a **Dual LP** to get dual variables for Benders cuts:

$$\max \sum_{i,j,t} (\bar{x}_{ij} - 1)\lambda_{ijt} - \sum_j c\mu_j + \sum_{j,t \in T_j} \nu_{jt}$$

### Integration
- Uses Gurobi's **Lazy Constraint Callbacks** to inject cuts dynamically
- Subtour elimination checked first; if valid, dual subproblem solved for Benders cuts
- Converges when $\theta =$ actual tool switching cost

## Requirements

**Required:**
- Python 3.6+
- **Gurobi** (with gurobipy) OR **CPLEX**
- NumPy

**Install Gurobi:**
```bash
pip install gurobipy
```

## Usage

### Basic Example
```python
from branch_and_benders_cut import BranchAndBendersCutSSP
from utils import load_ssp_instance

# Load instance
n_jobs, n_tools, capacity, tool_req = load_ssp_instance("instance.txt")

# Create solver
solver = BranchAndBendersCutSSP(n_jobs, n_tools, capacity, tool_req)

# Build and solve
solver.build_master_problem(verbose=True)
status, obj_val, sequence = solver.solve(time_limit=3600, verbose=True)

print(f"Status: {status}")
print(f"Objective: {obj_val}")
print(f"Sequence: {sequence}")
```

### Command Line
```bash
python branch_and_benders_cut.py
```

## Algorithm Details

### 1. Master Problem Setup
- Variables: $x_{ij} \in \{0,1\}$ for arc from job $i$ to job $j$, and $\theta \in \mathbb{R}^+$
- Initial lower bound based on pairwise union sizes
- MTZ-style subtour elimination handled dynamically

### 2. Callback Mechanism
When Gurobi finds an integer solution:

1. **Subtour Check:** Verify the sequence has no subtours
   - If found → Add subtour elimination constraint and return
   
2. **Dual LP:** If valid sequence, solve the Dual Subproblem
   - Extracts dual variables: $\lambda_{ijt}, \mu_j, \nu_{jt}, \eta_{jt}$
   
3. **Benders Cut:** If dual objective > $\theta$, add cut:
   $$\theta \ge \sum_{i,j,t} (x_{ij} - 1)\bar{\lambda}_{ijt} - \sum_j c\bar{\mu}_j + \sum_{j,t \in T_j} \bar{\nu}_{jt}$$

### 3. Convergence
Algorithm terminates when:
- Gurobi finds integer solution with $\theta =$ actual cost, OR
- Time/iteration limit reached

## Implementation Notes

**Key Features:**
- Fully implements Gurobi Lazy Constraint Callbacks
- Exact Dual LP formulation (not heuristic)
- Proper subtour elimination via DFS
- Efficient pairwise bound computation
- Callback error handling

**Performance Characteristics:**
- Strong bounds from lower bound constraint
- Aggressive cutting planes from Benders cuts
- Branch-and-cut exploits both bounds

## Files

- `branch_and_benders_cut.py` - Main solver implementation
- `plan-from-gemma.md` - Full specification document
- `idea.md` - Problem context and theory

## Testing

Run solver on example instance:
```bash
python branch_and_benders_cut.py
```

The solver will load `Instances/Shankar/shankar-example.txt` and display:
- Progress information from Gurobi
- Number of cuts added
- Final solution and objective value
