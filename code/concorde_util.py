import numpy as np
import subprocess
from utils import compute_switch_cost
import os

CONCORDE_EXE = "./concorde/TSP/concorde"

def generate_distance_matrix(configs):
    n = len(configs)
    if n == 0:
        return np.array([])  # Return empty matrix for no configurations
    cap = len(configs[0])
    # Initialize matrix with zeros
    matrix = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(i + 1, n):
            cost = compute_switch_cost(configs[i], configs[j], cap)
            matrix[i][j] = matrix[j][i] = cost
    return matrix

def write_tsp_file(matrix, filename):
    n = len(matrix)
    # To find a Path instead of a Cycle, we add a dummy node (n+1)
    # distance from dummy to all other nodes is 0.
    dim_with_dummy = n + 1
    
    with open(filename, 'w') as f:
        f.write(f"NAME: config_tsp\n")
        f.write(f"TYPE: TSP\n")
        f.write(f"DIMENSION: {dim_with_dummy}\n")
        f.write(f"EDGE_WEIGHT_TYPE: EXPLICIT\n")
        f.write(f"EDGE_WEIGHT_FORMAT: FULL_MATRIX\n")
        f.write(f"EDGE_WEIGHT_SECTION\n")
        
        for i in range(dim_with_dummy):
            row = []
            for j in range(dim_with_dummy):
                if i == n or j == n: # Dummy node connections
                    row.append(0)
                else:
                    row.append(int(matrix[i][j]))
            f.write(" ".join(map(str, row)) + "\n")
        f.write("EOF\n")

def solve_hamiltonian_path(configs):
    # 1. Prep Matrix
    dist_matrix = generate_distance_matrix(configs)
    num_original_nodes = len(configs)
    
    # 2. Create Temp Files
    temp_tsp = 'temp_config.tsp'
    sol_file = temp_tsp.replace('.tsp', '.sol')
    write_tsp_file(dist_matrix, temp_tsp)

    # 3. Run Concorde
    try:
        # -s: silent; -o: output
        result = subprocess.run([CONCORDE_EXE, "-o", sol_file, temp_tsp], shell=True, check=True,capture_output=True, text=True)
        if result.returncode != 0:
            print("Concorde Error Output:", result.stderr)
            print("Concorde Standard Output:", result.stdout)
            raise RuntimeError(f"Concorde failed with return code {result.returncode}")
        
        # 4. Parse Solution
        with open(sol_file, 'r') as f:
            data = f.read().split()
            # The first number is the node count, followed by the tour
            full_tour = [int(x) for x in data[1:]]
            
        # 5. Convert Cycle to Path
        # The dummy node (index = num_original_nodes) breaks the cycle into a path
        dummy_idx = full_tour.index(num_original_nodes)
        # Shift the tour so the dummy is at the end, then remove it
        ham_path = full_tour[dummy_idx+1:] + full_tour[:dummy_idx]
        
        return ham_path

    finally:
        # Cleanup
        for ext in ['.tsp', '.sol', '.res', '.pul', '.sav', '.mas']: # Concorde generates extra files
            path = temp_tsp.replace('.tsp', ext)
            if os.path.exists(path):
                os.remove(path)
            path = 'O' + path
            if os.path.exists(path):
                os.remove(path)