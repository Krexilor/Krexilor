# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import os
import json
import math
import urllib.request
from pathlib import Path
from string import Template
from xml.sax.saxutils import escape

API_URL = "https://api.github.com/graphql"
RING_CX = 316
RING_CY = 470
RING_R = 159
RING_LENGTH = 2 * math.pi * RING_R
SEGMENT_GAP = 5
BAR_X = 616
BAR_WIDTH = 1042
MAX_LANGUAGES = 5
OTHERS_NAME = "Others"
OTHERS_COLOR = "#6f7fa6"
PALETTE = ["#ff8a14", "#1e9bff", "#8b5cf6", "#16e07a", "#fbbf24"]
COLUMNS = [616, 964, 1312]
ROWS = [
    {"dot": 386, "name": 396, "value": 470},
    {"dot": 568, "name": 578, "value": 652}
]

# FETCHES REPOSITORY LANGUAGES ---------------------------------------------------------------------------------------------------------------------|
REPOSITORIES_QUERY = """
query($login: String!, $cursor: String) {
    user(login: $login) {
        repositories(first: 50, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
            pageInfo {
                hasNextPage
                endCursor
            }
            nodes {
                languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
                    edges {
                        size
                        node {
                            name
                        }
                    }
                }
            }
        }
    }
}
"""

# SVG TEMPLATE --------------------------------------------------------------------------------------------------------------------------------------|
SVG_TEMPLATE = Template("""<svg xmlns="http://www.w3.org/2000/svg" width="1646" height="641" viewBox="64 103 1646 641" font-family="Inter, 'Segoe UI', Arial, Helvetica, sans-serif" role="img" aria-label="Most used languages card">
    <defs>
        <clipPath id="barClip">
            <rect x="616" y="298" width="1042" height="24" rx="12"/>
        </clipPath>
    </defs>
    <rect x="65.5" y="104.5" width="1643" height="638" rx="41" fill="#0b1628" stroke="#1f4aa3" stroke-width="3"/>
    <g transform="translate(129,145) scale(4.875)" fill="#ffffff">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
    </g>
    <text x="245" y="203" font-size="58" font-weight="700" fill="#ffffff" textLength="545" lengthAdjust="spacingAndGlyphs">Most Used Languages</text>
    <g transform="translate(1603.2,151.2) scale(2.4)" fill="none" stroke="#4f7cff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 8l-4 4l4 4M17 8l4 4l-4 4M14 4l-4 16"/>
    </g>
    <line x1="104" y1="243" x2="1670" y2="243" stroke="#1a2d52" stroke-width="2"/>
    <g fill="none" stroke-width="24" transform="rotate(-90 316 470)">$donut</g>
    <g transform="translate(274.6,350) scale(3.45)" fill="none" stroke="#ff8a14" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round">
        <path d="M7 8l-4 4l4 4M17 8l4 4l-4 4M14 4l-4 16"/>
    </g>
    <text x="316" y="516" font-size="$top_size" font-weight="700" fill="#ffffff" text-anchor="middle">$top_name</text>
    <text x="214" y="566" font-size="28" font-weight="600" fill="#8493b6" textLength="203" lengthAdjust="spacingAndGlyphs">TOP LANGUAGE</text>
    <line x1="562" y1="302" x2="562" y2="690" stroke="#1a2d52" stroke-width="2"/>
    <g clip-path="url(#barClip)">$bar</g>
    <line x1="940" y1="360" x2="940" y2="690" stroke="#1a2d52" stroke-width="2"/>
    <line x1="1288" y1="360" x2="1288" y2="690" stroke="#1a2d52" stroke-width="2"/>
    <line x1="616" y1="512" x2="1658" y2="512" stroke="#1a2d52" stroke-width="2"/>
    $items
</svg>
""")

# SENDS GRAPHQL REQUEST TO GITHUB API --------------------------------------------------------------------------------------------------------------|
def graphql(token: str, query: str, variables: dict) -> dict:
    request = urllib.request.Request(
        API_URL,
        data = json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "github-languages-card"
        }
    )
    with urllib.request.urlopen(request, timeout = 30) as response:
        payload = json.load(response)

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    return payload["data"]

# GATHERS LANGUAGE BYTES FROM ALL REPOSITORIES -----------------------------------------------------------------------------------------------------|
def collect_languages(token: str, login: str) -> dict:
    totals: dict[str, int] = {}
    cursor = None

    while True:
        data = graphql(token, REPOSITORIES_QUERY, {"login": login, "cursor": cursor})
        repositories = data["user"]["repositories"]

        for repository in repositories["nodes"]:
            for edge in repository["languages"]["edges"]:
                name = edge["node"]["name"]
                totals[name] = totals.get(name, 0) + edge["size"]

        page = repositories["pageInfo"]
        if not page["hasNextPage"]:
            break

        cursor = page["endCursor"]

    return totals

# BUILDS TOP LANGUAGES AND OTHERS LIST -------------------------------------------------------------------------------------------------------------|
def build_entries(totals: dict) -> list:
    total = sum(totals.values())

    if total <= 0:
        return []

    ranked = sorted(totals.items(), key = lambda item: item[1], reverse = True)
    entries = [
        {"name": name, "fraction": size / total, "color": PALETTE[index]}
        for index, (name, size) in enumerate(ranked[:MAX_LANGUAGES])
    ]
    remainder = sum(size for _, size in ranked[MAX_LANGUAGES:])

    if remainder > 0:
        entries.append({"name": OTHERS_NAME, "fraction": remainder / total, "color": OTHERS_COLOR})

    return entries

# TRUNCATES LONG LANGUAGE NAMES --------------------------------------------------------------------------------------------------------------------|
def truncate(name: str, limit: int) -> str:
    return name if len(name) <= limit else name[:limit - 1] + "…"

# BUILD THE DONUT SEGMENTS -------------------------------------------------------------------------------------------------------------------------|
def build_donut(entries: list) -> str:
    segments = []
    cumulative = 0.0

    for entry in entries:
        length = max(entry["fraction"] * RING_LENGTH - SEGMENT_GAP, 1.0)
        offset = cumulative * RING_LENGTH + SEGMENT_GAP / 2
        color = entry["color"]
        segments.append(
            f'<circle cx="{RING_CX}" cy="{RING_CY}" r="{RING_R}" stroke="{color}" '
            f'stroke-dasharray="{length:.2f} {RING_LENGTH:.2f}" stroke-dashoffset="-{offset:.2f}"/>'
        )
        cumulative += entry["fraction"]

    return "".join(segments)

# BUILD THE PROGRESS BAR SEGMENTS ------------------------------------------------------------------------------------------------------------------|
def build_bar(entries: list) -> str:
    available = BAR_WIDTH - SEGMENT_GAP * (len(entries) - 1)
    cursor = float(BAR_X)
    segments = []

    for entry in entries:
        width = entry["fraction"] * available
        color = entry["color"]
        segments.append(f'<rect x="{cursor:.1f}" y="298" width="{width:.1f}" height="24" fill="{color}"/>')
        cursor += width + SEGMENT_GAP

    return "".join(segments)

# BUILD THE LANGUAGE GRID ITEMS --------------------------------------------------------------------------------------------------------------------|
def build_items(entries: list) -> str:
    items = []

    for index, entry in enumerate(entries):
        column = COLUMNS[index % len(COLUMNS)]
        row = ROWS[index // len(COLUMNS)]
        color = entry["color"]
        name = escape(truncate(entry["name"], 18))
        percent = f"{entry['fraction'] * 100:.1f}%"
        items.append(
            f'<circle cx="{column + 10}" cy="{row["dot"]}" r="9" fill="{color}"/>\n'
            f'    <text x="{column + 34}" y="{row["name"]}" font-size="29" fill="#8ea2c6">{name}</text>\n'
            f'    <text x="{column + 34}" y="{row["value"]}" font-size="58" font-weight="700" fill="#ffffff">{percent}</text>'
        )

    return "\n    ".join(items)

# FILL AND RETURN THE FINAL SVG MARKUP -------------------------------------------------------------------------------------------------------------|
def render(entries: list) -> str:
    top_name = truncate(entries[0]["name"], 16) if entries else "N/A"
    top_size = max(24, min(80, int(250 / (0.65 * len(top_name)))))

    return SVG_TEMPLATE.substitute(
        donut = build_donut(entries),
        bar = build_bar(entries),
        items = build_items(entries),
        top_name = escape(top_name),
        top_size = top_size
    )

# WRITE SVG FILE -----------------------------------------------------------------------------------------------------------------------------------|
def main() -> None:
    token = os.environ["GH_TOKEN"]
    login = os.environ["GITHUB_USER"]
    output = Path(os.environ.get("OUTPUT_PATH", "assets/stats/github-languages.svg"))

    totals = collect_languages(token, login)
    entries = build_entries(totals)

    output.parent.mkdir(parents = True, exist_ok = True)
    output.write_text(render(entries), encoding = "utf-8")
    print(f"{login}: languages = {len(totals)} top = {entries[0]['name'] if entries else 'none'}")

# MAIN FUNCTION ------------------------------------------------------------------------------------------------------------------------------------|
if __name__ == "__main__":
    main()
