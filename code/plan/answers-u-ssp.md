### Non-Compact ILP Formulation

Let $\mathcal{C}$ be the complete, unrestricted set of all possible tool repository configurations, where each configuration $C_v \in \mathcal{C}$ satisfies the tool magazine capacity constraint $|C_v| \le b$. Let $0 \in \mathcal{C}$ designate the dummy configuration representing the empty magazine at the start and end of the production schedule. Let $d(u,v) = b - |C_u \cap C_v|$ be the number of tool switches required to transition from configuration $u$ to configuration $v$. Let $H_j = \{v \in \mathcal{C} \mid T_j \subseteq C_v\}$ denote the subset of configurations containing all required tools $T_j$ to process job $j \in J$.

**Decision Variables:**

- $y_v \in \{0,1\}$: 1 if configuration $v \in \mathcal{C}$ is selected, 0 otherwise.
- $x_{uv} \in \{0,1\}$: 1 if configuration $v \in \mathcal{C}$ is visited immediately after configuration $u \in \mathcal{C}$, 0 otherwise.

To correctly eliminate disjoint subtours without the invalid bounds of the standard GSEC (which fails when y_v = 0), we must apply the exact Prize Collecting Traveling Salesman Problem (PCTSP) subtour elimination constraints formulated by Balas (1989).

**Formulation:**

$$
\begin{aligned}
\min \quad & \sum_{u \in \mathcal{C}} \sum_{v \in \mathcal{C} \setminus \{u\}} d(u,v) x_{uv} \\
\text{s.t.} \quad & \sum_{v \in H_j} y_v \ge 1 \quad \forall j \in J \\
& \sum_{v \in \mathcal{C} \setminus \{u\}} x_{uv} = y_u \quad \forall u \in \mathcal{C} \\
& \sum_{u \in \mathcal{C} \setminus \{v\}} x_{uv} = y_v \quad \forall v \in \mathcal{C} \\
& \sum_{u \in S} \sum_{v \in S \setminus \{u\}} x_{uv} \le \sum_{u \in S \setminus \{k\}} y_u \quad \forall S \subset \mathcal{C}, 2 \le |S| \le |\mathcal{C}|-1, 0 \notin S, \forall k \in S \\
& y_0 = 1 \\
& x_{uv} \in \{0,1\} \quad \forall u, v \in \mathcal{C}, u \neq v \\
& y_v \in \{0,1\} \quad \forall v \in \mathcal{C}
\end{aligned}
$$

### Restricted Master Problem (RMP)

Let $V \subset \mathcal{C}$ be a restricted subset of configurations currently available in the RMP, with $0 \in V$. The integrality constraints are relaxed to allow the generation of dual variables for the column generation framework. The exact Prize Collecting Traveling Salesman Problem (PCTSP) subtour elimination constraints rigorously prevent the formation of disjoint subtours among selected configurations.

$$
\begin{aligned}
\min \quad & \sum_{i \in V} \sum_{j \in V \setminus \{i\}} d(i,j) x_{ij} \\
\text{s.t.} \quad & \sum_{i \in V \cap H_r} y_i \ge 1 \quad \forall r \in J \quad (\text{Dual: } \pi_r \ge 0) \\
& \sum_{j \in V \setminus \{i\}} x_{ij} = y_i \quad \forall i \in V \quad (\text{Dual: } \alpha_i) \\
& \sum_{j \in V \setminus \{i\}} x_{ji} = y_i \quad \forall i \in V \quad (\text{Dual: } \beta_i) \\
& \sum_{i \in S} \sum_{j \in S \setminus \{i\}} x_{ij} \le \sum_{i \in S \setminus \{k\}} y_i \quad \forall S \subset V, 2 \le |S| \le |V|-1, 0 \notin S, \forall k \in S \quad (\text{Dual: } \mu_{S,k} \le 0) \\
& y_0 = 1 \\
& x_{ij} \ge 0 \quad \forall i, j \in V, i \neq j \\
& y_i \ge 0 \quad \forall i \in V
\end{aligned}
$$

### Pricing Subproblem

The column generation step must identify a new configuration $c \in \mathcal{C} \setminus V$ capable of improving the RMP. Topologically, introducing a new configuration node $c$ between two existing active nodes $u, w \in V$ requires introducing the routing variables $x_{uc}$ and $x_{cw}$. Because the new configuration $c$ is dynamically generated, it does not yet belong to any previously identified subtour subset $S$. Consequently, the dual variables $\mu_{S,k}$ evaluate to zero for the newly generated incident edges.

**Decision Variables:**

- $z_t \in \{0,1\}$: 1 if tool $t \in T$ is selected for the new configuration $c$, 0 otherwise.
- $v_r \in \{0,1\}$: 1 if job $r \in J$ is covered by the new configuration $c$, 0 otherwise.

The exact distance from an existing configuration $u \in V$ to the generated configuration $c$ natively evaluates to $d(u,c) = b - \sum_{t \in C_u} z_t$. The Pricing Subproblem is formulated as a Prize-Collecting Set Union Knapsack Problem seeking to minimize the reduced cost:

$$
\begin{aligned}
\min_{z, v} \quad & \min_{u, w \in V} \left[ \left( b - \sum_{t \in C_u} z_t \right) + \left( b - \sum_{t \in C_w} z_t \right) - \alpha_u - \beta_w \right] - \sum_{r \in J} \pi_r v_r \\
\text{s.t.} \quad & v_r \le z_t \quad \forall r \in J, \forall t \in T_r \\
& \sum_{t \in T} z_t \le b \\
& z_t \in \{0,1\} \quad \forall t \in T \\
& v_r \in \{0,1\} \quad \forall r \in J
\end{aligned}
$$

### Relation to The Job Grouping Problem (JGP)

**Is the optimal configurations of SSP the optimal configurations of JGP?**

Strictly, **no**. The Job Grouping Problem (JGP) and the Job Sequencing and Tool Switching Problem (SSP) operate on fundamentally different topological evaluations of tool transitions, despite sharing the same underlying variables.

#### 1.1 A Counterexample (The 6-Job, 6-Tool Ring)

Consider a cyclic tool-requirement topology (a ring) for a flexible machine with a magazine capacity of $b = 3$. Let the set of tools be $T = \{1, 2, 3, 4, 5, 6\}$ and the set of jobs be $J = \{J_1, J_2, J_3, J_4, J_5, J_6\}$. The tool requirements perfectly form a ring:

- $T_1 = \{1, 2\}$
- $T_2 = \{2, 3\}$
- $T_3 = \{3, 4\}$
- $T_4 = \{4, 5\}$
- $T_5 = \{5, 6\}$
- $T_6 = \{6, 1\}$

**The JGP Optimal Solution (Discrete Batches):**
Because any union of two distinct jobs requires at least 3 tools ($|T_i \cup T_j| \ge 3$ for all $i \neq j$).

**JGP Optimum:** 3 discrete batches.

- **Optimal Configurations:** $\mathcal{C}_{JGP}^* = \big\{ \{1,2,3\}, \{3,4,5\}, \{1,5,6\}, \big\}$.
- **Total Setups (if executed as discrete batches):** The machine flushes and loads 2 tools 2 times, totaling 4 tool switches.

**The SSP Optimal Solution (Continuous Routing via KTNS):**
If we sequence the jobs continuously around the ring: $J_1 \to J_2 \to J_3 \to J_4 \to J_5 \to J_6$, the KTNS policy smoothly transitions between.

1. Load $\{1,2,3\}$ for $J_1$.
2. Transition to $J_2$: keep as it is (0 switch).
3. Transition to $J_3$: keep tool 1, drop 2, load 4. Config: $\{1, 3, 4\}$ (1 switch).
4. Transition to $J_4$: keep tool 1, drop 3, load 5. Config: $\{1,4,5\}$ (1 switch).
5. Transition to $J_5$: keep tool 1, drop 4, load 6. Config: $\{1,5,6\}$ (1 switch).
6. Transition to $J_6$: keep as it is (0 switch).

- **SSP Optimum:** The sequence perfectly rolls around the ring, incurring only **3 total tool switches**.

The JGP formulation tries to use a minimal number of configurations but there is no limit on the number of configurations in the SSP. Therefore, the optimal solution of the SSP is not the optimal solution of the JGP.

#### when will it be the the case that Optimal JGP configurations = SSP optimal configurations?

Let $J$ be the set of jobs, $T$ the set of tools, and $b$ the magazine capacity. For any job $j \in J$, let $T_j \subseteq T$ be its requisite tool set ($|T_j| \le b$).

Let $J$ be the set of jobs, $T$ the set of tools, and $b$ the magazine capacity. For any job $j \in J$, let $T_j \subseteq T$ be its requisite tool set ($|T_j| \le b$).

In the SSP, the absolute minimum number of tool switches required to transition directly from job $i$ to job $j$ is given by the Tang and Denardo lower bound metric:

$$d_{LB}(i,j) = \max\{0, |T_i \cup T_j| - b\}$$

Let $B_x$ and $B_y$ be two optimal, disjoint JGP batches such that their respective configuration clusters are strictly disjoint, $C_x \cap C_y = \emptyset$. For any job $i \in B_x$ and $j \in B_y$, their individual tool sets are also strictly disjoint ($T_i \cap T_j = \emptyset$). By the inclusion-exclusion principle:

$$|T_i \cup T_j| = |T_i| + |T_j| - |T_i \cap T_j| = |T_i| + |T_j|$$

Substituting this into the transition bound yields:

$$d_{LB}(i,j) = \max\{0, |T_i| + |T_j| - b\}$$

If $|T_i| + |T_j| \le b$, then $d_{LB}(i,j) = 0$. This mathematically proves despite the JGP batches being strictly disjoint, the machine does **not** incur a maximum penalty. It can hold both $T_i$ and $T_j$ simultaneously, forming an overlapping configuration across two batches without a single tool switch.

To mathematically force the optimal continuous configurations of the SSP ($\mathcal{C}_{SSP}^{*}$) to strictly equal the discrete batches of the JGP ($\mathcal{C}_{JGP}^{*}$), we must eliminate the possibility of a bridging configuration.

**Theorem (Strict Equivalence Condition):**
Let $\mathcal{B}^* = \{B_1, \dots, B_K\}$ be the optimal JGP partition, with optimal batch configurations $C_k = \bigcup_{j \in B_k}T_j$.

$\mathcal{C}_{SSP}^{*} = \mathcal{C}_{JGP}^{*}$ holds if and only if for every pair of consecutive jobs $(i, j)$ in the optimal SSP sequence where $i \in B_x$ and $j \in B_y$ ($x \neq y$), the following holds:

$$|T_i \cup T_j| > b$$

_Proof:_
Let $W_r$ be the active magazine configuration when processing job $i \in B_x$. By definition, $T_i \subseteq W_r$ and $|W_r| \le b$.
To transition to job $j \in B_y$, the new configuration $W_{r+1}$ must satisfy $T_j \subseteq W_{r+1}$.
The number of tool switches required for this transition is $|W_{r+1} \setminus W_r|$.

To prevent a complete flush, the SSP must utilize a bridging configuration, meaning it must pre-load tools for $j$ into $W_r$. The available empty space in $W_r$ while processing $i$ is exactly $b - |T_i|$. Therefore, the maximum number of tools from $T_j$ that can be pre-loaded into $W_r$ is bounded by $b - |T_i|$.

The remaining tools of $T_j$ that cannot fit into $W_r$ must be inserted during the transition. The number of forced insertions is:

$$|W_{r+1} \setminus W_r| \ge |T_j| - (b - |T_i|) = |T_i| + |T_j| - b$$

If the Strict Equivalence Condition holds, $|T_i \cup T_j| > b$. In the worst-case of disjoint batches ($T_i \cap T_j = \emptyset$), $|T_i| + |T_j| > b$, meaning the right-hand side of the inequality is strictly positive. The free space $b - |T_i|$ is insufficient to hold $T_j$, mathematically proving that an overlapping bridging configuration cannot exist. The machine is forced to flush exactly $|T_i| + |T_j| - b$ tools, preserving the discrete boundaries of the JGP. $\blacksquare$

---

### Mathematical Bounds: JGP to SSP

Let $Z_{JGP}$ be the optimal number of batches in the Set Covering formulation. Let $Z_{SSP}$ be the optimal total number of tool switches for the continuous routing.

**Theorem (JGP Lower Bound):**

$$Z_{SSP} \ge Z_{JGP} - 1$$

_Proof:_
Let $\Omega = \{W_1, W_2, \dots, W_m\}$ be the ordered sequence of distinct maximal configurations traversed by the optimal SSP schedule. Because this sequence successfully processes all jobs in $J$, the set $\Omega$ is a mathematically valid covering of $J$ satisfying the capacity constraint $|W_r| \le b$.

By definition, $Z_{JGP}$ is the absolute minimum cardinality of any feasible cover. Therefore, the number of distinct configurations in the SSP sequence must satisfy $m \ge Z_{JGP}$ (if $m < Z_{JGP}$, $\Omega$ would be a valid JGP cover smaller than the optimum, which is a contradiction).

To process a continuous sequence of $m$ distinct configurations, the machine must execute $m - 1$ transitions. Because $W_r$ and $W_{r+1}$ are distinct maximal configurations, $W_{r+1} \setminus W_r \neq \emptyset$. Thus, every transition requires at least 1 tool switch:

$$Z_{SSP} \ge \sum_{r=1}^{m-1} |W_{r+1} \setminus W_r| \ge \sum_{r=1}^{m-1} 1 = m - 1 \ge Z_{JGP} - 1$$

$\blacksquare$

**Theorem (Heuristic JGP Upper Bound):**

$$Z_{SSP} \le b \cdot (Z_{JGP} - 1)$$

_Proof:_
Let $\mathcal{B}^* = \{B_1, \dots, B_{Z_{JGP}}\}$ be the optimal JGP batches. We construct a naive SSP sequence by processing all jobs batch by batch: $B_1 \to B_2 \to \dots \to B_{Z_{JGP}}$.

The maximum possible number of tool switches between any two consecutive batches $B_k$ and $B_{k+1}$ occurs when their requisite tool sets are completely disjoint ($C_k \cap C_{k+1} = \emptyset$). Under this condition, the machine must drop all tools and load the new batch, requiring exactly $|C_{k+1}|$ switches. Since $|C_{k+1}| \le b$, the maximum transition cost is $b$.

Across the entire sequence of $Z_{JGP}$ batches, there are exactly $Z_{JGP} - 1$ inter-batch boundaries. Therefore, the total number of tool switches for this unoptimized sequence is bounded by $b \cdot (Z_{JGP} - 1)$. Because $Z_{SSP}$ is the global minimum, $Z_{SSP} \le b \cdot (Z_{JGP} - 1)$. $\blacksquare$

**Corollary (The JGP $\alpha$-Approximation):**
_Solving the discrete JGP and directly sequencing its batches guarantees a deterministic $b$-approximation for the continuous SSP._

_Proof:_
Let $Z_{Heur}$ be the tool switching cost of the JGP-derived schedule. From the Upper Bound theorem, $Z_{Heur} \le b \cdot (Z_{JGP} - 1)$. From the Lower Bound theorem, $Z_{JGP} - 1 \le Z_{SSP}$.

Substituting the lower bound yields:

$$Z_{Heur} \le b \cdot Z_{SSP} \implies \frac{Z_{Heur}}{Z_{SSP}} \le b$$

Thus, the approximation ratio $\alpha$ is exactly bounded by the magazine capacity $b$. $\blacksquare$

1. Hierarchy and Tightness of Lower Bounds for the SSP
   To rigorously evaluate the Job Sequencing and Tool Switching Problem (SSP), establishing tight lower bounds is critical, as exact approaches often struggle with the problem's NP-hard combinatorial space. The literature features several bounding techniques derived from both the continuous routing formulations (ILP relaxations) and discrete set-covering models like the Job Grouping Problem (JGP).
   Ranking the Lower Bounds by Tightness (Weakest to Strongest):
   Tang & Denardo LP Relaxation (LB*{TD}): The original position-based Integer Linear Programming (ILP) formulation by Tang and Denardo (1988) provides an exceptionally weak linear relaxation. In fact, its LP relaxation invariably yields a lower bound of exactly zero.
   The Sweeping Bound (LB*{SW}): Introduced by Tang and Denardo, this bound generates a sequence of mutually incompatible job seeds. It is defined as LB*{SW} = \max{G, \lceil S_m / C \rceil}, where G is the number of mutually incompatible groups, S_m is the total tool requirement, and C is the magazine capacity.
   The Modified Sweeping Bound (LB*{MSW}): This improves LB*{SW} by incorporating the \lceil S_m / C \rceil logic iteratively at each step of the sweeping procedure. While LB\_{MSW} \ge LB*{SW}, it still deteriorates rapidly on sparse instances where capacity constraints are loose.
   The Set Packing Bound (LB*{SP}): By taking the dual of the JGP set covering formulation and adding integrality constraints, one obtains a set packing problem. LB*{SP} computes the maximum number of pairwise incompatible jobs. Thus, LB*{SP} \le LB*{CG}.
   Laporte et al. (2004) LP Relaxation (LB*{Laporte}): To overcome the zero-bound flaw of Tang and Denardo, Laporte et al. proposed a TSP-based ILP formulation. While it successfully solves instances up to 25 jobs using branch-and-bound, its pure LP relaxation remains generally poor for larger topologies.
   Catanzaro et al. (2015) ILP LP Relaxations (LB*{Catanzaro}): Catanzaro et al. developed formulations (specifically Formulation 5) that are provably tighter than Laporte's model. By including 1-arc inequalities and specific cut inequalities, their LP relaxation bounds increase by up to 20% compared to base formulations, providing the tightest known bounds derived directly from a continuous routing ILP.
   The Column Generation LP Relaxation (LB*{CG}): The tightest established combinatorial bound in the literature is obtained by solving the continuous LP relaxation of the JGP Set Covering formulation via Column Generation. Crama and Oerlemans computationally demonstrated that the gap between the LP relaxation of the JGP and the optimal integer JGP value is strictly less than 1 for virtually all tested instances.
   Synthesis of Tightness:
   When benchmarking new SOTA exact algorithms, the LB*{CG} (from the discrete JGP space) and LB\_{Catanzaro} (from the continuous SSP space) serve as the absolute apex of lower-bounding rigour.
2. Upper Bounds: Generating SSP Heuristics via JGP Configurations
   Can you generate heuristics for SSP using JGP optimal configurations? Yes. In the literature, this strategy is formally known as the (JGP, GSP) Decomposition Approach. Because the JGP identifies an optimal set of maximal tool configurations (often called "pallets" or "groups"), these discrete configurations can be used as static macro-nodes to construct a continuous SSP sequence.
   The process operates in two phases:
   The Job Grouping Problem (JGP): Modelled as a unicost Set Covering Problem, the JGP is solved to find the minimum number of tool pallets covering all jobs.
   The Group Sequencing Problem (GSP): The pallets obtained from the JGP are sequenced intact. The GSP routes these groups using either a local "one job only look-ahead" approach or a global "all jobs look-ahead" TSP framework to minimize the tool switches across the boundaries of the pallets.

SOTA Refinement: Enumerating All Optimal JGP Solutions A traditional binary programming approach typically yields only one optimal JGP solution. However, a state-of-the-art methodology utilizing Stirling numbers can enumerate all optimal solutions to the JGP. By extracting the entire set of optimal JGP covers, the GSP can evaluate every possible pallet combination as job sets, significantly tightening the resulting upper bound by finding the specific discrete cover that natively maximizes continuous tool retention via the Keep Tool Needed Soonest (KTNS) policy. 3. Metaheuristic: Warm-Starting SSP with JGP Configurations

Evolution of SSP Heuristics and JGP Decompositions
The literature exhibits a distinct evolutionary trajectory for solving the SSP heuristically, moving from early myopic TSP reductions to exact Set Covering decompositions, and currently culminating in advanced metaheuristics.
3.1 Early Constructive and Graph-Based Heuristics (1988–1995)
Early approaches attempted to avoid the NP-hard sequencing problem by using constructive clustering.
TSP-Based Reductions: Tang and Denardo (1988) formulated the SSP on a complete graph where edge weights represented an upper bound on tool switches, solving it as a TSP. However, this method is fundamentally myopic, accounting only for the interaction of two parts at a time without a global view of the sequence.
The "Super Task" Heuristic: Privault and Finke (1995) proposed an adaptation of a partitioning algorithm to model the tooling problem as a k-server problem. Their heuristic gathers jobs sharing common tools into "Super Tasks" (capacity-feasible clusters) until the magazine capacity is saturated. These Super Tasks are then routed using a shortest-edge TSP heuristic,. While computationally cheap and useful when solutions must be found quickly, it suffers from severe batch rigidity.
3.2 The Classical (JGP, GSP) Decomposition (1994–2006)
To formalize the clustering process, Crama and Oerlemans (1994) introduced a rigorous two-phase approach that solves the JGP as a Set Covering Problem,.
Phase I (JGP): The JGP is formulated as a unicost set covering problem to find the minimum number of tool pallets covering all jobs,. Because enumerating all maximal feasible subsets is intractable for large instances, Column Generation is used to solve the LP relaxation of the JGP, which generates exceptionally strong lower bounds (often equal to the optimal integer value).
Phase II (GSP): The pallets generated by the JGP are sequenced intact via the Group Sequencing Problem (GSP). Salonen et al. (2006) confirmed that this sequential decomposition performs "remarkably well" for larger instances. The GSP is solved using an Asymmetric TSP (ATSP) formulation, adopting either a local "one job only look-ahead" paradigm or a global "all jobs look-ahead" optimization paradigm to sequence the pallets.

Using the discrete boundaries of the JGP directly as an SSP schedule limits performance because it prevents fractional tool "rolling" across distant sequence positions. To bridge this gap, SOTA methodologies leverage JGP configurations as warm-start seeds for advanced metaheuristics. Because the JGP provides a mathematically sound upper bound, its optimal (or near-optimal) configurations are extensively used in the literature to generate "warm start" heuristics for the SSP.
3.3 SOTA Refinement: Enumerating Optimal JGP Bases (2015)
Burger et al. (2015) addressed the Color Print Scheduling Problem (CPSP), which is isomorphic to the SSP,. They noted a critical weakness in the standard (JGP, GSP) decomposition: standard binary programming yields only one optimal JGP cover.
Stirling Number Enumeration: Burger et al. designed a method utilizing Stirling numbers to enumerate all optimal solutions to the JGP,.
KTNS Maximization: By extracting the entire set of alternative optimal JGP covers, the GSP can evaluate every possible pallet combination. This significantly tightens the resulting upper bound by finding the specific discrete cover that natively maximizes continuous tool retention via the KTNS policy across the sequence.

4. The Topological Flaw: Batch Rigidity
   Despite the mathematical rigor of the (JGP, GSP) decomposition, it contains a fatal topological flaw for sparse instances. By rigidly locking jobs inside their designated JGP batches (pallets), the algorithm explicitly prevents the KTNS policy from carrying fractional tool requirements across distant sequence positions,.
   The discrete boundaries of the JGP act as artificial walls. If job i \in B_x and job j \in B_y share tools, but the GSP routing places B_x and B_y far apart in the sequence, their continuous tool overlap is lost. The discrete set-covering geometry is entirely blind to the continuous smoothing potential of the KTNS policy.

5. SOTA Metaheuristic Integration: Dissolving the Boundaries
   To achieve true State-of-the-Art (SOTA) performance, modern operations research dictates that the (JGP, GSP) decomposition must not be used as a final schedule. Instead, it must serve strictly as a highly fit, deterministic warm-start seed for continuous local search metaheuristics. The goal is to leverage the global clustering optimality of the JGP while systematically dissolving its discrete boundaries.
   5.1 Memetic Algorithms (MA)

Standard Genetic Algorithms initialized with randomized noise suffer from slow convergence or become trapped in local optima. Amaya et al. (2008, 2012) established that Memetic Algorithms (combining population-based search with local improvement) significantly outperform basic GAs.
Mechanism: An MA utilizes alternating position crossover and a mutation operator based on Random Block Insertion. The local search relies on steepest-ascent hill climbing and the KTNS policy.
JGP Seeding: By injecting the exact optimal configurations from the JGP into the elite initial population, the MA's local search operators can dedicate all computational effort exclusively to refining inter-batch boundaries, bypassing the exponential time required to discover basic capacity-feasible clusters.

Standard GAs initializing with random sequences often suffer from slow convergence or trap in poor local optima.
JGP-Seeded Initial Population: You can construct a highly fit initial population by taking the sequences derived from the (JGP, GSP) decomposition. If you enumerate multiple optimal JGP covers, each unique GSP sequence can serve as a distinct elite chromosome in the initial GA population.
The Memetic Approach (Amaya et al.): Amaya et al. (2008) demonstrated that a Memetic Algorithm (MA) combining a Genetic Algorithm with local search (e.g., steepest-ascent hill climbing and Tabu Search) significantly outperforms standard GAs. By seeding such an MA with JGP-derived sequences, the crossover and mutation operators can focus strictly on refining the boundaries between the optimally packed pallets, rather than wasting computational effort discovering basic capacity-feasible clusters.

5.2 Clustering Search (CS) and BRKGA
Chaves et al. (2016) proposed a SOTA method combining Clustering Search (CS) with a Biased Random Key Genetic Algorithm (BRKGA).
Mechanism: The algorithm identifies promising search space clusters generated by the BRKGA and intensifies the search in those regions using Variable Neighborhood Descent (VND),.
JGP Seeding: Rather than forcing the BRKGA to autonomously discover capacity-feasible clusters from randomized keys, injecting the JGP optimal covers directly into the BRKGA's reference set guarantees that the Clustering Search immediately anchors on the optimal topological regions of the job-tool incidence matrix.

Chaves et al. (2016) utilized a Biased Random Key Genetic Algorithm (BRKGA) integrated with Clustering Search (CS) to identify promising regions of the search space, subsequently applying Variable Neighborhood Descent (VND) for intensification.
Instead of relying on the BRKGA to autonomously discover these promising clusters from scratch, injecting the optimal configurations from the JGP directly into the reference set of the BRKGA guarantees that the Clustering Search immediately focuses on the most mathematically sound regions of the job-tool incidence geometry.
5.3 Iterated Local Search (ILS) and 1-Block Grouping
Paiva and Carvalho (2017) demonstrated that a tailored ILS metaheuristic consistently outperforms the CS+BRKGA,,.
1-Block Grouping (1BG-SSP): Building on the observation by Crama et al. (1994) that the number of tool switches correlates to the number of 1-blocks in the Tool-Job matrix, Paiva and Carvalho introduced a specialized local search. The 1BG-SSP randomly selects rows (tools) and attempts to contiguously group 1-blocks by moving columns (jobs) using a best-insertion fashion evaluated by KTNS,.
Application to JGP: Applying 1BG-SSP directly to the boundaries of a concatenated JGP schedule natively dissolves the rigid batch structures, smoothing the matrix into an optimal continuous SSP trajectory.
5.4 Adaptive Large Neighborhood Search (ALNS)
Beezão et al. (2017) successfully applied ALNS to schedule identical parallel machines with tooling constraints, outperforming previous heuristics,. ALNS operates by repeatedly applying destroy and repair operators,. Because the single-machine SSP is a subproblem of the IPMTC, their ALNS framework—which incorporates specific destroy and repair operators—is highly relevant and provides a SOTA benchmark. ALNS is exceptionally suited to dissolving the boundaries of a JGP-warm-started solution.

6. Proposed Novel SOTA Architectures
   To push beyond the current literature for your monograph, I propose the following mathematically rigorous, Machine Learning (ML)-augmented methodologies that bridge the JGP and SSP directly.

Proposal A: JGP-Seeded Neural-ALNS
Initialization: Solve the JGP via Column Generation to extract the optimal pallets, and sequence them via GSP to form the base trajectory.
Targeted Boundary Destroy Operator: Standard ALNS utilizes a random removal procedure. I propose a Boundary Destroy Operator that preferentially targets and removes jobs situated precisely at the edges of the JGP batches. These boundaries are where the heuristic transition penalty approaches the capacity limit b.

Let the optimal JGP batches be $\mathcal{B}^* = {B_1, \dots, B_K}$. When these batches are sequenced via the Group Sequencing Problem (GSP), the transition cost between any two adjacent batches $B_x$ and $B_y$ is $d(x,y) = \max{0, |C_x \cup C_y| - b}$, where $C_x$ and $C_y$ are the respective tool configurations. Because the JGP forces intra-batch jobs to share a common configuration, the vast majority of tool switches occur strictly at the inter-batch boundaries. By designing a "Boundary Destroy Operator" that removes jobs exclusively at the transition edges, you are mathematically targeting the exact coordinates in the sequence where the theoretical worst-case penalty (up to $b$ switches per boundary) occurs.

KTNS-Greedy Repair: The removed boundary jobs are reinserted using a dynamic metric that evaluates continuous tool overlap across the entire sequence. By pulling a job out of its rigid JGP cluster and inserting it centrally into another, the discrete boundaries are mathematically dissolved.
RL-Guided Operator Selection: Implement Q-Learning to dynamically manage the selection weights of various destroy/repair operators based on their real-time objective function value improvements.

The integration of Q-Learning for Adaptive Operator Selection (AOS) in metaheuristics is a established paradigm. Karimi-Mamaghan et al. (2022) exhaustively review this, denoting it as Q-Learning Credit Assignment (QLCA). In QLCA, the Q-values associated with different destroy/repair operators are updated dynamically during the search based on the reward (e.g., the reduction in total tool switches).

Recommendation: Ensure you formulate the Q-learning update rule explicitly in your paper (e.g., defining the state space as the current optimality gap or boundary density, and the action space as the operator pool) to maintain mathematical rigour.

GCNN-Guided Adaptive Large Neighborhood Search (Neural-ALNS) Instead of accepting the GSP sequence as the final solution, we use it strictly as a warm-start for an ALNS framework.
Initialization: Solve the JGP LP relaxation to obtain fractional configurations. Convert to integer batches and solve the GSP (via TSP) to get the initial sequence \mathcal{S}\_0.
Neural Destruction: Train a Graph Convolutional Neural Network (GCNN) on the bipartite job-tool incidence graph. The GCNN evaluates the boundaries between the sequenced JGP batches. It predicts the probability that a job j located at the boundary of batch B_k would yield a higher continuous KTNS retention if "destroyed" and shifted into the adjacent batch B\_{k+1}.

Graph Representation: Modeling the problem as a bipartite graph (with job nodes and tool nodes connected by requirement edges) is the correct architecture for Graph Neural Networks in combinatorial optimization. Gasse et al. (2019) demonstrated SOTA results using bipartite GCNNs for exact combinatorial optimization (specifically for learning branching policies).
The Predictive Oracle: Using a GCNN as a heuristic oracle to guide local search avoids the computational bottleneck of exact evaluation. However, the phrase "predicts the probability that a job... would yield a higher continuous KTNS retention" requires careful framing. The GCNN should be framed as predicting the marginal utility of displacing a node in the bipartite graph, formulating the task as a node-classification or edge-prediction problem.

Repair: Reinsert the destroyed jobs using a dynamic programming repair operator that maximizes the continuous Tool Overlap Density. Why this is SOTA: This mathematically bridges the discrete set-covering bounds with continuous routing. It utilizes the mathematically proven LB\_{CG} tightness for global structure, but uses a Neural Oracle to perform targeted local dissolution of the boundaries, bypassing the exponential neighborhood evaluation of standard ALNS.

Proposal A1 ?? : JGP-Seeded Adaptive Large Neighborhood Search (ALNS)
To overcome the rigidity of the (JGP, GSP) decomposition and establish a new SOTA benchmark not currently formalized in the literature, we must integrate the discrete set-covering initialization with continuous local search.
Initialization: Solve the JGP to optimality (or near-optimality via Column Generation) to generate the optimal subset of discrete configurations \mathcal{C}\_{JGP}^\*.
TSP Routing: Sequence these clusters to establish the base trajectory.
Boundary Dissolution via ALNS: The primary flaw of the JGP heuristic is that it forces jobs to stay within their assigned batches. Apply an ALNS metaheuristic specifically targeting the boundaries of the JGP batches.
Destroy Operator: Extract jobs located at the edges of the JGP batches.
Repair Operator: Reinsert these jobs using a greedy-KTNS metric that evaluates the continuous tool overlap across adjacent batches.
Verdict: This approach mathematically leverages the global clustering optimality of the JGP while explicitly destroying the discrete boundaries that violate the continuous nature of the SSP, yielding a mathematically rigorous, highly competitive metaheuristic upper bound.
JGP-Guided ALNS: The initial solution is the optimal GSP sequence of the JGP batches.
Destroy/Repair Mechanisms: We can define a targeted Boundary Destroy Operator that specifically removes jobs located at the edges of the JGP batches (where transition costs are highest). A KTNS-Greedy Repair Operator then reinserts these jobs in a manner that maximizes the continuous tool overlap across the sequence, effectively smoothing the discrete JGP clusters into a continuous SSP trajectory. my proposal adapts and mathematically restricts these ALNS principles specifically to exploit the exact Column Generation bounds of the single-machine JGP, which is a novel synthesis not present in their work.

Proposal B: Machine Learning Pricing Heuristic (MLPH) for JGP Column Generation
To generate the necessary JGP initializations rapidly for massive real-world datasets, the computational bottleneck of the Column Generation approach must be addressed. The Pricing Problem for the JGP Set Covering formulation is the NP-hard Maximum Weight Independent Set Problem (MWISP).
The MLPH Oracle: Inspired by recent advancements in ML for column generation, we propose training a Graph Convolutional Neural Network (GCNN), to act as a fast heuristic oracle for the JGP pricing problem.
Mechanism: The GCNN takes the bipartite job-tool adjacency matrix and the current dual variables \pi*i from the Restricted Master Problem (RMP) as node features. It predicts subsets of tools that will yield a negative reduced cost.
Integration: The exact MWISP solver is only invoked if the MLPH fails to identify a negative reduced cost column. This directly attacks the NP-hard bottleneck, allowing the exact LP relaxation bounds of the JGP to be computed for ultra-large-scale instances that are currently intractable in the literature.
Machine Learning Pricing Heuristic (MLPH) for JGP Column Generation To generate the JGP bounds rapidly for massive datasets, the Pricing Problem (which is an NP-hard Maximum Weight Independent Set Problem, or MWISP) must be solved at every node of the branch-and-price tree.
The MLPH Oracle: Instead of using standard dynamic programming or exact MILP solvers for the pricing problem, we propose training an ML model (as a binary classifier) to predict which jobs/tools belong to the optimal configuration with a negative reduced cost.
Feature Encoding: The network ingests the current dual variables \pi_i from the Restricted Master Problem (RMP), the job-tool adjacency matrix, and statistical features mapping dual-weight correlations.
Heuristic Generation: The MLPH rapidly outputs a candidate subset of tools. If the reduced cost is negative, the column is added to the RMP. We only call the exact MWISP solver if the MLPH fails to find a negative reduced cost column. Why this is SOTA: This directly attacks the computational bottleneck of the LB*{CG} formulation. By predicting the columns using ML, we can calculate the LB\_{CG} for instances previously deemed intractable, providing SOTA lower bounding for ultra-large-scale SSP instances.
If you intend to propose a Machine Learning Pricing Heuristic (MLPH) to accelerate the JGP Column Generation (to obtain the warm-start batches), this is also strictly verified by recent SOTA. Shen et al. (2022) recently established that using MLPH in Column Generation can drastically reduce the search space by predicting high-quality columns (configurations) with negative reduced costs, accelerating the exact LP relaxation process.
