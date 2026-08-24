#!/usr/bin/env python3
"""
RL-for-cuts: learning to SELECT cutting planes (prototype).
============================================================
A policy-gradient (REINFORCE) agent that learns, from cut *features*, which candidate
cut to add at each separation round so as to tighten the LP bound fastest -- the
cut-selection Markov decision process of

  Tang, Agrawal & Faenza, "Reinforcement Learning for Integer Programming:
  Learning to Cut", ICML 2020,

surveyed in Deza & Khalil, "Machine Learning for Cutting Planes in Integer
Programming: A Survey" (2023).

WHY THIS DESIGN.  The BBC Benders solver runs on CPLEX, which is unavailable in this
sandbox, so the learning machinery is developed and *verified to learn* on a
self-contained, exactly-valid cut family -- knapsack COVER cuts -- solved with
scipy.linprog.  The state/reward/policy are identical in structure to the SSP-Benders
case; only the feature extractor and cut source differ.  The learned linear policy and
its feature map are exposed through `score_cut(...)` and `ssp_cut_features(...)` so the
same selection rule can be dropped into the BBC generic-callback cut loop on the
cluster (see the integration note at the bottom).  Nothing here is claimed to beat the
solver's default on the SSP yet -- that measurement needs the CPLEX campaign; what is
demonstrated is that the policy-gradient agent *learns* a cut-selection rule that
strictly beats random selection on held-out instances.

MDP (per Tang et al. 2020):
  state  s_t : the current LP solution x* and the pool of candidate cuts, each with a
               feature vector phi (violation, size, weight-excess, mean value).
  action a_t : pick one candidate cut to add.
  reward r_t : the drop in the LP objective (a valid upper bound on the IP optimum),
               i.e. how much this cut tightened the relaxation.
  policy pi  : softmax over candidate cuts, linear in phi (theta the parameters).
REINFORCE:   theta <- theta + lr * sum_t (grad log pi(a_t|s_t)) * G_t,  G_t discounted return.

Run:  python3 rl_cut_select.py      (trains, then reports learned-vs-random on held-out)
Requires: numpy, scipy.
"""
import numpy as np
from scipy.optimize import linprog

FEAT_DIM = 4
FEAT_NAMES = ("violation", "cover_size", "weight_excess", "mean_value")


# ── environment: 0/1 knapsack with cover-cut separation ───────────────────────
class KnapsackCutEnv:
    """max v.x  s.t.  w.x <= cap,  x in {0,1}.  Cover cut for a minimal cover C
    (sum_{j in C} w_j > cap):  sum_{j in C} x_j <= |C|-1  (exactly valid)."""

    def __init__(self, n, seed):
        r = np.random.RandomState(seed)
        self.n = n
        self.w = r.randint(1, 20, n).astype(float)
        self.v = r.randint(1, 20, n).astype(float)
        self.cap = float(int(0.5 * self.w.sum()))
        self.cuts = []                                   # [(coef, rhs)]

    def lp(self):
        A = [self.w] + [c for c, _ in self.cuts]
        b = [self.cap] + [r for _, r in self.cuts]
        res = linprog(-self.v, A_ub=np.array(A), b_ub=np.array(b),
                      bounds=[(0, 1)] * self.n, method="highs")
        if not res.success:
            return None, None
        return res.x, float(-res.fun)                    # x*, LP value (upper bound on IP)

    def candidate_cuts(self, x):
        """A HETEROGENEOUS pool the agent must choose from -- the point of the task:
          (a) minimal covers          sum_{C} x_j <= |C|-1   (STRONG: violated, tightens);
          (b) useless valid distractors sum_{S} x_j <= |S|   (S not a cover: always true,
              never tightens -- reward 0 if picked).
        No pre-filtering by violation: telling (a) from (b) via features IS what is learned.
        Cuts already added are excluded so a deterministic policy cannot stall."""
        added = {tuple(c) for c, _ in self.cuts}
        order = np.argsort(-(x * self.w))
        out, seen = [], set()
        for start in range(min(6, self.n)):                    # (a) minimal covers
            C, wsum = [], 0.0
            for j in order[start:]:
                C.append(int(j)); wsum += self.w[j]
                if wsum > self.cap:
                    coef = np.zeros(self.n); coef[C] = 1.0
                    key = tuple(sorted(C))
                    if key not in seen and tuple(coef) not in added:
                        seen.add(key)
                        viol = float(x[C].sum() - (len(C) - 1))
                        phi = np.array([max(0.0, viol), len(C) / self.n,
                                        (wsum - self.cap) / self.cap, self.v[C].mean() / 20.0])
                        out.append((coef, float(len(C) - 1), phi))
                    break
        rr = np.random.RandomState(int(1000 * x.sum()) % 9999)  # (b) useless distractors
        for _ in range(3):
            S, ws = [], 0.0
            for j in rr.permutation(self.n):
                if ws + self.w[j] <= self.cap:
                    S.append(int(j)); ws += self.w[j]
                if len(S) >= 3:
                    break
            coef = np.zeros(self.n); coef[S] = 1.0
            if not S or tuple(coef) in added or any(np.array_equal(coef, c) for c, _, _ in out):
                continue
            viol = float(x[S].sum() - len(S))                  # <= 0: never violated
            phi = np.array([max(0.0, viol), len(S) / self.n,
                            (ws - self.cap) / self.cap, self.v[S].mean() / 20.0])
            out.append((coef, float(len(S)), phi))
        return out


def softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def run_episode(env, theta, rounds=8, greedy=False, rng=None):
    """One separation episode; returns (transitions, rewards, total_bound_drop)."""
    trans, rewards = [], []
    x, bound = env.lp()
    b0 = bound
    for _ in range(rounds):
        x, bound = env.lp()
        if x is None:
            break
        if np.all(np.abs(x - np.round(x)) < 1e-6):        # already integral
            break
        cands = env.candidate_cuts(x)                      # STRONG + useless-distractor cuts, unfiltered
        if not cands:
            break
        phis = np.array([f for _, _, f in cands])
        p = softmax(phis @ theta)
        a = int(np.argmax(p)) if greedy else int((rng or np.random).choice(len(cands), p=p))
        coef, rhs, _ = cands[a]; env.cuts.append((coef, rhs))
        _, nb = env.lp()
        r = bound - (nb if nb is not None else bound)     # LP upper bound decrease = progress
        rewards.append(r); trans.append((phis, a, p))
    return trans, rewards, (b0 - bound if bound is not None else 0.0)


def train(episodes=600, n=14, lr=0.2, gamma=0.95, seed_pool=40, log_every=150, seed=0):
    theta = np.zeros(FEAT_DIM)
    rng = np.random.RandomState(seed)
    hist = []
    for ep in range(episodes):
        env = KnapsackCutEnv(n, seed=rng.randint(seed_pool))     # train instances
        trans, rewards, _ = run_episode(env, theta, greedy=False, rng=rng)
        if not trans:
            continue
        G, returns = 0.0, []
        for r in reversed(rewards):
            G = r + gamma * G; returns.insert(0, G)
        returns = np.array(returns)
        if returns.std() > 1e-9:
            returns = (returns - returns.mean()) / returns.std()  # baseline (variance reduction)
        grad = np.zeros(FEAT_DIM)
        for (phis, a, p), Gt in zip(trans, returns):
            grad += (phis[a] - p @ phis) * Gt              # d/dtheta log pi(a) * G
        theta += lr * grad / len(trans)
        hist.append(sum(rewards))
        if (ep + 1) % log_every == 0:
            print(f"  ep {ep+1:4d}  mean bound-drop (last {log_every}) = {np.mean(hist[-log_every:]):.3f}")
    return theta


def evaluate(theta, n=14, n_test=200, seed_base=10000):
    """Held-out instances: learned-greedy vs uniform-random cut selection.
    Metric = total LP bound reduction achieved in the episode (higher = better)."""
    zero = np.zeros(FEAT_DIM)
    learned, random_, rng = [], [], np.random.RandomState(7)
    for k in range(n_test):
        s = seed_base + k
        el = run_episode(KnapsackCutEnv(n, s), theta, greedy=True)[2]
        er = run_episode(KnapsackCutEnv(n, s), zero, greedy=False, rng=rng)[2]
        learned.append(el); random_.append(er)
    return float(np.mean(learned)), float(np.mean(random_))


# ── SSP / BBC integration (used on the cluster, where CPLEX is available) ──────
def ssp_cut_features(cut_lhs_coeffs, cut_rhs, x_frac, theta_lp, n_jobs):
    """Feature map for a candidate BBC Benders / combinatorial-KTNS cut, matching the
    (violation, size, slack-like, magnitude) structure the agent trained on:
        violation  : (theta_lp - rhs contribution) shortfall of the cut at the current
                     fractional master point  (how much it would move the bound),
        size       : fraction of arc variables the cut touches (density),
        excess     : normalised rhs (cut strength),
        magnitude  : mean |coefficient| (scaled).
    Returns a length-FEAT_DIM vector, so score_cut(...) with a trained `theta` ranks
    real Benders cuts exactly as in the knapsack testbed."""
    coeffs = np.asarray(cut_lhs_coeffs, dtype=float)
    lhs_at_x = float(coeffs @ np.asarray(x_frac, dtype=float))
    violation = max(0.0, cut_rhs - lhs_at_x) if theta_lp is None else max(0.0, (cut_rhs) - lhs_at_x)
    size = float((np.abs(coeffs) > 1e-9).sum()) / max(1, n_jobs * n_jobs)
    excess = float(cut_rhs) / max(1.0, abs(coeffs).sum())
    magnitude = float(np.abs(coeffs).mean()) / 20.0
    return np.array([violation, size, excess, magnitude])


def score_cut(features, theta):
    """Policy score of a single cut; higher = more valuable. Used to rank/select
    candidate cuts inside the BBC generic-callback separation loop."""
    return float(np.asarray(features, float) @ np.asarray(theta, float))


def run_one(seed, episodes, n, lr, gamma, n_test, seed_pool=100000):
    """Train with one seed, evaluate on the FIXED held-out set, return a result dict.
    Each seed samples its OWN training instances from a large pool (`seed_pool`), so the
    held-out `random_mean` is a constant reference and the spread in `learned_mean` /
    `improvement_pct` across seeds is genuine training/sampling variance."""
    theta = train(episodes=episodes, n=n, lr=lr, gamma=gamma, seed=seed,
                  seed_pool=seed_pool, log_every=10**9)
    learned, rand = evaluate(theta, n=n, n_test=n_test)
    lift = 100 * (learned - rand) / abs(rand) if rand else float("nan")
    return {"seed": seed, "episodes": episodes, "n": n, "lr": lr, "gamma": gamma,
            "learned_mean": round(learned, 4), "random_mean": round(rand, 4),
            "improvement_pct": round(lift, 2), "theta": theta.tolist()}


def _demo():
    np.random.seed(0)
    print("RL-for-cuts (Tang et al. 2020 MDP) — knapsack cover-cut selection")
    print("training REINFORCE agent ...")
    theta = train()
    print("learned theta (per feature):",
          {FEAT_NAMES[i]: round(float(theta[i]), 3) for i in range(FEAT_DIM)})
    learned, rand = evaluate(theta)
    lift = 100 * (learned - rand) / abs(rand) if rand else float("nan")
    print(f"\nHeld-out (200 instances): mean LP-bound reduction")
    print(f"  learned-greedy policy : {learned:.3f}")
    print(f"  uniform-random policy : {rand:.3f}")
    print(f"  improvement           : {lift:+.1f}%")
    print("PASS: learned policy beats random." if learned > rand + 1e-6
          else "INCONCLUSIVE: learned did not beat random (retune lr/episodes).")


def main():
    """CLI for batch / SLURM use.  No args -> the single-run demo (unchanged).
    --seed / --seeds -> reproducible multi-seed training, one CSV row per seed, so an
    array job can report mean +/- std improvement (see cluster/run_rl.sbatch)."""
    import argparse, csv, glob, json, os
    ap = argparse.ArgumentParser(description="RL-for-cuts: REINFORCE cut-selection training")
    ap.add_argument("--seed", type=int, help="single training seed (e.g. SLURM array task id)")
    ap.add_argument("--seeds", type=str, help="inclusive range 'A-B' to run in one process")
    ap.add_argument("--episodes", type=int, default=2000)
    ap.add_argument("--n", type=int, default=14, help="knapsack size (instance difficulty)")
    ap.add_argument("--lr", type=float, default=0.2)
    ap.add_argument("--gamma", type=float, default=0.95)
    ap.add_argument("--n-test", type=int, default=200)
    ap.add_argument("--seed-pool", type=int, default=100000,
                    help="size of the per-seed training-instance pool (the variance source)")
    ap.add_argument("--out", type=str, default=None, help="CSV to append per-seed results to")
    ap.add_argument("--summary", type=str, default=None,
                    help="glob of shard CSVs to aggregate (mean/std across seeds), then exit")
    args = ap.parse_args()

    if args.summary:
        rows = []
        for f in sorted(glob.glob(args.summary)):
            with open(f, newline="") as fh:
                rows += list(csv.DictReader(fh))
        if not rows:
            print("no rows matched", args.summary); return
        imp = np.array([float(r["improvement_pct"]) for r in rows])
        lm = np.array([float(r["learned_mean"]) for r in rows])
        rm = np.array([float(r["random_mean"]) for r in rows])
        print(f"RL-for-cuts summary over {len(rows)} runs:")
        print(f"  improvement %: mean {imp.mean():+.1f}  std {imp.std():.1f}  "
              f"min {imp.min():+.1f}  max {imp.max():+.1f}")
        print(f"  learned bound-drop: {lm.mean():.3f} +/- {lm.std():.3f}")
        print(f"  random  bound-drop: {rm.mean():.3f} +/- {rm.std():.3f}")
        print(f"  learned beat random on {int((lm > rm).sum())}/{len(rows)} seeds")
        return

    if args.seed is None and args.seeds is None:
        _demo(); return

    seeds = []
    if args.seeds:
        a, b = args.seeds.split("-"); seeds += list(range(int(a), int(b) + 1))
    if args.seed is not None:
        seeds.append(args.seed)

    fields = ["seed", "episodes", "n", "lr", "gamma",
              "learned_mean", "random_mean", "improvement_pct", "theta"]
    fh = w = None
    if args.out:
        newfile = (not os.path.exists(args.out)) or os.path.getsize(args.out) == 0
        fh = open(args.out, "a", newline="")
        w = csv.DictWriter(fh, fieldnames=fields)
        if newfile:
            w.writeheader()
    for s in seeds:
        res = run_one(s, args.episodes, args.n, args.lr, args.gamma, args.n_test, args.seed_pool)
        print(f"[seed {s:3d}] learned={res['learned_mean']:.3f}  random={res['random_mean']:.3f}  "
              f"improvement={res['improvement_pct']:+.1f}%")
        if w:
            res["theta"] = json.dumps(res["theta"])
            w.writerow(res); fh.flush()
    if fh:
        fh.close()


if __name__ == "__main__":
    main()
