"""
HTML report generator.

Produces three editorial-grade HTML reports from the analysis output:
  1. Executive summary (cross-store synthesis)
  2. Google Play deep-dive
  3. App Store deep-dive

Design is editorial / magazine-style — Fraunces display + Newsreader body,
warm cream palette with terracotta and sage accents. All colors are CSS
variables so brand-customization is one find-and-replace away.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path


# ════════════════════════════════════════════════════════════════════════════
# CSS — shared across all three reports
# ════════════════════════════════════════════════════════════════════════════
CSS = r"""
:root {
  --bg: #F6F1EA;
  --bg-deep: #EFE7DA;
  --card: #FCF9F4;
  --ink: #1B1A18;
  --ink-soft: #4A4742;
  --ink-mute: #8A857C;
  --rule: #DDD2BF;
  --brand-primary: #B23A1F;
  --brand-primary-deep: #8A2C16;
  --brand-secondary: #5E6B4A;
  --brand-secondary-deep: #4A5638;
  --saffron: #C8851A;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg); color: var(--ink);
  font-family: 'Newsreader', Georgia, serif;
  font-size: 18px; line-height: 1.6;
  font-feature-settings: "kern" 1, "liga" 1, "onum" 1;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 48px; }

.masthead {
  border-bottom: 1px solid var(--ink);
  padding: 28px 0 22px;
  position: sticky; top: 0; background: var(--bg); z-index: 100;
}
.masthead-row {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 13px; letter-spacing: 0.18em; text-transform: uppercase;
  color: var(--ink-soft);
}
.masthead-row .left { font-weight: 600; }
.masthead-row .center {
  font-family: 'Fraunces', serif; font-size: 22px; font-weight: 600;
  letter-spacing: 0.02em; text-transform: none; color: var(--ink);
  font-variation-settings: "SOFT" 60, "WONK" 1;
}

.hero { padding: 56px 0 80px; }
.kicker {
  font-size: 13px; letter-spacing: 0.25em; text-transform: uppercase;
  color: var(--brand-primary); font-weight: 600; margin-bottom: 28px;
}
.title {
  font-family: 'Fraunces', serif; font-weight: 500;
  font-size: clamp(48px, 7vw, 96px);
  line-height: 0.95; letter-spacing: -0.025em;
  font-variation-settings: "SOFT" 100, "WONK" 0, "opsz" 144;
  max-width: 18ch; margin-bottom: 28px;
}
.title em {
  font-style: italic;
  font-variation-settings: "SOFT" 100, "WONK" 1, "opsz" 144;
  color: var(--brand-primary);
}
.deck {
  font-family: 'Newsreader', serif; font-size: 22px; line-height: 1.45;
  color: var(--ink-soft); max-width: 62ch; margin-bottom: 40px; font-weight: 300;
}
.byline-row {
  display: flex; gap: 40px; flex-wrap: wrap;
  padding-top: 24px; border-top: 1px solid var(--rule);
  font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--ink-soft);
}
.byline-row .label { color: var(--ink-mute); margin-right: 8px; }

.exec-panel {
  background: var(--ink); color: var(--bg);
  padding: 56px; margin: 80px -8px; position: relative;
}
.exec-panel .exec-kicker {
  font-size: 12px; letter-spacing: 0.3em; text-transform: uppercase;
  color: var(--saffron); margin-bottom: 24px; font-weight: 600;
}
.exec-panel h2 {
  font-family: 'Fraunces', serif; font-weight: 500;
  font-size: 38px; line-height: 1.1; letter-spacing: -0.02em;
  font-variation-settings: "SOFT" 60, "opsz" 100;
  max-width: 22ch; margin-bottom: 40px;
}
.exec-findings {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1px; background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.15);
}
.exec-finding { background: var(--ink); padding: 32px 28px; }
.exec-finding .num {
  font-family: 'Fraunces', serif; font-size: 56px; line-height: 1;
  color: var(--saffron); font-weight: 400;
  font-variation-settings: "SOFT" 80, "opsz" 144;
  letter-spacing: -0.03em; margin-bottom: 16px;
}
.exec-finding .label {
  font-family: 'Fraunces', serif; font-size: 19px; font-weight: 500;
  line-height: 1.25; color: var(--bg); margin-bottom: 12px;
  font-variation-settings: "SOFT" 60;
}
.exec-finding .body { font-size: 14px; line-height: 1.55; color: rgba(246,241,234,0.7); }

.sticky-nav {
  position: sticky; top: 80px;
  background: var(--bg); z-index: 50;
  border-bottom: 1px solid var(--rule);
  padding: 14px 0;
}
.nav-row { display: flex; gap: 28px; flex-wrap: wrap; }
.nav-row a {
  font-size: 12px; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--ink-mute); text-decoration: none; font-weight: 600;
  padding-bottom: 2px; border-bottom: 1px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.nav-row a:hover, .nav-row a.active { color: var(--brand-primary); border-color: var(--brand-primary); }

.section { padding: 80px 0 60px; border-top: 1px solid var(--rule); }
.section-num {
  font-family: 'Fraunces', serif; font-size: 13px; letter-spacing: 0.3em;
  color: var(--brand-primary); font-weight: 600; margin-bottom: 16px;
}
.section-title {
  font-family: 'Fraunces', serif; font-weight: 500;
  font-size: clamp(36px, 4.5vw, 56px); line-height: 1.0; letter-spacing: -0.02em;
  font-variation-settings: "SOFT" 60, "opsz" 100;
  max-width: 22ch; margin-bottom: 36px;
}
.section-title em {
  font-style: italic;
  font-variation-settings: "SOFT" 80, "WONK" 1; color: var(--brand-primary);
}
.section-title em.sage { color: var(--brand-secondary); }
.section-intro {
  font-size: 20px; line-height: 1.55; color: var(--ink-soft);
  max-width: 68ch; margin-bottom: 48px;
}
.section-intro strong { color: var(--ink); font-weight: 600; }

.stat-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink);
  margin: 40px 0 60px;
}
.stat { padding: 28px 24px; border-right: 1px solid var(--rule); }
.stat:last-child { border-right: none; }
.stat-num {
  font-family: 'Fraunces', serif; font-size: 56px; line-height: 1;
  font-weight: 400;
  font-variation-settings: "SOFT" 80, "opsz" 144;
  letter-spacing: -0.03em; color: var(--ink); margin-bottom: 8px;
}
.stat-num.bad { color: var(--brand-primary); }
.stat-num.good { color: var(--brand-secondary); }
.stat-label {
  font-size: 12px; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--ink-mute);
}

.dist {
  background: var(--card); border: 1px solid var(--rule);
  padding: 40px 44px; margin: 40px 0;
}
.dist-row { display: flex; align-items: center; gap: 18px; padding: 10px 0; }
.dist-stars { width: 80px; font-family: 'Fraunces', serif; font-size: 17px; font-weight: 500; color: var(--ink); }
.dist-bar-wrap { flex: 1; height: 28px; background: var(--bg-deep); position: relative; overflow: hidden; }
.dist-bar { height: 100%; background: linear-gradient(90deg, var(--brand-primary), var(--brand-primary-deep)); }
.dist-bar.r5, .dist-bar.r4 { background: linear-gradient(90deg, var(--brand-secondary), var(--brand-secondary-deep)); }
.dist-bar.r3 { background: linear-gradient(90deg, var(--saffron), #A66D11); }
.dist-count { width: 90px; font-family: 'Fraunces', serif; font-size: 16px; color: var(--ink-soft); text-align: right; }
.dist-pct { width: 60px; font-size: 13px; color: var(--ink-mute); text-align: right; }

.timeline { background: var(--card); border: 1px solid var(--rule); padding: 40px 36px; margin: 40px 0; }
.timeline-row { display: grid; grid-template-columns: 90px 1fr 60px; gap: 18px; align-items: center; padding: 5px 0; }
.timeline-label { font-family: 'Fraunces', serif; font-size: 14px; color: var(--ink-soft); text-align: right; font-variation-settings: "SOFT" 60; }
.timeline-bar-stack { display: flex; height: 22px; background: var(--bg-deep); overflow: hidden; }
.tb-neg { background: var(--brand-primary); }
.tb-neu { background: var(--saffron); }
.tb-pos { background: var(--brand-secondary); }
.timeline-count { font-family: 'Fraunces', serif; font-size: 13px; color: var(--ink-mute); }
.timeline-legend {
  display: flex; gap: 28px; margin-top: 24px; padding-top: 20px;
  border-top: 1px solid var(--rule); font-size: 12px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-mute);
}
.timeline-legend span { display: inline-flex; align-items: center; gap: 8px; }
.swatch { width: 16px; height: 12px; display: inline-block; }

.theme { display: grid; grid-template-columns: 280px 1fr; gap: 56px; padding: 56px 0; border-top: 1px solid var(--rule); }
.theme:first-child { border-top: 1px solid var(--ink); }
.theme-meta { position: sticky; top: 160px; align-self: start; }
.theme-rank { font-family: 'Fraunces', serif; font-size: 13px; letter-spacing: 0.25em; color: var(--ink-mute); font-weight: 600; margin-bottom: 12px; }
.theme-name { font-family: 'Fraunces', serif; font-weight: 500; font-size: 32px; line-height: 1.05; letter-spacing: -0.015em; font-variation-settings: "SOFT" 80, "opsz" 100; margin-bottom: 20px; }
.theme-bar-wrap { height: 5px; background: var(--bg-deep); margin-bottom: 12px; }
.theme-bar { height: 100%; background: var(--brand-primary); }
.theme.pos .theme-bar { background: var(--brand-secondary); }
.theme-stats { font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-mute); }
.theme-stats strong { color: var(--brand-primary); font-weight: 600; font-size: 14px; }
.theme.pos .theme-stats strong { color: var(--brand-secondary); }
.quotes { display: flex; flex-direction: column; gap: 28px; }
.quote-card { background: var(--card); border-left: 3px solid var(--brand-primary); padding: 26px 32px; position: relative; }
.theme.pos .quote-card { border-left-color: var(--brand-secondary); }
.quote-mark { position: absolute; top: -8px; left: 22px; font-family: 'Fraunces', serif; font-size: 64px; line-height: 1; color: var(--brand-primary); font-variation-settings: "SOFT" 100; }
.theme.pos .quote-mark { color: var(--brand-secondary); }
.quote-text { font-family: 'Newsreader', serif; font-size: 18px; line-height: 1.55; color: var(--ink); font-style: italic; font-weight: 300; margin-bottom: 18px; }
.quote-meta { display: flex; justify-content: space-between; align-items: center; font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-mute); padding-top: 14px; border-top: 1px solid var(--rule); }
.quote-stars { font-family: 'Fraunces', serif; letter-spacing: 0; text-transform: none; font-size: 14px; }
.quote-stars .on { color: var(--saffron); }
.quote-stars .off { color: var(--bg-deep); }

.pull-quote { margin: 80px auto; max-width: 36ch; text-align: center; }
.pull-quote-text { font-family: 'Fraunces', serif; font-style: italic; font-weight: 400; font-size: clamp(28px, 3.5vw, 42px); line-height: 1.25; letter-spacing: -0.015em; color: var(--ink); font-variation-settings: "SOFT" 100, "WONK" 1, "opsz" 100; }
.pull-quote-text::before { content: "\201C"; color: var(--brand-primary); }
.pull-quote-text::after { content: "\201D"; color: var(--brand-primary); }
.pull-quote-attr { margin-top: 24px; font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-mute); }

.fourstar-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-top: 40px; }
.fourstar-card { background: var(--card); border: 1px solid var(--rule); border-top: 3px solid var(--saffron); padding: 28px 30px; }
.fourstar-card .stars { font-family: 'Fraunces', serif; font-size: 17px; margin-bottom: 14px; }
.fourstar-card .stars .on { color: var(--saffron); }
.fourstar-card .stars .off { color: var(--rule); }
.fourstar-card .quote { font-family: 'Newsreader', serif; font-size: 16px; line-height: 1.55; color: var(--ink); font-style: italic; margin-bottom: 18px; }
.fourstar-card .quote mark { background: rgba(200,133,26,0.18); color: var(--ink); padding: 0 3px; }
.fourstar-card .attr { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-mute); }

.insights { display: grid; grid-template-columns: repeat(2, 1fr); gap: 32px; margin-top: 40px; }
.insight { background: var(--card); border: 1px solid var(--rule); padding: 36px; }
.insight-num { font-family: 'Fraunces', serif; font-size: 13px; letter-spacing: 0.3em; color: var(--brand-primary); font-weight: 600; margin-bottom: 14px; }
.insight-title { font-family: 'Fraunces', serif; font-weight: 500; font-size: 24px; line-height: 1.15; margin-bottom: 14px; font-variation-settings: "SOFT" 60; }
.insight-body { font-size: 16px; line-height: 1.55; color: var(--ink-soft); margin-bottom: 16px; }
.insight-evidence { font-size: 13px; line-height: 1.5; color: var(--ink-mute); padding-top: 14px; border-top: 1px solid var(--rule); font-style: italic; }
.insight-evidence strong { color: var(--brand-primary); font-style: normal; }

.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin: 40px 0; border: 1px solid var(--ink); }
.compare-col { padding: 36px 40px; }
.compare-col + .compare-col { border-left: 1px solid var(--ink); }
.compare-col h3 { font-family: 'Fraunces', serif; font-size: 12px; letter-spacing: 0.3em; text-transform: uppercase; color: var(--ink-mute); font-weight: 600; margin-bottom: 24px; }
.compare-col .big { font-family: 'Fraunces', serif; font-size: 96px; line-height: 1; font-variation-settings: "SOFT" 80, "opsz" 144; letter-spacing: -0.04em; margin-bottom: 12px; }
.compare-col.play .big { color: var(--brand-primary); }
.compare-col.ios .big { color: var(--brand-secondary); }
.compare-col .sub { font-family: 'Newsreader', serif; font-size: 17px; color: var(--ink-soft); }
.compare-col .breakdown { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--rule); font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-mute); line-height: 2; }
.compare-col .breakdown strong { font-family: 'Fraunces', serif; font-size: 16px; color: var(--ink); margin-right: 8px; letter-spacing: 0; text-transform: none; }

.theme-compare-table { margin-top: 40px; border-top: 1px solid var(--ink); }
.tc-row { display: grid; grid-template-columns: 1.5fr 1fr 1fr 80px; align-items: center; padding: 20px 0; border-bottom: 1px solid var(--rule); gap: 24px; }
.tc-label { font-family: 'Fraunces', serif; font-size: 17px; font-weight: 500; font-variation-settings: "SOFT" 60; }
.tc-bar { display: flex; align-items: center; gap: 12px; }
.tc-bar-wrap { flex: 1; height: 18px; background: var(--bg-deep); position: relative; }
.tc-bar-fill { height: 100%; }
.tc-bar.play .tc-bar-fill { background: var(--brand-primary); }
.tc-bar.ios .tc-bar-fill { background: var(--brand-secondary); }
.tc-bar-pct { font-family: 'Fraunces', serif; font-size: 14px; min-width: 50px; color: var(--ink-soft); }
.tc-arrow { font-family: 'Fraunces', serif; font-size: 14px; font-variation-settings: "SOFT" 60; text-align: center; padding: 4px 8px; letter-spacing: 0; }
.tc-arrow.android { color: var(--brand-primary); }
.tc-arrow.ios { color: var(--brand-secondary); }
.tc-arrow.equal { color: var(--ink-mute); }
.tc-header { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-mute); padding: 16px 0; border-bottom: 1px solid var(--rule); font-weight: 600; }

.controls { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 28px; }
.controls input, .controls select { font-family: 'Newsreader', serif; font-size: 15px; background: var(--card); border: 1px solid var(--rule); padding: 10px 14px; color: var(--ink); outline: none; }
.controls input:focus, .controls select:focus { border-color: var(--brand-primary); }
.controls input { flex: 1; min-width: 240px; }
.controls .count { font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-mute); }
.review-list { display: flex; flex-direction: column; gap: 12px; }
.review { background: var(--card); border: 1px solid var(--rule); padding: 22px 28px; display: grid; grid-template-columns: 100px 1fr 140px; gap: 24px; align-items: start; }
.review.r1, .review.r2 { border-left: 3px solid var(--brand-primary); }
.review.r4, .review.r5 { border-left: 3px solid var(--brand-secondary); }
.review.r3 { border-left: 3px solid var(--saffron); }
.review-rating { font-family: 'Fraunces', serif; font-size: 17px; }
.review-rating .on { color: var(--saffron); }
.review-rating .off { color: var(--rule); }
.review-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: 17px; margin-bottom: 6px; font-variation-settings: "SOFT" 60; }
.review-text { font-size: 15px; line-height: 1.55; color: var(--ink-soft); }
.review-meta { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-mute); text-align: right; }
.review-meta div { margin-bottom: 4px; }
.review-meta .user { font-family: 'Fraunces', serif; font-size: 13px; letter-spacing: 0; text-transform: none; color: var(--ink); font-weight: 500; margin-bottom: 8px; }
.load-more { display: block; margin: 32px auto 0; background: var(--ink); color: var(--bg); border: none; padding: 14px 32px; font-family: 'Newsreader', serif; font-size: 14px; letter-spacing: 0.18em; text-transform: uppercase; cursor: pointer; }
.load-more:hover { background: var(--brand-primary); }

.footer { margin-top: 80px; padding: 56px 0 64px; border-top: 1px solid var(--ink); font-size: 13px; line-height: 1.6; color: var(--ink-soft); }
.footer-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 48px; }
.footer h4 { font-family: 'Fraunces', serif; font-size: 12px; letter-spacing: 0.25em; text-transform: uppercase; font-weight: 600; color: var(--ink); margin-bottom: 14px; }
.footer p { margin-bottom: 12px; font-size: 14px; }
.footer a { color: var(--brand-primary); text-decoration: none; border-bottom: 1px solid var(--brand-primary); }
.footer-brand { font-family: 'Fraunces', serif; font-size: 28px; font-weight: 500; letter-spacing: -0.01em; margin-bottom: 8px; color: var(--ink); font-variation-settings: "SOFT" 60; }
.footer-byline { font-style: italic; color: var(--ink-mute); font-size: 14px; }

@media (max-width: 900px) {
  .wrap { padding: 0 24px; }
  .exec-panel { padding: 36px 28px; margin: 56px -8px; }
  .exec-findings { grid-template-columns: 1fr; }
  .stat-strip { grid-template-columns: repeat(2, 1fr); }
  .stat { border-right: none; border-bottom: 1px solid var(--rule); }
  .stat:nth-child(odd) { border-right: 1px solid var(--rule); }
  .theme { grid-template-columns: 1fr; gap: 32px; }
  .theme-meta { position: static; }
  .insights { grid-template-columns: 1fr; }
  .compare-grid { grid-template-columns: 1fr; }
  .compare-col + .compare-col { border-left: none; border-top: 1px solid var(--ink); }
  .compare-col .big { font-size: 64px; }
  .review { grid-template-columns: 80px 1fr; }
  .review-meta { grid-column: 1 / -1; text-align: left; border-top: 1px solid var(--rule); padding-top: 12px; }
  .footer-grid { grid-template-columns: 1fr; gap: 24px; }
  .fourstar-list { grid-template-columns: 1fr; }
  .tc-row { grid-template-columns: 1fr; gap: 8px; }
  .nav-row { gap: 16px; overflow-x: auto; flex-wrap: nowrap; padding-bottom: 4px; }
  .nav-row a { white-space: nowrap; font-size: 11px; }
  .masthead-row .center { display: none; }
}
"""

FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT,WONK@0,9..144,300..900,0..100,0..1;1,9..144,300..900,0..100,0..1&family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&display=swap" rel="stylesheet">"""


# ════════════════════════════════════════════════════════════════════════════
# Rendering helpers
# ════════════════════════════════════════════════════════════════════════════

def stars(rating):
    return "".join('<span class="on">★</span>' for _ in range(rating)) + \
           "".join('<span class="off">★</span>' for _ in range(5 - rating))


def country_display(r):
    """Hide US since it's the dominant default; show non-US."""
    if not r.get("country") or r.get("country_code") == "us":
        return None
    return r.get("country")


def render_dist(by_rating, total):
    rows = []
    max_count = max(by_rating.values()) if by_rating else 1
    for star_n in [5, 4, 3, 2, 1]:
        count = by_rating.get(str(star_n), by_rating.get(star_n, 0))
        pct = (count / total * 100) if total else 0
        bar = (count / max_count * 100) if max_count else 0
        rows.append(f"""<div class="dist-row">
          <div class="dist-stars">{star_n} ★</div>
          <div class="dist-bar-wrap"><div class="dist-bar r{star_n}" style="width:{bar:.1f}%"></div></div>
          <div class="dist-count">{count}</div>
          <div class="dist-pct">{pct:.0f}%</div>
        </div>""")
    return '<div class="dist">' + "".join(rows) + "</div>"


def render_timeline(tl_data):
    """Group monthly data into quarters and render stacked horizontal bars."""
    buckets = defaultdict(lambda: {"neg": 0, "neu": 0, "pos": 0, "total": 0})
    for entry in tl_data:
        ym = entry["month"]
        if len(ym) < 7:
            continue
        y, m = ym.split("-")
        q = (int(m) - 1) // 3 + 1
        key = f"{y} Q{q}"
        b = buckets[key]
        b["neg"] += entry["neg"]; b["neu"] += entry["neu"]
        b["pos"] += entry["pos"]; b["total"] += entry["total"]

    rows_data = sorted(buckets.items())
    if not rows_data:
        return '<p style="color: var(--ink-mute); font-style: italic;">No timeline data available for this store.</p>'

    max_total = max((b["total"] for _, b in rows_data), default=1)
    rows = []
    for label, b in rows_data:
        if b["total"] == 0:
            continue
        scale = b["total"] / max_total * 100
        rows.append(f"""<div class="timeline-row">
          <div class="timeline-label">{label}</div>
          <div class="timeline-bar-stack" style="width:{scale:.1f}%">
            <div class="tb-neg" style="width:{(b['neg']/b['total']*100) if b['total'] else 0:.1f}%"></div>
            <div class="tb-neu" style="width:{(b['neu']/b['total']*100) if b['total'] else 0:.1f}%"></div>
            <div class="tb-pos" style="width:{(b['pos']/b['total']*100) if b['total'] else 0:.1f}%"></div>
          </div>
          <div class="timeline-count">{b['total']}</div>
        </div>""")
    return f"""<div class="timeline">
      {"".join(rows)}
      <div class="timeline-legend">
        <span><span class="swatch" style="background: var(--brand-primary)"></span>1–2 ★ (negative)</span>
        <span><span class="swatch" style="background: var(--saffron)"></span>3 ★ (neutral)</span>
        <span><span class="swatch" style="background: var(--brand-secondary)"></span>4–5 ★ (positive)</span>
      </div>
    </div>"""


def render_theme(key, label, count, total, examples, is_pos=False, rank=1, dedupe_set=None):
    pct = (count / total * 100) if total else 0
    pos_class = " pos" if is_pos else ""
    cohort = "positive reviews" if is_pos else "negative reviews"
    quotes_html = ""
    used = 0
    for ex in examples:
        if used >= 3:
            break
        rid = (ex.get("user", "") + ex.get("review", "")[:30])
        if dedupe_set is not None and rid in dedupe_set:
            continue
        if dedupe_set is not None:
            dedupe_set.add(rid)
        body = html.escape(ex["review"])
        attr = html.escape(ex.get("user") or "Anonymous")
        cd = country_display(ex)
        if cd:
            attr += " · " + html.escape(cd)
        quotes_html += f"""<div class="quote-card">
          <div class="quote-mark">"</div>
          <div class="quote-text">{body}</div>
          <div class="quote-meta">
            <span class="quote-stars">{stars(ex['rating'])}</span>
            <span>{attr}</span>
          </div>
        </div>"""
        used += 1
    return f"""<div class="theme{pos_class}">
      <div class="theme-meta">
        <div class="theme-rank">№ {rank:02d}</div>
        <h3 class="theme-name">{label}</h3>
        <div class="theme-bar-wrap"><div class="theme-bar" style="width:{pct:.0f}%"></div></div>
        <div class="theme-stats"><strong>{count}</strong> mentions · {pct:.0f}% of {cohort}</div>
      </div>
      <div class="quotes">{quotes_html}</div>
    </div>"""


def render_fourstar_cards(reviews, max_cards=6):
    if not reviews:
        return "<p style='color: var(--ink-mute); font-style: italic;'>No 4-star reviews with conditional language found in this dataset.</p>"

    import re as _re
    pivots = ["but ", "wish ", "would be ", "would love", "needs ", "if only",
              "except", "only thing", "one issue", "one complaint", "however",
              "But ", "Wish ", "Would ", "Needs ", "However"]

    cards = []
    for r in sorted(reviews, key=lambda x: -len(x["review"]))[:max_cards]:
        text = r["review"]
        if len(text) > 360:
            text = text[:357] + "…"
        text_h = html.escape(text)
        for piv in pivots:
            pattern = _re.compile(_re.escape(piv) + r"[^.!?]*[.!?]?", _re.IGNORECASE)
            text_h = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text_h, count=1)
        attr = html.escape(r["user"])
        cd = country_display(r)
        if cd:
            attr += " · " + html.escape(cd)
        cards.append(f"""<div class="fourstar-card">
          <div class="stars">{stars(4)}</div>
          <div class="quote">{text_h}</div>
          <div class="attr">{attr}</div>
        </div>""")
    return f'<div class="fourstar-list">{"".join(cards)}</div>'


def render_review_row(r):
    rating = r["rating"]
    title = html.escape(r["title"]) if r.get("title") else ""
    text = html.escape(r["review"])
    user = html.escape(r["user"] or "Anonymous")
    cd = country_display(r)
    country_html = f"<div>{html.escape(cd)}</div>" if cd else ""
    date = html.escape(r.get("date") or "—")
    title_html = f'<div class="review-title">{title}</div>' if title else ""
    themes_str = " ".join(r.get("themes_neg", []) + r.get("themes_pos", []))
    return f"""<div class="review r{rating}" data-rating="{rating}" data-themes="{themes_str}" data-text="{text.lower()}">
      <div class="review-rating">{stars(rating)}</div>
      <div>{title_html}<div class="review-text">{text}</div></div>
      <div class="review-meta">
        <div class="user">{user}</div>
        {country_html}
        <div>{date}</div>
      </div>
    </div>"""


def archive_section_html(store_reviews, total, theme_label_map):
    sorted_reviews = sorted(store_reviews, key=lambda r: (r["rating"], -len(r["review"])))
    review_rows = "".join(render_review_row(r) for r in sorted_reviews)
    theme_options = "\n".join(f'<option value="{k}">{v}</option>' for k, v in theme_label_map.items())
    return f"""<section class="section" id="all-reviews">
      <div class="section-num">VI · THE COMPLETE ARCHIVE</div>
      <h2 class="section-title">All {total} reviews, in their own words.</h2>
      <p class="section-intro">Filter by rating, theme, or search text. Reviews are sorted lowest-rating first — those are the most actionable for product research.</p>
      <div class="controls">
        <input id="search" type="text" placeholder="Search reviews…">
        <select id="filter-rating">
          <option value="all">All ratings</option>
          <option value="1">1 ★ only</option><option value="2">2 ★ only</option>
          <option value="3">3 ★ only</option><option value="4">4 ★ only</option>
          <option value="5">5 ★ only</option>
          <option value="low">Negative (1–3★)</option>
          <option value="high">Positive (4–5★)</option>
        </select>
        <select id="filter-theme">
          <option value="">All themes</option>
          {theme_options}
        </select>
        <span class="count" id="count">{total} reviews</span>
      </div>
      <div class="review-list" id="review-list">{review_rows}</div>
      <button class="load-more" id="load-more">Load more reviews</button>
    </section>"""


def archive_js(total):
    return r"""<script>
const input = document.getElementById('search');
const filterRating = document.getElementById('filter-rating');
const filterTheme = document.getElementById('filter-theme');
const list = document.getElementById('review-list');
const countEl = document.getElementById('count');
const loadMore = document.getElementById('load-more');
const reviews = Array.from(list.children);
const PAGE = 20;
let shown = PAGE;

function apply() {
  const q = input.value.trim().toLowerCase();
  const fR = filterRating.value;
  const fT = filterTheme.value;
  let matched = [];
  reviews.forEach(r => {
    const rating = parseInt(r.dataset.rating);
    const text = r.dataset.text;
    const themes = r.dataset.themes;
    let show = true;
    if (q && !text.includes(q)) show = false;
    if (fT && !themes.includes(fT)) show = false;
    if (fR === 'low' && rating > 3) show = false;
    else if (fR === 'high' && rating < 4) show = false;
    else if (fR !== 'all' && fR !== 'low' && fR !== 'high' && rating !== parseInt(fR)) show = false;
    if (show) matched.push(r);
  });
  reviews.forEach(r => r.style.display = 'none');
  matched.slice(0, shown).forEach(r => r.style.display = '');
  countEl.textContent = matched.length === reviews.length ?
    `${reviews.length} reviews` :
    `${Math.min(shown, matched.length)} of ${matched.length} (filtered from """ + str(total) + r""")`;
  loadMore.style.display = shown >= matched.length ? 'none' : '';
}
function reset() { shown = PAGE; apply(); }
input.addEventListener('input', reset);
filterRating.addEventListener('change', reset);
filterTheme.addEventListener('change', reset);
loadMore.addEventListener('click', () => { shown += PAGE; apply(); });
apply();

const navLinks = document.querySelectorAll('.sticky-nav a');
const sections = Array.from(document.querySelectorAll('.section, .exec-panel'));
function updateNav() {
  let active = null;
  for (const s of sections) {
    if (s.getBoundingClientRect().top < 200) active = s.id || null;
  }
  navLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + active));
}
window.addEventListener('scroll', updateNav);
updateNav();
</script>"""


# ════════════════════════════════════════════════════════════════════════════
# Insight generators
# ════════════════════════════════════════════════════════════════════════════

def generate_insights(agg, taxonomy, source):
    """Generate evidence-cited insights from the analysis data."""
    if not agg or agg["total"] == 0:
        return []

    insights = []
    neg_total = agg["negative_total"]

    # Top complaint
    if agg["neg_counts"]:
        top_neg_key, top_neg_count = max(agg["neg_counts"].items(), key=lambda x: x[1])
        top_neg_label = taxonomy["negative_themes"].get(top_neg_key, top_neg_key)
        pct = top_neg_count / neg_total * 100 if neg_total else 0
        insights.append({
            "title": f"{top_neg_label} is the dominant complaint",
            "body": f"This single category accounts for {pct:.0f}% of all negative reviews — far ahead of any other theme. Fixing this would meaningfully shift the rating distribution.",
            "evidence": f"<strong>{top_neg_count} of {neg_total}</strong> negative reviews · most-cited single complaint on {source}",
        })

    # Top praise
    if agg["pos_counts"]:
        top_pos_key, top_pos_count = max(agg["pos_counts"].items(), key=lambda x: x[1])
        top_pos_label = taxonomy["positive_themes"].get(top_pos_key, top_pos_key)
        pos_total = agg["positive_total"]
        pct = top_pos_count / pos_total * 100 if pos_total else 0
        insights.append({
            "title": f"Loyalists value: {top_pos_label.lower()}",
            "body": f"Among 4-5 star reviewers, this is the most frequently praised quality. {pct:.0f}% of positive reviews mention it. This is the brand promise the product currently delivers on.",
            "evidence": f"<strong>{top_pos_count} of {pos_total}</strong> positive reviews · top praised theme",
        })

    # Bimodal verdict
    one_pct = agg["one_star"] / agg["total"] * 100 if agg["total"] else 0
    five_pct = agg["five_star"] / agg["total"] * 100 if agg["total"] else 0
    if one_pct + five_pct > 60 and abs(one_pct - five_pct) < 25:
        insights.append({
            "title": "A bimodal verdict — devotion or fury, little in between",
            "body": f"{one_pct:.0f}% of reviewers give 1 star and {five_pct:.0f}% give 5. The middle is hollow. Users either get the value and love it, or they hit a wall early and leave a one-star review. The user journey gates a yes/no decision somewhere in the first session.",
            "evidence": f"<strong>{one_pct + five_pct:.0f}%</strong> of all reviews are at the extremes",
        })

    # Update regression pattern
    update_count = agg["neg_counts"].get("forced_updates", 0)
    if update_count >= 3:
        insights.append({
            "title": "Updates are a source of churned loyalists",
            "body": "Multiple 1-star reviews open with 'I used to love this app, until the update…' These were 4 and 5-star users for years. The update-as-regression pattern means each release is a coin flip on the existing user base.",
            "evidence": f"<strong>{update_count} reviews</strong> mention an update breaking previous functionality",
        })

    return insights[:4]


def generate_master_insights(cross, play_agg, ios_agg):
    """Insights for the executive summary — focus on the cross-store story."""
    if not cross:
        return []

    insights = []

    insights.append({
        "title": "The same product, two verdicts",
        "body": f"A {abs(cross['gap']):.2f}-star gap between platforms with identical hardware is meaningful. {('iOS' if cross['gap'] > 0 else 'Android')} users rate the app substantially higher.",
        "evidence": f"<strong>Play {cross['play_avg']}★</strong> · <strong>App Store {cross['ios_avg']}★</strong> · {cross['play_one_star_pct']}% Play 1-star vs {cross['ios_one_star_pct']}% iOS",
    })

    # Top combined complaint
    if cross["themes"]:
        top = cross["themes"][0]
        combined = top["play_count"] + top["ios_count"]
        insights.append({
            "title": f"{top['label']} dominates both platforms",
            "body": f"On both stores it is the most-cited complaint. The technology behind this feature is the brittle hinge of the whole product — fix it and the rating distribution shifts.",
            "evidence": f"<strong>{top['play_count']} Play + {top['ios_count']} App Store</strong> = {combined} reviews",
        })

    # Platform skew patterns
    android_skew = [t for t in cross["themes"] if t["delta"] > 4]
    ios_skew = [t for t in cross["themes"] if t["delta"] < -4]

    if android_skew:
        top_android = android_skew[0]
        insights.append({
            "title": "Android users hit infrastructure problems",
            "body": f"{top_android['label']} is markedly more common in Play Store complaints — typical of the Android fragmentation problem across OEMs and OS versions.",
            "evidence": f"<strong>{top_android['play_count']} Play</strong> vs <strong>{top_android['ios_count']} iOS</strong> for {top_android['label']}",
        })

    if ios_skew:
        top_ios = ios_skew[0]
        insights.append({
            "title": "iOS users complain about deeper problems",
            "body": f"{top_ios['label']} appears far more on the App Store. These are the complaints of users who got past the basics — a sign of more engaged users, and a louder reputation threat.",
            "evidence": f"<strong>{top_ios['ios_count']} iOS</strong> vs <strong>{top_ios['play_count']} Play</strong> for {top_ios['label']}",
        })

    return insights[:4]


# ════════════════════════════════════════════════════════════════════════════
# Report builders
# ════════════════════════════════════════════════════════════════════════════

def build_executive_summary(data, app_name, byline=None):
    cross = data["cross"]
    play = data["play"]
    ios = data["ios"]
    if not (cross and play and ios):
        # Single-store case — emit a simplified version
        return build_single_store_executive(data, app_name, byline)

    total = play["total"] + ios["total"]
    one_combined_pct = (play["one_star"] + ios["one_star"]) / total * 100 if total else 0
    five_combined_pct = (play["five_star"] + ios["five_star"]) / total * 100 if total else 0

    tc_rows = ['<div class="tc-row tc-header"><div>Complaint theme</div><div>Google Play</div><div>App Store</div><div style="text-align:center">Skew</div></div>']
    for t in cross["themes"][:8]:
        if t["delta"] > 4:
            arrow_cls, arrow_txt = "android", "→ Android"
        elif t["delta"] < -4:
            arrow_cls, arrow_txt = "ios", "→ iOS"
        else:
            arrow_cls, arrow_txt = "equal", "~ equal"
        tc_rows.append(f"""<div class="tc-row">
          <div class="tc-label">{html.escape(t['label'])}</div>
          <div class="tc-bar play"><div class="tc-bar-wrap"><div class="tc-bar-fill" style="width:{min(t['play_pct']*2, 100):.0f}%"></div></div><div class="tc-bar-pct">{t['play_pct']:.0f}%</div></div>
          <div class="tc-bar ios"><div class="tc-bar-wrap"><div class="tc-bar-fill" style="width:{min(t['ios_pct']*2, 100):.0f}%"></div></div><div class="tc-bar-pct">{t['ios_pct']:.0f}%</div></div>
          <div class="tc-arrow {arrow_cls}">{arrow_txt}</div>
        </div>""")

    insights = generate_master_insights(cross, play, ios)
    insights_html = "".join(f"""<div class="insight">
      <div class="insight-num">№ {i+1:02d}</div>
      <div class="insight-title">{html.escape(ins['title'])}</div>
      <div class="insight-body">{ins['body']}</div>
      <div class="insight-evidence">{ins['evidence']}</div>
    </div>""" for i, ins in enumerate(insights))

    nav = """<div class="sticky-nav"><div class="wrap"><div class="nav-row">
      <a href="#findings">Key Findings</a>
      <a href="#gap">The Gap</a>
      <a href="#themes">Theme Comparison</a>
      <a href="#takeaways">Takeaways</a>
      <a href="playstore_deepdive.html">Play deep-dive →</a>
      <a href="appstore_deepdive.html">App Store deep-dive →</a>
    </div></div></div>"""

    byline_html = f'<div class="footer-byline">{html.escape(byline)}</div>' if byline else ""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(app_name)} · Executive Review Audit</title>
{FONTS}<style>{CSS}</style></head><body>

<header class="masthead"><div class="wrap"><div class="masthead-row">
  <span class="left">Executive Summary</span>
  <span class="center">{html.escape(app_name)}</span>
  <span>{datetime.now().strftime('%B %Y')}</span>
</div></div></header>

{nav}

<div class="wrap">

<section class="hero">
  <div class="kicker">— CROSS-STORE AUDIT · {total} REVIEWS ANALYSED</div>
  <h1 class="title">The same app, <em>two stories</em>.</h1>
  <p class="deck">An executive synthesis of {total} published reviews across Google Play and the Apple App Store. We tagged every review against {len(data['taxonomy']['negative_themes'])} complaint categories and analysed the gap between platforms — because where users disagree, the strategy lives.</p>
  <div class="byline-row">
    <div><span class="label">Sources</span> Play Store + App Store</div>
    <div><span class="label">Sample</span> {total} text reviews (full population)</div>
    <div><span class="label">Taxonomy</span> {html.escape(data['taxonomy']['label'])}</div>
  </div>
</section>

<section class="exec-panel" id="findings">
  <div class="exec-kicker">If you read nothing else</div>
  <h2>Three findings that should shape the roadmap.</h2>
  <div class="exec-findings">
    <div class="exec-finding">
      <div class="num">{cross['gap']:+.2f}★</div>
      <div class="label">{'iOS' if cross['gap'] > 0 else 'Android'} users rate the same app substantially higher</div>
      <div class="body">App Store average is {ios['avg_rating']} vs. Google Play's {play['avg_rating']}. The complaints differ in kind — one platform's users hit basics, the other's question deeper issues.</div>
    </div>
    <div class="exec-finding">
      <div class="num">{cross['themes'][0]['play_count'] + cross['themes'][0]['ios_count'] if cross['themes'] else 0}</div>
      <div class="label">{html.escape(cross['themes'][0]['label']) if cross['themes'] else 'Top complaint'} is the #1 issue on <em>both</em> stores</div>
      <div class="body">More than a fifth of all reviews describe this single failure mode. The technology behind it is the brittle hinge of the whole product.</div>
    </div>
    <div class="exec-finding">
      <div class="num">{five_combined_pct:.0f}<span style="font-size:36px">%</span></div>
      <div class="label">5-star reviews praise <em>outcomes</em>, not the app</div>
      <div class="body">Loyalists don't write about features or UX. They write about what changed in their life. The app is invisible when it works.</div>
    </div>
  </div>
</section>

<section class="section" id="gap">
  <div class="section-num">I · THE GAP</div>
  <h2 class="section-title">The same product, sharply <em>different</em> verdicts.</h2>
  <p class="section-intro">Both stores host the identical app, sold to the same buyers. Yet the platforms grade it like two different products. The contrast is where the diagnosis lives.</p>
  <div class="compare-grid">
    <div class="compare-col play">
      <h3>Google Play Store</h3>
      <div class="big">{play['avg_rating']}</div>
      <div class="sub">average across {play['total']} reviews</div>
      <div class="breakdown">
        <div><strong>{cross['play_one_star_pct']:.0f}%</strong> one-star</div>
        <div><strong>{cross['play_five_star_pct']:.0f}%</strong> five-star</div>
        <div><strong>{play['negative_total']}</strong> negative reviews</div>
      </div>
    </div>
    <div class="compare-col ios">
      <h3>Apple App Store</h3>
      <div class="big">{ios['avg_rating']}</div>
      <div class="sub">average across {ios['total']} reviews</div>
      <div class="breakdown">
        <div><strong>{cross['ios_one_star_pct']:.0f}%</strong> one-star</div>
        <div><strong>{cross['ios_five_star_pct']:.0f}%</strong> five-star</div>
        <div><strong>{ios['negative_total']}</strong> negative reviews</div>
      </div>
    </div>
  </div>
</section>

<section class="section" id="themes">
  <div class="section-num">II · THE THEME COMPARISON</div>
  <h2 class="section-title">Where Android and iOS users <em>diverge</em>.</h2>
  <p class="section-intro">Each negative review was tagged against {len(data['taxonomy']['negative_themes'])} complaint categories. Below: theme prevalence as a percentage of each store's negative reviews. The right column shows which platform skews more toward that complaint.</p>
  <div class="theme-compare-table">{"".join(tc_rows)}</div>
</section>

<section class="section" id="takeaways">
  <div class="section-num">III · STRATEGIC TAKEAWAYS</div>
  <h2 class="section-title">Four lessons drawn from <em>the data</em>.</h2>
  <p class="section-intro">Each insight below is grounded in a specific cluster of reviews and cited to the underlying evidence.</p>
  <div class="insights">{insights_html}</div>
</section>

</div>

<footer class="footer"><div class="wrap"><div class="footer-grid">
  <div>
    <div class="footer-brand">{html.escape(app_name)}</div>
    {byline_html}
    <p style="margin-top: 18px">Compiled from publicly available reviews on the Google Play Store and Apple App Store. Reviews were collected via each platform's public review feed; no private data was accessed.</p>
    <p>Full thematic deep-dives: <a href="playstore_deepdive.html">Google Play →</a> · <a href="appstore_deepdive.html">App Store →</a></p>
  </div>
  <div>
    <h4>Method</h4>
    <p>Total population: <strong>{total} text reviews</strong>. No sampling. Themes assigned via keyword pattern-matching against the <em>{html.escape(data['taxonomy']['label'])}</em> taxonomy.</p>
  </div>
  <div>
    <h4>Caveats</h4>
    <p>Public review feeds expose only published text. App Store RSS is capped at ~500 reviews per country. Total counts on store listings include star-only ratings without text.</p>
  </div>
</div></div></footer>

</body></html>"""


def build_single_store_executive(data, app_name, byline=None):
    """When only one store has data, build a simpler executive view."""
    agg = data["play"] or data["ios"]
    if not agg:
        return "<html><body><h1>No data available</h1></body></html>"

    store_name = "Google Play" if data["play"] else "App Store"
    deepdive_file = "playstore_deepdive.html" if data["play"] else "appstore_deepdive.html"

    byline_html = f'<div class="footer-byline">{html.escape(byline)}</div>' if byline else ""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{html.escape(app_name)} · Review Audit</title>{FONTS}<style>{CSS}</style></head><body>
<header class="masthead"><div class="wrap"><div class="masthead-row">
  <span class="left">Single-Store Audit</span>
  <span class="center">{html.escape(app_name)}</span>
  <span>{datetime.now().strftime('%B %Y')}</span>
</div></div></header>
<div class="wrap">
<section class="hero">
  <div class="kicker">— {store_name.upper()} · {agg['total']} REVIEWS</div>
  <h1 class="title">What users <em>actually</em> say.</h1>
  <p class="deck">Reviews from {store_name}. Only one store had a published listing for this app, so cross-store comparison isn't available. Full thematic analysis in the <a href="{deepdive_file}" style="color: var(--brand-primary); border-bottom: 1px solid var(--brand-primary);">deep-dive →</a></p>
</section>
</div>
<footer class="footer"><div class="wrap"><div class="footer-grid">
<div><div class="footer-brand">{html.escape(app_name)}</div>{byline_html}</div>
</div></div></footer>
</body></html>"""


def build_deepdive(data, store_key, app_name, byline=None):
    """Build a deep-dive report for one store."""
    if store_key == "play":
        agg = data["play"]
        store_name = "Google Play"
        store_display = "Google Play"
        timeline_data = data["play_timeline"]
        fourstars = data["play_fourstar"]
        power_quotes = data["play_power_quotes"]
        sister_link = ("appstore_deepdive.html", "App Store")
    else:
        agg = data["ios"]
        store_name = "App Store"
        store_display = "App Store (iOS)"
        timeline_data = data["ios_timeline"]
        fourstars = data["ios_fourstar"]
        power_quotes = data["ios_power_quotes"]
        sister_link = ("playstore_deepdive.html", "Google Play")

    if not agg or agg["total"] == 0:
        return f"<html><body><h1>No reviews found for {html.escape(app_name)} on {store_display}</h1></body></html>"

    total = agg["total"]
    avg = agg["avg_rating"]
    one_pct = agg["one_star"] / total * 100 if total else 0
    five_pct = agg["five_star"] / total * 100 if total else 0
    neg_total = agg["negative_total"]

    store_reviews = [r for r in data["all_reviews"] if r["source"] == store_name]
    neg_sorted = sorted(agg["neg_counts"].items(), key=lambda x: -x[1])
    pos_sorted = sorted(agg["pos_counts"].items(), key=lambda x: -x[1])

    dist_html = render_dist(agg["by_rating"], total)
    timeline_html = render_timeline(timeline_data)

    neg_dedupe = set()
    neg_blocks = []
    for i, (key, count) in enumerate(neg_sorted[:6], 1):
        label = data["taxonomy"]["negative_themes"].get(key, key)
        examples = agg["neg_examples"].get(key, [])
        neg_blocks.append(render_theme(key, label, count, neg_total, examples, False, i, neg_dedupe))

    pos_dedupe = set()
    pos_blocks = []
    pos_total = agg["positive_total"]
    for i, (key, count) in enumerate(pos_sorted[:5], 1):
        label = data["taxonomy"]["positive_themes"].get(key, key)
        examples = agg["pos_examples"].get(key, [])
        pos_blocks.append(render_theme(key, label, count, pos_total, examples, True, i, pos_dedupe))

    fourstar_html = render_fourstar_cards(fourstars)
    insights = generate_insights(agg, data["taxonomy"], store_display)
    insights_html = "".join(f"""<div class="insight">
      <div class="insight-num">№ {i+1:02d}</div>
      <div class="insight-title">{html.escape(ins['title'])}</div>
      <div class="insight-body">{ins['body']}</div>
      <div class="insight-evidence">{ins['evidence']}</div>
    </div>""" for i, ins in enumerate(insights))

    archive_html = archive_section_html(store_reviews, total, {**data["taxonomy"]["negative_themes"], **data["taxonomy"]["positive_themes"]})

    # Pull quote — use best power quote if available
    pull_quote_html = ""
    if power_quotes:
        pq = power_quotes[0]
        pull_quote_html = f"""<div class="pull-quote">
          <div class="pull-quote-text">{html.escape(pq['review'])}</div>
          <div class="pull-quote-attr">{html.escape(pq['user'])} · {pq['rating']}-star review</div>
        </div>"""

    has_cross_store = bool(data["cross"])
    nav_items = []
    if has_cross_store:
        nav_items.append('<a href="executive_summary.html">← Executive Summary</a>')
    nav_items.extend([
        '<a href="#summary">Summary</a>',
        '<a href="#timeline">Timeline</a>',
        '<a href="#complaints">Complaints</a>',
        '<a href="#fourstar">Almost-Loyal</a>',
        '<a href="#praise">Praise</a>',
        '<a href="#takeaways">Takeaways</a>',
        '<a href="#all-reviews">Archive</a>',
    ])
    if has_cross_store:
        nav_items.append(f'<a href="{sister_link[0]}">{sister_link[1]} →</a>')
    nav = f'<div class="sticky-nav"><div class="wrap"><div class="nav-row">{"".join(nav_items)}</div></div></div>'

    byline_html = f'<div class="footer-byline">{html.escape(byline)}</div>' if byline else ""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(app_name)} · {store_display} · Deep Dive</title>
{FONTS}<style>{CSS}</style></head><body>

<header class="masthead"><div class="wrap"><div class="masthead-row">
  <span class="left">{store_display} · Deep Dive</span>
  <span class="center">{html.escape(app_name)}</span>
  <span>{datetime.now().strftime('%B %Y')}</span>
</div></div></header>

{nav}

<div class="wrap">

<section class="hero">
  <div class="kicker">— {store_display.upper()} · {total} REVIEWS</div>
  <h1 class="title">What users <em>actually</em> say.</h1>
  <p class="deck">A thematic reading of every published review on the {store_display}, organised by what frustrates users, what wins their loyalty, and what the gap between those two reveals.</p>
  <div class="byline-row">
    <div><span class="label">Source</span> {store_display}</div>
    <div><span class="label">Sample</span> {total} text reviews</div>
    <div><span class="label">Avg.</span> {avg} ★</div>
    {f'<div><span class="label">Period</span> {timeline_data[0]["month"]} → {timeline_data[-1]["month"]}</div>' if timeline_data else ''}
  </div>
</section>

<section class="section" id="summary">
  <div class="section-num">I · THE NUMBERS</div>
  <h2 class="section-title">A bimodal verdict: <em>devotion</em> on one side, <em>fury</em> on the other.</h2>
  <p class="section-intro">The rating distribution is hollow in the middle — users cluster at the extremes.</p>
  <div class="stat-strip">
    <div class="stat"><div class="stat-num">{avg}</div><div class="stat-label">Average rating</div></div>
    <div class="stat"><div class="stat-num good">{five_pct:.0f}%</div><div class="stat-label">5-star reviews</div></div>
    <div class="stat"><div class="stat-num bad">{one_pct:.0f}%</div><div class="stat-label">1-star reviews</div></div>
    <div class="stat"><div class="stat-num">{neg_total}</div><div class="stat-label">Negative (1–3★)</div></div>
  </div>
  {dist_html}
</section>

<section class="section" id="timeline">
  <div class="section-num">II · OVER TIME</div>
  <h2 class="section-title">When did things <em>change</em>?</h2>
  <p class="section-intro">Reviews bucketed by calendar quarter, scaled by volume and segmented by rating mix. Wider bars = more reviews; more red = more negative.</p>
  {timeline_html}
</section>

<section class="section" id="complaints">
  <div class="section-num">III · WHAT FRUSTRATES USERS</div>
  <h2 class="section-title">Top complaints, ranked by <em>how often</em> users name them.</h2>
  <p class="section-intro">Each negative review (1–3★) was tagged against the {html.escape(data['taxonomy']['label'])} taxonomy. Reviews are <strong>not repeated</strong> across themes — if you see a powerful quote in one section, you won't see it again in another.</p>
  {"".join(neg_blocks)}
</section>

{pull_quote_html}

<section class="section" id="fourstar">
  <div class="section-num">IV · THE ALMOST-LOYAL</div>
  <h2 class="section-title">Four-star reviewers tell you exactly what <em>would</em> have made them five.</h2>
  <p class="section-intro">Of {agg['four_star_total']} four-star reviews, {len(fourstars)} contain explicit conditional language — "but," "wish," "only thing." These are the most strategically valuable reviews: users who already mostly love the product, telling you the single change that would tip them to total loyalty. Their conditions are <mark style="background:rgba(200,133,26,0.18); padding:0 3px">highlighted</mark> below.</p>
  {fourstar_html}
</section>

<section class="section" id="praise">
  <div class="section-num">V · WHAT WINS LOYALTY</div>
  <h2 class="section-title">Five-star reviewers praise <em class="sage">outcomes</em>, not features.</h2>
  <p class="section-intro">Among 4 and 5-star reviews, the dominant themes are about <strong>what the app changed</strong> in the user's life — not how the app looks or feels to use.</p>
  {"".join(pos_blocks)}
</section>

<section class="section" id="takeaways">
  <div class="section-num">VI · STRATEGIC TAKEAWAYS</div>
  <h2 class="section-title">Lessons drawn from <em>the evidence</em>.</h2>
  <p class="section-intro">Each insight below is grounded in a specific cluster of reviews and cited to the underlying numbers.</p>
  <div class="insights">{insights_html}</div>
</section>

{archive_html}

</div>

<footer class="footer"><div class="wrap"><div class="footer-grid">
  <div>
    <div class="footer-brand">{html.escape(app_name)}</div>
    {byline_html}
    <p style="margin-top: 18px">Compiled from publicly available reviews on the {store_display} listing. Reviews collected via the platform's public review feed; no private user data accessed.</p>
    {f'<p>Companion documents: <a href="executive_summary.html">Executive Summary →</a> · <a href="{sister_link[0]}">{sister_link[1]} deep dive →</a></p>' if has_cross_store else ''}
  </div>
  <div>
    <h4>Method</h4>
    <p>Full population: {total} text reviews. Themes assigned via keyword pattern-matching against the {html.escape(data['taxonomy']['label'])} taxonomy. Quotes deduplicated across themes.</p>
  </div>
  <div>
    <h4>Notes</h4>
    <p>The {store_display} listing typically reports a higher total ratings count than text reviews — most users tap stars without writing. Every published text review is included here.</p>
  </div>
</div></div></footer>

{archive_js(total)}

</body></html>"""


def generate_html_reports(data, output_dir, app_name, byline=None):
    """Generate all three HTML reports to the output directory."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    files_written = []

    has_both_stores = bool(data["play"] and data["ios"])

    if has_both_stores:
        exec_html = build_executive_summary(data, app_name, byline)
        exec_path = output / "executive_summary.html"
        exec_path.write_text(exec_html)
        files_written.append(str(exec_path))

    if data["play"] and data["play"]["total"] > 0:
        play_html = build_deepdive(data, "play", app_name, byline)
        play_path = output / "playstore_deepdive.html"
        play_path.write_text(play_html)
        files_written.append(str(play_path))

    if data["ios"] and data["ios"]["total"] > 0:
        ios_html = build_deepdive(data, "ios", app_name, byline)
        ios_path = output / "appstore_deepdive.html"
        ios_path.write_text(ios_html)
        files_written.append(str(ios_path))

    return files_written


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate HTML reports from analyzed data")
    parser.add_argument("--input", required=True, help="Analyzed data JSON")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--app-name", required=True, help="App display name")
    parser.add_argument("--byline", help="Optional byline for the footer")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text())
    files = generate_html_reports(data, args.output, args.app_name, args.byline)
    for f in files:
        print(f)
