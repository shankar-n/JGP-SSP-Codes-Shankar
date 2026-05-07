import itertools

import numpy as np

def load_ssp_instance(filepath):
        """
        Load an SSP instance from the standard text format.

        Format (first non-blank line):  J  T  C
        Followed by a T × J (tools × jobs) binary incidence matrix.

        Returns
        -------
        J : int   — number of jobs
        T : int   — number of tools
        C : int   — magazine capacity  (b)
        A : ndarray shape (T, J)  — incidence matrix  A[t, j] = 1 iff job j needs tool t
        """
        with open(filepath, 'r') as fh:
            tokens = fh.read().split()
        tokens = [int(x) for x in tokens if x.strip()]
        J, T_dim, C = tokens[0], tokens[1], tokens[2]
        A = np.array(tokens[3:], dtype=int).reshape((T_dim, J))
        # Per-job tool requirement list
        T_j = {j: [t for t in range(T_dim) if A[t, j] == 1]
            for j in range(J)}
        return J, T_dim, C, A, T_j


def detect_0blocks(A_matrix):
        """
        Return a dict  tool -> list of (start_col, end_col) tuples
        for every maximal consecutive-zero span in each tool row.
        """
        T, J = A_matrix.shape
        blocks = {}
        for t in range(T):
            blocks[t] = []
            in_block, start = False, None
            for j in range(J):
                if A_matrix[t, j] == 0:
                    if not in_block:
                        in_block, start = True, j
                else:
                    if in_block:
                        blocks[t].append((start, j - 1))
                        in_block = False
            if in_block:
                blocks[t].append((start, J - 1))
        return blocks

def compute_switch_cost(cfg_a, cfg_b, cap):
        """Switch cost between two configurations (0 if either is DUMMY)."""
        return cap - len(set(cfg_a).intersection(set(cfg_b)))

def compute_ssp_cost(route, cap):
        """Compute switch cost from a route."""
        cost = 0
        prev_cfg = None
        for (cfg, j) in route:
            if cfg == "DUMMY":
                continue
            if prev_cfg is not None:
                cost += compute_switch_cost(prev_cfg, cfg, cap)
            prev_cfg = cfg
        return cost

def compute_ktns(sequence, tool_req, cap):
        """
        Apply the KTNS policy to a job sequence and return total switch cost.

        Parameters
        ----------
        sequence : list of job indices (0-based)
        tool_req : dict {job: [tools]}
        cap      : magazine capacity

        Returns
        -------
        total switch cost (int)
        configs : ndarray of shape (n, m)  — list of magazine configurations
        """
        magazine = set()
        configs = []
        total_cost = 0

        for pos, job in enumerate(sequence):
            needed = set(tool_req[job])
            # Tools to add
            to_add = needed - magazine
            # While over capacity, evict the tool needed farthest in future
            while len(magazine) + len(to_add) > cap:
                # Find future needs for every tool in magazine \ needed
                candidates = magazine - needed
                def next_use(t):
                    for k in range(pos + 1, len(sequence)):
                        if t in tool_req[sequence[k]]:
                            return k
                    return len(sequence)  # never needed again → evict first
                evict = max(candidates, key=next_use)
                magazine.discard(evict)
            magazine.update(to_add)
            configs.append(list(magazine))
            total_cost += len(to_add)   # each tool added = 1 switch

        return (total_cost, np.array(configs))

def run_brute_force_TSP_on_configs(configs):
        n = len(configs)
        if(n == 0):
            return (0, [])
        b = len(configs[0])
        dist = np.zeros((n,n))
        
        for i in range(n):
            for j in range(i,n):
                xx = compute_switch_cost(configs[i],configs[j],b)
                dist[i][j] = xx
                dist[j][i] = xx
        
        possible_routes = list(itertools.combinations(range(n), n))
        min_c = 1e9
        min_routes = []
        for route in possible_routes:
            cost = 0
            for i in range(1,n):
                cost += dist[route[i]][route[i-1]]
            if min_c > cost:
                min_c = cost
                min_routes = [route]
            elif min_c == cost:
                min_routes.append(route)
            else:
                continue
        return (min_c, min_routes)