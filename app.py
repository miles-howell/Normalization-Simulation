"""Interactive dashboard for the simulation. Run with:  streamlit run app.py"""
from collections import OrderedDict
from dataclasses import asdict, replace

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from normalization_sim.dashboard import (
    CONTROL_GROUPS, CONTROLS, PRESETS, Params, affiliation_shares, format_days, frame_days, opinion_density,
    params_key, parse_days, preset_params, run_recorded, spring_layout, summarize,
)
from normalization_sim.outliers_config import OUTLIERS

# Categorical slots in fixed order (series 1 is always scenario A / the first series, 2 scenario B, ...)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Sequential blue for density, light -> dark
DENSITY_SCALE = [[0.0, "#f4f8fd"], [0.15, "#b7d3f2"], [0.4, "#5f9ce3"], [0.7, "#2a78d6"], [1.0, "#0d3a73"]]
MUTED = "#8a8985"
# Diverging blue <-> red with a neutral gray midpoint, for opinions in [-1, 1]. The midpoint is a mid gray rather
# than the near-white surface gray so centrist agents stay visible on the light background
OPINION_SCALE = [[0.0, "#1f5fae"], [0.25, "#7aa9e3"], [0.5, "#bdbcb6"], [0.75, "#ee8a83"], [1.0, "#b8302f"]]
INK = "#0b0b0b"

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


@st.cache_data(max_entries=8, show_spinner="Laying out the network...")
def cached_layout(adj):
    return spring_layout(adj)


def network_figure(run, pos, arrange, color_by, links):
    """Animated network of agents, one frame per sampled day.

    Traces are plain dicts and the figure skips plotly's validation: validating the hundreds of per-frame traces
    took seconds. Numbers are sent as float32 (plotly ships numpy arrays as binary) to keep the page small.
    """
    by_opinion = arrange == "Opinion"
    src, dst = np.nonzero(np.triu(run.adj))
    moving_links = by_opinion and links
    # Links are only in every frame when nodes move; then keep frames x links roughly constant
    days = frame_days(run.params.days, int(np.clip(60_000 // max(len(src), 1), 20, 75)) if moving_links else 75)
    size_ref = max(np.percentile(run.on_hand, 98), 1e-9)
    names = np.array([k.replace("_", " ") for k in OUTLIERS] + ["no group"], dtype=object)
    group_index = {k: i for i, k in enumerate(list(OUTLIERS) + ["none"])}
    camp = np.where(run.is_minority, "minority", "majority")
    agent_ids = np.arange(len(camp)).astype(str)
    if color_by == "Group":
        categories = [(names[i], SERIES[i] if i < len(OUTLIERS) else MUTED) for i in range(len(names))]
    elif color_by == "Majority / minority":
        categories = [("majority", SERIES[0]), ("minority", SERIES[1])]
    else:
        categories = [(None, None)]

    f32 = lambda a: np.asarray(a, dtype=np.float32)

    def coords(day):
        return f32(run.opinions[day] if by_opinion else pos[:, 0]), f32(pos[:, 1])

    def link_xy(values):
        # Each link is a segment followed by a gap
        return np.column_stack([values[src], values[dst], np.full(len(src), np.nan, dtype=np.float32)]).ravel()

    def link_trace(day):
        x, y = coords(day)
        return dict(type="scatter", x=link_xy(x), y=link_xy(y), mode="lines", hoverinfo="skip",
                    line=dict(color="rgba(138,137,133,0.18)", width=1), showlegend=False)

    def node_traces(day):
        x, y = coords(day)
        group = names[[group_index[a] for a in run.affil[day]]]
        on_hand = run.on_hand[day]
        starving = on_hand < run.params.survival_floor
        size = f32(7 + 11 * np.sqrt(np.clip(on_hand / size_ref, 0, 1)))
        # Hover text: whatever the legend doesn't already say (the trace name is added in the hovertemplate)
        text = {"Group": camp, "Majority / minority": group}.get(color_by, group + " · " + camp)
        custom = f32(np.column_stack([run.opinions[day], on_hand]))
        label = group if color_by == "Group" else camp
        traces = []
        for name, color in categories:
            m = np.ones(len(x), dtype=bool) if name is None else label == name
            # Ring: white normally, dark when starving (0/1 through a two-color scale is far smaller than strings)
            marker = dict(size=size[m], line=dict(color=starving[m].astype(np.uint8), cmin=0, cmax=1, width=2,
                                                  colorscale=[[0, "white"], [1, INK]]))
            if color is None:
                marker.update(color=f32(run.opinions[day]), colorscale=OPINION_SCALE, cmin=-1, cmax=1,
                              colorbar=dict(title=dict(text="Opinion"), thickness=12, len=0.6))
            else:
                marker.update(color=color)
            traces.append(dict(
                type="scatter", x=x[m], y=y[m], ids=agent_ids[m], mode="markers", marker=marker,
                name=name.capitalize() if name else None, showlegend=name is not None, text=text[m],
                customdata=custom[m],
                hovertemplate=("%{fullData.name} · " if name else "") + "%{text}<br>Opinion %{customdata[0]:.2f}"
                              "<br>On hand %{customdata[1]:.2f}<extra></extra>",
            ))
        return traces

    first = node_traces(days[0])
    starving_key = dict(type="scatter", x=[None], y=[None], mode="markers", name="Starving (dark ring)",
                        marker=dict(size=11, color="white", line=dict(color=INK, width=2)))
    links_now = link_trace(days[0]) if links else dict(type="scatter", x=[], y=[], showlegend=False)
    # Frames update the node traces, plus the links when nodes move with their opinions
    animated = ([0] if moving_links else []) + list(range(1, 1 + len(first)))
    # Frame data is merged into the traces, so moving links only need their new x
    frames = [dict(name=str(d), traces=animated,
                   data=([dict(x=link_xy(coords(d)[0]))] if moving_links else []) + node_traces(d)) for d in days]

    play = dict(frame=dict(duration=180, redraw=False), transition=dict(duration=120), fromcurrent=True,
                mode="immediate")
    # Controls sit under the plot, below the opinion axis when it is shown
    controls_y = -0.1 if by_opinion else -0.02
    axis = dict(range=[-1.1, 1.1], showgrid=False)
    xaxis = (dict(axis, title=dict(text="Opinion"), zeroline=True, zerolinecolor="rgba(138,137,133,0.5)")
             if by_opinion else dict(axis, visible=False, scaleanchor="y"))
    layout = dict(
        height=660, margin=dict(l=10, r=10, t=40, b=10), hovermode="closest", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0), xaxis=xaxis, yaxis=dict(axis, visible=False),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=controls_y, xanchor="left", yanchor="top",
                          pad=dict(t=10, r=10), showactive=False, buttons=[
                              dict(label="▶ Play", method="animate", args=[None, play]),
                              dict(label="❚❚ Pause", method="animate",
                                   args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                          ])],
        sliders=[dict(active=0, x=0.16, len=0.84, y=controls_y, yanchor="top", pad=dict(t=10),
                      currentvalue=dict(prefix="Day ", font=dict(size=13)),
                      steps=[dict(label=str(d), method="animate",
                                  args=[[str(d)], dict(mode="immediate", frame=dict(duration=0, redraw=False),
                                                       transition=dict(duration=0))]) for d in days])],
    )
    return go.Figure(dict(data=[links_now] + first + [starving_key], layout=layout, frames=frames), _validate=False)


def view_network(run):
    c1, c2, c3 = st.columns([2, 3, 1])
    arrange = c1.segmented_control("Arrange by", ["Network", "Opinion"], default="Network", key="net_arrange",
                                   help="Network: fixed positions from the links. Opinion: x is the agent's "
                                        "opinion that day, so agents move as opinions shift") or "Network"
    color_by = c2.segmented_control("Color by", ["Opinion", "Group", "Majority / minority"], default="Opinion",
                                    key="net_color") or "Opinion"
    links = c3.toggle("Show links", value=arrange == "Network", key=f"net_links_{arrange}")
    st.caption("Each dot is an agent; size is what it has on hand after aid, a dark ring means it is starving. "
               "Press Play or drag the day slider under the chart. Hover a dot for details.")
    pos = cached_layout(run.adj)
    # The toolbar would cover the long group legend; drag-to-zoom and double-click-to-reset still work without it
    st.plotly_chart(network_figure(run, pos, arrange, color_by, links), config={"displayModeBar": False})


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

view = st.segmented_control("View", ["Dashboard", "Opinions", "Network", "Compare A/B", "Data"],
                            default="Dashboard", key="view", label_visibility="collapsed") or "Dashboard"
run_a = get_run(a)
if view == "Dashboard":
    view_dashboard(run_a)
elif view == "Opinions":
    view_opinions(run_a)
elif view == "Network":
    view_network(run_a)
elif view == "Compare A/B":
    view_compare(run_a, a)
else:
    view_data(run_a)
