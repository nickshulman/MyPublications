#!/usr/bin/env python
"""Build a self-contained index.html from papers.json.

Everything (data, charts, styles) is baked into one HTML file, so the page works
both by double-clicking it locally (file://) and when served by GitHub Pages, with
no external libraries or network calls. Charts are hand-drawn inline SVG.

Usage:
  python -X utf8 build_page.py

Reads papers.json (produced by fetch_papers.py) next to this script and writes
index.html next to it. Re-run any time the data or design changes.
"""
import os
import re
import json
import html

HERE = os.path.dirname(os.path.abspath(__file__))

NAME = "Nicholas Shulman"
TAGLINE = "Software developer on Skyline — MacCoss Lab, UW Genome Sciences"
ACCENT = "#4b2e83"  # UW purple


def clean_title(t):
    """Strip OpenAlex markup tags (e.g. <i>) and unescape entities for display."""
    t = re.sub(r"<[^>]+>", "", t or "")
    return html.unescape(t).strip()


def h_index(citations):
    h = 0
    for i, c in enumerate(sorted(citations, reverse=True), start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def area_chart(cumulative, width=640, height=300):
    """cumulative: list of (year, value) sorted by year. Returns inline SVG."""
    if len(cumulative) < 2:
        return "<p class='muted'>Not enough yearly data to chart.</p>"
    pad_l, pad_r, pad_t, pad_b = 52, 16, 16, 36
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    years = [y for y, _ in cumulative]
    vals = [v for _, v in cumulative]
    ymin, ymax = min(years), max(years)
    vmax = max(vals) or 1

    def X(yr):
        return pad_l + (yr - ymin) / (ymax - ymin) * pw

    def Y(v):
        return pad_t + ph - (v / vmax) * ph

    pts = [(X(y), Y(v)) for y, v in cumulative]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = (f"M {pts[0][0]:.1f},{pad_t + ph:.1f} "
            + " ".join(f"L {x:.1f},{y:.1f}" for x, y in pts)
            + f" L {pts[-1][0]:.1f},{pad_t + ph:.1f} Z")

    # y gridlines / labels (0, half, max)
    yticks = ""
    for frac in (0, 0.5, 1.0):
        v = vmax * frac
        yy = Y(v)
        yticks += (f"<line x1='{pad_l}' y1='{yy:.1f}' x2='{width - pad_r}' y2='{yy:.1f}' "
                   f"class='grid'/>"
                   f"<text x='{pad_l - 8}' y='{yy + 4:.1f}' class='ylab'>{int(round(v))}</text>")
    # x labels (every other year to avoid crowding)
    xticks = ""
    for i, yr in enumerate(years):
        if i % 2 == 0 or yr == years[-1]:
            xticks += f"<text x='{X(yr):.1f}' y='{height - 12}' class='xlab'>{yr}</text>"

    return (
        f"<svg viewBox='0 0 {width} {height}' class='chart' role='img' "
        f"aria-label='Cumulative citations over time'>"
        f"{yticks}"
        f"<path d='{area}' class='area'/>"
        f"<polyline points='{line}' class='line'/>"
        f"{xticks}"
        f"</svg>"
    )


def bar_chart(counts, width=640, height=300):
    """counts: list of (year, n) sorted by year. Returns inline SVG bar chart."""
    if not counts:
        return "<p class='muted'>No data.</p>"
    pad_l, pad_r, pad_t, pad_b = 52, 16, 16, 36
    pw, ph = width - pad_l - pad_r, height - pad_t - pad_b
    nmax = max(n for _, n in counts) or 1
    step = pw / len(counts)
    bw = step * 0.7
    bars, xticks = "", ""
    for i, (yr, n) in enumerate(counts):
        x = pad_l + i * step + (step - bw) / 2
        h = (n / nmax) * ph
        y = pad_t + ph - h
        bars += f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{h:.1f}' class='bar'/>"
        if len(counts) <= 12 or i % 2 == 0 or yr == counts[-1][0]:
            xticks += (f"<text x='{x + bw/2:.1f}' y='{height - 12}' "
                       f"class='xlab'>{yr}</text>")
    yticks = ""
    for frac in (0, 0.5, 1.0):
        v = nmax * frac
        yy = pad_t + ph - frac * ph
        yticks += (f"<line x1='{pad_l}' y1='{yy:.1f}' x2='{width - pad_r}' y2='{yy:.1f}' "
                   f"class='grid'/>"
                   f"<text x='{pad_l - 8}' y='{yy + 4:.1f}' class='ylab'>{int(round(v))}</text>")
    return (
        f"<svg viewBox='0 0 {width} {height}' class='chart' role='img' "
        f"aria-label='Papers published per year'>{yticks}{bars}{xticks}</svg>"
    )


def paper_rows(papers):
    rows = ""
    for p in sorted(papers, key=lambda p: p["cited_by_count"] or 0, reverse=True):
        title = html.escape(clean_title(p["title"]))
        url = html.escape(p.get("url") or "#")
        year = p.get("year") or ""
        venue = html.escape(p.get("venue") or "")
        cites = p.get("cited_by_count") or 0
        ptype = html.escape(p.get("type") or "work")
        meta = " · ".join(x for x in [str(year), venue] if x)
        rows += (
            "<li class='paper'>"
            f"<a class='ptitle' href='{url}' target='_blank' rel='noopener'>{title}</a>"
            "<div class='pmeta'>"
            f"<span class='badge badge-{ptype}'>{ptype}</span>"
            f"<span class='pmeta-text'>{meta}</span>"
            f"<span class='pcite'>{cites:,} citations</span>"
            "</div></li>"
        )
    return rows


def main():
    with open(os.path.join(HERE, "papers.json"), encoding="utf-8") as f:
        data = json.load(f)
    papers = data["papers"]

    citations = [p["cited_by_count"] or 0 for p in papers]
    total_papers = len(papers)
    total_citations = sum(citations)
    h = h_index(citations)
    years = [p["year"] for p in papers if p["year"]]
    span = f"{min(years)}–{max(years)}" if years else ""

    # cumulative citations by year (from counts_by_year, ~2012 onward)
    by_year = {}
    for p in papers:
        for e in p.get("counts_by_year", []):
            by_year[e["year"]] = by_year.get(e["year"], 0) + (e.get("cited_by_count") or 0)
    running = 0
    cumulative = []
    for yr in sorted(by_year):
        running += by_year[yr]
        cumulative.append((yr, running))

    # papers per year (full publication range)
    ppy = {}
    for p in papers:
        if p["year"]:
            ppy[p["year"]] = ppy.get(p["year"], 0) + 1
    ppy_series = [(yr, ppy.get(yr, 0)) for yr in range(min(years), max(years) + 1)]

    page = TEMPLATE.format(
        name=html.escape(NAME),
        tagline=html.escape(TAGLINE),
        accent=ACCENT,
        h_index=h,
        total_papers=f"{total_papers:,}",
        total_citations=f"{total_citations:,}",
        span=span,
        area=area_chart(cumulative),
        bars=bar_chart(ppy_series),
        rows=paper_rows(papers),
    )
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote index.html — {total_papers} papers, {total_citations:,} citations, "
          f"h-index {h}, span {span}")


TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — Publications</title>
<style>
  :root {{
    --accent: {accent};
    --bg: #f6f7fb; --card: #ffffff; --text: #16181d; --muted: #666b76;
    --border: #e6e8ef; --grid: #eceef4; --badge-bg: #efe9f7;
  }}
  html[data-theme="dark"] {{
    --bg: #0f1116; --card: #191c24; --text: #eef0f6; --muted: #9aa0ad;
    --border: #262a34; --grid: #22262f; --badge-bg: #2a2140; --accent: #b79cf0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; }}
  header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }}
  h1 {{ font-size: clamp(2rem, 5vw, 3.2rem); margin: 0; letter-spacing: -0.02em; line-height: 1.05; }}
  h1 .hl {{ color: var(--accent); }}
  .tagline {{ color: var(--muted); font-size: 1.05rem; margin: 8px 0 0; }}
  .toggle {{
    flex: none; cursor: pointer; border: 1px solid var(--border); background: var(--card);
    color: var(--text); border-radius: 999px; padding: 8px 14px; font-size: .9rem;
  }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 32px 0; }}
  .stat {{
    background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    padding: 22px; text-align: center;
  }}
  .stat .num {{ font-size: clamp(1.8rem, 5vw, 2.8rem); font-weight: 800; color: var(--accent);
    letter-spacing: -0.02em; }}
  .stat .lab {{ color: var(--muted); font-size: .9rem; text-transform: uppercase;
    letter-spacing: .05em; margin-top: 4px; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 720px) {{ .stats, .charts {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }}
  .panel h2 {{ margin: 0 0 12px; font-size: 1.05rem; }}
  .chart {{ width: 100%; height: auto; }}
  .area {{ fill: var(--accent); opacity: .18; }}
  .line {{ fill: none; stroke: var(--accent); stroke-width: 2.5; }}
  .bar {{ fill: var(--accent); opacity: .85; rx: 2; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .ylab {{ fill: var(--muted); font-size: 11px; text-anchor: end; }}
  .xlab {{ fill: var(--muted); font-size: 11px; text-anchor: middle; }}
  h2.section {{ margin: 40px 0 4px; font-size: 1.3rem; }}
  .count {{ color: var(--muted); margin: 0 0 12px; }}
  ul.papers {{ list-style: none; padding: 0; margin: 0; }}
  .paper {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 16px 18px; margin-bottom: 12px; }}
  .ptitle {{ color: var(--text); text-decoration: none; font-weight: 650; font-size: 1.05rem; }}
  .ptitle:hover {{ color: var(--accent); text-decoration: underline; }}
  .pmeta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 8px;
    color: var(--muted); font-size: .9rem; }}
  .pcite {{ color: var(--accent); font-weight: 600; }}
  .badge {{ background: var(--badge-bg); color: var(--accent); border-radius: 999px;
    padding: 2px 10px; font-size: .78rem; font-weight: 600; text-transform: capitalize; }}
  footer {{ color: var(--muted); font-size: .85rem; margin-top: 40px; text-align: center; }}
  footer a {{ color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>{name}</h1>
      <p class="tagline">{tagline}</p>
    </div>
    <button class="toggle" id="themeToggle" aria-label="Toggle dark mode">🌙 Dark</button>
  </header>

  <section class="stats">
    <div class="stat"><div class="num">{total_papers}</div><div class="lab">Publications</div></div>
    <div class="stat"><div class="num">{total_citations}</div><div class="lab">Citations</div></div>
    <div class="stat"><div class="num">{h_index}</div><div class="lab">h-index</div></div>
  </section>

  <section class="charts">
    <div class="panel">
      <h2>Citations over time</h2>
      {area}
    </div>
    <div class="panel">
      <h2>Papers per year</h2>
      {bars}
    </div>
  </section>

  <h2 class="section">Publications</h2>
  <p class="count">{total_papers} works ({span}), most cited first.</p>
  <ul class="papers">
    {rows}
  </ul>

  <footer>
    Data from <a href="https://openalex.org" target="_blank" rel="noopener">OpenAlex</a> ·
    ORCID <a href="https://orcid.org/0000-0003-1674-0794" target="_blank" rel="noopener">0000-0003-1674-0794</a>
  </footer>
</div>
<script>
  var root = document.documentElement, btn = document.getElementById('themeToggle');
  function apply(t) {{
    root.setAttribute('data-theme', t);
    btn.textContent = t === 'dark' ? '☀️ Light' : '🌙 Dark';
  }}
  var saved = localStorage.getItem('theme');
  if (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) saved = 'dark';
  apply(saved || 'light');
  btn.addEventListener('click', function () {{
    var t = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    apply(t); localStorage.setItem('theme', t);
  }});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
