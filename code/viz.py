import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import ListedColormap
import numpy as np
from utils import compute_ktns, compute_switch_cost
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
        baseline = compute_ktns(sequence, tool_req, cap)[0]
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

def visualize_ssp_jgp_solution(job_sequence: list, 
                               T_j: dict, 
                               magazine_states: list, 
                               b: int, 
                               jgp_batches: list = None,
                               title: str = "Interactive SSP/JGP Configuration"):
    """
    Visualizes job sequencing, tool overlaps, and magazine capacity.
    
    Parameters:
    - job_sequence: List of Job IDs in the order they are processed.
    - T_j: Dictionary mapping Job ID to a list/set of required Tool IDs.
    - magazine_states: List of lists. magazine_states[i] contains all tools 
                       loaded in the magazine during job_sequence[i].
    - b: Integer, the tool magazine capacity.
    - jgp_batches: (Optional) List of sequence indices where a new JGP batch begins.
                   Draws vertical lines to separate independent groups.
    """
    num_steps = len(job_sequence)
    all_tools = sorted({tool for tools in T_j.values() for tool in tools})
    
    # Create subplots: Top for capacity tracking, Bottom for tool overlaps
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.2, 0.8])

    # --- 1. Top Plot: Magazine Capacity Tracker ---
    tools_loaded_counts = [len(state) for state in magazine_states]
    x_steps = list(range(1, num_steps + 1))
    
    fig.add_trace(go.Scatter(
        x=x_steps, y=tools_loaded_counts, 
        mode='lines+markers', name='Tools in Magazine',
        line=dict(color='firebrick', width=2),
        marker=dict(size=8),
        hovertemplate="Step: %{x}<br>Tools Loaded: %{y}<extra></extra>"
    ), row=1, col=1)

    # Add maximum capacity boundary line
    fig.add_trace(go.Scatter(
        x=[1, num_steps], y=[b, b], 
        mode='lines', name=f'Capacity Limit (b={b})',
        line=dict(color='black', width=2, dash='dash'),
        hoverinfo='skip'
    ), row=1, col=1)

    # --- 2. Bottom Plot: Tool Loading Heatmap / Overlaps ---
    req_x, req_y, req_text = [], [], []
    carry_x, carry_y, carry_text = [], [], []

    for step_idx, (job_id, loaded_tools) in enumerate(zip(job_sequence, magazine_states)):
        step = step_idx + 1
        required_tools = set(T_j[job_id])
        
        for tool in loaded_tools:
            hover_info = f"Sequence Step: {step}<br>Job ID: {job_id}<br>Tool ID: {tool}"
            if tool in required_tools:
                # Tool is actively required by the job
                req_x.append(step)
                req_y.append(tool)
                req_text.append(hover_info + "<br>Status: <b>Required</b>")
            else:
                # Tool is stored in magazine for future/past jobs (Overlap)
                carry_x.append(step)
                carry_y.append(tool)
                carry_text.append(hover_info + "<br>Status: <i>Stored (KTNS)</i>")

    # Trace for Required Tools
    fig.add_trace(go.Scatter(
        x=req_x, y=req_y, mode='markers', name='Required Tool',
        marker=dict(symbol='square', size=24, color='#1f77b4', line=dict(width=1, color='DarkSlateGrey')),
        text=req_text, hoverinfo='text'
    ), row=2, col=1)

    # Trace for Carried-over Tools (Overlaps)
    fig.add_trace(go.Scatter(
        x=carry_x, y=carry_y, mode='markers', name='Stored Tool (Overlap)',
        marker=dict(symbol='square', size=24, color='#aec7e8', opacity=0.7),
        text=carry_text, hoverinfo='text'
    ), row=2, col=1)

    # --- 3. JGP Batch Separators (Optional) ---
    if jgp_batches:
        for batch_start in jgp_batches:
            if batch_start > 1: # Don't draw line at the very beginning
                fig.add_vline(x=batch_start - 0.5, line_width=2, line_dash="dash", line_color="green")
                # Add annotation for the batch
                fig.add_annotation(x=batch_start - 0.5, y=max(all_tools) + 1, 
                                   text="Batch Split", showarrow=False, 
                                   xanchor="left", yanchor="bottom", font=dict(color="green"))

    # --- 4. Layout & Aesthetics ---
    x_tick_labels = [f"Step {i+1}<br>(Job {job})" for i, job in enumerate(job_sequence)]
    
    fig.update_layout(
        title=title,
        xaxis2=dict(
            tickmode='array',
            tickvals=x_steps,
            ticktext=x_tick_labels,
            title="Processing Sequence",
            showgrid=True,
            gridcolor='lightgrey'
        ),
        yaxis=dict(title="Usage", range=[0, b + 1]),
        yaxis2=dict(
            title="Tool ID", 
            tickmode='array', 
            tickvals=all_tools,
            showgrid=True,
            gridcolor='lightgrey'
        ),
        plot_bgcolor='white',
        hovermode='closest',
        height=700
    )

    fig.show()

# ============================================================
# 2D VISUALIZATION (FIXED: hyperedges shown as regions)
# ============================================================

def visualize_2d(configurations, hyperedges):
    n = len(configurations)

    # simple circular layout (stable, interpretable)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    pos = {i: (np.cos(a), np.sin(a)) for i, a in enumerate(angles)}

    fig = go.Figure()

    # --- draw nodes (configs) ---
    x = [pos[i][0] for i in range(n)]
    y = [pos[i][1] for i in range(n)]

    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode='markers+text',
        text=[str(c) for c in configurations],
        textposition="top center",
        marker=dict(size=10),
        name="Configurations"
    ))

    # --- draw hyperedges as polygons ---
    for j, nodes in hyperedges.items():
        if len(nodes) < 3:
            continue

        hx = [pos[i][0] for i in nodes] + [pos[nodes[0]][0]]
        hy = [pos[i][1] for i in nodes] + [pos[nodes[0]][1]]

        fig.add_trace(go.Scatter(
            x=hx, y=hy,
            fill="toself",
            opacity=0.15,
            mode='lines',
            name=f"Job {j}"
        ))

    fig.update_layout(title="2D Hypergraph (Jobs as Hyperedges)")
    fig.show()


# ============================================================
# Metrics
# ============================================================

def compute_config_job_coverage(hyperedges, num_configs):
    coverage = [0] * num_configs
    job_list = [[] for _ in range(num_configs)]

    for j, configs in hyperedges.items():
        for c in configs:
            coverage[c] += 1
            job_list[c].append(j)

    return coverage, job_list


def compute_avg_switch_cost(configurations, capacity):
    n = len(configurations)
    avg_cost = []

    for i in range(n):
        total = 0
        for j in range(n):
            if i != j:
                total += compute_switch_cost(configurations[i], configurations[j], capacity)
        avg_cost.append(total / (n - 1))

    return avg_cost


def compute_pareto_frontier(coverage, avg_cost):
    n = len(coverage)
    pareto = [True] * n

    for i in range(n):
        for j in range(n):
            if (coverage[j] >= coverage[i] and avg_cost[j] <= avg_cost[i]) and \
               (coverage[j] > coverage[i] or avg_cost[j] < avg_cost[i]):
                pareto[i] = False
                break

    return pareto

# ============================================================
# Embedding
# ============================================================

def embed_configurations_3d(configurations, capacity):
    n = len(configurations)
    D = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            D[i, j] = compute_switch_cost(configurations[i], configurations[j], capacity)

    H = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * H @ (D ** 2) @ H

    eigvals, eigvecs = np.linalg.eigh(B)
    idx = np.argsort(eigvals)[::-1][:3]
    coords = eigvecs[:, idx] * np.sqrt(np.maximum(eigvals[idx], 0))
    return coords

# ============================================================
# Visualization
# ============================================================

def visualize_3d(configurations, coords, hyperedges, capacity, solutions=None,
                 show_edges=False, edge_threshold=1):

    x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]

    coverage, job_list = compute_config_job_coverage(hyperedges, len(configurations))
    avg_switch = compute_avg_switch_cost(configurations, capacity)
    pareto = compute_pareto_frontier(coverage, avg_switch)

    max_cov = max(coverage) if max(coverage) > 0 else 1

    colors = [c / max_cov for c in coverage]
    sizes = [6 + 10 * (c / max_cov) for c in coverage]

    # --- always-visible labels ---
    labels = [f"{configurations[i]}\n({coverage[i]})" for i in range(len(configurations))]

    hover_text = []
    for i, cfg in enumerate(configurations):
        hover_text.append(
            f"Config: {cfg}<br>"
            f"Jobs: {job_list[i]}<br>"
            f"Coverage: {coverage[i]}<br>"
            f"Avg switch cost: {round(avg_switch[i], 2)}<br>"
            f"Pareto: {pareto[i]}"
        )

    fig = go.Figure()

    # --- configs ---
    fig.add_trace(go.Scatter3d(
        x=x, y=y, z=z,
        mode='markers+text',
        text=labels,
        textposition='top center',
        marker=dict(
            size=sizes,
            color=colors,
            colorscale='Viridis',
            colorbar=dict(
                title="#Jobs Covered",
                orientation='h',
                x=0.5,
                xanchor='center',
                y=-0.2
            ),
            opacity=0.9
        ),
        hovertext=hover_text,
        hoverinfo='text',
        name="Configurations"
    ))

    # # --- pareto ---
    # fig.add_trace(go.Scatter3d(
    #     x=[x[i] for i in range(len(x)) if pareto[i]],
    #     y=[y[i] for i in range(len(y)) if pareto[i]],
    #     z=[z[i] for i in range(len(z)) if pareto[i]],
    #     mode='markers',
    #     marker=dict(size=12, symbol='diamond'),
    #     name='Pareto Frontier'
    # ))

    # --- hyperedges per job (FIXED legend visibility) ---
    for j, nodes in hyperedges.items():
        if len(nodes) >= 3:
            fig.add_trace(go.Mesh3d(
                x=[x[i] for i in nodes],
                y=[y[i] for i in nodes],
                z=[z[i] for i in nodes],
                opacity=0.08,
                name=f"Job {j}",
                hovertext=f"Job {j} covers configs: {[configurations[i] for i in nodes]}",
                hoverinfo='text',
                # visible='legendonly'
            ))
        elif len(nodes) == 2:
            fig.add_trace(go.Scatter3d(
                x=[x[nodes[0]], x[nodes[1]]],
                y=[y[nodes[0]], y[nodes[1]]],
                z=[z[nodes[0]], z[nodes[1]]],
                mode='lines',
                fill="toself",
                line=dict(width=4),
                name=f"Job {j}",
                hovertext=f"Job {j} covers configs: {[configurations[i] for i in nodes]}",
                hoverinfo='text',
                # visible='legendonly'
            ))

    # --- OPTIONAL sparse edges (recommended OFF by default) ---
    if show_edges:
        ex, ey, ez, etext = [], [], [], []

        for i in range(len(configurations)):
            for j in range(i+1, len(configurations)):
                w = compute_switch_cost(configurations[i], configurations[j], capacity)
                if w <= edge_threshold:
                    ex += [x[i], x[j], None]
                    ey += [y[i], y[j], None]
                    ez += [z[i], z[j], None]
                    etext.append(f"cost={w}")

        fig.add_trace(go.Scatter3d(
            x=ex, y=ey, z=ez,
            mode='lines',
            line=dict(width=1, color='gray'),
            opacity=0.2,
            hovertext=etext,
            hoverinfo='text',
            name='Switch edges'
        ))

    # --- solutions ---
    if solutions:
        config_index = {tuple(c): i for i, c in enumerate(configurations)}

        for idx, sol in enumerate(solutions):
            px, py, pz = [], [], []

            for (_, c1), (_, c2) in zip(sol[:-1], sol[1:]):
                i1 = config_index[tuple(c1)]
                i2 = config_index[tuple(c2)]

                px += [x[i1], x[i2], None]
                py += [y[i1], y[i2], None]
                pz += [z[i1], z[i2], None]

            fig.add_trace(go.Scatter3d(
                x=px, y=py, z=pz,
                mode='lines',
                line=dict(width=5),
                name=f"Solution {idx+1}"
            ))

    fig.update_layout(
        title="3D SSP Visualization",
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            dragmode='orbit'
        ),
        margin=dict(l=0, r=0, b=60, t=40),
        legend=dict(itemsizing='constant')
    )

    fig.show(config={'scrollZoom': True, 'showLink': False, 'displayModeBar': True})



# ============================================================
# ANIMATION (FIXED: actual SSP trajectory in config space)
# ============================================================

def animate_solution(configurations, coords, solution, capacity):
    config_index = {tuple(c): i for i, c in enumerate(configurations)}

    x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]

    frames = []

    for step in range(1, len(solution)):
        px, py, pz = [], [], []

        for (j1, c1), (j2, c2) in zip(solution[:step], solution[1:step+1]):
            i1 = config_index[tuple(c1)]
            i2 = config_index[tuple(c2)]

            px += [x[i1], x[i2], None]
            py += [y[i1], y[i2], None]
            pz += [z[i1], z[i2], None]

        frames.append(go.Frame(data=[go.Scatter3d(
            x=px, y=py, z=pz,
            mode='lines',
            line=dict(width=6)
        )]))

    fig = go.Figure(
        data=[go.Scatter3d(x=x, y=y, z=z, mode='markers')],
        frames=frames
    )

    fig.update_layout(
        title="SSP Solution Trajectory",
        updatemenus=[{
            "type": "buttons",
            "buttons": [{"label": "Play", "method": "animate", "args": [None]}]
        }]
    )

    fig.show()


def my_plot(configs, H_j, capacity):

    visualize_2d(configs, H_j)

    coords = embed_configurations_3d(configs, capacity)

    # Example: multiple solutions
    sol1 = [(1, configs[0]), (2, configs[1]), (3, configs[2])]
    sol2 = [(1, configs[2]), (2, configs[3]), (3, configs[1])]

    visualize_3d(configs, coords, H_j, capacity,
                 solutions=[sol1, sol2])

    # animate_solution(configs, coords, sol1, capacity)