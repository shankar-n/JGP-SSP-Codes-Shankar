import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import networkx as nx
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyArrowPatch
import numpy as np
from util import compute_ktns_cost

 # Global plot style
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "figure.dpi": 100,
})

def plot_zero_blocks(num_jobs, num_tools, zero_blocks, A):
    fig_inc, ax = plt.subplots(figsize=(max(8, num_jobs * 0.7),
                                        max(4, num_tools * 0.55)))

    # Heatmap
    cmap_inc = ListedColormap(['#F5F5F5', '#4682B4'])
    im = ax.imshow(A, cmap=cmap_inc, aspect='auto', vmin=0, vmax=1)

    # Grid lines
    for x in range(num_jobs + 1):
        ax.axvline(x - 0.5, color='white', lw=1.5)
    for y in range(num_tools + 1):
        ax.axhline(y - 0.5, color='white', lw=1.5)

    # 0-block highlights
    for t, blist in zero_blocks.items():
        for (s, e) in blist:
            width = e - s + 1
            rect = plt.Rectangle(
                (s - 0.5, t - 0.5), width, 1,
                fill=False, edgecolor='red', lw=2.2, linestyle='--'
            )
            ax.add_patch(rect)

    ax.set_xticks(range(num_jobs))
    ax.set_xticklabels([f"$j_{{{j+1}}}$" for j in range(num_jobs)], fontsize=9)
    ax.set_yticks(range(num_tools))
    ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(num_tools)], fontsize=9)
    ax.set_title("Incidence Matrix with 0-Blocks Highlighted\n"
                 "(blue = tool required; red dashed = 0-block gap)", fontsize=12)
    ax.set_xlabel("Jobs", fontsize=10)
    ax.set_ylabel("Tools", fontsize=10)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#4682B4', label='Tool required ($A_{tj}=1$)'),
        Patch(facecolor='#F5F5F5', edgecolor='gray', label='Tool not required'),
        Patch(facecolor='none', edgecolor='red',
              linestyle='--', linewidth=2, label='0-block'),
    ]
    ax.legend(handles=legend_elements, loc='upper right',
              fontsize=8, framealpha=0.9)

    plt.tight_layout()
    plt.show()

    print(f"\n0-blocks detected:")
    for t, blist in zero_blocks.items():
        if blist:
            print(f"  tool t{t+1}: {blist}")
    return


def plot_magazine_timeline(route, batches, n_tools, cap):
        """
        Two-panel heatmap:
          Left  — JGP rigid batches (magazine state per batch, switch on boundary)
          Right — SSP continuous routing (magazine state per job position)
        """
        cmap_mag = ListedColormap(['#F0F0F0', '#4682B4'])  # empty / loaded

        # ── Left panel: JGP ────────────────────────────────────────────
        jgp_matrix  = np.zeros((n_tools, len(batches)))
        jgp_xticks  = []
        for step, (jobs, tools) in enumerate(batches):
            for t in tools:
                jgp_matrix[t, step] = 1
            jgp_xticks.append(
                f"Batch {step+1}\n(jobs {[j+1 for j in jobs]})"
            )

        # ── Right panel: SSP ────────────────────────────────────────────
        # Filter out DUMMY entries
        real_route = [(cfg, j) for (cfg, j) in route if cfg != "DUMMY"]
        ssp_matrix = np.zeros((n_tools, len(real_route)))
        ssp_xticks = []
        prev_cfg   = None

        for step, (cfg, j) in enumerate(real_route):
            for t in cfg:
                ssp_matrix[t, step] = 1
            cost_here = (cap - len(set(prev_cfg).intersection(set(cfg)))
                         if prev_cfg else 0)
            ssp_xticks.append(
                f"$j_{{{j+1}}}$\n(Δ={cost_here})"
            )
            prev_cfg = cfg

        # ── Plot ────────────────────────────────────────────────────────
        fig, axes = plt.subplots(1, 2, figsize=(
            max(8,  len(batches) * 1.5 + 3),
            max(5,  n_tools * 0.55 + 2)
        ))

        for ax, mat, xticks, title in [
            (axes[0], jgp_matrix,  jgp_xticks,
             "JGP: Rigid Batch Magazine States"),
            (axes[1], ssp_matrix,  ssp_xticks,
             "SSP (GTSP): Continuous Magazine Routing"),
        ]:
            sns_kw = dict(cmap=cmap_mag, cbar=False, linewidths=1.5,
                          linecolor='white', ax=ax, vmin=0, vmax=1)
            sns.heatmap(mat, **sns_kw)
            ax.set_xticks(np.arange(mat.shape[1]) + 0.5)
            ax.set_xticklabels(xticks, fontsize=7, rotation=0)
            ax.set_yticks(np.arange(n_tools) + 0.5)
            ax.set_yticklabels([f"$t_{{{t+1}}}$" for t in range(n_tools)],
                               rotation=0, fontsize=8)
            ax.set_title(title, fontsize=10, fontweight='bold')
            ax.set_xlabel("Sequence position", fontsize=9)
            ax.set_ylabel("Tool slot", fontsize=9)

        # Vertical lines marking batch boundaries on left panel
        for sep in range(1, len(batches)):
            axes[0].axvline(sep, color='red', lw=2.5, linestyle='--')

        # Switch cost annotations on right panel
        from matplotlib.patches import FancyArrowPatch
        for step in range(1, len(real_route)):
            ci_prev = set(real_route[step-1][0])
            ci_curr = set(real_route[step][0])
            delta   = cap - len(ci_prev.intersection(ci_curr))
            if delta > 0:
                axes[1].axvline(step, color='orange', lw=1.5, linestyle=':',
                                alpha=0.8)

        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#4682B4', label='Tool loaded'),
            Patch(facecolor='#F0F0F0', edgecolor='gray', label='Slot empty'),
        ]
        fig.legend(handles=legend_elements, loc='lower center',
                   ncol=2, fontsize=9, bbox_to_anchor=(0.5, -0.03))
        plt.suptitle(
            "Magazine Timeline Comparison\n"
            "(left: JGP batches with full reloads at dashed lines; "
            "right: SSP with per-step switch costs Δ)",
            fontsize=11, y=1.02
        )
        plt.tight_layout()
        return fig


def plot_active_config_network(route, cap):
        """
        Draw a directed graph of only the configurations actually used in the
        SSP solution.  Nodes = (config, job) pairs; edges = transitions.
        Node size ∝ number of unique tools in config.
        Edge thickness ∝ switch cost (tools swapped).
        """
        import networkx as nx

        real_route = [(cfg, j) for (cfg, j) in route if cfg != "DUMMY"]
        if not real_route:
            print("Empty route — nothing to draw.")
            return None

        G = nx.DiGraph()

        # Add nodes
        for (cfg, j) in real_route:
            lbl = f"C{id(cfg) % 1000}\nj{j+1}"
            G.add_node((cfg, j), label=lbl, cfg=cfg, job=j)

        # Add edges
        edge_costs = {}
        for k in range(len(real_route) - 1):
            u = real_route[k]
            v = real_route[k+1]
            cost = cap - len(set(u[0]).intersection(set(v[0])))
            G.add_edge(u, v, weight=cost)
            edge_costs[(u, v)] = cost

        pos = nx.spring_layout(G, seed=42, k=2.0)

        fig_net, ax_n = plt.subplots(figsize=(
            max(8, len(real_route) * 1.1), 5)
        )

        # Node colours by job index
        cmap_n   = plt.cm.tab20
        node_clr = [cmap_n(r[1] / max(1, len(real_route))) for r in real_route]
        node_sz  = [300 + len(r[0]) * 80 for r in real_route]
        labels   = {r: f"j{r[1]+1}\n{set(r[0])}" for r in real_route}

        nx.draw_networkx_nodes(G, pos, node_color=node_clr,
                               node_size=node_sz, alpha=0.85, ax=ax_n)
        nx.draw_networkx_labels(G, pos, labels=labels,
                                font_size=6, ax=ax_n)

        # Edge width ∝ switch cost; colour: red = expensive, green = cheap
        max_cost  = max(edge_costs.values()) if edge_costs else 1
        for (u, v), cost in edge_costs.items():
            intensity = cost / max(max_cost, 1)
            ec = (intensity, 0.3 * (1 - intensity), 0.1)
            nx.draw_networkx_edges(G, pos, edgelist=[(u, v)],
                                   width=1.5 + 3 * intensity,
                                   edge_color=[ec], alpha=0.8,
                                   arrows=True, arrowsize=15, ax=ax_n,
                                   connectionstyle='arc3,rad=0.05')

        # Edge cost labels
        edge_labels = {(u, v): f"Δ{c}" for (u, v), c in edge_costs.items()}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                     font_size=6, ax=ax_n)

        ax_n.set_title(
            "Active Configuration Transition Network (SSP Solution)\n"
            "Nodes = (config, job)  |  Edge thickness ∝ switch cost Δ",
            fontsize=10
        )
        ax_n.axis('off')
        plt.tight_layout()
        return fig_net

def plot_timedep_costs(sequence, tool_req, cap, tau_values=None):
        """
        Visualise how switch cost varies under different time-dependent
        weight functions  w(τ).

        We fix the SSP sequence and vary τ (idle time between jobs).
        Cost under w(τ) = baseline_cost × w(τ).
        """
        baseline = compute_ktns_cost(sequence, tool_req, cap)
        if tau_values is None:
            tau_values = np.linspace(0, 5, 100)

        w_linear  = 1 + 0.5 * tau_values
        w_exp     = np.exp(0.3 * tau_values)
        w_step    = np.where(tau_values < 2, 1.0, 2.0)  # step at τ=2

        fig_td, ax_td = plt.subplots(figsize=(9, 5))

        ax_td.plot(tau_values, baseline * w_linear,
                   color='#e74c3c', lw=2, label=r'$w(\tau) = 1 + 0.5\tau$ (linear)')
        ax_td.plot(tau_values, baseline * w_exp,
                   color='#9b59b6', lw=2, label=r'$w(\tau) = e^{0.3\tau}$ (exponential)')
        ax_td.plot(tau_values, baseline * w_step,
                   color='#2ecc71', lw=2, linestyle='--',
                   label=r'$w(\tau) = $ step at $\tau=2$')
        ax_td.axhline(baseline, color='#3498db', lw=1.5, linestyle=':',
                      label=r'Baseline ($\tau=0$, standard SSP)')

        ax_td.fill_between(tau_values, baseline, baseline * w_exp,
                           alpha=0.08, color='#9b59b6')
        ax_td.set_xlabel(r'Idle duration between jobs $\tau$', fontsize=11)
        ax_td.set_ylabel('Total switch cost', fontsize=11)
        ax_td.set_title(
            'Time-Dependent Switch Cost under Different Weight Functions\n'
            r'$d_\tau(C,C\prime) = (b - |C \cap C\prime|) \cdot w(\tau)$',
            fontsize=11
        )
        ax_td.legend(fontsize=9)
        ax_td.grid(alpha=0.3, linestyle='--')
        plt.tight_layout()
        return fig_td