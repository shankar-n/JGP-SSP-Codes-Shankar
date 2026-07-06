"""
Job Sequencing and Tool Switching Problem (SSP) - Instance Generator

Generates random SSP instances following the methodology described in:

  Crama, Y., Kolen, A.W.J., Oerlemans, A.G., & Spieksma, F.C.R. (1994).
  "Minimizing the Number of Tool Switches on a Flexible Machine."
  The International Journal of Flexible Manufacturing Systems, 6, 33-54.

  Laporte, G., Salazar-González, J.J., & Semet, F. (2004).
  "Exact algorithms for the job sequencing and tool switching problem."
  IIE Transactions, 36:1, 37-45.

File format
-----------
Instances are saved in the standard SSP text format expected by
load_ssp_instance() in utils.py::

    <n_jobs> <n_tools> <capacity>
    <binary matrix: n_tools rows x n_jobs columns, space-separated>

This is compatible with all other SSP solvers in this project.
"""

import random
import numpy as np
from typing import Tuple, Set, List, Dict, Optional


class SSPInstanceGenerator:
    """
    Random SSP instance generator following Crama et al. (1994).

    Parameters
    ----------
    M : int   – number of tools
    N : int   – number of jobs
    C : int   – magazine capacity
    min_tools : int – lower bound on tools per job  (must be <= C)
    max_tools : int – upper bound on tools per job  (must be <= C)
    """

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    # ── Core generation helpers ───────────────────────────────────────────────

    def _generate_tool_set(self,
                           job_id: int,
                           M: int,
                           min_tools: int,
                           max_tools: int,
                           existing_tool_sets: List[Set[int]],
                           max_attempts: int = 1000) -> Set[int]:
        """
        Draw a tool set for job ``job_id`` that has no inclusion relation with
        any previously accepted tool set.

        Reference: Crama et al. (1994), Section 4.1 —
        "Next, a set Tj of tj distinct integers were drawn from the uniform
        distribution over [1, M]… we checked whether Tj ⊆ Ti or Ti ⊆ Tj
        held for any i < j.  If any of these inclusions was found to hold,
        then the previous choice of Tj was cancelled, and a new set Tj was
        generated."
        """
        for _ in range(max_attempts):
            tj       = random.randint(min_tools, max_tools)
            tool_set = set(random.sample(range(1, M + 1), tj))

            if not any(
                tool_set.issubset(prev) or prev.issubset(tool_set)
                for prev in existing_tool_sets
            ):
                return tool_set

        # Do NOT fall back to an inclusion-violating set: both Crama (1994) and
        # Laporte (2004) guarantee the anti-inclusion property (so the
        # Tang-Denardo dominance rule never applies). A silent violation would
        # corrupt any benchmark claiming that property. (Changed 2026-07-02;
        # previously returned the last set with only a printed warning.)
        raise RuntimeError(
            f"Could not draw an inclusion-free tool set for job {job_id} after "
            f"{max_attempts} attempts (M={M}, tools per job in "
            f"[{min_tools},{max_tools}], {len(existing_tool_sets)} jobs placed). "
            "The parameter combination is too tight for the Crama/Laporte "
            "anti-inclusion scheme; enlarge M or the [min,max] interval."
        )

    # ── Crama-style generator ─────────────────────────────────────────────────

    def generate_instance(self,
                          M: int,
                          N: int,
                          C: int,
                          min_tools: int,
                          max_tools: int) -> Tuple[np.ndarray, Dict]:
        """
        Generate one random SSP instance à la Crama et al. (1994).

        Returns
        -------
        A        : ndarray (M_filtered × N) – tool-job incidence matrix
        metadata : dict with generation details
        """
        if max_tools > C:
            raise ValueError(
                f"max_tools ({max_tools}) must be ≤ capacity C ({C}): "
                "every job must fit in the magazine."
            )
        if min_tools < 1:
            raise ValueError("min_tools must be ≥ 1.")
        if min_tools > max_tools:
            raise ValueError("min_tools must be ≤ max_tools.")

        A         = np.zeros((M, N), dtype=int)
        tool_sets = []

        for j in range(N):
            T_j = self._generate_tool_set(j, M, min_tools, max_tools, tool_sets)
            for tool_id in T_j:
                A[tool_id - 1, j] = 1   # 1-indexed tools → 0-indexed rows
            tool_sets.append(T_j)

        # Remove null rows (tools never required by any job).
        # Crama et al. note: "only two of the 40 matrices … contained null rows".
        non_null = np.any(A != 0, axis=1)
        A_out    = A[non_null]
        M_out    = int(np.sum(non_null))

        metadata = {
            'M': M,
            'M_after_filtering': M_out,
            'N': N,
            'C': C,
            'min_tools': min_tools,
            'max_tools': max_tools,
            'null_rows_removed': M - M_out,
            'tool_sets': tool_sets,
            'method': 'crama',
        }
        return A_out, metadata

    # ── Overlapping generator ─────────────────────────────────────────────────

    def generate_overlapping_instance(self,
                                      M: int,
                                      N: int,
                                      C: int,
                                      min_tools: int,
                                      max_tools: int,
                                      overlap_factor: float = 0.65
                                      ) -> Tuple[np.ndarray, Dict]:
        """
        Generate an SSP instance with deliberately high job overlap.

        Jobs are built by sampling from a small number of shared "core" tool
        groups, producing more shared tools across jobs than the Crama-style
        random generation (which enforces the anti-inclusion constraint).

        Parameters
        ----------
        overlap_factor : float in (0, 1]
            Fraction of each job's tools drawn from shared cores.
        """
        if max_tools > C:
            raise ValueError(f"max_tools ({max_tools}) must be ≤ C ({C}).")
        if not 0 < overlap_factor <= 1:
            raise ValueError("overlap_factor must be in (0, 1].")

        A            = np.zeros((M, N), dtype=int)
        tool_sets    = []
        tool_universe = list(range(1, M + 1))

        # Build a small number of shared core groups
        n_cores    = min(3, max(1, N // 3))
        core_size  = max(1, min_tools // 2 + 1)
        core_groups = []
        for _ in range(n_cores):
            sz = min(M, core_size + random.randint(0, max(0, min_tools - 1)))
            core_groups.append(set(random.sample(tool_universe, sz)))

        for j in range(N):
            t_j = random.randint(min_tools, max_tools)
            k   = 1 if n_cores == 1 else random.choice([1, 2])
            core_tools  = set().union(*random.sample(core_groups, k))
            shared_n    = min(len(core_tools), max(1, round(overlap_factor * t_j)))
            T_j         = set(random.sample(list(core_tools), shared_n))

            remaining = [t for t in tool_universe if t not in T_j]
            extra     = t_j - len(T_j)
            if extra > 0 and remaining:
                T_j.update(random.sample(remaining, min(extra, len(remaining))))
            if len(T_j) > t_j:
                T_j = set(random.sample(list(T_j), t_j))

            for tool_id in T_j:
                A[tool_id - 1, j] = 1
            tool_sets.append(T_j)

        metadata = {
            'M': M, 'M_after_filtering': M,
            'N': N, 'C': C,
            'min_tools': min_tools, 'max_tools': max_tools,
            'null_rows_removed': 0,
            'tool_sets': tool_sets,
            'method': 'overlapping',
            'overlap_factor': overlap_factor,
            'core_groups': [sorted(g) for g in core_groups],
        }
        return A, metadata

    # ── Batch generation ──────────────────────────────────────────────────────

    def generate_instance_set(self,
                              instance_types: List[Tuple[int, int, int, int, int]],
                              num_instances_per_type: int = 10
                              ) -> List[Tuple[np.ndarray, Dict]]:
        """Generate a set of instances of the given types (Crama-style)."""
        results = []
        for M, N, C, min_t, max_t in instance_types:
            for idx in range(num_instances_per_type):
                A, meta = self.generate_instance(M, N, C, min_t, max_t)
                meta['instance_number'] = idx + 1
                results.append((A, meta))
        return results

    def generate_small_overlap_instances(self,
                                         num_instances: int = 10,
                                         max_total_size: int = 50,
                                         min_tools: int = 2,
                                         max_tools: Optional[int] = None,
                                         C: Optional[int] = None
                                         ) -> List[Tuple[np.ndarray, Dict]]:
        """Generate small high-overlap instances (M*N ≤ max_total_size)."""
        pairs = [(M, N)
                 for M in range(2, max_total_size + 1)
                 for N in range(2, max_total_size + 1)
                 if M * N <= max_total_size]
        if not pairs:
            raise ValueError("No valid (M, N) pairs for max_total_size.")

        results = []
        for k in range(num_instances):
            M, N       = random.choice(pairs)
            local_max  = min(max_tools, M) if max_tools else min(M, max(2, min_tools + 1))
            local_min  = max(1, min(min_tools, local_max))
            local_C    = C if C else max(local_max,
                                         random.randint(local_max, max(M, local_max)))
            A, meta = self.generate_overlapping_instance(
                M, N, local_C, local_min, local_max, overlap_factor=0.75)
            meta.update({'instance_category': 'small_overlap', 'instance_number': k + 1})
            results.append((A, meta))
        return results

    # ── Standard Crama instance types ────────────────────────────────────────

    @staticmethod
    def get_crama_instance_types() -> List[Tuple[int, int, int, int, int]]:
        """
        Return the 16 (M, N, C, min_tools, max_tools) tuples from
        Crama et al. (1994), Tables 1 & 2.

        Problem sizes and capacities::

            (10, 10): C ∈ {4, 5, 6, 7},   t ∈ [2, 4]
            (20, 15): C ∈ {6, 8, 10, 12},  t ∈ [2, 6]
            (40, 30): C ∈ {15, 17, 20, 25}, t ∈ [5, 15]
            (60, 40): C ∈ {20, 22, 25, 30}, t ∈ [7, 20]
        """
        params = {
            (10, 10): {'min': 2, 'max': 4,  'capacities': [4, 5, 6, 7]},
            (20, 15): {'min': 2, 'max': 6,  'capacities': [6, 8, 10, 12]},
            (40, 30): {'min': 5, 'max': 15, 'capacities': [15, 17, 20, 25]},
            (60, 40): {'min': 7, 'max': 20, 'capacities': [20, 22, 25, 30]},
        }
        types = []
        for (M, N), p in params.items():
            for C in p['capacities']:
                types.append((M, N, C, p['min'], p['max']))
        return types

    # ── Save / load ───────────────────────────────────────────────────────────

    @staticmethod
    def save_instance(instance_matrix: np.ndarray,
                      metadata: Dict,
                      filename: str) -> None:
        """
        Save an instance in the standard SSP text format.

        Format (compatible with utils.load_ssp_instance)::

            <n_jobs> <n_tools> <capacity>
            <n_tools rows, each with n_jobs 0/1 values>

        Parameters
        ----------
        instance_matrix : ndarray (n_tools × n_jobs)
        metadata        : dict containing at least 'C', 'N'
        filename        : output path
        """
        # FIX: header must be  N  M  C  (jobs first, tools second)
        # because load_ssp_instance reads tokens[0]=J, tokens[1]=T, tokens[2]=C.
        M_out, N = instance_matrix.shape   # M_out = tools after filtering, N = jobs
        C        = metadata['C']

        with open(filename, 'w') as fh:
            fh.write(f"{N} {M_out} {C}\n")   # jobs  tools  capacity
            for row in instance_matrix:
                fh.write(" ".join(map(str, row)) + "\n")

    @staticmethod
    def load_instance(filename: str) -> Tuple[np.ndarray, Dict]:
        """
        Load an instance saved by save_instance().

        Returns (A, metadata) where A has shape (n_tools × n_jobs).
        """
        tokens = []
        with open(filename) as fh:
            for line in fh:
                tokens.extend(int(x) for x in line.split() if x.strip())

        N, M, C = tokens[0], tokens[1], tokens[2]   # jobs, tools, capacity
        A = np.array(tokens[3:], dtype=int).reshape((M, N))

        metadata = {'M': M, 'M_after_filtering': M, 'N': N, 'C': C,
                    'min_tools': None, 'max_tools': None}
        return A, metadata

    # ── Convenience: matrix → T_j dict ───────────────────────────────────────

    @staticmethod
    def matrix_to_tool_req(A: np.ndarray) -> Dict[int, List[int]]:
        """
        Convert a tool-job incidence matrix (n_tools × n_jobs) to a
        per-job tool requirement dict  {job_idx: [tool_idx, ...]}.
        """
        n_tools, n_jobs = A.shape
        return {j: [t for t in range(n_tools) if A[t, j] == 1]
                for j in range(n_jobs)}
