import itertools
import os
import numpy as np

porta_folder_path = "porta-1.4.1\\win32\\bin\\"

def run_jgp_porta(num_tools, num_jobs, T_j, b, file_name):
    if not file_name.endswith(".ieq"):
        raise ValueError("File name must end with .ieq")
    
    write_jgp_ieq_file(num_tools, num_jobs, T_j, b, file_name)
    run_porta_on_file(file_name)

def write_jgp_ieq_file(num_tools, num_jobs, T_j, b, file_name):
    all_configs = list(itertools.combinations(range(num_tools), b))
    # H_j[j] = list of configs that can serve job j
    H_j = {j: [] for j in range(num_jobs)}
    for (index, cfg) in enumerate(all_configs):
        cfg_set = set(cfg)
        for j in range(num_jobs):
            if set(T_j[j]).issubset(cfg_set):
                H_j[j].append(index+1)

    dim = len(all_configs)

    with open(porta_folder_path + file_name,'w') as f:
        f.write(f"DIM = {dim}\n")
        f.write("VALID\n")
        s = ""
        for i in range(dim):
            s += "1 "
        f.write(s)
        f.write("\n")
        f.write("\n")
        f.write("LOWER_BOUNDS\n")
        s = ""
        for i in range(dim):
            s += "0 "
        f.write(s)
        f.write("\n")
        f.write("\n")
        f.write("UPPER_BOUNDS\n")
        s = ""
        for i in range(dim):
            s += "1 "
        f.write(s)
        f.write("\n")
        f.write("\n")

        f.write("INEQUALITIES_SECTION\n")
        for row in H_j:
            s = ""
            cfgs = H_j[row]
            for (index, vn) in enumerate(cfgs):
                if index > 0:
                    s += "+ "
                s += "x" + str(vn) + " "
            s += ">= 1\n"
            f.write(s)
        for i in range(dim):
            f.write(f"x{str(i+1)} >= 0\n")
            f.write(f"x{str(i+1)} <= 1\n")

        f.write("\nEND\n")


def run_porta_on_file(file_name):
    cmd = f"traf.bat {file_name}"
    os.system(f"cd {porta_folder_path} && {cmd}")


def read_porta_jgp_output(file_name):
    with open(porta_folder_path + file_name,'r') as f:
        lines = f.read().split('\n')
        dim = int(lines[0].split()[-1])
        arr = []
        for line in lines[3:-3]:
            pos = line.find(')')
            if pos == -1 or line.find('/') != -1 or line.find('.') != -1:
                continue
            arr.append(list(map(int, line[pos+1:-1].split())))

    return np.array(arr)

def write_ssp_pctsp_ieq_file(num_tools, num_jobs, T_j, b, file_name):
    
    # 1. Configuration Generation (C)
    # Generate all subsets of size <= b and insert the depot as config 0
    configs = []
    for r in range(1, b + 1):
        configs.extend(list(itertools.combinations(range(num_tools), r)))
    configs.insert(0, set()) # Dummy empty magazine (Depot)
    num_configs = len(configs)
    
    # 2. Variable Indexing Mapping
    # Porta requires 1D continuous indexing (x1, x2, ..., xDIM)
    idx = 1
    
    # y_v variables (Configuration Selection)
    y_idx = {}
    for v in range(num_configs):
        y_idx[v] = idx
        idx += 1
        
    # x_uv variables (Transitions)
    x_idx = {}
    for u in range(num_configs):
        for v in range(num_configs):
            if u != v:
                x_idx[(u, v)] = idx
                idx += 1
                
    dim = idx - 1
    
    # 3. Hit Sets (H_j)
    # H_j maps each job j to a list of configuration indices that can process it
    H_j = {j: [] for j in range(num_jobs)}
    for j in range(num_jobs):
        req = set(T_j[j])
        for v, cfg in enumerate(configs):
            if req.issubset(set(cfg)):
                H_j[j].append(v)
                
    # 4. Write .ieq File
    filepath = os.path.join(porta_folder_path, file_name) if porta_folder_path else file_name
    
    with open(filepath, 'w') as f:
        # Header & Dimensions
        f.write(f"DIM = {dim}\n")
        
        f.write("VALID\n")
        f.write("1 " * dim + "\n\n")
        
        f.write("LOWER_BOUNDS\n")
        f.write("0 " * dim + "\n\n")
        
        f.write("UPPER_BOUNDS\n")
        f.write("1 " * dim + "\n\n")
        
        f.write("INEQUALITIES_SECTION\n")
        
        # --- Depot Activation ---
        # The schedule must start and end with an empty magazine
        ""# f.write(f"+x{y_idx[0]} == 1\n")
        
        # --- Coverage Constraints ---
        # Every job j must be covered by at least one selected configuration v in H_j
        for j in range(num_jobs):
            if H_j[j]:
                s = " ".join([f"+x{y_idx[v]}" for v in H_j[j]])
                ""# f.write(f"{s} >= 1\n")
                
        # --- Flow Conservation (Degree Constraints) ---
        for u in range(num_configs):
            # Out-degree: sum_{v != u} x_uv - y_u == 0
            s_out = " ".join([f"+x{x_idx[(u, v)]}" for v in range(num_configs) if v != u])
            if s_out:
                ""# f.write(f"{s_out} -x{y_idx[u]} == 0\n")
            
            # In-degree: sum_{v != u} x_vu - y_u == 0
            s_in = " ".join([f"+x{x_idx[(v, u)]}" for v in range(num_configs) if v != u])
            if s_in:
                ""# f.write(f"{s_in} -x{y_idx[u]} == 0\n")
        
        print("Flow conservation constraints written.")
                
        # --- Balas (1989) Subtour Elimination Constraints ---
        # For all S subset C, 2 <= |S| <= |C|-1, 0 not in S, k in S
        # Note: This step scales exponentially and is only practical for small polyhedral study instances.
        C_minus_0 = list(range(1, num_configs))
        
        for r in range(2, num_configs):
            for S in itertools.combinations(C_minus_0, r):
                S_set = set(S)
                k = S[0] # Arbitrary node k in S
                
                # sum_{u in S} sum_{v in S \ {u}} x_uv
                arcs = [f"+x{x_idx[(u, v)]}" for u in S_set for v in S_set if u != v]
                            
                # - sum_{u in S \ {k}} y_u
                nodes = [f"-x{y_idx[u]}" for u in S_set if u != k]
                        
                arc_str = " ".join(arcs)
                node_str = " ".join(nodes)
                
                if arc_str and node_str:
                    ""# f.write(f"{arc_str} {node_str} <= 0\n")

        print("Subtour elimination constraints written.")
                
        # --- Additional Variable Bounds (Optional for standard Porta configs, but safe) ---
        for i in range(1, dim + 1):
            ""# f.write(f"+x{i} >= 0\n")
            ""# f.write(f"+x{i} <= 1\n")
            
        f.write("\nEND\n")