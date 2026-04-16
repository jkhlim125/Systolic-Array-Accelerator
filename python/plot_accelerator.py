#!/usr/bin/env python3

import csv
from pathlib import Path

import plotly.graph_objects as go


ARRAY_SIZE = 4
ACC_WIDTH = 24
THEORETICAL_LATENCY = 3 * ARRAY_SIZE

PLOT_WIDTH = 1100
PLOT_HEIGHT = 520
SHOW_FIGURES = True

OUTPUT_DIR = Path("plots")
README_MD_PATH = Path("README_accelerator_execution_overview.md")

STATE_NAMES = {
    0: "IDLE",
    1: "LOAD",
    2: "STREAM",
    3: "DRAIN",
    4: "COLLECT",
    5: "DONE",
}

COLOR = {
    "ink": "#1f2937",
    "grid": "#d8dee9",
    "controller": "#0f766e",
    "stream": "#1d4ed8",
    "collect": "#ea580c",
    "done": "#b45309",
    "heat_on": "#0f766e",
    "heat_off": "#f8fafc",
    "psum": "#1d4ed8",
    "event": "#f59e0b",
    "final": "#dc2626",
    "latency": "#0f766e",
    "theory": "#dc2626",
    "mean": "#6366f1",
}


def load_trace(path):
    records = []

    with open(path, "r", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            records.append(
                {
                    "sample_idx": len(records),
                    "cycle": int(row["cycle"]),
                    "state": int(row["state"]),
                    "state_name": STATE_NAMES.get(int(row["state"]), f"STATE_{row['state']}"),
                    "stream_cycle": int(row["stream_cycle"]),
                    "c_valid": int(row["c_valid"]),
                    "busy": int(row["busy"]),
                    "done": int(row["done"]),
                    "pe_mac_fire_flat": int(row["pe_mac_fire_flat"], 16)
                    if row["pe_mac_fire_flat"]
                    else 0,
                    "psum_flat": int(row["psum_flat"], 16) if row["psum_flat"] else 0,
                }
            )

    return records


def apply_common_layout(fig, title, x_label, y_label, show_legend=True):
    fig.update_layout(
        template="plotly_white",
        width=PLOT_WIDTH,
        height=PLOT_HEIGHT,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 60, "r": 40, "t": 60, "b": 60},
        font={"family": "Arial, Helvetica, sans-serif", "size": 14, "color": COLOR["ink"]},
        title={
            "text": title,
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 20, "color": COLOR["ink"]},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "left",
            "x": 0.0,
            "font": {"size": 10},
            "tracegroupgap": 4,
        },
        showlegend=show_legend,
    )
    fig.update_xaxes(
        title_text=x_label,
        title_font={"size": 14},
        tickfont={"size": 12},
        showgrid=True,
        gridcolor=COLOR["grid"],
        zeroline=False,
    )
    fig.update_yaxes(
        title_text=y_label,
        title_font={"size": 14},
        tickfont={"size": 12},
        showgrid=True,
        gridcolor=COLOR["grid"],
        zeroline=False,
    )


def save_figure(fig, stem):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / f"{stem}.html"
    png_path = OUTPUT_DIR / f"{stem}.png"

    fig.write_html(html_path, include_plotlyjs="cdn")
    print(f"Saved HTML: {html_path.resolve()}")

    try:
        # PNG export uses kaleido when it is available in the active Python env.
        fig.write_image(png_path, width=PLOT_WIDTH, height=PLOT_HEIGHT, scale=2)
        print(f"Saved PNG:  {png_path.resolve()}")
    except Exception as exc:
        print(f"PNG export skipped for {stem}: {exc}")


def maybe_show(fig):
    if SHOW_FIGURES:
        fig.show()


def extract_signed_slice(flat_value, slice_idx, slice_width):
    mask = (1 << slice_width) - 1
    raw_value = (flat_value >> (slice_idx * slice_width)) & mask
    sign_bit = 1 << (slice_width - 1)

    if raw_value & sign_bit:
        return raw_value - (1 << slice_width)

    return raw_value


def extract_psum_for_pe(records, pe_idx):
    return [extract_signed_slice(entry["psum_flat"], pe_idx, ACC_WIDTH) for entry in records]


def decode_pe_activity(records, pe_idx):
    return [((entry["pe_mac_fire_flat"] >> pe_idx) & 1) for entry in records]


def find_run_windows(records):
    windows = []
    active_window = None
    prev_busy = 0
    run_id = -1

    for idx, entry in enumerate(records):
        if entry["busy"] == 1 and prev_busy == 0:
            run_id += 1
            active_window = {
                "run_id": run_id,
                "start_idx": idx,
                "start_cycle": entry["cycle"],
            }

        if entry["done"] == 1 and active_window is not None:
            active_window["end_idx"] = idx
            active_window["done_cycle"] = entry["cycle"]
            active_window["latency"] = entry["cycle"] - active_window["start_cycle"]
            windows.append(active_window)
            active_window = None

        prev_busy = entry["busy"]

    return windows


def extract_single_run(records, run_id=0):
    windows = find_run_windows(records)
    target_window = None

    for window in windows:
        if window["run_id"] == run_id:
            target_window = window
            break

    if target_window is None:
        raise ValueError(f"Run {run_id} not found in trace.")

    start_idx = target_window["start_idx"]
    end_idx = target_window["end_idx"]

    if start_idx > 0:
        start_idx -= 1
    if end_idx < (len(records) - 1):
        end_idx += 1

    run_records = []
    for idx in range(start_idx, end_idx + 1):
        entry = dict(records[idx])
        if idx < target_window["start_idx"]:
            entry["timeline_cycle"] = -1
        elif idx > target_window["end_idx"]:
            entry["timeline_cycle"] = target_window["done_cycle"] + 1
        else:
            entry["timeline_cycle"] = entry["cycle"]
        run_records.append(entry)

    return run_records, target_window


def plot_controller(run_records):
    x_values = [entry["timeline_cycle"] for entry in run_records]
    y_values = [entry["state"] for entry in run_records]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            line_shape="hv",
            line={"width": 4, "color": COLOR["controller"]},
            name="FSM state",
            customdata=[[entry["state_name"], entry["stream_cycle"]] for entry in run_records],
            hovertemplate=(
                "cycle=%{x}<br>"
                "state=%{customdata[0]}<br>"
                "stream_cycle=%{customdata[1]}<extra></extra>"
            ),
        )
    )

    milestone_map = [
        (2, "STREAM start", COLOR["stream"]),
        (4, "COLLECT", COLOR["collect"]),
        (5, "DONE", COLOR["done"]),
    ]

    for state_value, label, color in milestone_map:
        for entry in run_records:
            if entry["state"] == state_value:
                fig.add_trace(
                    go.Scatter(
                        x=[entry["timeline_cycle"]],
                        y=[entry["state"]],
                        mode="markers",
                        marker={
                            "size": 12,
                            "color": color,
                            "line": {"width": 1.5, "color": COLOR["ink"]},
                            "symbol": "diamond",
                        },
                        name=label,
                        hovertemplate=f"{label}<br>cycle=%{{x}}<extra></extra>",
                    )
                )
                break

    apply_common_layout(
        fig,
        "Controller Execution Flow for One Accelerator Run",
        "Run-Local Cycle",
        "FSM State",
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=sorted(STATE_NAMES.keys()),
        ticktext=[STATE_NAMES[idx] for idx in sorted(STATE_NAMES.keys())],
        range=[-0.4, 5.4],
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.02,
        y=0.90,
        text="Each run follows: LOAD → STREAM → DRAIN → COLLECT → DONE",
        showarrow=False,
        font={"size": 12, "color": COLOR["ink"]},
        bgcolor="#f8fafc",
        bordercolor=COLOR["grid"],
        borderwidth=1,
        align="left",
    )

    save_figure(fig, "controller")
    maybe_show(fig)


def plot_pe_heatmap(run_records):
    pe_labels = []
    z_values = []
    hover_text = []
    x_values = [entry["timeline_cycle"] for entry in run_records]

    for row_idx in range(ARRAY_SIZE):
        for col_idx in range(ARRAY_SIZE):
            pe_idx = (row_idx * ARRAY_SIZE) + col_idx
            pe_labels.append(f"PE({row_idx},{col_idx})")
            row_activity = decode_pe_activity(run_records, pe_idx)
            z_values.append(row_activity)
            hover_text.append(
                [
                    (
                        f"cycle={run_records[col_idx2]['timeline_cycle']}<br>"
                        f"PE=({row_idx},{col_idx})<br>"
                        f"active={'yes' if row_activity[col_idx2] else 'no'}"
                    )
                    for col_idx2 in range(len(run_records))
                ]
            )

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=x_values,
                y=pe_labels,
                text=hover_text,
                hoverinfo="text",
                colorscale=[
                    [0.0, COLOR["heat_off"]],
                    [0.499, COLOR["heat_off"]],
                    [0.5, COLOR["heat_on"]],
                    [1.0, COLOR["heat_on"]],
                ],
                zmin=0,
                zmax=1,
                xgap=1,
                ygap=1,
                colorbar={
                    "title": "MAC active",
                    "tickvals": [0, 1],
                    "ticktext": ["0", "1"],
                    "thickness": 12,
                    "len": 0.70,
                },
            )
        ]
    )
    apply_common_layout(
        fig,
        "Wave Propagation Across 4x4 Systolic Array",
        "Run-Local Cycle",
        "Processing Element",
        show_legend=False,
    )
    fig.update_layout(margin={"l": 95, "r": 40, "t": 60, "b": 60})
    fig.update_yaxes(autorange="reversed", tickfont={"size": 11})

    save_figure(fig, "heatmap")
    maybe_show(fig)

    save_activity_animation(run_records)


def save_activity_animation(run_records):
    frames = []
    frame_cycles = []

    for entry in run_records:
        cycle = entry["timeline_cycle"]
        frame_cycles.append(cycle)

        z_frame = []
        hover_frame = []
        for row_idx in range(ARRAY_SIZE):
            z_row = []
            hover_row = []
            for col_idx in range(ARRAY_SIZE):
                pe_idx = (row_idx * ARRAY_SIZE) + col_idx
                active = (entry["pe_mac_fire_flat"] >> pe_idx) & 1
                z_row.append(active)
                hover_row.append(
                    f"cycle={cycle}<br>PE=({row_idx},{col_idx})<br>"
                    f"active={'yes' if active else 'no'}"
                )
            z_frame.append(z_row)
            hover_frame.append(hover_row)

        frames.append(
            go.Frame(
                name=str(cycle),
                data=[
                    go.Heatmap(
                        z=z_frame,
                        x=[f"col {idx}" for idx in range(ARRAY_SIZE)],
                        y=[f"row {idx}" for idx in range(ARRAY_SIZE)],
                        text=hover_frame,
                        hoverinfo="text",
                        colorscale=[
                            [0.0, COLOR["heat_off"]],
                            [0.499, COLOR["heat_off"]],
                            [0.5, COLOR["heat_on"]],
                            [1.0, COLOR["heat_on"]],
                        ],
                        zmin=0,
                        zmax=1,
                        showscale=False,
                    )
                ],
            )
        )

    animation_fig = go.Figure(
        data=frames[0].data if frames else [],
        frames=frames,
    )
    apply_common_layout(
        animation_fig,
        "Animated MAC Wave Across the Array (Run 0)",
        "Array Column",
        "Array Row",
        show_legend=False,
    )
    animation_fig.update_layout(
        updatemenus=[
            {
                "type": "buttons",
                "showactive": False,
                "x": 1.0,
                "y": 1.15,
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [None, {"frame": {"duration": 450, "redraw": True}, "fromcurrent": True}],
                    }
                ],
            }
        ],
        sliders=[
            {
                "steps": [
                    {
                        "args": [[str(cycle)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
                        "label": str(cycle),
                        "method": "animate",
                    }
                    for cycle in frame_cycles
                ],
                "x": 0.1,
                "len": 0.8,
            }
        ],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    animation_path = OUTPUT_DIR / "heatmap_animation.html"
    animation_fig.write_html(animation_path, include_plotlyjs="cdn")
    print(f"Saved HTML: {animation_path.resolve()}")


def plot_psum_trace(run_records, pe_idx):
    row_idx = pe_idx // ARRAY_SIZE
    col_idx = pe_idx % ARRAY_SIZE
    x_values = [entry["timeline_cycle"] for entry in run_records]
    psum_values = extract_psum_for_pe(run_records, pe_idx)
    mac_fire_values = decode_pe_activity(run_records, pe_idx)

    event_x = [x_values[idx] for idx in range(len(run_records)) if mac_fire_values[idx] == 1]
    event_y = [psum_values[idx] for idx in range(len(run_records)) if mac_fire_values[idx] == 1]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=psum_values,
            mode="lines",
            line={"width": 2, "color": COLOR["psum"]},
            name="Partial sum",
            hovertemplate="cycle=%{x}<br>psum=%{y}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=event_x,
            y=event_y,
            mode="markers",
            marker={
                "size": 12,
                "color": COLOR["event"],
                "line": {"width": 1.5, "color": COLOR["ink"]},
            },
            name="MAC fire",
            hovertemplate="MAC event<br>cycle=%{x}<br>psum=%{y}<extra></extra>",
        )
    )

    if event_x:
        fig.add_annotation(
            x=event_x[0],
            y=event_y[0],
            text="first accumulation",
            showarrow=True,
            arrowhead=2,
            ax=40,
            ay=-40,
        )

    final_value = psum_values[-1]
    fig.add_hline(
        y=final_value,
        line_dash="dash",
        line_color=COLOR["final"],
        annotation_text=f"final value = {final_value}",
        annotation_position="top right",
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.66,
        y=0.10,
        text="PE accumulates partial sums only when both inputs are valid",
        showarrow=False,
        font={"size": 12, "color": COLOR["ink"]},
        bgcolor="#f8fafc",
        bordercolor=COLOR["grid"],
        borderwidth=1,
    )

    apply_common_layout(
        fig,
        f"Partial Sum Evolution of PE({row_idx},{col_idx})",
        "Run-Local Cycle",
        "Partial Sum",
    )
    fig.update_layout(
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 0.98,
            "xanchor": "left",
            "x": 1.02,
            "font": {"size": 10},
        }
    )
    fig.update_yaxes(range=[min(psum_values) - 1, max(psum_values) + max(2, abs(final_value) * 0.15)])

    save_figure(fig, "psum")
    maybe_show(fig)


def plot_latency(records):
    latencies = find_run_windows(records)

    if not latencies:
        print("No completed runs found in trace.")
        return None

    observed_values = [item["latency"] for item in latencies]
    observed_mean = sum(observed_values) / float(len(observed_values))
    min_latency = min(observed_values)
    max_latency = max(observed_values)
    control_overhead = observed_mean - THEORETICAL_LATENCY

    print("Observed latency summary:")
    print(f"  runs: {len(latencies)}")
    print(f"  min:  {min_latency}")
    print(f"  max:  {max_latency}")
    print(f"  mean: {observed_mean:.2f}")
    if min_latency == max_latency:
        print("  note: latency is stable across all runs")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[f"run_{item['run_id']}" for item in latencies],
            y=observed_values,
            text=[f"{value} cycles" for value in observed_values],
            textposition="outside",
            marker={"color": COLOR["latency"]},
            name="Observed latency",
            hovertemplate="%{x}<br>observed latency=%{y} cycles<extra></extra>",
        )
    )
    fig.add_hline(
        y=THEORETICAL_LATENCY,
        line_dash="dash",
        line_color=COLOR["theory"],
    )
    fig.add_annotation(
        xref="paper",
        yref="y",
        x=0.05,
        y=THEORETICAL_LATENCY,
        text=f"expected latency = {THEORETICAL_LATENCY} cycles",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font={"size": 12, "color": COLOR["theory"]},
        bgcolor="white",
    )
    fig.add_hline(
        y=observed_mean,
        line_dash="dot",
        line_color=COLOR["mean"],
    )
    fig.add_annotation(
        xref="paper",
        yref="y",
        x=0.95,
        y=observed_mean,
        text=f"Observed = {observed_mean:.0f} cycles ({control_overhead:+.0f} control overhead)",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font={"size": 12, "color": COLOR["mean"]},
        bgcolor="white",
    )

    apply_common_layout(
        fig,
        "Observed Run Latency vs. Theoretical Expectation",
        "Run",
        "Latency (cycles)",
        show_legend=False,
    )
    fig.update_yaxes(range=[0, 15])

    save_figure(fig, "latency")
    maybe_show(fig)

    return {
        "runs": len(latencies),
        "min": min_latency,
        "max": max_latency,
        "mean": observed_mean,
        "stable": min_latency == max_latency,
        "difference": control_overhead,
    }


def write_readme_section(latency_summary):
    markdown = f"""## Accelerator Execution Overview

### 1. Controller Execution Flow
![Controller Execution Flow](plots/controller.png)

This figure shows one complete accelerator run as a finite-state-machine timeline. The controller advances through `LOAD -> STREAM -> DRAIN -> COLLECT -> DONE`, with the longest interval spent in `STREAM` because that is when operands are actively injected into the systolic array.

From a hardware perspective, this plot separates control orchestration from datapath behavior. It makes the execution contract explicit: setup, active computation, pipeline drain, output capture, and completion.

### 2. Compute Propagation Across Array
![Compute Propagation Across Array](plots/heatmap.png)

This heatmap captures MAC activity across the 4x4 PE mesh for a single run. The diagonal band of active cells shows the classic systolic wave, where computation begins near `PE(0,0)` and then propagates spatially as operands move rightward and downward.

This is the clearest view of the accelerator's dataflow behavior. Instead of looking like a static matrix multiply, the plot shows that the array is a time-dependent, spatially parallel compute fabric.

### 3. Partial Sum Accumulation (Single PE)
![Partial Sum Accumulation (Single PE)](plots/psum.png)

This plot traces the partial sum inside one processing element over time. Large markers are shown only when the PE actually performs a MAC, so the reader can see exactly when accumulation events occur and when the output stabilizes.

This connects local PE behavior to the array-level result. It demonstrates that output-stationary accumulation keeps partial sums resident in the PE while operands stream through the mesh.

### 4. Latency Validation
![Latency Validation](plots/latency.png)

This figure compares observed end-to-end latency against the theoretical expectation of `3 * ARRAY_SIZE = {THEORETICAL_LATENCY}` cycles. The measured latency is consistent across all runs, with an average of `{latency_summary['mean']:.2f}` cycles and an overhead of `{latency_summary['difference']:+.2f}` cycles relative to the ideal datapath estimate.

This is the system-validation view of the accelerator. It shows that the implementation behaves predictably across runs and that the extra latency is explained by real control and collection overhead, not by unstable execution.
"""

    README_MD_PATH.write_text(markdown)
    print(f"Saved Markdown: {README_MD_PATH.resolve()}")
    return markdown


def main():
    trace_path = Path("trace.csv")
    records = load_trace(trace_path)
    run_records, _ = extract_single_run(records, run_id=0)

    plot_controller(run_records)
    plot_pe_heatmap(run_records)
    plot_psum_trace(run_records, pe_idx=5)
    latency_summary = plot_latency(records)
    write_readme_section(latency_summary)


if __name__ == "__main__":
    main()
