"""
Job Sequencing and Tool Switching Problem (SSP) - Instance Generator

This module generates random instances of the SSP following the methodology 
described in:

1. Crama, Y., Kolen, A.W.J., Oerlemans, A.G., & Spieksma, F.C.R. (1994)
   "Minimizing the Number of Tool Switches on a Flexible Machine"
   The International Journal of Flexible Manufacturing Systems, 6, 33-54.

2. Laporte, G., Salazar-González, J.J., & Semet, F. (2004)
   "Exact algorithms for the job sequencing and tool switching problem"
   IIE Transactions, 36:1, 37-45.

Reference: Crama et al. (1994), Section 4.1: "Generation of problem instances"
"""

import random
import numpy as np
from typing import Tuple, Set, List, Dict


class SSPInstanceGenerator:
    """
    Generator for random SSP instances following Crama et al. (1994).
    
    Instance parameters:
    - M: Number of tools
    - N: Number of jobs
    - C: Magazine capacity (max tools that can fit at once)
    - min_tools: Lower bound on the number of tools per job
    - max_tools: Upper bound on the number of tools per job
    """

    def __init__(self, seed: int = None):
        """
        Initialize the generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _generate_tool_set(self, 
                           job_id: int,
                           M: int,
                           min_tools: int,
                           max_tools: int,
                           existing_tool_sets: List[Set[int]],
                           max_attempts: int = 1000) -> Set[int]:
        """
        Generate a tool set for a job, ensuring no inclusions with previous jobs.
        
        Reference: Crama et al. (1994), Section 4.1
        "Next, a set Tj of tj distinct integers were drawn from the uniform 
        distribution over [1, M]: these integers denote the tools required by 
        job j, i.e., akj = 1 if and only if k is in Tj. Finally, we checked 
        whether Tj ⊆ Ti or Ti ⊆ Tj held for any i < j. If any of these 
        inclusions was found to hold, then the previous choice of Tj was 
        cancelled, and a new set Tj was generated."
        
        Args:
            job_id: Index of the current job
            M: Number of tools (indexed from 1 to M)
            min_tools: Minimum number of tools for this job
            max_tools: Maximum number of tools for this job
            existing_tool_sets: List of tool sets for previously generated jobs
            max_attempts: Maximum attempts before giving up
            
        Returns:
            Set of tools for this job
        """
        for attempt in range(max_attempts):
            # Draw tj from uniform distribution [min_tools, max_tools]
            tj = random.randint(min_tools, max_tools)
            
            # Draw tj distinct integers from [1, M]
            tool_set = set(random.sample(range(1, M + 1), tj))
            
            # Check if this tool set has inclusion relation with any previous set
            has_inclusion = False
            for prev_set in existing_tool_sets:
                # Check if tool_set ⊆ prev_set or prev_set ⊆ tool_set
                if tool_set.issubset(prev_set) or prev_set.issubset(tool_set):
                    has_inclusion = True
                    break
            
            if not has_inclusion:
                return tool_set
        
        # Fallback: return the last generated set if max attempts exceeded
        print(f"Warning: Max attempts ({max_attempts}) exceeded for job {job_id}. "
              "Returning last generated set.")
        return tool_set

    def generate_instance(self,
                         M: int,
                         N: int,
                         C: int,
                         min_tools: int,
                         max_tools: int) -> Tuple[np.ndarray, Dict]:
        """
        Generate a single random SSP instance.
        
        Reference: Crama et al. (1994), Section 4.1
        "Each random instance falls into one of 16 instance types, 
        characterized by the size (M, N) of the tool-job matrix and by the 
        value C of the capacity. For each problem size (M, N), 10 random 
        matrices A were generated. For each j = 1, 2, ..., N, the jth column 
        of A was generated as follows..."
        
        Args:
            M: Number of tools
            N: Number of jobs
            C: Magazine capacity (must satisfy C >= each job's tool requirement)
            min_tools: Minimum number of tools required per job
            max_tools: Maximum number of tools required per job
                      (must satisfy max_tools <= C for feasibility)
            
        Returns:
            Tuple of:
            - A: Tool-job matrix (M x N binary matrix where A[i,j]=1 if tool i 
                 is required for job j)
            - metadata: Dictionary containing instance information
        """
        if max_tools > C:
            raise ValueError(
                f"max_tools ({max_tools}) must be <= capacity C ({C}). "
                "This is required to ensure feasibility (no job requires more than C tools)."
            )
        
        # Initialize binary tool-job matrix
        A = np.zeros((M, N), dtype=int)
        
        # Generate tool sets for each job
        tool_sets = []  # List of sets, one per job
        
        for j in range(N):
            # Generate tool set for job j (columns are 0-indexed in code)
            T_j = self._generate_tool_set(
                job_id=j,
                M=M,
                min_tools=min_tools,
                max_tools=max_tools,
                existing_tool_sets=tool_sets
            )
            
            # Set corresponding entries in matrix to 1
            for tool_id in T_j:
                A[tool_id - 1, j] = 1  # Convert 1-indexed tools to 0-indexed
            
            tool_sets.append(T_j)
        
        # Remove null rows (rows with all zeros)
        # Reference: "Notice that this generation procedure does not a priori 
        # prevent the occurrence of null rows in the matrix. In practice, only 
        # two of the 40 matrices that we generated contained null rows"
        non_null_rows = np.any(A != 0, axis=1)
        A_filtered = A[non_null_rows]
        
        M_filtered = np.sum(non_null_rows)
        null_rows_removed = M - M_filtered
        
        metadata = {
            'M': M,                          # Original number of tools
            'M_after_filtering': M_filtered,  # Number of tools after removing null rows
            'N': N,                          # Number of jobs
            'C': C,                          # Magazine capacity
            'min_tools': min_tools,
            'max_tools': max_tools,
            'null_rows_removed': null_rows_removed,
            'tool_sets': tool_sets,          # List of tool sets for each job
            'method': 'crama'
        }
        
        return A_filtered, metadata

    def generate_overlapping_instance(self,
                                 M: int,
                                 N: int,
                                 C: int,
                                 min_tools: int,
                                 max_tools: int,
                                 overlap_factor: float = 0.65) -> Tuple[np.ndarray, Dict]:
        """
        Generate a single SSP instance with increased job overlap.

        This generator creates jobs from overlapping core tool groups to produce
        more shared tools across jobs than the Crama-style random generation.

        Args:
            M: Number of tools
            N: Number of jobs
            C: Magazine capacity (must satisfy C >= max_tools)
            min_tools: Minimum number of tools per job
            max_tools: Maximum number of tools per job
            overlap_factor: Fraction of each job's tools drawn from shared cores

        Returns:
            A: Tool-job matrix
            metadata: Metadata dictionary
        """
        if max_tools > C:
            raise ValueError(
                f"max_tools ({max_tools}) must be <= capacity C ({C}). "
                "This is required to ensure feasibility."
            )
        if overlap_factor <= 0 or overlap_factor > 1:
            raise ValueError("overlap_factor must be in (0, 1].")

        A = np.zeros((M, N), dtype=int)
        tool_sets = []
        tool_universe = list(range(1, M + 1))

        # Create a small number of shared overlapping tool cores.
        n_cores = min(3, max(1, N // 3))
        core_size = max(1, min_tools // 2 + 1)
        core_groups = []
        for _ in range(n_cores):
            size = min(M, core_size + random.randint(0, max(0, min_tools - 1)))
            core_groups.append(set(random.sample(tool_universe, size)))

        for j in range(N):
            t_j = random.randint(min_tools, max_tools)
            selected_cores = random.sample(core_groups, k=1 if n_cores == 1 else random.choice([1, 2]))
            core_tools = set().union(*selected_cores)
            shared_count = min(len(core_tools), max(1, int(round(overlap_factor * t_j))))
            shared_part = set(random.sample(list(core_tools), shared_count))

            T_j = set(shared_part)
            remaining_tools = [tool for tool in tool_universe if tool not in T_j]
            extra_needed = t_j - len(T_j)
            if extra_needed > 0 and remaining_tools:
                extra_count = min(extra_needed, len(remaining_tools))
                T_j.update(random.sample(remaining_tools, extra_count))

            # If the core selected more tools than needed, sample down to t_j
            if len(T_j) > t_j:
                T_j = set(random.sample(list(T_j), t_j))

            for tool_id in T_j:
                A[tool_id - 1, j] = 1
            tool_sets.append(T_j)

        metadata = {
            'M': M,
            'N': N,
            'C': C,
            'min_tools': min_tools,
            'max_tools': max_tools,
            'tool_sets': tool_sets,
            'method': 'overlapping',
            'overlap_factor': overlap_factor,
            'core_groups': [sorted(list(core)) for core in core_groups]
        }

        return A, metadata

    def generate_small_overlap_instances(self,
                                         num_instances: int = 10,
                                         max_total_size: int = 50,
                                         min_tools: int = 2,
                                         max_tools: int = None,
                                         C: int = None) -> List[Tuple[np.ndarray, Dict]]:
        """
        Generate a set of small SSP instances with high overlap between jobs.

        Small instances satisfy M * N <= max_total_size. Capacity can be any value
        greater than or equal to max_tools.
        """
        instances = []
        possible_pairs = [
            (M, N)
            for M in range(2, max_total_size + 1)
            for N in range(2, max_total_size + 1)
            if M * N <= max_total_size
        ]

        if not possible_pairs:
            raise ValueError("No valid (M, N) pairs satisfy the requested max_total_size.")

        for instance_num in range(num_instances):
            M, N = random.choice(possible_pairs)
            local_max_tools = max_tools if max_tools is not None else min(M, max(2, min_tools + 1))
            local_max_tools = min(local_max_tools, M)
            local_min_tools = min(min_tools, local_max_tools)
            if local_min_tools < 1:
                local_min_tools = 1

            local_C = C if C is not None else max(local_max_tools, random.randint(local_max_tools, max(M, local_max_tools)))
            A, metadata = self.generate_overlapping_instance(
                M=M,
                N=N,
                C=local_C,
                min_tools=local_min_tools,
                max_tools=local_max_tools,
                overlap_factor=0.75
            )
            metadata['instance_category'] = 'small_overlap'
            metadata['instance_number'] = instance_num + 1
            instances.append((A, metadata))

        return instances

    def generate_instance_set(self,
                             instance_types: List[Tuple[int, int, int, int, int]],
                             num_instances_per_type: int = 10,
                             include_null_rows: bool = False) -> List[Tuple[np.ndarray, Dict]]:
        """
        Generate a set of SSP instances of specified types.
        
        Reference: Crama et al. (1994), Table 1 and Section 4.1
        "There are 10 instances of each type."
        
        Args:
            instance_types: List of tuples (M, N, C, min_tools, max_tools)
            num_instances_per_type: Number of instances to generate per type
            include_null_rows: If True, do not remove null rows from matrices
            
        Returns:
            List of (tool_job_matrix, metadata) tuples
        """
        instances = []
        
        for M, N, C, min_tools, max_tools in instance_types:
            for instance_num in range(num_instances_per_type):
                A, metadata = self.generate_instance(M, N, C, min_tools, max_tools)
                metadata['instance_type'] = (M, N, C, min_tools, max_tools)
                metadata['instance_number'] = instance_num + 1
                instances.append((A, metadata))
        
        return instances

    @staticmethod
    def get_crama_instance_types() -> List[Tuple[int, int, int, int, int]]:
        """
        Return the 16 instance types used in Crama et al. (1994) computational experiments.
        
        Reference: Crama et al. (1994), Tables 1 and 2
        "The tool-job matrices are M × N matrices, where (M, N) is either 
        (10, 10), (20, 15), (40, 30), or (60, 40)."
        
        Each instance type is a tuple: (M, N, C, min_tools, max_tools)
        
        Table 1 parameters:
            (10,10):  min=2, max=4
            (20,15):  min=2, max=6
            (40,30):  min=5, max=15
            (60,40):  min=7, max=20
            
        Table 2 capacities (C1, C2, C3, C4):
            (10,10): 4, 5, 6, 7
            (20,15): 6, 8, 10, 12
            (40,30): 15, 17, 20, 25
            (60,40): 20, 22, 25, 30
        """
        instance_types = []
        
        problem_sizes = [(10, 10), (20, 15), (40, 30), (60, 40)]
        params = {
            (10, 10): {'min': 2, 'max': 4, 'capacities': [4, 5, 6, 7]},
            (20, 15): {'min': 2, 'max': 6, 'capacities': [6, 8, 10, 12]},
            (40, 30): {'min': 5, 'max': 15, 'capacities': [15, 17, 20, 25]},
            (60, 40): {'min': 7, 'max': 20, 'capacities': [20, 22, 25, 30]},
        }
        
        for M, N in problem_sizes:
            p = params[(M, N)]
            for C in p['capacities']:
                instance_types.append((M, N, C, p['min'], p['max']))
        
        return instance_types

    @staticmethod
    def save_instance(instance_matrix: np.ndarray,
                     metadata: Dict,
                     filename: str):
        """
        Save an instance to a file in a simple text format.
        
        Format:
            Line 1: M N C (number of tools, jobs, capacity)
            Line 2: min_tools max_tools
            Lines 3+: Binary matrix (one row per tool, one column per job)
        
        Args:
            instance_matrix: Tool-job matrix (M x N)
            metadata: Instance metadata dictionary
            filename: Output filename
        """
        M, N = instance_matrix.shape
        C = metadata['C']
        min_tools = metadata['min_tools']
        max_tools = metadata['max_tools']
        
        with open(filename, 'w') as f:
            # Header line
            f.write(f"{M} {N} {C}\n")
            f.write(f"{min_tools} {max_tools}\n")
            
            # Matrix
            for i in range(M):
                f.write(" ".join(str(instance_matrix[i, j]) 
                                for j in range(N)))
                f.write("\n")

    @staticmethod
    def load_instance(filename: str) -> Tuple[np.ndarray, Dict]:
        """
        Load an instance from a file.
        
        Args:
            filename: Input filename
            
        Returns:
            Tuple of (tool_job_matrix, metadata)
        """
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Parse header
        M, N, C = map(int, lines[0].strip().split())
        min_tools, max_tools = map(int, lines[1].strip().split())
        
        # Parse matrix
        matrix = []
        for i in range(2, 2 + M):
            row = list(map(int, lines[i].strip().split()))
            matrix.append(row)
        
        A = np.array(matrix, dtype=int)
        
        metadata = {
            'M': M,
            'N': N,
            'C': C,
            'min_tools': min_tools,
            'max_tools': max_tools,
        }
        
        return A, metadata


def main():
    """
    Example usage demonstrating instance generation.
    """
    print("=" * 70)
    print("Job Sequencing and Tool Switching Problem (SSP)")
    print("Random Instance Generator")
    print("=" * 70)
    print()
    
    # Initialize generator
    generator = SSPInstanceGenerator(seed=42)
    
    # Example 1: Generate a single instance
    print("Example 1: Generate a single instance")
    print("-" * 70)
    M, N, C = 10, 10, 5
    min_tools, max_tools = 2, 4
    
    A, metadata = generator.generate_instance(M, N, C, min_tools, max_tools)
    
    print(f"Instance parameters:")
    print(f"  Tools (M): {metadata['M']} → {metadata['M_after_filtering']} (after filtering null rows)")
    print(f"  Jobs (N): {metadata['N']}")
    print(f"  Capacity (C): {metadata['C']}")
    print(f"  Tools per job: [{metadata['min_tools']}, {metadata['max_tools']}]")
    print(f"  Null rows removed: {metadata['null_rows_removed']}")
    print()
    print("Tool-job matrix (rows=tools, columns=jobs):")
    print(A)
    print()
    
    # Example 2: Generate Crama et al. instance types
    print("Example 2: Generate all Crama et al. (1994) instance types")
    print("-" * 70)
    instance_types = SSPInstanceGenerator.get_crama_instance_types()
    print(f"Number of instance types: {len(instance_types)}")
    print(f"Instance types (M, N, C, min, max):")
    for i, (M, N, C, min_t, max_t) in enumerate(instance_types, 1):
        print(f"  {i:2d}. ({M:2d}, {N:2d}, {C:2d}, {min_t:2d}, {max_t:2d})")
    print()
    
    # Example 3: Generate a small set of instances
    print("Example 3: Generate a small set of instances (first 2 types, 2 instances each)")
    print("-" * 70)
    small_types = instance_types[:2]
    instances = generator.generate_instance_set(small_types, num_instances_per_type=2)
    
    for i, (A, meta) in enumerate(instances, 1):
        print(f"Instance {i}: M={meta['M']} → {meta['M_after_filtering']}, "
              f"N={meta['N']}, C={meta['C']}, "
              f"Tools required per job: {[len(ts) for ts in meta['tool_sets']]}")
    print()
    
    # Example 4: Save and load an instance
    print("Example 4: Save and load an instance")
    print("-" * 70)
    filename = "/Instances/ssp_example_instance.txt"
    generator.save_instance(A, meta, filename)
    print(f"Instance saved to: {filename}")
    
    A_loaded, meta_loaded = generator.load_instance(filename)
    print(f"Instance loaded successfully")
    print(f"Matrices match: {np.array_equal(A, A_loaded)}")
    print()
    
    print("=" * 70)
    print("Generation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
