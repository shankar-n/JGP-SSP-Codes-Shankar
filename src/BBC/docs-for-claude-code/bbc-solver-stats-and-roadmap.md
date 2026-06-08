# BBC Solver — Stats, Diagnostics, and Implementation Roadmap

---

## Part 1: What Solver Stats Matter and Why

### The Fundamental Loop

In any B&B-based exact solver, two bounds converge toward each other:

- **Dual bound (lower bound / LB)**: the LP relaxation says "the optimum can't be less than this." Starts at the root node, increases as cuts are added and branching narrows the feasible set.
- **Primal bound (upper bound / UB)**: the best feasible integer solution found so far. Decreases as better sequences are discovered.
- **MIP gap** = (UB − LB) / |UB| × 100% — the single most important number. The solver terminates when this hits 0% (or your tolerance).

For BBC specifically: the dual bound is θ from the master LP, initialised at `Σ w_ij x_ij` and tightened by Benders cuts. The primal bound is the KTNS cost of the best Hamiltonian sequence found so far.

---

### Stats to Watch, In Priority Order

#### 1. Root Node LP Bound

The value of θ after the initial constraint `θ ≥ Σ w_ij x_ij` but before any Benders cuts fire. Tells you how tight the initial relaxation is.

- If root LP = 2.0 and optimum = 7.0 → ratio 0.29 → extremely weak → expect thousands of nodes.
- If root LP = 6.0 and optimum = 7.0 → ratio 0.86 → tight → B&B will be fast.

**This is the #1 reason exact SSP solvers are slow.** It's why Catanzaro (2015) and da Silva (2024) invest heavily in tightening LP bounds, and why fractional Benders cuts matter.

#### 2. MIP Gap Over Time (Convergence Plot)

Plot `(time, dual_bound, primal_bound)`. Healthy behaviour: dual bound jumps quickly at the root (first few cuts have high impact), then grinds upward. Unhealthy: dual bound stays flat for a long time — this is the **tailing-off** effect, the classical Benders pathology, and the motivation for fractional (user) cuts.

#### 3. Nodes Explored

How many B&B nodes before optimality.

- ≤10 jobs: expect hundreds of nodes.
- 20+ jobs: thousands to millions.
- **If nodes is low but time is long** → bottleneck is the DSP callback (LP solve per call), not B&B → `worker_lp_reuse` will help.
- **If nodes is high** → bottleneck is weak bounds → better cuts or tighter formulation needed.

#### 4. Cuts Added — SECs vs Benders (separately)

The current code conflates both in `solver.cuts_added`. They should be tracked separately:

| Pattern                         | Meaning                                            |
| ------------------------------- | -------------------------------------------------- |
| Many SECs early, few later      | Normal — subtour structure resolved quickly        |
| Many Benders cuts throughout    | LP relaxation is loose; cuts are doing real work   |
| Very few Benders cuts           | Initial `w_ij` bound already tight (rare but good) |
| Zero Benders cuts + not optimal | **Bug** — callback is not firing or cut is wrong   |

#### 5. Callback Invocations vs Cuts Added

`iteration_count` = how many times the callback fires. If it fires 500 times but only adds 10 Benders cuts, the initial bound is doing most of the work. If it fires 500 times and adds 490 cuts, the LP is very loose.

#### 6. DSP Solve Time (not currently tracked)

If each DSP solve takes ~0.5s and the callback fires 500 times, that's 250s of a 300s budget spent purely in the subproblem. This is precisely where `worker_lp_reuse` helps — build the DSP model once, update objective coefficients, re-solve.

---

### What Your Advisor Will Ask For

A table like this for each instance class:

| Instance | n   | m   | C   | LB_root | UB_init | Nodes | SECs | Benders cuts | Time (s) | Gap % | Status  |
| -------- | --- | --- | --- | ------- | ------- | ----- | ---- | ------------ | -------- | ----- | ------- |
| A1-1     | 10  | 15  | 5   | 3.0     | 12      | 847   | 23   | 41           | 4.2      | 0%    | OPTIMAL |
| ...      |     |     |     |         |         |       |      |              |          |       |         |

The `LB_root / UB_init / final gap` trio tells the story of how tight the formulation is. Nodes and time tell scalability.

---

### How to Extract These Stats from CPLEX

Currently all CPLEX output is suppressed. To get stats programmatically after `cpx.solve()`:

```python
stats = {
    "status":        cpx.solution.status[cpx.solution.get_status()],
    "primal_bound":  cpx.solution.get_objective_value(),          # incumbent UB
    "dual_bound":    cpx.solution.MIP.get_best_objval(),          # LB at termination
    "gap_pct":       cpx.solution.MIP.get_mip_relative_gap() * 100,
    "nodes":         cpx.solution.progress.get_num_nodes_processed(),
    "lp_iters":      cpx.solution.progress.get_num_iterations(),
    "sec_cuts":      cb.sec_cuts_added,       # track separately in callback
    "benders_cuts":  cb.benders_cuts_added,   # track separately in callback
    "cb_invocations": cb.iteration_count,
}
```

For the root node LP bound, capture θ inside the callback on its first invocation (before any cuts are added), or solve a separate LP relaxation at root only.

For a convergence plot, log `(elapsed_time, dual_bound, primal_bound)` tuples inside the callback at each invocation. This currently requires adding a `time.perf_counter()` call and a log list to `BendersCutCallback`.

---

## Part 2: Open Implementation Items — Difficulty and Priority

### Summary Table

| Item                                   | File                              | Difficulty         | Priority     | Payoff                                     |
| -------------------------------------- | --------------------------------- | ------------------ | ------------ | ------------------------------------------ |
| Add solver stats & convergence logging | `branch_and_benders_cut_cplex.py` | Low                | **Do first** | Immediate visibility into solver behaviour |
| Separate SEC vs Benders cut counters   | `branch_and_benders_cut_cplex.py` | Low                | **Do first** | Required for any result table              |
| Test `worker_lp_reuse=True`            | `branch_and_benders_cut_cplex.py` | Zero (flag exists) | High         | Direct speedup, no algorithmic change      |
| Combinatorial Benders cuts             | `branch_and_benders_cut_cplex.py` | Low (~2 days)      | High         | Cheaper cuts, interesting comparison       |
| Triplet lower bounds                   | `branch_and_benders_cut_cplex.py` | Low (~1 day)       | Medium       | Tighter root bound, larger MP              |
| Fractional Benders cuts (user cuts)    | `branch_and_benders_cut_cplex.py` | Medium (~1 week)   | Medium-High  | Closes tailing-off, needs careful testing  |
| Parallel B&B                           | `branch_and_benders_cut_cplex.py` | Medium (threading) | Low          | Minimal benefit at current instance sizes  |

---

### Item Details

#### A. Solver Stats & Convergence Logging _(Low difficulty)_

Add to `BendersCutCallback`:

- Separate counters `sec_cuts_added` and `benders_cuts_added`.
- A log list `[(time, dual_bound, primal_bound)]` appended on each `_handle_candidate` call.
- Capture the root node LP bound (θ value at first callback invocation).

Add to `BranchAndBendersCutSSP_CPLEX.solve()`:

- Extract CPLEX stats after `cpx.solve()` into a `self.solve_stats` dict (nodes, gap, LP iters, etc.).
- Expose a `plot_convergence()` method that plots the dual/primal bound trajectory.

#### B. Worker LP Reuse _(Zero difficulty — already implemented)_

`_solve_dsp_reuse` is already written. It updates only the λ objective coefficients between calls using `dsp.objective.set_linear(updates)`, then re-solves with dual simplex.

To activate: set `worker_lp_reuse=True` in the solver constructor. The only task is to run the test harness and verify the objective values match the default fresh-model approach on 3–4 instances.

#### C. Combinatorial Benders Cuts _(Low — ~2 days)_

Instead of solving the DSP LP, use KTNS directly. The cut is:

```
θ ≥ Z*(π) · (1 − Σ_{(i,j)∈π} (1 − x_ij))
```

where `Z*(π) = compute_ktns(sequence, tool_req, cap)[0]`.

**Trade-off**: O(nM) to compute (vs LP solve) but weaker — only binds at the exact sequence π. Does not generalise across sequences the way dual cuts do.

**Implementation**: in `_handle_candidate`, after extracting the Hamiltonian sequence, optionally call `compute_ktns` and build the combinatorial cut instead of calling `_solve_dsp_with_xbar`. Can be run alongside LP cuts or as a cheaper alternative. Comparison between the two is itself a research result.

#### D. Triplet Lower Bounds _(Low — ~1 day)_

Strengthen the initial θ lower bound. For every triple of consecutive jobs (i, j, k):

```
w_ijk = max(0, |T_i ∪ T_j ∪ T_k| − c)
```

If `x_ij = 1` and `x_jk = 1`, then `θ ≥ w_ijk`. Add O(n³) constraints to the master at build time. Trades larger MP for tighter root bound. Worth comparing root LP with and without on Catanzaro instances.

#### E. Fractional Benders Cuts _(Medium — ~1 week)_

Fire the DSP callback at LP relaxation nodes (not just integer candidates) and inject Benders _user cuts_ via `context.add_user_cut()`. Tightens the LP bound before branching, which directly attacks the tailing-off problem.

Key considerations:

1. **CPLEX presolve must be disabled** — already handled (`presolve.set(0)` when flag is True), but this slows CPLEX on instances where presolve normally helps.
2. **Fractional x_bar is valid DSP input** — the LP dual is well-defined for any x_bar ∈ [0,1]^arcs. The code already passes fractional x_bar to `_solve_dsp_with_xbar`. ✓
3. **`context.add_user_cut()` can fail silently** at some LP nodes (presolve-transformed variables). Needs a try/except wrapper (already present in the code).
4. **Cut strength vs frequency trade-off**: firing at every LP node may add many weak cuts; may need a violation threshold (e.g., only add if `dsp_obj > θ + 0.1`).

This is a meaningful research experiment: measure the convergence curves with and without fractional cuts on Catanzaro A/B instances.

#### F. Parallel B&B _(Medium — mostly testing)_

Thread-up/thread-down pattern is implemented. Main risk: `self._cb_ref` is assigned in `solve()` before `cpx.set_callback()`, but `_get_dsp_model` reads `_cb_ref._thread_dsps` inside the callback. If CPLEX spawns a thread before `_cb_ref` is set (possible race), it will crash with `AttributeError`. Fix: assign `_cb_ref` inside `BendersCutCallback.__init__` directly, or add a threading.Lock.

**Practical note**: at current instance sizes (≤25 jobs, narrow B&B tree), parallel B&B is unlikely to help much. Worth implementing properly but not the highest priority.

---

## Research Experiment Checklist

Before publishing BBC results, the following experiments should be run:

- [ ] Root LP bound ratio (LB_root / OPT) vs instance class — characterises formulation tightness
- [ ] Convergence plot (dual/primal bound over time) on representative instances
- [ ] Cut effectiveness: SECs added vs Benders cuts added vs nodes
- [ ] Worker LP reuse: time comparison fresh vs reuse on Catanzaro A/B/C/D
- [ ] Combinatorial cuts vs LP cuts: objective quality and solve time
- [ ] Fractional cuts on/off: convergence curve comparison
- [ ] Comparison table: BBC vs LSS vs SSPMF on standard benchmarks

Good. Let me read the existing code before writing anything.Now let me check the SCIP solver for JGP (needed for precompute) and verify the data folder structure.I have everything I need. Let me create the task list and start writing.Now let me verify the file structure and do a quick sanity check on the config paths:All paths resolve correctly. Let me present all files:5 files implemented. Here's what was built and what to watch for before running:

**What was built:**

`benchmark_config.py` — single source of truth. Paths resolved to 411 primary instances (171 Catanzaro, 160 Crama, 80 Laporte7) × 10 configs = 4110 pairs. Secondary sets (Laporte3-5, ~1010 instances) use 9 configs (no SSPMF).

`benchmark_runner.py` — each run goes in a subprocess (spawn, not fork — CPLEX-safe on Windows). The main process joins with `time_limit + 90s` OS-level timeout, kills if still alive, and records `time_limit`. Results append to `raw_results.csv` row by row. Restart with `python benchmark_runner.py` — already-completed pairs are skipped automatically.

`precompute_jgp_gsp.py` — solves JGP via ARF MILP, then exhaustively tries all K*! batch orderings (capped at K*≤8; nearest-neighbor beyond that). Run this before or after the benchmark — it joins with exact optima from `raw_results.csv` if they already exist.

`analysis/generate_tables.py` / `generate_plots.py` — read from `raw_results.csv` and write to `analysis/output/`. Plots need `matplotlib` + `numpy` (`pip install matplotlib numpy --break-system-packages`). Fig 5 (convergence traces) is a documented stub — it requires adding per-timestep `(elapsed, dual_bound)` logging inside `branch_and_benders_cut_cplex.py`.

**Suggested run order:**

```bash
# 1. Smoke test on 5 Catanzaro instances, all configs
python benchmark_runner.py --only-sets Catanzaro --dry-run   # check queue looks right
python benchmark_runner.py --only-sets Catanzaro --configs BBC-K LSS  # 10 instances, fast

# 2. Full primary run (long)
python benchmark_runner.py --sets primary

# 3. Precompute JGP+GSP costs (can run in parallel with above)
python precompute_jgp_gsp.py --sets primary

# 4. Analysis
python analysis/generate_tables.py
python analysis/generate_plots.py
```

---

## Part 3: Running the Benchmark on the LIMOS Cluster

LIMOS operates a SLURM-managed HPC cluster accessible to ISIMA interns.
Documentation: https://hpc.isima.fr and https://doc.isima.fr

---

### Step 0 — Get a Cluster Account

If you do not yet have access, email **Hélène Toussaint** (helene.toussaint@uca.fr) or **Raphaël Amato** (raphael.amato@uca.fr) and ask them to open a cluster account for you, mentioning you are an intern at LIMOS.

Once granted, your credentials are your **UCA ENT login/password** (same as your UCA email).

---

### Step 1 — Connect to the Cluster

If you are **outside the ISIMA building**, first connect to the VPN:
see https://doc.isima.fr/services/acces-distant/vpn/

Then SSH into the login node:

```bash
ssh yourlogin@frontalhpc2020
# or, if transitioning to the new frontal:
ssh yourlogin@frontalhpc2025
```

Enter your UCA password when prompted. You are now on the **login node** — do not run computations here, only submit jobs.

---

### Step 2 — Keep Your Session Alive with `screen`

SSH sessions die if your connection drops. Use `screen` so your terminal survives:

```bash
# Start a named screen session
screen -S benchmark

# Detach from screen (leaves it running): Ctrl+A then D
# Reattach to it later:
screen -r benchmark

# List running sessions:
screen -ls

# Kill a session from inside it:
exit
```

For `tmux` users (same idea, different keybindings):

```bash
tmux new -s benchmark        # start
# Ctrl+B then D              # detach
tmux attach -t benchmark     # reattach
```

---

### Step 3 — Transfer the Project to the Cluster

From your **local machine** (Windows: use MobaXterm's built-in file transfer, or WSL):

```bash
# From your local terminal — replace LOGIN and adjust the local path
rsync -avz --exclude='*.pyc' --exclude='__pycache__' \
  /path/to/JGP-SSP-Codes-Shankar/ \
  LOGIN@frontalhpc2020:~/JGP-SSP-Codes-Shankar/
```

Or with `scp`:

```bash
scp -r /path/to/JGP-SSP-Codes-Shankar LOGIN@frontalhpc2020:~/
```

---

### Step 4 — Check Python and CPLEX on the Cluster

Once logged in:

```bash
# Check Python
python3 --version

# Check if CPLEX Python API is available
python3 -c "import cplex; print(cplex.__version__)"

# Check PySCIP (needed for JGP precompute)
python3 -c "import pyscipopt; print('pyscip ok')"
```

If `import cplex` fails, CPLEX may be installed but not on the Python path. Try:

```bash
# Find where CPLEX is installed on the cluster
find /opt /usr/local -name "cplex" -type f 2>/dev/null | head -5

# If found at e.g. /opt/ibm/ILOG/CPLEX_Studio2211/
export PYTHONPATH=/opt/ibm/ILOG/CPLEX_Studio2211/cplex/python/3.x/x86-64_linux:$PYTHONPATH
python3 -c "import cplex; print('cplex ok')"
```

Add the working `export PYTHONPATH=...` line to your `~/.bashrc` so it persists.

If packages are missing, install them in user space (no sudo needed):

```bash
pip install pyscipopt numpy matplotlib --user
```

---

### Step 5 — Write a SLURM Job Script

Create `~/JGP-SSP-Codes-Shankar/src/BBC/run_benchmark.sh`:

```bash
#!/bin/bash
#SBATCH --job-name=bbc_benchmark
#SBATCH --partition=normal          # up to 7 days; use 'court' for <2h tests
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1           # benchmark runner is single-threaded
#SBATCH --mem=8000                  # 8 GB; CPLEX + SCIP together need ~4-6 GB
#SBATCH --time=3-00:00:00           # 3 days for a full primary run
#SBATCH --output=slurm_%j.out       # stdout → slurm_<jobid>.out
#SBATCH --error=slurm_%j.err        # stderr → slurm_<jobid>.err

# ── Environment ─────────────────────────────────────────────────────────────
# Adjust CPLEX path if needed (find it with: find /opt -name "cplex" 2>/dev/null)
export PYTHONPATH=/opt/ibm/ILOG/CPLEX_Studio2211/cplex/python/3.x/x86-64_linux:$PYTHONPATH

cd ~/JGP-SSP-Codes-Shankar/src/BBC

# ── Run ─────────────────────────────────────────────────────────────────────
echo "Starting benchmark at $(date)"
python3 benchmark_runner.py --sets primary
echo "Done at $(date)"
```

For a **quick smoke test** (5 Catanzaro instances, BBC-K and LSS only), use a short-partition script:

```bash
#!/bin/bash
#SBATCH --job-name=bbc_pilot
#SBATCH --partition=court
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8000
#SBATCH --time=2:00:00
#SBATCH --output=pilot_%j.out
#SBATCH --error=pilot_%j.err

export PYTHONPATH=/opt/ibm/ILOG/CPLEX_Studio2211/cplex/python/3.x/x86-64_linux:$PYTHONPATH
cd ~/JGP-SSP-Codes-Shankar/src/BBC

python3 benchmark_runner.py --only-sets Catanzaro --configs BBC-K LSS --limit 5
```

---

### Step 6 — Submit and Monitor

```bash
# Submit
sbatch run_benchmark.sh
# → prints: Submitted batch job 1234567

# Check job status (ST: PD=pending, R=running, CG=completing)
squeue -u $USER

# Watch it live (updates every 5s)
watch -n5 squeue -u $USER

# See live output as the job runs
tail -f slurm_1234567.out

# Cancel a job
scancel 1234567

# Check detailed job info (after it ends)
sacct -j 1234567 --format=JobID,State,Elapsed,MaxRSS,ExitCode
```

---

### Step 7 — Retrieve Results

After the job completes, the results are in `~/JGP-SSP-Codes-Shankar/src/BBC/raw_results.csv`.

Copy back to your local machine:

```bash
# From your LOCAL machine:
rsync -avz LOGIN@frontalhpc2020:~/JGP-SSP-Codes-Shankar/src/BBC/raw_results.csv \
  /path/to/local/JGP-SSP-Codes-Shankar/src/BBC/

# Also grab logs
rsync -avz LOGIN@frontalhpc2020:~/JGP-SSP-Codes-Shankar/src/BBC/slurm_*.out ./
```

---

### Step 8 — If the Job Fails or Times Out

The benchmark runner **appends results row-by-row and resumes automatically** from the last completed pair. If the job dies mid-run:

```bash
# Check how far it got
wc -l raw_results.csv
tail -5 raw_results.csv

# Resubmit — it will skip already-completed pairs
sbatch run_benchmark.sh
```

If CPLEX fails to import inside the job, check `slurm_<id>.err`:

```bash
cat slurm_1234567.err
```

The most common cause is a wrong `PYTHONPATH`. Fix it in the script and resubmit.

---

### Checklist Before Submitting the Full Run

- [ ] `python3 -c "import cplex"` works on the login node
- [ ] `python3 -c "import pyscipopt"` works (needed for JGP precompute)
- [ ] Dry-run passes: `python3 benchmark_runner.py --sets primary --dry-run`
- [ ] Pilot (5 instances) completed without errors
- [ ] `raw_results.csv` has the expected columns (open with `head -1 raw_results.csv`)
- [ ] SLURM `--time` is long enough: primary run worst-case ≈ 411 instances × 10 configs × 1h = 4110 CPU-hours, but sequential so wall time ≈ the same. Request at least 3 days. If the cluster limits wall time, split by `--only-sets`.
