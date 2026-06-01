**Role:** You are an expert Optimization Engineer specializing in Mixed-Integer Linear Programming (MILP) and Benders Decomposition.

**Objective:** Implement a "Branch-and-Benders-Cut" algorithm to solve the **Job Sequencing and Tool Switching Problem (SSP)** using Python and either **Gurobi** or **CPLEX**.

### 1. Problem Context
The goal is to find a sequence of jobs that minimizes the total number of tool switches. We have a magazine with capacity $c$. Each job $j$ requires a set of tools $T_j$. If the required tools for the next job are not in the magazine, tools must be switched out.

### 2. Technical Architecture: The Master Problem (MP)
The Master Problem is a TSP that decides the sequence and manages a surrogate variable $\theta$ for the tool switching cost.

*   **Variables:** 
    *   $x_{ij} \in \{0, 1\}$ (1 if job $i$ is followed by job $j$).
    *   $\theta \in \mathbb{R}^+$ (The estimated tool switching cost).
*   **Objective:** $\min \theta$
*   **Constraints:**
    1.  **Degree Constraints:** Every node must have exactly one incoming and one outgoing edge.
    2.  **Initial Lower Bound:** To prevent a poor root node relaxation, add the constraint: $\theta \ge \sum_{i,j} w_{ij} x_{ij}$, where $w_{ij} = \max(0, |T_i \cup T_j| - c)$.
    3.  **Subtour Elimination:** Must be handled via **Lazy Constraint Callbacks**.
    4.  **Benders Optimality Cuts:** Must be handled via **Lazy Constraint Callbacks**.

### 3. Technical Architecture: The Dual Subproblem (DSP)
For a fixed integer sequence $\bar{x}$ provided by the Master Problem, we must solve the Dual Subproblem to obtain the dual variables required for the Benders cut. **Do not use the KTNS combinatorial algorithm; use the LP Dual formulation.**

**The DSP Formulation:**
$$\max \sum_{i,j,t} (\bar{x}_{ij} - 1) \lambda_{ijt} - \sum_{j} c \mu_j + \sum_{j, t \in T_j} \nu_{jt}$$
**Subject to:**
*   $-\mu_j - \sum_{i} \lambda_{ijt} + \sum_{k} \lambda_{jkt} + (\nu_{jt} \text{ if } t \in T_j \text{ else } 0) \le 0 \quad \forall j, t$
*   $\sum_{i} \lambda_{ijt} + (\eta_{jt} \text{ if } t \notin T_j \text{ else } 0) \le (1 \text{ if } t \in T_j \text{ else } 0) \quad \forall j, t$
*   $\lambda_{ijt} \ge 0, \mu_j \ge 0, \nu_{jt} \in \mathbb{R}, \eta_{jt} \in \mathbb{R}$

### 4. The Benders Optimality Cut
If the optimal objective value of the DSP, $Z^*(\bar{x})$, is greater than the current $\theta$, inject the following linear cut into the Master Problem:
$$\theta \ge \sum_{i, j, t} (x_{ij} - 1)\bar{\lambda}_{ijt} - \sum_{j} c \bar{\mu}_j + \sum_{j, t \in T_j} \bar{\nu}_{jt}$$
Where $\bar{\lambda}, \bar{\mu}, \bar{\nu}$ are the optimal dual variables from the DSP.

### 5. Implementation Requirements (Step-by-Step)
1.  **Model Setup:** Create the Master Problem (TSP + $\theta$) in Gurobi/CPLEX.
2.  **Callback Integration:** Implement a `LazyConstraint` callback that triggers on every integer solution.
3.  **The Callback Logic:**
    *   **Step A (Subtour Check):** Check the integer sequence $\bar{x}$ for subtours. If found, add the corresponding subtour elimination constraint and return.
    *   **Step B (Dual Subproblem):** If no subtours exist, solve the **DSP LP** described above using the current sequence $\bar{x}$.
    *   **Step C (Cut Injection):** Compare the DSP result $Z^*(\bar{x})$ with the current $\theta$. If $Z^*(\bar{x}) > \theta$, add the Benders Optimality Cut as a lazy constraint.
4.  **Convergence:** The solver should iterate until the gap between $\theta$ and the actual cost from the DSP is zero.

### 6. Critical Constraints for the Agent
*   **Strictly no KTNS:** Use the Dual LP for cuts.
*   **Lazy Constraints:** You must use the solver's callback mechanism (e.g., `gurobipy.Callback`).
*   **Efficiency:** Ensure the Dual Subproblem is constructed efficiently within the callback loop to avoid performance bottlenecks.
*   **Validation:** Provide a method to validate the final sequence against a small-scale monolithic model to ensure global optimality.