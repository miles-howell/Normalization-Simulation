"""Interactive dashboard for the simulation. Run with:  streamlit run app.py"""
from collections import OrderedDict
from dataclasses import asdict, replace

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from normalization_sim.dashboard import (
    CONTROL_GROUPS, CONTROLS, PRESETS, Params, affiliation_shares, format_days, opinion_density, params_key,
    parse_days, preset_params, run_recorded, summarize,
)

# Categorical slots in fixed order (series 1 is always scenario A / the first series, 2 scenario B, ...)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Sequential blue for density, light -> dark
DENSITY_SCALE = [[0.0, "#f4f8fd"], [0.15, "#b7d3f2"], [0.4, "#5f9ce3"], [0.7, "#2a78d6"], [1.0, "#0d3a73"]]
MUTED = "#8a8985"

METRIC_LABELS = {
    "stability": "Stability",
    "inequality": "Inequality (Gini)",
    "diversity": "Opinion diversity",
    "avg_trust": "Average trust",
    "avg_trust_in": "In-group trust",
    "avg_trust_out": "Out-group trust",
    "minority_starvation_rate": "Minority starvation",
    "majority_starvation_rate": "Majority starvation",
    "overall_starvation_rate": "Overall starvation",
    "affil_entropy": "Affiliation diversity",
    "mean_opinion": "Mean opinion",
    "opinion_std": "Opinion spread (sd)",
    "extreme_share": "Share at the bounds",
}
# Metrics where a rise is bad news, so their deltas are colored inversely
BAD_WHEN_UP = {"inequality", "minority_starvation_rate", "majority_starvation_rate", "overall_starvation_rate",
               "extreme_share", "opinion_std"}

st.set_page_config(page_title="Normalization Simulation", layout="wide")


# --- parameters ---------------------------------------------------------------------------------------------

def to_widget(field, value):
    kind = CONTROLS[field].kind
    if kind == "toggle":
        return bool(value)
    if kind == "days":
        return format_days(value)
    return value


def from_widget(field, value):
    kind = CONTROLS[field].kind
    if kind == "toggle":
        return int(value)
    if kind == "days":
        try:
            return parse_days(value)
        except ValueError:
            return None
    if kind == "int":
        return int(value)
    return float(value)


def load_params(p: Params, prefix: str):
    for field in CONTROLS:
        st.session_state[prefix + field] = to_widget(field, getattr(p, field))


def render_control(field, key, where=st):
    c = CONTROLS[field]
    if c.kind == "toggle":
        where.toggle(c.label, key=key, help=c.help or None)
    elif c.kind == "days":
        where.text_input(c.label, key=key, help=c.help or None, placeholder="none")
    elif c.kind == "int":
        where.number_input(c.label, min_value=int(c.lo), max_value=int(c.hi), step=int(c.step), key=key,
                           help=c.help or None)
    else:
        where.slider(c.label, min_value=float(c.lo), max_value=float(c.hi), step=float(c.step), key=key,
                     help=c.help or None)


def read_params(prefix: str) -> Params:
    values = {}
    for field in CONTROLS:
        v = from_widget(field, st.session_state[prefix + field])
        if v is None:
            st.sidebar.error("Disaster days must be whole numbers separated by spaces; ignoring them.")
            v = ()
        values[field] = v
    return replace(Params(), **values)


def apply_preset():
    load_params(preset_params(st.session_state.preset), "a_")


if "a_lambda_" not in st.session_state:
    st.session_state.preset = next(iter(PRESETS))
    apply_preset()


# --- runs ---------------------------------------------------------------------------------------------------

@st.cache_resource
def run_store():
    # Shared across sessions; a run is a pure function of its Params, so it is safe to share
    return OrderedDict()


def get_run(p: Params):
    store, key = run_store(), params_key(p)
    if key in store:
        store.move_to_end(key)
        return store[key]
    bar = st.progress(0.0, text="Simulating...")
    result = run_recorded(p, on_day=lambda d: bar.progress((d + 1) / p.days, text=f"Simulating day {d + 1} of {p.days}"))
    bar.empty()
    store[key] = result
    while len(store) > 16:
        store.popitem(last=False)
    return result


# --- charts -------------------------------------------------------------------------------------------------

def base_layout(fig, title, yrange=None, height=320):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)), height=height, margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        xaxis_title="Day",
    )
    fig.update_xaxes(showgrid=False)
    if yrange:
        fig.update_yaxes(range=yrange)
    return fig


def mark_disasters(fig, metrics):
    for day in metrics.loc[metrics["disaster_loss"] > 0, "day"]:
        fig.add_vline(x=day, line=dict(color=MUTED, width=1, dash="dot"))


def line_chart(metrics, cols, title, yrange=(0, 1), dashes=None):
    fig = go.Figure()
    for i, col in enumerate(cols):
        fig.add_trace(go.Scatter(
            x=metrics["day"], y=metrics[col], name=METRIC_LABELS[col], mode="lines",
            line=dict(color=SERIES[i], width=2, dash=(dashes or {}).get(col, "solid")),
            hovertemplate="%{y:.3f}",
        ))
    mark_disasters(fig, metrics)
    return base_layout(fig, title, yrange)


def opinion_band_chart(metrics, title="Mean opinion ± 1 sd"):
    fig = go.Figure()
    day, mean, sd = metrics["day"], metrics["mean_opinion"], metrics["opinion_std"]
    fig.add_trace(go.Scatter(x=day, y=mean + sd, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=day, y=mean - sd, fill="tonexty", fillcolor="rgba(42,120,214,0.15)",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=day, y=mean, name="Mean opinion", line=dict(color=SERIES[0], width=2),
                             hovertemplate="%{y:.3f}"))
    mark_disasters(fig, metrics)
    return base_layout(fig, title, (-1, 1))


def density_heatmap(run, title="Opinion distribution over time", height=360):
    centers, density = opinion_density(run.opinions)
    fig = go.Figure(go.Heatmap(
        x=run.metrics["day"], y=centers, z=density, colorscale=DENSITY_SCALE, zmin=0,
        colorbar=dict(title="Share", thickness=12),
        hovertemplate="Day %{x}<br>Opinion %{y:.2f}<br>Share %{z:.1%}<extra></extra>",
    ))
    fig = base_layout(fig, title, (-1, 1), height)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(title="Opinion")
    return fig


def kpi_row(metrics, cols):
    settled = summarize(metrics)
    start = metrics.head(10).mean(numeric_only=True)
    for box, col in zip(st.columns(len(cols)), cols):
        change = settled[col] - start[col]
        color = "off" if abs(change) < 0.0005 else "inverse" if col in BAD_WHEN_UP else "normal"
        box.metric(METRIC_LABELS[col], f"{settled[col]:.3f}", f"{change:+.3f} vs first 10 days",
                   delta_color=color, delta_arrow="off" if color == "off" else "auto", border=True)


# --- views --------------------------------------------------------------------------------------------------

def view_dashboard(run):
    st.caption("Tiles: mean over the last 30 days, change against the first 10. Dotted lines mark disasters.")
    kpi_row(run.metrics, ["stability", "inequality", "minority_starvation_rate", "avg_trust_out", "extreme_share"])
    left, right = st.columns(2)
    left.plotly_chart(line_chart(run.metrics, ["stability", "inequality"], "Stability and inequality"))
    right.plotly_chart(line_chart(run.metrics, ["avg_trust", "avg_trust_in", "avg_trust_out"], "Trust",
                                  dashes={"avg_trust_in": "dot", "avg_trust_out": "dash"}))
    left.plotly_chart(line_chart(run.metrics, ["minority_starvation_rate", "majority_starvation_rate",
                                               "overall_starvation_rate"], "Starvation by group",
                                 dashes={"majority_starvation_rate": "dash", "overall_starvation_rate": "dot"}))
    right.plotly_chart(line_chart(run.metrics, ["diversity", "affil_entropy", "extreme_share"],
                                  "Diversity and extremity"))
    st.plotly_chart(opinion_band_chart(run.metrics))


def view_opinions(run):
    st.plotly_chart(density_heatmap(run))
    last = len(run.metrics) - 1
    day = st.slider("Day", 0, last, last, help="Pick a day to see who holds which opinion")
    ops = run.opinions[day]
    left, right = st.columns(2)
    hist = go.Figure()
    for i, (name, mask) in enumerate([("Majority", ~run.is_minority), ("Minority", run.is_minority)]):
        hist.add_trace(go.Histogram(x=ops[mask], name=name, xbins=dict(start=-1, end=1, size=0.05),
                                    marker=dict(color=SERIES[i], line=dict(color="white", width=1))))
    hist = base_layout(hist, f"Opinions on day {day}")
    hist.update_layout(barmode="stack", hovermode="x unified", xaxis_title="Opinion", yaxis_title="Agents",
                       legend_traceorder="normal")
    hist.update_xaxes(range=[-1, 1])
    hist.update_yaxes(range=None, autorange=True)
    left.plotly_chart(hist)

    shares = affiliation_shares(run.affil).drop(columns="none")
    area = go.Figure()
    for i, col in enumerate(shares.columns):
        area.add_trace(go.Scatter(x=run.metrics["day"], y=shares[col], name=col.replace("_", " "), stackgroup="g",
                                  mode="lines", line=dict(color=SERIES[i], width=1), hovertemplate="%{y:.1%}"))
    area.add_vline(x=day, line=dict(color=MUTED, width=1))
    area = base_layout(area, "Outlier group membership (share of agents)", height=380)
    # Five long group names don't fit above the plot; list them under it
    area.update_layout(legend=dict(y=-0.3, yanchor="top", traceorder="normal"), margin=dict(b=10))
    area.update_yaxes(tickformat=".0%", rangemode="tozero")
    right.plotly_chart(area)


def view_compare(run_a, a: Params):
    st.markdown("Scenario **B** is scenario A (the sidebar) with the changes below. Both use the same seed.")
    saved = st.session_state.setdefault("b_overrides", {"engagement": int(not a.engagement)})
    chosen = st.multiselect("Change in scenario B", list(CONTROLS), default=list(saved),
                            format_func=lambda f: CONTROLS[f].label)
    with st.form("scenario_b"):
        cols = st.columns(3)
        for i, field in enumerate(chosen):
            value = saved.get(field, getattr(a, field))
            st.session_state.setdefault("b_" + field, to_widget(field, value))
            render_control(field, "b_" + field, cols[i % 3])
        if st.form_submit_button("Run comparison", type="primary"):
            new = {f: from_widget(f, st.session_state["b_" + f]) for f in chosen}
            st.session_state.b_overrides = {f: (() if v is None else v) for f, v in new.items()}
            st.rerun()
    overrides = st.session_state.b_overrides
    if not overrides:
        st.info("Pick at least one parameter to change.")
        return
    run_b = get_run(replace(a, **overrides))

    shown = lambda f, v: ("on" if v else "off") if CONTROLS[f].kind == "toggle" else to_widget(f, v) or "none"
    changes = ", ".join(f"{CONTROLS[f].label} = {shown(f, v)}" for f, v in overrides.items())
    st.subheader(f"A: sidebar settings · B: {changes}")
    sa, sb = summarize(run_a.metrics), summarize(run_b.metrics)
    table = (
        sa.to_frame("A").join(sb.to_frame("B")).assign(**{"B − A": lambda t: t["B"] - t["A"]})
        .rename(index=METRIC_LABELS)
    )
    st.caption("Mean over the last 30 days")
    st.dataframe(table.style.format("{:.3f}"), width="stretch", height="content")

    picked = st.multiselect(
        "Metrics to compare", list(METRIC_LABELS), format_func=METRIC_LABELS.get,
        default=["stability", "avg_trust_out", "minority_starvation_rate", "extreme_share", "opinion_std",
                 "inequality"],
    )
    cols = st.columns(2)
    for i, metric in enumerate(picked):
        fig = go.Figure()
        for j, (name, run) in enumerate([("A", run_a), ("B", run_b)]):
            fig.add_trace(go.Scatter(x=run.metrics["day"], y=run.metrics[metric], name=name, mode="lines",
                                     line=dict(color=SERIES[j], width=2), hovertemplate="%{y:.3f}"))
        mark_disasters(fig, run_a.metrics)
        yrange = (-1, 1) if metric == "mean_opinion" else (0, 1)
        cols[i % 2].plotly_chart(base_layout(fig, METRIC_LABELS[metric], yrange, height=280))

    left, right = st.columns(2)
    left.plotly_chart(density_heatmap(run_a, "Opinions over time: A", height=320))
    right.plotly_chart(density_heatmap(run_b, "Opinions over time: B", height=320))


def view_data(run):
    st.dataframe(run.metrics, width="stretch", hide_index=True)
    st.download_button("Download metrics.csv", run.metrics.to_csv(index=False), "metrics.csv", "text/csv")
    st.json(asdict(run.params), expanded=False)


# --- page ---------------------------------------------------------------------------------------------------

with st.sidebar:
    st.header("Scenario A")
    st.selectbox("Preset", list(PRESETS), key="preset", on_change=apply_preset,
                 help="Loads a starting point; you can tweak any dial afterwards")
    with st.form("scenario_a"):
        st.form_submit_button("Run simulation", type="primary", width="stretch")
        for i, (group, controls) in enumerate(CONTROL_GROUPS.items()):
            with st.expander(group, expanded=i == 0):
                for c in controls:
                    render_control(c.field, "a_" + c.field)

st.title("Normalization vs. Outliers")
a = read_params("a_")
mode = "engagement" if a.engagement else "normalizing"
st.caption(f"{a.N} agents · {a.days} days · feed attention {a.lambda_:.2f} ({mode} feed) · seed {a.seed}")

view = st.segmented_control("View", ["Dashboard", "Opinions", "Compare A/B", "Data"], default="Dashboard",
                            key="view", label_visibility="collapsed") or "Dashboard"
run_a = get_run(a)
if view == "Dashboard":
    view_dashboard(run_a)
elif view == "Opinions":
    view_opinions(run_a)
elif view == "Compare A/B":
    view_compare(run_a, a)
else:
    view_data(run_a)
