#!/usr/bin/env python3
"""Generate Material-style SVG cards (language doughnut + stats) for a GitHub profile README.

Pure standard library. Env vars:
  GH_USER        GitHub username (default: gideonzozingao)
  GH_TOKEN       Token. GITHUB_TOKEN sees public repos only; a PAT with `repo`
                 scope (stored as secret STATS_TOKEN) includes private repos.
  EXCLUDE_REPOS  Comma-separated repo names to skip
  EXCLUDE_LANGS  Comma-separated languages to skip (e.g. "HTML,CSS,Blade")
  TOP_N          Languages shown before grouping into "Other" (default 8)
"""
import json, math, os, sys, urllib.request, urllib.error
from pathlib import Path

USER = os.getenv("GH_USER", "gideonzozingao")
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
EXCLUDE_REPOS = {s.strip().lower() for s in os.getenv("EXCLUDE_REPOS", "").split(",") if s.strip()}
EXCLUDE_LANGS = {s.strip().lower() for s in os.getenv("EXCLUDE_LANGS", "").split(",") if s.strip()}
TOP_N = int(os.getenv("TOP_N", "8"))
OUT = Path(os.getenv("OUT_DIR", "assets"))

# Material palette
BG, BORDER, TITLE, TEXT, MUTED = "#263238", "#37474F", "#80CBC4", "#ECEFF1", "#B0BEC5"
PALETTE = ["#80CBC4", "#FFB74D", "#64B5F6", "#BA68C8", "#81C784", "#E57373", "#FFF176", "#4DD0E1", "#90A4AE"]
FONT = "Roboto, 'Segoe UI', Helvetica, Arial, sans-serif"


def api(url, data=None):
    req = urllib.request.Request(url, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def paged(url):
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        chunk = api(f"{url}{sep}per_page=100&page={page}")
        if not chunk:
            return
        yield from chunk
        if len(chunk) < 100:
            return
        page += 1


def collect_repos():
    # /user/repos (authenticated) includes private repos; fall back to public listing.
    if TOKEN:
        try:
            repos = list(paged("https://api.github.com/user/repos?affiliation=owner&visibility=all"))
            repos = [r for r in repos if r["owner"]["login"].lower() == USER.lower()]
            if repos:
                return repos
        except urllib.error.HTTPError as e:
            print(f"/user/repos failed ({e.code}); falling back to public repos", file=sys.stderr)
    return list(paged(f"https://api.github.com/users/{USER}/repos?type=owner"))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <rect x="0.5" y="0.5" rx="12" width="{width-1}" height="{height-1}" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="38" font-family="{FONT}" font-size="18" font-weight="600" fill="{TITLE}">{esc(title)}</text>
{body}
</svg>
"""


def languages_svg(totals):
    items = [(k, v) for k, v in totals.items() if k.lower() not in EXCLUDE_LANGS]
    items.sort(key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in items) or 1
    head, rest = items[:TOP_N], items[TOP_N:]
    if rest:
        head.append(("Other", sum(v for _, v in rest)))

    cx, cy, r, sw = 120, 140, 62, 28
    circ = 2 * math.pi * r
    gap = 2
    parts, legend, offset = [], [], 0.0
    for i, (name, val) in enumerate(head):
        color = PALETTE[i % len(PALETTE)]
        frac = val / total
        seg = max(frac * circ - gap, 0.5)
        parts.append(
            f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{seg:.2f} {circ - seg:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += frac * circ
        y = 72 + i * 22
        legend.append(
            f'  <rect x="240" y="{y-11}" width="12" height="12" rx="3" fill="{color}"/>\n'
            f'  <text x="260" y="{y}" font-family="{FONT}" font-size="13" fill="{TEXT}">{esc(name)}</text>\n'
            f'  <text x="440" y="{y}" font-family="{FONT}" font-size="13" fill="{MUTED}" text-anchor="end">{frac*100:.1f}%</text>'
        )
    centre = (
        f'  <text x="{cx}" y="{cy-2}" font-family="{FONT}" font-size="22" font-weight="600" fill="{TEXT}" text-anchor="middle">{len(items)}</text>\n'
        f'  <text x="{cx}" y="{cy+16}" font-family="{FONT}" font-size="11" fill="{MUTED}" text-anchor="middle">languages</text>'
    )
    height = max(230, 72 + len(head) * 22 + 20)
    return card(460, height, "Language Usage", "\n".join(parts + [centre] + legend))


def stats_svg(stats):
    rows = [
        ("Public repositories", stats["repos"]),
        ("Stars earned", stats["stars"]),
        ("Forks received", stats["forks"]),
        ("Followers", stats["followers"]),
    ]
    if stats.get("contributions") is not None:
        rows.append(("Contributions (last year)", stats["contributions"]))
    body = []
    for i, (label, val) in enumerate(rows):
        y = 78 + i * 30
        body.append(
            f'  <circle cx="30" cy="{y-5}" r="4" fill="{PALETTE[i % len(PALETTE)]}"/>\n'
            f'  <text x="44" y="{y}" font-family="{FONT}" font-size="14" fill="{TEXT}">{esc(label)}</text>\n'
            f'  <text x="430" y="{y}" font-family="{FONT}" font-size="14" font-weight="600" fill="{TITLE}" text-anchor="end">{val:,}</text>'
        )
    return card(460, max(230, 78 + len(rows) * 30 + 10), "GitHub Stats", "\n".join(body))


def contributions():
    if not TOKEN:
        return None
    q = {"query": 'query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{totalContributions}}}}',
         "variables": {"l": USER}}
    try:
        d = api("https://api.github.com/graphql", json.dumps(q).encode())
        return d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception as e:  # optional metric
        print(f"contributions unavailable: {e}", file=sys.stderr)
        return None


def main():
    repos = [r for r in collect_repos() if not r.get("fork") and r["name"].lower() not in EXCLUDE_REPOS]
    totals = {}
    for r in repos:
        try:
            for lang, n in api(r["languages_url"]).items():
                totals[lang] = totals.get(lang, 0) + n
        except urllib.error.HTTPError as e:
            print(f"skip {r['name']}: {e.code}", file=sys.stderr)
    user = api(f"https://api.github.com/users/{USER}")
    stats = {
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "forks": sum(r["forks_count"] for r in repos),
        "followers": user["followers"],
        "contributions": contributions(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "languages.svg").write_text(languages_svg(totals), encoding="utf-8")
    (OUT / "stats.svg").write_text(stats_svg(stats), encoding="utf-8")
    print(f"{len(repos)} repos, {len(totals)} languages -> {OUT}/")


if __name__ == "__main__":
    main()
