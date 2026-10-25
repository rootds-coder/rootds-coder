#!/usr/bin/env python3
"""Generate assets/stats.svg from real GitHub data (GraphQL API).

Environment:
  GITHUB_TOKEN  token used for the API (the Actions default token works for public data)
  GH_USER       GitHub username (defaults to the repository owner in Actions)
Only the standard library is used.
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.request

API = "https://api.github.com/graphql"
FONT = "'JetBrains Mono','Fira Code','SFMono-Regular',Consolas,'Courier New',monospace"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "stats.svg")


def gql(query, variables, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-generator"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def collect(user, token):
    profile = gql(
        """query($login:String!){user(login:$login){createdAt followers{totalCount}
        repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100){totalCount
          nodes{stargazerCount languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}""",
        {"login": user}, token)["user"]
    created = dt.datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    days = {}
    for year in range(created.year, now.year + 1):
        start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
        end = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        cal = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){
            contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}""",
            {"login": user, "from": start.isoformat(), "to": end.isoformat()}, token,
        )["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    langs = {}
    stars = 0
    for repo in profile["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            cur = langs.get(n, [0, e["node"]["color"] or "#8b949e"])
            cur[0] += e["size"]
            langs[n] = cur
    return {
        "user": user,
        "since": created.year,
        "days": days,
        "repos": profile["repositories"]["totalCount"],
        "stars": stars,
        "followers": profile["followers"]["totalCount"],
        "langs": sorted(((n, v[0], v[1]) for n, v in langs.items()), key=lambda x: -x[1]),
    }


def streaks(days):
    today = dt.datetime.now(dt.timezone.utc).date()
    ordered = sorted(dt.date.fromisoformat(d) for d, c in days.items() if c > 0)
    have = set(ordered)
    longest, best_range, run, run_start, prev = 0, None, 0, None, None
    for d in ordered:
        if prev and (d - prev).days == 1:
            run += 1
        else:
            run, run_start = 1, d
        if run > longest:
            longest, best_range = run, (run_start, d)
        prev = d
    cur_end = today if today in have else today - dt.timedelta(days=1)
    cur, d = 0, cur_end
    while d in have:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_range = (d + dt.timedelta(days=1), cur_end) if cur else None
    return cur, cur_range, longest, best_range


def fmt_range(r):
    if not r:
        return ["no active streak"]
    a, b = r
    f = lambda x: x.strftime("%b %d, %Y")
    return [f(a)] if a == b else [f(a) + " →", f(b)]


def esc(s):
    return html.escape(str(s), quote=False)


def render(data):
    """data=None draws the 'waiting for first sync' card (no numbers)."""
    W, H = 900, 330
    head = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<title>GitHub activity statistics</title>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#050816"/><stop offset="1" stop-color="#0d1330"/></linearGradient>
<linearGradient id="bd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f472b6"/><stop offset=".5" stop-color="#a78bfa"/><stop offset="1" stop-color="#22d3ee"/></linearGradient>
<pattern id="gr" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="#1e2a4a" stroke-width=".6" opacity=".5"/></pattern>
<clipPath id="lb"><rect x="30" y="268" width="840" height="12" rx="6"/></clipPath>
</defs>
<style>
.bdr{{stroke-dasharray:240 2700;animation:bdr 7s linear infinite}}@keyframes bdr{{to{{stroke-dashoffset:-2940}}}}
.in{{opacity:0;animation:in .8s ease forwards}}@keyframes in{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
.ring{{stroke-dasharray:289;stroke-dashoffset:289;animation:ring 1.6s ease-out forwards}}@keyframes ring{{to{{stroke-dashoffset:var(--o)}}}}
.fl{{animation:fl 1.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}@keyframes fl{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.18)}}}}
.seg{{transform-box:fill-box;transform-origin:left;animation:sg 1.4s ease-out both}}@keyframes sg{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.pu{{animation:pu 2.4s ease-in-out infinite}}@keyframes pu{{0%,100%{{opacity:.6}}50%{{opacity:1}}}}
</style>
<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="url(#bg)"/>
<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="url(#gr)"/>
<rect x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="none" stroke="#a78bfa" stroke-opacity=".25" stroke-width="1.5"/>
<rect class="bdr" x="2" y="2" width="{W-4}" height="{H-4}" rx="18" fill="none" stroke="url(#bd)" stroke-width="3" stroke-linecap="round"/>
'''
    if data is None:
        return head + f'''<text class="pu" x="{W/2}" y="150" fill="#22d3ee" font-size="16" font-weight="700" text-anchor="middle" letter-spacing="3">AWAITING FIRST SYNC</text>
<text x="{W/2}" y="182" fill="#8ea0c4" font-size="13" text-anchor="middle">Run the "Update profile stats" workflow once (Actions tab) to load your real GitHub data.</text></svg>'''

    total = sum(data["days"].values())
    cur, cur_r, lng, lng_r = streaks(data["days"])
    now = dt.datetime.now(dt.timezone.utc)
    s = head
    s += f'<text x="30" y="34" fill="#f472b6" font-size="12" font-weight="700" letter-spacing="3">GITHUB ACTIVITY · @{esc(data["user"])}</text>'
    s += f'<text x="870" y="34" fill="#6a7ba3" font-size="11" text-anchor="end">auto-synced {now.strftime("%Y-%m-%d %H:%M")} UTC</text>'
    tiles = [("TOTAL CONTRIBUTIONS", f"{total:,}", [f"since {data['since']}"], "#22d3ee", min(total / 1000, 1)),
             ("CURRENT STREAK", f"{cur}", fmt_range(cur_r), "#f472b6", min(cur / 30, 1)),
             ("LONGEST STREAK", f"{lng}", fmt_range(lng_r), "#a78bfa", min(lng / 60, 1))]
    for i, (lab, val, sub, c, frac) in enumerate(tiles):
        x = 30 + i * 285
        off = 289 * (1 - max(frac, 0.04))
        s += f'''<g class="in" style="animation-delay:{.15+i*.2}s">
<rect x="{x}" y="52" width="270" height="130" rx="14" fill="#0a1128" stroke="{c}" stroke-opacity=".45"/>
<g transform="translate({x+26},70)"><circle cx="46" cy="46" r="46" fill="none" stroke="{c}" stroke-opacity=".15" stroke-width="7"/>
<circle class="ring" cx="46" cy="46" r="46" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round" transform="rotate(-90 46 46)" style="--o:{off:.0f}px;animation-delay:{.3+i*.2}s"/>
<text x="46" y="{56 if len(val) < 5 else 54}" fill="#ffffff" font-size="{26 if len(val) < 5 else 20}" font-weight="800" text-anchor="middle">{esc(val)}</text></g>
<text x="{x+134}" y="104" fill="{c}" font-size="12" font-weight="700" letter-spacing="1.5">{lab.split()[0]}</text>
<text x="{x+134}" y="122" fill="{c}" font-size="12" font-weight="700" letter-spacing="1.5">{lab.split(' ',1)[1]}</text>
{"".join(f'<text x="{x+134}" y="{146+k*15}" fill="#8ea0c4" font-size="10.5">{esc(line)}</text>' for k, line in enumerate(sub))}</g>'''
    minis = [("PUBLIC REPOS", data["repos"], "#34d399"), ("STARS EARNED", data["stars"], "#fbbf24"), ("FOLLOWERS", data["followers"], "#38bdf8")]
    for i, (lab, val, c) in enumerate(minis):
        x = 30 + i * 285
        s += f'''<g class="in" style="animation-delay:{.7+i*.15}s"><rect x="{x}" y="196" width="270" height="44" rx="12" fill="{c}" fill-opacity=".08" stroke="{c}" stroke-opacity=".4"/>
<text x="{x+18}" y="224" fill="{c}" font-size="11.5" font-weight="700" letter-spacing="1.5">{lab}</text>
<text x="{x+252}" y="226" fill="#ffffff" font-size="20" font-weight="800" text-anchor="end">{val:,}</text></g>'''
    langs = data["langs"][:6]
    tot = sum(l[1] for l in langs) or 1
    s += '<text x="30" y="260" fill="#8ea0c4" font-size="11" font-weight="700" letter-spacing="2">TOP LANGUAGES (BY CODE VOLUME IN PUBLIC REPOS)</text>'
    s += '<rect x="30" y="268" width="840" height="12" rx="6" fill="#0a1128"/><g clip-path="url(#lb)">'
    x = 30.0
    for i, (n, sz, c) in enumerate(langs):
        w = 840 * sz / tot
        s += f'<rect class="seg" x="{x:.1f}" y="268" width="{max(w,1):.1f}" height="12" fill="{esc(c)}" style="animation-delay:{.9+i*.15}s"/>'
        x += w
    s += '</g>'
    lx = 30
    for n, sz, c in langs:
        s += f'<circle cx="{lx+5}" cy="304" r="5" fill="{esc(c)}"/><text x="{lx+16}" y="308" fill="#c9d6e8" font-size="11.5">{esc(n)} {sz/tot*100:.1f}%</text>'
        lx += 16 + int(len(n) * 7.4) + 52
    return s + '</svg>'


def main():
    token = os.environ.get("GITHUB_TOKEN")
    user = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if not token or not user:
        sys.exit("Set GITHUB_TOKEN and GH_USER (or GITHUB_REPOSITORY_OWNER).")
    data = collect(user, token)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(data))
    print("stats.svg written for", user)


if __name__ == "__main__":
    main()
