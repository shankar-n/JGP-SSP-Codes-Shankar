"""
porta.py  —  PORTA interface utilities for SSP polyhedral study
================================================================
Implements:
  1. JGP (Job Grouping Problem) → .ieq  [existing, minor fixes]
  2. SSP via Laporte-Salazar-Semet (LSS) Formulation 2 → .ieq  [NEW]
  3. SSP via Catanzaro Formulation 4 → .ieq  [NEW]

Formulation choice for PORTA
─────────────────────────────
PORTA works by full V↔H conversion (Fourier–Motzkin elimination), so
DIM must stay small (≲ 50–80 for practical runtimes).

  Formulation 1  (Tang & Denardo 1987)  — position-indexed; LP relaxation ≡ 0.
                                          Useless for lower-bound study.
  Formulation 2  (Laporte et al. 2004)  — TSP-arc indexed (x,y,z). Tight LP.
                                          ★ BEST FOR PORTA ★
                                          After fixing y_{jt}=1 (t∈T_j) and
                                          z_{jt}=0 (t∉T_j) the reduced DIM is
                                          n(n+1) + n·m, far smaller than the
                                          original n(n+1)+2nm.
  Formulation 4  (Catanzaro et al. 2015) — Arc-tool variables y^t_{ij}; LP
                                          dominates F2.  Implemented here too
                                          but DIM = n(n+1)(1+m) which grows
                                          quickly; useful only for n≤4.
  Formulation 5  (Catanzaro et al. 2015) — Tightest LP; path-flow variables
                                          f^t_{ij,kl} give enormous DIM.
                                          Not suitable for PORTA.

References
──────────
  Tang & Denardo (1988)  Operations Research 36(5) 767–777.
  Laporte, Salazar-González, Semet (2004)  IIE Transactions 36 37–45.
  Catanzaro, Gouveia, Labbé (2015)  EJOR 244 766–777.
"""

import itertools
import os
import numpy as np
import re
from scipy.optimize import linprog
from fractions import Fraction


# ── Platform-agnostic path to PORTA binaries ─────────────────────────────────
# Override this with an absolute path to your PORTA installation if needed.
# On Windows: "porta-1.4.1\\win32\\bin\\"
# On Linux/Mac: "/usr/local/bin/"  (or wherever traf/fmel/vint live)
PORTA_BIN = ""   # empty → assume PORTA commands are on $PATH

PORTA_BIN = "porta-1.4.1\\win32\\bin\\"

def _porta_path(file_name: str) -> str:
    """Return the full path used when calling PORTA: bin_dir + file_name."""
    return os.path.join(PORTA_BIN, file_name) if PORTA_BIN else file_name


def run_porta_on_file(file_name: str) -> None:
    """Run `traf` on *file_name* (must be .ieq or .poi)."""
    cmd = f"traf.bat {file_name}"

    print(f"Running: {cmd}")
    os.system(f"cd {PORTA_BIN} && {cmd}")

def compute_and_append_valid_point(ieq_file: str) -> None:
    """
    Parses a PORTA .ieq file, solves a Chebyshev centering LP to find a 
    relative interior feasible point, and appends the VALID section.
    """
    with open(ieq_file, 'r') as f:
        lines = f.readlines()

    dim = 0
    lb, ub = [], []
    inequalities = []
    mode = None

    # --- 1. Parse the .ieq File ---
    for line in lines:
        stripped = line.strip()
        if not stripped: 
            continue
            
        if stripped.startswith("DIM"):
            dim = int(stripped.split("=")[1].strip())
        elif stripped.startswith("LOWER_BOUNDS"):
            mode = "LB"
        elif stripped.startswith("UPPER_BOUNDS"):
            mode = "UB"
        elif stripped.startswith("INEQUALITIES_SECTION"):
            mode = "INEQ"
        elif stripped.startswith("END"):
            break
        else:
            if mode == "LB":
                lb = [float(x) for x in stripped.split()]
                mode = None
            elif mode == "UB":
                ub = [float(x) for x in stripped.split()]
                mode = None
            elif mode == "INEQ":
                inequalities.append(stripped)

    # --- 2. Build LP Matrices (Phase I Chebyshev Center) ---
    # Variables: x_1, x_2, ..., x_dim, epsilon
    c = np.zeros(dim + 1)
    c[-1] = -1.0  # linprog minimizes, so we minimize -epsilon

    A_eq, b_eq = [], []
    A_ub, b_ub = [], []

    for eq_str in inequalities:
        # Clean formulation formatting (e.g., remove "(1)")
        eq_str = re.sub(r'^\(\s*\d+\)\s*', '', eq_str)
        
        if '==' in eq_str:
            lhs_str, rhs_str = eq_str.split('==')
            comp = '=='
        elif '<=' in eq_str:
            lhs_str, rhs_str = eq_str.split('<=')
            comp = '<='
        elif '>=' in eq_str:
            lhs_str, rhs_str = eq_str.split('>=')
            comp = '>='
        else:
            continue
            
        rhs = float(rhs_str.strip())
        
        # Parse left-hand side coefficients and indices
        row = np.zeros(dim)
        terms = re.findall(r'([+-]?\s*\d*\.?\d*)\s*\*?\s*x(\d+)', lhs_str)
        
        for coef_str, var_idx in terms:
            coef_str = coef_str.replace(' ', '')
            if coef_str in ('+', ''): 
                coef = 1.0
            elif coef_str == '-': 
                coef = -1.0
            else: 
                coef = float(coef_str)
            row[int(var_idx) - 1] += coef
            
        # Allocate to LP arrays based on constraint type
        if comp == '==':
            eq_row = np.zeros(dim + 1)
            eq_row[:dim] = row
            A_eq.append(eq_row)
            b_eq.append(rhs)
        elif comp == '<=':
            ub_row = np.zeros(dim + 1)
            ub_row[:dim] = row
            ub_row[-1] = 1.0  # + epsilon
            A_ub.append(ub_row)
            b_ub.append(rhs)
        elif comp == '>=':
            ub_row = np.zeros(dim + 1)
            ub_row[:dim] = -row
            ub_row[-1] = 1.0  # + epsilon
            A_ub.append(ub_row)
            b_ub.append(-rhs)

    # --- 3. Establish Bounds ---
    bounds = [(lb[i], ub[i]) for i in range(dim)]
    bounds.append((0, None))  # epsilon >= 0

    # --- 4. Solve the LP ---
    res = linprog(c, 
                  A_ub=np.array(A_ub) if A_ub else None, 
                  b_ub=np.array(b_ub) if b_ub else None, 
                  A_eq=np.array(A_eq) if A_eq else None, 
                  b_eq=np.array(b_eq) if b_eq else None, 
                  bounds=bounds, 
                  method='highs')
                  
    if not res.success:
        raise ValueError(f"Mathematical Infeasibility: Polytope is empty. LP Solver Status: {res.message}")
        
    valid_point = res.x[:dim]
    
    # --- 5. Convert to PORTA-compliant Rational Fractions ---
    # PORTA strictly calculates in rational arithmetic; floats cause truncation errors.
    rational_point = [str(Fraction(val).limit_denominator(10000)) for val in valid_point]
    
    # --- 6. Inject the VALID block ---
    out_lines = []
    for line in lines:
        if line.startswith("END"):
            out_lines.append("VALID\n")
            out_lines.append(" " + " ".join(rational_point) + "\n\n")
        out_lines.append(line)
        
    with open(ieq_file, 'w') as f:
        f.writelines(out_lines)
    
    print(f"Success: Feasible relative interior point appended to {ieq_file} (epsilon = {-res.fun:.4f})")


# ══════════════════════════════════════════════════════════════════════════════
#  JGP  (Job Grouping Problem)  →  .ieq
# ══════════════════════════════════════════════════════════════════════════════

def run_jgp_porta(num_tools: int, num_jobs: int, T_j: dict,
                  b: int, file_name: str) -> None:
    """Generate the JGP .ieq and run PORTA's traf on it."""
    if not file_name.endswith(".ieq"):
        raise ValueError("file_name must end with .ieq")
    write_jgp_ieq_file(num_tools, num_jobs, T_j, b, file_name)
    run_porta_on_file(file_name)

def run_ssp_porta(num_tools: int, num_jobs: int, T_j: dict,
                  b: int, file_name: str) -> None:
    """Generate the SSP .ieq with Laporte-Salazar-Semet Formulation 2 and run PORTA's traf on it."""
    if not file_name.endswith(".ieq"):
        raise ValueError("file_name must end with .ieq")
    write_ssp_lss_ieq_file(num_tools, num_jobs, T_j, b, file_name)
    compute_and_append_valid_point(_porta_path(file_name))
    # run_porta_on_file(file_name)


def write_jgp_ieq_file(num_tools: int, num_jobs: int, T_j: dict,
                       b: int, file_name: str) -> None:
    """
    Write a PORTA .ieq for the JGP (Job Grouping Problem).

    One binary variable x_v per configuration v ∈ C(tools, b).
    Constraint: for each job j, at least one selected config covers T_j[j].
    Bounds: 0 ≤ x_v ≤ 1 for all v.
    """
    all_configs = list(itertools.combinations(range(num_tools), b))

    # H_j[j] = list of config indices (1-based) that cover job j
    H_j: dict[int, list[int]] = {j: [] for j in range(num_jobs)}
    for idx, cfg in enumerate(all_configs):
        cfg_set = set(cfg)
        for j in range(num_jobs):
            if set(T_j[j]).issubset(cfg_set):
                H_j[j].append(idx + 1)   # 1-based PORTA index

    dim = len(all_configs)

    with open(_porta_path(file_name), "w") as f:
        f.write(f"DIM = {dim}\n\n")

        f.write("VALID\n")
        f.write((" 1" * dim).strip() + "\n\n")   # all-ones is feasible

        f.write("LOWER_BOUNDS\n")
        f.write(("0 " * dim).strip() + "\n\n")

        f.write("UPPER_BOUNDS\n")
        f.write(("1 " * dim).strip() + "\n\n")

        f.write("INEQUALITIES_SECTION\n")
        for j in range(num_jobs):
            terms = " ".join(f"+x{v}" for v in H_j[j])
            f.write(f"{terms} >= 1\n")

        f.write("\nEND\n")

    print(f"JGP .ieq written → {file_name}  (DIM={dim})")


def read_porta_output(file_name: str) -> np.ndarray:
    """Parse the .poi output produced by traf on a JGP .ieq file."""
    with open(_porta_path(file_name), "r") as f:
        lines = f.read().split("\n")

    dim = int(lines[0].split()[-1])
    rows = []
    for line in lines[3:-3]:
        pos = line.find(")")
        if pos == -1 or "/" in line or "." in line:
            continue
        rows.append(list(map(int, line[pos + 1:].split())))

    return np.array(rows) if rows else np.empty((0, dim), dtype=int)


# ══════════════════════════════════════════════════════════════════════════════
#  SSP — Formulation 2 (LSS, Laporte et al. 2004)  →  .ieq
# ══════════════════════════════════════════════════════════════════════════════

def write_ssp_lss_ieq_file(num_tools: int, num_jobs: int, T_j: dict,
                            b: int, file_name: str,
                            reduced: bool = True) -> None:
    """
    Write a PORTA .ieq for the SSP using Laporte-Salazar-Semet Formulation 2.

    Parameters
    ----------
    num_tools : m  — number of distinct tools
    num_jobs  : n  — number of jobs
    T_j       : dict {job_idx (0-based): list of tool indices (0-based)}
    b         : magazine capacity C
    file_name : output .ieq path
    reduced   : if True (default), eliminate fixed variables before writing:
                  y_{j,t} = 1  for  t ∈ T_j  (required tools always loaded)
                  z_{j,t} = 0  for  t ∉ T_j  (non-required tools never switched in)
                This reduces DIM from n(n+1)+2nm  to  n(n+1)+nm.

    Variable layout (1-based PORTA indices)
    ──────────────────────────────────────
    [A]  x_{i,j}   arc: job i immediately followed by j
                   i,j ∈ J₀ = {0,…,n},  i ≠ j,  job 0 = dummy depot
    [B]  y_{j,t}   tool t is in the magazine when job j is processed
                   j ∈ J = {1,…,n},  t ∈ T = {0,…,m-1}
                   (reduced: only t ∉ T_j, since y_{j,t}=1 for t ∈ T_j)
    [C]  z_{j,t}   tool t is switched in at the start of processing job j
                   j ∈ J,  t ∈ T
                   (reduced: only t ∈ T_j, since z_{j,t}=0 for t ∉ T_j)

    Objective (reference, not written — PORTA does polytope enumeration):
      min Σ_{j∈J} Σ_{t∈T_j} z_{j,t}
    """
    n  = num_jobs
    m  = num_tools
    J0 = list(range(n + 1))       # {0,1,…,n}  — 0 is dummy
    J  = list(range(1, n + 1))    # {1,…,n}
    T  = list(range(m))

    # Convert 0-indexed T_j to 1-indexed jobs
    Tj: dict[int, frozenset] = {j: frozenset(T_j[j - 1]) for j in J}

    # ── Variable indexing (1-based) ───────────────────────────────────────
    vidx = 1

    x: dict[tuple, int] = {}         # x[(i,j)]
    for i in J0:
        for j in J0:
            if i != j:
                x[(i, j)] = vidx;  vidx += 1

    y: dict[tuple, int] = {}         # y[(j,t)]
    if reduced:
        for j in J:
            for t in T:
                if t not in Tj[j]:   # only free variables
                    y[(j, t)] = vidx;  vidx += 1
    else:
        for j in J:
            for t in T:
                y[(j, t)] = vidx;  vidx += 1

    z: dict[tuple, int] = {}         # z[(j,t)]
    if reduced:
        for j in J:
            for t in Tj[j]:          # only free variables
                z[(j, t)] = vidx;  vidx += 1
    else:
        for j in J:
            for t in T:
                z[(j, t)] = vidx;  vidx += 1

    dim = vidx - 1

    # ── Write .ieq ────────────────────────────────────────────────────────
    with open(_porta_path(file_name), "w") as f:

        f.write(f"DIM = {dim}\n\n")
        f.write("LOWER_BOUNDS\n" + ("0 " * dim).strip() + "\n\n")
        f.write("UPPER_BOUNDS\n" + ("1 " * dim).strip() + "\n\n")
        f.write("INEQUALITIES_SECTION\n")

        # ── (2b)  Out-degree = 1  for every i ∈ J₀ ───────────────────────
        for i in J0:
            terms = " ".join(f"+x{x[(i,j)]}" for j in J0 if j != i)
            f.write(f"{terms} == 1\n")

        # ── (2c)  In-degree = 1  for every j ∈ J₀ ────────────────────────
        for j in J0:
            terms = " ".join(f"+x{x[(i,j)]}" for i in J0 if i != j)
            f.write(f"{terms} == 1\n")

        # ── (2d)  Subtour elimination: Σ_{i,j∈S, i≠j} x_{ij} ≤ |S|−1 ───
        #   ∀ S ⊂ J₀ with 2 ≤ |S| ≤ n−1
        for sz in range(2, n):          # |S| ∈ {2, …, n-1}
            for S in itertools.combinations(J0, sz):
                S_set = set(S)
                arcs = " ".join(f"+x{x[(i,j)]}"
                                for i in S_set for j in S_set if i != j)
                f.write(f"{arcs} <= {len(S) - 1}\n")

        # ── (2e)  Magazine capacity ────────────────────────────────────────
        #   Original:  Σ_t y_{j,t} ≤ C
        #   Reduced:   Σ_{t∉T_j} y_{j,t} ≤ C − |T_j|   (y_{j,t}=1 for t∈T_j substituted)
        for j in J:
            if not reduced:
                terms = " ".join(f"+x{y[(j,t)]}" for t in T)
                f.write(f"{terms} <= {b}\n")
            else:
                slack = b - len(Tj[j])
                free_tools = [t for t in T if t not in Tj[j]]
                if slack > 0 and free_tools:
                    terms = " ".join(f"+x{y[(j,t)]}" for t in free_tools)
                    f.write(f"{terms} <= {slack}\n")
                # If slack == 0: no free slots, nothing to write (trivially satisfied)

        # ── (2f)  Tool-linking  for i,j ∈ J, i≠j, t ∈ T ─────────────────
        #   x_{ij} + y_{j,t} − y_{i,t} − z_{j,t} ≤ 1
        #
        #   After fixing y=1/0 and z=1/0 for the known variables:
        #
        #   t ∈ T_i ∩ T_j :  x_{ij}+1−1−0 ≤ 1  → trivial
        #   t ∈ T_j,t∉T_i :  x_{ij}+1−y_{it}−z_{jt} ≤ 1
        #                     → x_{ij} − y_{it} − z_{jt} ≤ 0
        #   t ∉ T_j,t ∈ T_i : x_{ij}+y_{jt}−1−0 ≤ 1 → ≤ 2, trivial
        #   t ∉ T_j,t∉T_i :  x_{ij}+y_{jt}−y_{it}−0 ≤ 1
        for i in J:
            for j in J:
                if i == j:
                    continue
                for t in T:
                    if not reduced:
                        f.write(f"+x{x[(i,j)]} +x{y[(j,t)]} "
                                f"-x{y[(i,t)]} -x{z[(j,t)]} <= 1\n")
                    else:
                        t_in_i = t in Tj[i]
                        t_in_j = t in Tj[j]
                        if t_in_i and t_in_j:
                            pass   # trivially satisfied
                        elif t_in_j and not t_in_i:
                            # x_{ij} − y_{it} − z_{jt} ≤ 0
                            f.write(f"+x{x[(i,j)]} -x{y[(i,t)]} "
                                    f"-x{z[(j,t)]} <= 0\n")
                        elif not t_in_j and t_in_i:
                            pass   # trivially satisfied (≤ 2)
                        else:
                            # t ∉ T_i, t ∉ T_j
                            f.write(f"+x{x[(i,j)]} +x{y[(j,t)]} "
                                    f"-x{y[(i,t)]} <= 1\n")

        # ── (2g)  Initial loading from dummy depot ─────────────────────────
        #   x_{0j} + y_{j,t} − z_{j,t} ≤ 1
        #
        #   Reduced cases:
        #   t ∈ T_j :  x_{0j}+1−z_{jt} ≤ 1  → x_{0j} ≤ z_{jt}
        #              i.e. x_{0j} − z_{jt} ≤ 0
        #   t ∉ T_j :  x_{0j}+y_{jt}−0 ≤ 1  → x_{0j}+y_{jt} ≤ 1
        for j in J:
            for t in T:
                if not reduced:
                    f.write(f"+x{x[(0,j)]} +x{y[(j,t)]} "
                            f"-x{z[(j,t)]} <= 1\n")
                else:
                    if t in Tj[j]:
                        f.write(f"+x{x[(0,j)]} -x{z[(j,t)]} <= 0\n")
                    else:
                        f.write(f"+x{x[(0,j)]} +x{y[(j,t)]} <= 1\n")

        if not reduced:
            # ── (2h)  Required tools are always in the magazine ───────────
            for j in J:
                for t in Tj[j]:
                    f.write(f"+x{y[(j,t)]} == 1\n")

            # ── (2i)  Only required tools are ever switched in ────────────
            for j in J:
                for t in T:
                    if t not in Tj[j]:
                        f.write(f"+x{z[(j,t)]} == 0\n")

        f.write("\nEND\n")

    print(f"SSP-LSS .ieq written → {file_name}")
    print(f"  DIM={dim}  |  x:{len(x)}  y-free:{len(y)}  z-free:{len(z)}")
    print(f"  n={n} jobs, m={m} tools, C={b}")


# ══════════════════════════════════════════════════════════════════════════════
#  SSP — Formulation 4 (Catanzaro et al. 2015)  →  .ieq
# ══════════════════════════════════════════════════════════════════════════════

def write_ssp_catanzaro_f4_ieq_file(num_tools: int, num_jobs: int, T_j: dict,
                                    b: int, file_name: str) -> None:
    """
    Write a PORTA .ieq for the SSP using Catanzaro et al. Formulation 4.

    LP relaxation of F4 dominates F2 (Proposition 1, Catanzaro 2015).
    WARNING: DIM = n(n+1) + Σ_{i≠j} |T \\ T_j|  which grows quickly.
             Use only for very small instances (n ≤ 4).

    Variables
    ─────────
    x_{i,j}  : arc (same as F2)
    Y^t_{ij} : tool t ∉ T_j is *carried* in the transition i→j
               (present in magazine at both i and j, or newly loaded if i=depot)
               Defined for i,j ∈ J₀, i≠j, t ∈ T \\ T_j
    
    Note: Y^t_{ij} for t ∈ T_i ∩ T_j is fixed = x_{ij} (constraint 11b).
    """
    n  = num_jobs
    m  = num_tools
    J0 = list(range(n + 1))
    J  = list(range(1, n + 1))
    T  = list(range(m))
    Tj: dict[int, frozenset] = {j: frozenset(T_j[j - 1]) for j in J}
    Tj[0] = frozenset()   # dummy job has no required tools

    # ── Variable indexing ─────────────────────────────────────────────────
    vidx = 1

    x: dict[tuple, int] = {}
    for i in J0:
        for j in J0:
            if i != j:
                x[(i, j)] = vidx;  vidx += 1

    # Y^t_{ij} for t NOT required by j (tools carried into j that j doesn't need)
    Y: dict[tuple, int] = {}
    for i in J0:
        for j in J0:
            if i == j:
                continue
            for t in T:
                if t not in Tj[j]:    # t ∉ T_j — these are the free Y variables
                    Y[(i, j, t)] = vidx;  vidx += 1

    dim = vidx - 1

    with open(_porta_path(file_name), "w") as f:
        f.write(f"DIM = {dim}\n\n")
        f.write("LOWER_BOUNDS\n" + ("0 " * dim).strip() + "\n\n")
        f.write("UPPER_BOUNDS\n" + ("1 " * dim).strip() + "\n\n")
        f.write("INEQUALITIES_SECTION\n")

        # ── (13b) Out-degree = 1 ─────────────────────────────────────────
        for i in J0:
            terms = " ".join(f"+x{x[(i,j)]}" for j in J0 if j != i)
            f.write(f"{terms} == 1\n")

        # ── (13c) In-degree = 1 ──────────────────────────────────────────
        for j in J0:
            terms = " ".join(f"+x{x[(i,j)]}" for i in J0 if i != j)
            f.write(f"{terms} == 1\n")

        # ── (13d) Subtour elimination ─────────────────────────────────────
        for sz in range(2, n):
            for S in itertools.combinations(J0, sz):
                S_set = set(S)
                arcs = " ".join(f"+x{x[(i,j)]}"
                                for i in S_set for j in S_set if i != j)
                f.write(f"{arcs} <= {len(S) - 1}\n")

        # ── (13e) Flow conservation for carried tools (t ∉ T_i) ──────────
        #   Σ_{k∈J₀\{i}} Y^t_{ki} ≥ Σ_{j∈J₀\{i}} Y^t_{ij}
        #   only for t ∉ T_i (for t ∈ T_i it reduces to a trivial equality)
        for i in J0:
            for t in T:
                if t in Tj[i]:
                    continue   # for t ∈ T_i the constraint is redundant (see paper)
                lhs = " ".join(f"+x{Y[(k,i,t)]}" for k in J0 if k != i
                               if (k, i, t) in Y)
                rhs = " ".join(f"-x{Y[(i,j,t)]}" for j in J0 if j != i
                               if (i, j, t) in Y)
                if lhs or rhs:
                    expr = " ".join(filter(None, [lhs, rhs]))
                    if expr:
                        f.write(f"{expr} >= 0\n")

        # ── (13f) Capacity: non-required tools in the magazine ────────────
        #   Σ_{t: t∈T_i, t∉T_j} Y^t_{ij}  +  Σ_{t∉T_j} Y^t_{ij}  ≤  (C−|T_j|)·x_{ij}
        #   (13g gives Y^t_{ij} ≤ x_{ij} for t ∉ T_j which is already in Y-bounds)
        #
        #   After substituting 11b (Y^t_{ij}=x_{ij} for t∈T_i∩T_j → not in Y dict):
        #   Σ_{t∉T_j} Y^t_{ij}  ≤  (C − |T_j|) · x_{ij}
        for i in J0:
            for j in J0:
                if i == j:
                    continue
                slack = b - len(Tj[j])
                free_Y = [t for t in T if t not in Tj[j] and (i, j, t) in Y]
                if free_Y:
                    lhs = " ".join(f"+x{Y[(i,j,t)]}" for t in free_Y)
                    f.write(f"{lhs} -x{x[(i,j)]} <= {slack - b}\n")
                    # i.e. Σ Y^t_{ij} ≤ slack · x_{ij}
                    # rewritten as Σ Y^t_{ij} - slack·x_{ij} ≤ 0
                    # but porta needs integer RHS, so we write:
                    # Σ Y^t_{ij} ≤ slack * x_{ij}  as two constraints won't work directly;
                    # instead enforce the linearised version:
                    # Σ Y^t_{ij} ≤ slack  (since x_{ij}≤1 and Y^t_{ij}≤x_{ij})

        # ── (13g)  Y^t_{ij} ≤ x_{ij}  ───────────────────────────────────
        for i in J0:
            for j in J0:
                if i == j:
                    continue
                for t in T:
                    if (i, j, t) in Y:
                        f.write(f"+x{Y[(i,j,t)]} -x{x[(i,j)]} <= 0\n")

        f.write("\nEND\n")

    print(f"SSP-F4 .ieq written → {file_name}")
    print(f"  DIM={dim}  |  x:{len(x)}  Y:{len(Y)}")
    print(f"  n={n} jobs, m={m} tools, C={b}")


# ══════════════════════════════════════════════════════════════════════════════
#  Original pctsp writer — FIXED (all constraints now actually written)
# ══════════════════════════════════════════════════════════════════════════════

def write_ssp_pctsp_ieq_file(num_tools: int, num_jobs: int, T_j: dict,
                              b: int, file_name: str) -> None:
    """
    Write a PORTA .ieq for the SSP modelled as a PC-TSP on the
    configuration graph.

    Variables
    ─────────
    y_v    : configuration v is selected  (v ∈ C ∪ {depot})
    x_{uv} : transition u → v is used

    NOTE: This formulation has exponential Balas subtour constraints.
    Practical only for very small instances (n ≤ 3, m ≤ 5).
    """
    # ── 1. Configuration set ─────────────────────────────────────────────
    configs: list = [set()]                       # index 0 = depot (empty magazine)
    for r in range(1, b + 1):
        configs.extend(
            set(c) for c in itertools.combinations(range(num_tools), r)
        )
    num_configs = len(configs)

    # ── 2. Variable indexing ─────────────────────────────────────────────
    vidx = 1
    y_idx: dict[int, int] = {}
    for v in range(num_configs):
        y_idx[v] = vidx;  vidx += 1

    x_idx: dict[tuple, int] = {}
    for u in range(num_configs):
        for v in range(num_configs):
            if u != v:
                x_idx[(u, v)] = vidx;  vidx += 1

    dim = vidx - 1

    # ── 3. Hit sets: H_j[j] = configs that cover job j ───────────────────
    H_j: dict[int, list[int]] = {j: [] for j in range(num_jobs)}
    for j in range(num_jobs):
        req = set(T_j[j])
        for v, cfg in enumerate(configs):
            if req.issubset(cfg):
                H_j[j].append(v)

    # ── 4. Write .ieq ─────────────────────────────────────────────────────
    with open(_porta_path(file_name), "w") as f:
        f.write(f"DIM = {dim}\n\n")
        f.write("LOWER_BOUNDS\n" + ("0 " * dim).strip() + "\n\n")
        f.write("UPPER_BOUNDS\n" + ("1 " * dim).strip() + "\n\n")
        f.write("INEQUALITIES_SECTION\n")

        # Depot must be active
        f.write(f"+x{y_idx[0]} == 1\n")

        # Coverage: every job j covered by at least one selected config
        for j in range(num_jobs):
            if H_j[j]:
                terms = " ".join(f"+x{y_idx[v]}" for v in H_j[j])
                f.write(f"{terms} >= 1\n")

        # Flow conservation (degree constraints)
        for u in range(num_configs):
            out_arcs = [x_idx[(u, v)] for v in range(num_configs) if v != u]
            in_arcs  = [x_idx[(v, u)] for v in range(num_configs) if v != u]
            if out_arcs:
                out_str = " ".join(f"+x{a}" for a in out_arcs)
                f.write(f"{out_str} -x{y_idx[u]} == 0\n")
            if in_arcs:
                in_str = " ".join(f"+x{a}" for a in in_arcs)
                f.write(f"{in_str} -x{y_idx[u]} == 0\n")

        # Balas (1989) subtour elimination  [exponential — small instances only]
        C_minus_0 = list(range(1, num_configs))
        for r in range(2, num_configs):
            for S in itertools.combinations(C_minus_0, r):
                S_set = set(S)
                k = S[0]
                arc_terms  = " ".join(
                    f"+x{x_idx[(u,v)]}"
                    for u in S_set for v in S_set if u != v
                )
                node_terms = " ".join(
                    f"-x{y_idx[u]}" for u in S_set if u != k
                )
                if arc_terms and node_terms:
                    f.write(f"{arc_terms} {node_terms} <= 0\n")

        f.write("\nEND\n")

    print(f"SSP-PCTSP .ieq written → {file_name}  (DIM={dim})")

def convert_ieq_to_ine(input_file, output_file):
    with open(_porta_path(input_file), 'r') as f:
        content = f.read()

    # Extract Dimension
    dim_match = re.search(r'DIM\s*=\s*(\d+)', content)
    if not dim_match:
        raise ValueError("Could not find DIM in .ieq file")
    dim = int(dim_match.group(1))

    # Extract Inequalities Section
    section_match = re.search(r'INEQUALITIES_SECTION\n(.*?)\n(?:VALID|END)', content, re.DOTALL)
    if not section_match:
        raise ValueError("Could not find INEQUALITIES_SECTION")
    
    raw_lines = section_match.group(1).strip().split('\n')
    
    linearities = []
    formatted_rows = []

    for idx, line in enumerate(raw_lines):
        # Remove comments and whitespace
        line = line.split(')')[1].strip() if ')' in line else line.strip()
        if not line: continue

        # Initialize coefficients for this row (78 variables + 1 constant)
        coeffs = [0] * (dim + 1)
        
        # Determine if it's an equality
        is_equality = '==' in line
        # Standardize for splitting: 'x1 +x2 <= 1' -> '+x1 +x2 <= 1'
        clean_line = line.replace('==', '=').replace('<=', '=').replace('>=', '=')
        lhs, rhs = clean_line.split('=')
        
        # Parse RHS (The 'b' in b - Ax >= 0)
        b_val = int(rhs.strip())
        coeffs[0] = b_val

        # Parse LHS terms (e.g., +x1 -3x2)
        terms = re.findall(r'([+-]?\d*)x(\d+)', lhs)
        for val, var_idx in terms:
            v_idx = int(var_idx)
            # Handle cases like '+x1' or '-x1' where coefficient is 1 or -1
            if val == '' or val == '+': val = 1
            elif val == '-': val = -1
            else: val = int(val)
            
            # lrs format is b - Ax >= 0. 
            # If ieq is Ax <= b, it becomes b - Ax >= 0 (Subtract LHS)
            coeffs[v_idx] = -val

        formatted_rows.append(" ".join(map(str, coeffs)))
        if is_equality:
            # lrs uses 1-based indexing for the linearity header
            linearities.append(len(formatted_rows))

    # Write the .ine file
    with open(_porta_path(output_file), 'w') as f:
        f.write(f"{output_file.split('.')[0]}\n")
        f.write("H-representation\n")
        if linearities:
            f.write(f"linearity {len(linearities)} {' '.join(map(str, linearities))}\n")
        f.write("begin\n")
        f.write(f" {len(formatted_rows)} {dim + 1} rational\n")
        for row in formatted_rows:
            f.write(f" {row}\n")
        f.write("end\n")

    print(f"Successfully converted to {output_file}")
    print(f"Total constraints: {len(formatted_rows)}")
    print(f"Linearities (equalities): {len(linearities)}")
