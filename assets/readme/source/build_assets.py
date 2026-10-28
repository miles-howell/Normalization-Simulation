"""Build the README SVGs from real simulation runs.

Run from the repository root:  python assets/readme/source/build_assets.py
Runs the same seed (7, 150 days, lambda 0.5) with a normalizing and an engagement feed.
"""
import os
import sys

sys.path.insert(0, os.getcwd())
from normalization_sim.sim import Params, Simulation  # noqa: E402

OUT = os.path.join("assets", "readme")
BG, PANEL, INK, MUTED, RULE = "#12151A", "#1A1F27", "#F2EEE6", "#9AA3AE", "#2C333D"
BLUE, ORANGE = "#5DA9E9", "#F08A4B"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif"
SERIF = "Georgia, 'Songti SC', serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, monospace"


def run(engagement):
    sim = Simulation(Params(seed=7, days=150, lambda_=0.5, engagement=engagement))
    df = sim.run()
    return sim.opinions.copy(), df


def swarm(values, width, r, limit):
    """Place dots at their opinion (x) and stack them vertically so they do not overlap."""
    placed = []
    for v in sorted(values):
        x = (v + 1) / 2 * width
        k = 0
        while True:
            cands = [0] if k == 0 else [k * r * 1.7, -k * r * 1.7]
            ok = None
            for dy in cands:
                if all((x - px) ** 2 + (dy - py) ** 2 >= (2 * r + 0.6) ** 2 for px, py in placed[-120:]):
                    ok = dy
                    break
            if ok is not None:
                break
            k += 1
        ok = max(-limit, min(limit, ok))
        placed.append((x, ok))
    return placed


def strip(values, x0, cy, width, r=3.5):
    parts = []
    for x, dy in swarm(values, width, r, 44):
        col = BLUE if x < width / 2 else ORANGE
        parts.append(f'<circle cx="{x0 + x:.1f}" cy="{cy + dy:.1f}" r="{r}" fill="{col}"/>')
    return "\n    ".join(parts)


def axis(x0, y, width):
    s = f'<line x1="{x0}" y1="{y}" x2="{x0 + width}" y2="{y}" stroke="{RULE}" stroke-width="2"/>'
    for frac, lab in ((0, "−1"), (0.5, "0"), (1, "+1")):
        x = x0 + frac * width
        anchor = "start" if frac == 0 else "end" if frac == 1 else "middle"
        s += (f'<line x1="{x}" y1="{y - 6}" x2="{x}" y2="{y + 6}" stroke="{MUTED}" stroke-width="2"/>'
              f'<text x="{x}" y="{y + 28}" text-anchor="{anchor}" font-family="{MONO}" font-size="18" fill="{MUTED}">{lab}</text>')
    return s


def head(w, h, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-labelledby="t d">\n  <title id="t">{title}</title>\n  <desc id="d">{desc}</desc>\n'
            f'  <rect width="{w}" height="{h}" rx="26" fill="{BG}"/>\n')


def hero(norm, eng):
    h = head(1200, 470, "Normalization vs. Outliers",
             "Two beeswarm strips of 240 simulated agents' opinions after 150 days: with a normalizing feed they "
             "cluster near zero, with an engagement feed they split into two camps.")
    h += f'''  <g id="title-block" transform="translate(64 0)">
    <text x="0" y="92" font-family="{MONO}" font-size="18" letter-spacing="2" fill="{MUTED}">AGENT-BASED SIMULATION · PYTHON</text>
    <text x="0" y="178" font-family="{SERIF}" font-size="64" font-weight="700" fill="{INK}">Normalization</text>
    <text x="0" y="250" font-family="{SERIF}" font-size="64" font-weight="700" fill="{INK}">vs. <tspan fill="{ORANGE}" font-style="italic">Outliers</tspan></text>
    <text x="0" y="308" font-family="{SANS}" font-size="24" fill="{INK}">Turn an algorithmic feed from calm to</text>
    <text x="0" y="342" font-family="{SANS}" font-size="24" fill="{INK}">outrage and watch opinions, trust and</text>
    <text x="0" y="376" font-family="{SANS}" font-size="24" fill="{INK}">mutual aid respond.</text>
    <text x="0" y="426" font-family="{MONO}" font-size="18" fill="{MUTED}">240 agents · 150 days · seed 7 · λ = 0.5</text>
  </g>
  <rect x="610" y="36" width="530" height="398" rx="18" fill="{PANEL}"/>
'''
    for top, vals, name, stat, col in ((36, norm, "Normalizing feed", f"spread {norm.std():.2f}", BLUE),
                                       (236, eng, "Engagement feed", f"spread {eng.std():.2f}", ORANGE)):
        h += f'''  <g transform="translate(0 {top - 36})">
    <text x="642" y="80" font-family="{SANS}" font-size="22" font-weight="700" fill="{INK}">{name}</text>
    <text x="1108" y="80" text-anchor="end" font-family="{MONO}" font-size="20" fill="{col}">{stat}</text>
    {strip(vals, 646, 142, 456)}
    {axis(646, 198, 456)}
  </g>
'''
    return h + "</svg>\n"


def workflow(n, e):
    last = lambda df, c: df[c].tail(50).mean()
    cols = [("Opinion spread", "opinion_std", "{:.2f}"), ("Out-group trust", "avg_trust_out", "{:.2f}"),
            ("Minority starvation", "minority_starvation_rate", "{:.2f}"), ("Stability", "stability", "{:.2f}")]
    h = head(1200, 430, "How the feed dial reaches hardship",
             "Normalizing versus engagement feed at lambda 0.5: opinion spread, out-group trust, minority "
             "starvation and stability, averaged over the last 50 days of a seed-7 run.")
    x0, cw = 270, 200
    h += f'  <text x="64" y="76" font-family="{MONO}" font-size="18" letter-spacing="2" fill="{MUTED}">FEED  →  OPINIONS  →  TRUST  →  HARDSHIP</text>\n'
    for i, (lab, _, _) in enumerate(cols):
        x = x0 + i * (cw + 24)
        h += (f'  <rect x="{x}" y="104" width="{cw}" height="64" rx="12" fill="{PANEL}" stroke="{RULE}" stroke-width="2"/>\n'
              f'  <text x="{x + cw / 2}" y="144" text-anchor="middle" font-family="{SANS}" font-size="20" font-weight="700" fill="{INK}">{lab}</text>\n')
        if i:
            h += f'  <path d="M{x - 18} 136 h12 m-5 -6 l6 6 l-6 6" fill="none" stroke="{MUTED}" stroke-width="2"/>\n'
    for row, (name, sub, df, col) in enumerate((("Normalizing feed", "mainstream content", n, BLUE),
                                                ("Engagement feed", "own side + outrage", e, ORANGE))):
        y = 196 + row * 98
        h += (f'  <rect x="48" y="{y}" width="1104" height="82" rx="14" fill="{PANEL}"/>\n'
              f'  <rect x="48" y="{y}" width="8" height="82" rx="4" fill="{col}"/>\n'
              f'  <text x="76" y="{y + 36}" font-family="{SANS}" font-size="22" font-weight="700" fill="{INK}">{name}</text>\n'
              f'  <text x="76" y="{y + 64}" font-family="{SANS}" font-size="18" fill="{MUTED}">{sub}</text>\n')
        for i, (_, c, f) in enumerate(cols):
            x = x0 + i * (cw + 24) + cw / 2
            h += f'  <text x="{x}" y="{y + 56}" text-anchor="middle" font-family="{SERIF}" font-size="42" font-weight="700" fill="{col}">{f.format(last(df, c))}</text>\n'
    h += f'  <text x="64" y="414" font-family="{MONO}" font-size="16" fill="{MUTED}">mean of days 100–150, one seed; seed ranges are in docs/model.md</text>\n</svg>\n'
    return h


def line(vals, x0, y0, w, h, lo, hi):
    pts = []
    for i, v in enumerate(vals):
        pts.append(f"{x0 + i / (len(vals) - 1) * w:.1f},{y0 + h - (v - lo) / (hi - lo) * h:.1f}")
    return " ".join(pts)


def trajectories(n, e):
    h = head(1200, 450, "Opinion spread and out-group trust over 150 days",
             "Left: opinion spread stays low with a normalizing feed and climbs with an engagement feed. "
             "Right: out-group trust holds with a normalizing feed and falls with an engagement feed.")
    panels = ((64, "Opinion spread", "opinion_std", 0.0, 0.8), (632, "Out-group trust", "avg_trust_out", 0.2, 0.8))
    for x0, title, col, lo, hi in panels:
        y0, w, hh = 120, 504, 220
        h += f'  <text x="{x0}" y="70" font-family="{SANS}" font-size="24" font-weight="700" fill="{INK}">{title}</text>\n'
        for k in range(int(round((hi - lo) / 0.2)) + 1):
            v = lo + 0.2 * k
            y = y0 + hh - (v - lo) / (hi - lo) * hh
            h += (f'  <line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="{RULE}" stroke-width="1.5"/>\n'
                  f'  <text x="{x0 - 8}" y="{y + 6:.1f}" text-anchor="end" font-family="{MONO}" font-size="18" fill="{MUTED}">{v:.1f}</text>\n')
        for df, c in ((n[1], BLUE), (e[1], ORANGE)):
            h += f'  <polyline points="{line(df[col].tolist(), x0, y0, w, hh, lo, hi)}" fill="none" stroke="{c}" stroke-width="4" stroke-linejoin="round"/>\n'
        h += (f'  <text x="{x0}" y="{y0 + hh + 34}" font-family="{MONO}" font-size="18" fill="{MUTED}">day 0</text>\n'
              f'  <text x="{x0 + w}" y="{y0 + hh + 34}" text-anchor="end" font-family="{MONO}" font-size="18" fill="{MUTED}">day 150</text>\n')
    h += (f'  <circle cx="64" cy="424" r="7" fill="{BLUE}"/><text x="82" y="431" font-family="{SANS}" font-size="20" fill="{INK}">Normalizing feed</text>\n'
          f'  <circle cx="290" cy="424" r="7" fill="{ORANGE}"/><text x="308" y="431" font-family="{SANS}" font-size="20" fill="{INK}">Engagement feed</text>\n'
          f'  <text x="1136" y="431" text-anchor="end" font-family="{MONO}" font-size="16" fill="{MUTED}">seed 7 · λ = 0.5</text>\n</svg>\n')
    return h


if __name__ == "__main__":
    no, ndf = run(0)
    eo, edf = run(1)
    n, e = (no, ndf), (eo, edf)
    os.makedirs(OUT, exist_ok=True)
    for name, svg in (("hero.svg", hero(no, eo)), ("workflow.svg", workflow(ndf, edf)),
                      ("trajectories.svg", trajectories(n, e))):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name, len(svg))
