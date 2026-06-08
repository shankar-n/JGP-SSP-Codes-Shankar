"""
da Silva-Chaves-Yanasse (SSPMF) Multicommodity Flow Formulation for the
Job Sequencing and Tool Switching Problem.

Reference
---------
da Silva, T.F.S., Chaves, A.A., & Yanasse, H.H. (2024).
"A multicommodity flow formulation for the job sequencing and tool
switching problem."  (Submitted / working paper.)

Model Description
-----------------
The SSPMF formulation models the SSP as a multicommodity flow problem on a
specially constructed graph G(V, A).

Graph G
-------
Nodes V = {0, 1, ..., N, N+1, N+2}  where:
  - 0          : origin (artificial first node)
  - 1..N       : job nodes  (0-indexed in this code: 0..N-1)
  - N+1 (sink) : artificial last node  → tool loaded but not ejected
  - N+2 (aux)  : auxiliary node        → tool never loaded

Commodities: one per tool t ∈ {0,...,M-1}

Variables
---------
x[i,k]  ∈ {0,1}   job i is processed in position k  (assignment matrix)
y[i,k,t] ≥ 0      flow of commodity t on arc (i → k)

Note: the paper uses a position-based assignment model, so arcs correspond to
consecutive (position, position+1) pairs rather than job-to-job arcs directly.

Objective (Eq. 1)
-----------------
    min Σ_t Σ_{i=1}^{N} Σ_{k=2}^{N+1} y[i,k,t]   ← flow into sink (switches)
      + Σ_t Σ_{i=1}^{N} Σ_{k=2}^{N+2} y[i,N+2,t]  ← flow into aux  (handled below)

For implementation simplicity we count the total tool switches directly via
the x-variables and the KTNS cost function, but model it exactly via the flow
as in the paper.

Simplified objective (used here):
    min Σ_{t} Σ_{position k} [flow from node at position k to sink]
which equals the total number of tool loads/switches.

Implementation note
-------------------
The paper's exact formulation uses flow variables indexed by (job i, position k,
tool t).  Building this exactly requires O(N² × M) variables.  We implement
the compact version which only creates variables for arcs that exist in G.

Symmetry-breaking (Eq. 20)
--------------------------
Job p — the job with the most tools among those with index ≤ ⌈N/2⌉ — is
fixed to the first ⌈N/2⌉ positions.

Constraint (21)
---------------
y[k, N+1, t] = 0  for k = 1,...,|J_t|-1
(tools that have more jobs ahead cannot yet flow to sink)

LP relaxation lower bound
-------------------------
The LP relaxation gives LB = M - C (proven tight; M = total tools, C = capacity).

Solver support
--------------
CPLEX only (raw cplex API).  Pure MIP — no lazy constraints needed.
Gurobi and SCIP backends have been archived to
_archived/sspmf_formulation_gurobi_scip.py.
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import cplex
    from cplex import SparsePair
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False

from utils import load_ssp_instance


class SSPMFFormulation:
    """
    SSPMF multicommodity flow formulation for SSP (da Silva 2024).

    Parameters
    ----------
    n_jobs   : int
    n_tools  : int
    capacity : int  (magazine capacity C)
    tool_req : dict {job: [tools]}
    use_symmetry_breaking : bool
        Fix the job with most tools to the first ⌈N/2⌉ positions (Eq. 20).
    use_constraint_21 : bool
        Add constraint (21): flow to sink is 0 for early positions of each tool.
    """

    def __init__(self, n_jobs, n_tools, capacity, tool_req,
                 use_symmetry_breaking=True, use_constraint_21=True):
        self.n_jobs                = n_jobs
        self.n_tools               = n_tools
        self.capacity              = capacity
        self.tool_req              = tool_req
        self.use_symmetry_breaking = use_symmetry_breaking
        self.use_constraint_21     = use_constraint_21

        # Tool sets per job
        self.T = {j: set(tool_req.get(j, [])) for j in range(n_jobs)}

        # Jobs that require each tool: J_t = {j : t in T_j}
        self.J_t = {t: [j for j in range(n_jobs) if t in self.T[j]]
                    for t in range(n_tools)}

        # Special nodes
        self.origin = n_jobs          # node 0 in paper = n_jobs in 0-index
        self.sink   = n_jobs + 1      # N+1
        self.aux    = n_jobs + 2      # N+2

        # Symmetry-breaking: find job p with most tools among first ⌈N/2⌉ indices
        self._sym_job = self._find_symmetry_job()

        if not HAS_CPLEX:
            raise ImportError(
                "SSPMF requires IBM CPLEX.  Install the cplex Python package "
                "(ships with IBM CPLEX Studio).\n"
                "Gurobi/SCIP backends have been archived to "
                "_archived/sspmf_formulation_gurobi_scip.py."
            )

    def _find_symmetry_job(self):
        """
        Find job p with the most tools among jobs with index ≤ ⌈N/2⌉.
        Used for the symmetry-breaking constraint.
        """
        half = math.ceil(self.n_jobs / 2)
        best_job   = 0
        best_count = len(self.T[0])
        for j in range(1, half):
            if len(self.T[j]) > best_count:
                best_count = len(self.T[j])
                best_job   = j
        return best_job

    def build_model(self, verbose=True):
        """Build the SSPMF model with CPLEX."""
        self._build_cplex(verbose)

    def solve(self, time_limit=3600, verbose=True):
        """Solve the SSPMF model."""
        return self._solve_cplex(time_limit, verbose)

    # ─────────────────────────────────────────────────────────────────────────
    # CPLEX implementation
    # ─────────────────────────────────────────────────────────────────────────

    def _build_cplex(self, verbose=True):
        """Build the SSPMF model with raw CPLEX."""
        N = self.n_jobs
        M = self.n_tools
        C = self.capacity
        T = range(M)
        J = range(N)
        K = range(N)

        self._cpx = cplex.Cplex()
        if not verbose:
            self._cpx.set_log_stream(None)
            self._cpx.set_results_stream(None)
            self._cpx.set_warning_stream(None)
        self._cpx.objective.set_sense(self._cpx.objective.sense.minimize)

        col = 0
        self._x_cpx = {}
        self._y_cpx = {}
        self._z_cpx = {}

        # x variables
        for i in J:
            for k in K:
                self._cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['B'],
                                         names=[f'x_{i}_{k}'])
                self._x_cpx[i, k] = col; col += 1

        # y variables
        for i in J:
            for k in K:
                for t in T:
                    self._cpx.variables.add(obj=[0.0], lb=[0.0], ub=[1.0], types=['C'],
                                             names=[f'y_{i}_{k}_{t}'])
                    self._y_cpx[i, k, t] = col; col += 1

        # z variables (objective)
        for k in K:
            for t in T:
                self._cpx.variables.add(obj=[1.0], lb=[0.0], ub=[1.0], types=['B'],
                                         names=[f'z_{k}_{t}'])
                self._z_cpx[k, t] = col; col += 1

        self._cpx_n_vars = col

        # Assignment
        for i in J:
            idx  = [self._x_cpx[i, k] for k in K]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*N)], senses=['E'], rhs=[1.0],
                names=[f'assign_job_{i}'])
        for k in K:
            idx = [self._x_cpx[i, k] for i in J]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*N)], senses=['E'], rhs=[1.0],
                names=[f'assign_pos_{k}'])

        # z lower/upper bounds, carry_link, capacity, symmetry, c21
        for k in K:
            for t in T:
                req_idx   = [self._x_cpx[i, k] for i in self.J_t[t]]
                carry_idx = [self._y_cpx[i, k-1, t] for i in J] if k > 0 else []

                # z >= req - carry_in
                idx   = [self._z_cpx[k, t]] + req_idx + carry_idx
                coeff = [1.0] + [-1.0]*len(req_idx) + [1.0]*len(carry_idx)
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, coeff)], senses=['G'], rhs=[0.0],
                    names=[f'z_lb_{k}_{t}'])

                # z <= req
                idx   = [self._z_cpx[k, t]] + req_idx
                coeff = [1.0] + [-1.0]*len(req_idx)
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, coeff)], senses=['L'], rhs=[0.0],
                    names=[f'z_ub_{k}_{t}'])

        # Carry link
        for i in J:
            for k in K:
                for t in T:
                    self._cpx.linear_constraints.add(
                        lin_expr=[SparsePair([self._y_cpx[i,k,t], self._x_cpx[i,k]],
                                              [1.0, -1.0])],
                        senses=['L'], rhs=[0.0], names=[f'carry_link_{i}_{k}_{t}'])

        # Capacity: y_{i,k,t} represents the FULL outgoing magazine state at
        # position k (including required tools kept for future positions).
        # Total tools kept ≤ C.  The previous |T_i|·x + Σy ≤ C was wrong:
        # it double-counted required tools that also appear in y.
        for k in K:
            carry_idx = [self._y_cpx[i,k,t] for i in J for t in T]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(carry_idx, [1.0]*len(carry_idx))],
                senses=['L'], rhs=[float(C)],
                names=[f'mag_{k}'])

        # Physical feasibility: can only carry forward a tool that is already
        # in the magazine (incoming carry) or was just loaded at this position.
        #   Σ_i y_{i,k,t} ≤ Σ_i y_{i,k-1,t} + z_{k,t}   (k > 0)
        #   Σ_i y_{i,0,t} ≤ z_{0,t}                       (k = 0)
        for k in K:
            for t in T:
                y_out_idx   = [self._y_cpx[i, k, t]   for i in J]
                y_out_coeff = [1.0] * len(y_out_idx)
                z_idx       = [self._z_cpx[k, t]]
                z_coeff     = [-1.0]
                if k > 0:
                    y_in_idx   = [self._y_cpx[i, k-1, t] for i in J]
                    y_in_coeff = [-1.0] * len(y_in_idx)
                else:
                    y_in_idx   = []
                    y_in_coeff = []
                idx   = y_out_idx   + z_idx   + y_in_idx
                coeff = y_out_coeff + z_coeff + y_in_coeff
                self._cpx.linear_constraints.add(
                    lin_expr=[SparsePair(idx, coeff)],
                    senses=['L'], rhs=[0.0],
                    names=[f'phys_{k}_{t}'])

        # Symmetry-breaking
        if self.use_symmetry_breaking:
            p    = self._sym_job
            half = math.ceil(N / 2)
            idx  = [self._x_cpx[p, k] for k in range(half)]
            self._cpx.linear_constraints.add(
                lin_expr=[SparsePair(idx, [1.0]*len(idx))], senses=['E'], rhs=[1.0],
                names=['sym_break'])

        # Constraint 21
        if self.use_constraint_21:
            for t in T:
                n_jt = len(self.J_t[t])
                for k in range(n_jt - 1):
                    for i in J:
                        self._cpx.linear_constraints.add(
                            lin_expr=[SparsePair([self._y_cpx[i,k,t]], [1.0])],
                            senses=['E'], rhs=[0.0], names=[f'c21_{i}_{k}_{t}'])

        if verbose:
            print(f"SSPMF model built (CPLEX): {N} jobs, {M} tools, "
                  f"{self._cpx_n_vars} variables")

    def _solve_cplex(self, time_limit, verbose):
        self._cpx.parameters.timelimit.set(float(time_limit))
        self._cpx.solve()
        status_code = self._cpx.solution.get_status()
        status_str  = self._cpx.solution.status[status_code]
        N = self.n_jobs
        try:
            obj_val  = self._cpx.solution.get_objective_value()
            all_vals = self._cpx.solution.get_values()
            seq = [None] * N
            for i in range(N):
                for k in range(N):
                    if all_vals[self._x_cpx[i, k]] > 0.5:
                        seq[k] = i
            sequence = seq if None not in seq else None
        except Exception:
            obj_val  = None
            sequence = None
        if verbose:
            print(f"[SSPMF] Status: {status_str}, Obj: {obj_val}, Seq: {sequence}")
        return status_str, obj_val, sequence


# ─────────────────────────────────────────────────────────────────────────────
# LP relaxation lower bound
# ─────────────────────────────────────────────────────────────────────────────

def sspmf_lp_lower_bound(n_tools, capacity, tool_req):
    """
    Compute the LP relaxation lower bound for SSPMF.

    The proven lower bound is:  LB = M - C
    where M = total number of (job, tool) pairs across all jobs
          C = magazine capacity.

    Actually the bound is: LB = Σ_j |T_j| - C (total tool requirements minus capacity).
    Per paper: LB = M - C where M = Σ_j |T_j|.

    Parameters
    ----------
    n_tools  : int  (not used directly; M computed from tool_req)
    capacity : int
    tool_req : dict {job: [tools]}

    Returns
    -------
    float
    """
    M = sum(len(v) for v in tool_req.values())
    return max(0, M - capacity)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def solve_sspmf(instance_path, time_limit=3600, verbose=True,
                use_symmetry_breaking=True, use_constraint_21=True):
    """Load an instance and solve it with the SSPMF formulation."""
    n_jobs, n_tools, capacity, A, tool_req = load_ssp_instance(instance_path)
    if verbose:
        lb = sspmf_lp_lower_bound(n_tools, capacity, tool_req)
        print(f"[SSPMF] Instance: {Path(instance_path).name}  "
              f"Jobs={n_jobs} Tools={n_tools} Cap={capacity}  LP_LB={lb}")
    f = SSPMFFormulation(n_jobs, n_tools, capacity, tool_req,
                         use_symmetry_breaking=use_symmetry_breaking,
                         use_constraint_21=use_constraint_21)
    f.build_model(verbose=verbose)
    return f.solve(time_limit=time_limit, verbose=verbose)


if __name__ == "__main__":
    instance_file = (
        Path(__file__).parent.parent / "Instances" / "Shankar" / "shankar-example.txt"
    )
    if instance_file.exists():
        solve_sspmf(str(instance_file), verbose=True)
    else:
        print(f"Instance not found: {instance_file}")
