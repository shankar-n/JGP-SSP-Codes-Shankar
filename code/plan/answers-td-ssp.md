### Unrestricted ILP Formulation for the TD-SSP

In the Tool-Dependent Job Sequencing and Tool Switching Problem (TD-SSP), the assumption of uniform tool switching times is relaxed. Let $c_t$ denote the specific non-uniform setup time (or cost) required to insert tool $t \in T$ into the magazine. The distance metric between configurations becomes asymmetric, depending strictly on the specific tools that must be loaded.

Let $\mathcal{C}$ be the complete, unrestricted set of all possible tool repository configurations, where each configuration $C_v \in \mathcal{C}$ satisfies the tool magazine capacity constraint $|C_v| \le b$. Let $0 \in \mathcal{C}$ designate the dummy configuration representing the empty magazine at the start and end of the production schedule.

The asymmetric distance (setup cost) to transition from configuration $u$ to configuration $v$ is exactly the sum of the insertion costs of the tools present in $v$ but absent in $u$:
$$ d(u,v) = \sum\_{t \in C_v \setminus C_u} c_t $$

Let $H_j = \{v \in \mathcal{C} \mid T_j \subseteq C_v\}$ denote the subset of configurations containing all required tools $T_j$ to process job $j \in J$.

**Decision Variables:**

- $y_v \in \{0,1\}$: 1 if configuration $v \in \mathcal{C}$ is selected, 0 otherwise.
- $x_{uv} \in \{0,1\}$: 1 if configuration $v \in \mathcal{C}$ is visited immediately after configuration $u \in \mathcal{C}$, 0 otherwise.

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

### Restricted Master Problem (RMP) for the TD-SSP

Let $V \subset \mathcal{C}$ be a restricted subset of configurations currently available in the RMP, with $0 \in V$. The integrality constraints are relaxed to allow the generation of dual variables for the Dantzig-Wolfe decomposition framework. The structure of the constraints identical to the U-SSP, utilizing the exact Prize Collecting Traveling Salesman Problem (PCTSP) subtour elimination constraints; however, the objective function natively integrates the asymmetric distance matrix $d(i,j)$.

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

### Pricing Subproblem for the TD-SSP

The column generation step seeks to dynamically identify a new tool configuration $c \in \mathcal{C} \setminus V$ that yields a negative marginal reduced cost. Generating the new configuration node $c$ between two existing active nodes $u, w \in V$ means introducing the new routing transitions $x_{uc}$ and $x_{cw}$. Because node $c$ is newly generated, the dual variables $\mu_{S,k}$ from the PCTSP subtour elimination constraints evaluate to zero for these incident edges.

**Decision Variables:**

- $z_t \in \{0,1\}$: 1 if tool $t \in T$ is selected for the new configuration $c$, 0 otherwise.
- $v_r \in \{0,1\}$: 1 if job $r \in J$ is covered by the new configuration $c$, 0 otherwise.

To evaluate the topological insertion cost, the asymmetric distances from an existing active configuration $u \in V$ to $c$, and from $c$ to a successor configuration $w \in V$, are explicitly formulated based on the specific tool selections $z_t$:

- $d(C_u, c) = \sum_{t \in T} c_t z_t (1 - \mathbb{I}_{t \in C_u})$
- $d(c, C_w) = \sum_{t \in C_w} c_t (1 - z_t)$

Where $\mathbb{I}_{t \in C_u}$ is an indicator parameter equal to 1 if tool $t$ is present in the known configuration $C_u$, and 0 otherwise. The Pricing Subproblem is formulated as an Asymmetric Prize-Collecting Set Union Knapsack Problem:

$$
\begin{aligned}
\min_{z, v} \quad & \min_{u, w \in V} \left[ \sum_{t \in T} c_t z_t (1 - \mathbb{I}_{t \in C_u}) + \sum_{t \in C_w} c_t (1 - z_t) - \alpha_u - \beta_w \right] - \sum_{r \in J} \pi_r v_r \\
\text{s.t.} \quad & v_r \le z_t \quad \forall r \in J, \forall t \in T_r \\
& \sum_{t \in T} z_t \le b \\
& z_t \in \{0,1\} \quad \forall t \in T \\
& v_r \in \{0,1\} \quad \forall r \in J
\end{aligned}
$$
