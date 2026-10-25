# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import os
import json
import random
import calendar
import urllib.request
from pathlib import Path
from string import Template
from collections import deque
from datetime import date, datetime, timezone

API_URL = "https://api.github.com/graphql"
CARD_CENTER_X = 887
CELL = 22
PITCH = 28
ROWS = 7
STATS_Y = 312
MONTHS_Y = 382
GRID_Y = 400
LEGEND_Y = 648
CARD_BACKGROUND = "#0b1628"
EMPTY_COLOR = "#14223a"
LEVEL_COLORS = ["#123a66", "#1560a8", "#1e86e0", "#38b6ff"]
LEVEL_NAMES = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4
}
SNAKE_STYLES = [
    (24, "#ffb21a"),
    (22, "#ff8a14"),
    (20, "#ff6a1f"),
    (18, "#ff4a2b"),
    (16, "#d83a2a")
]
SNAKE_LENGTH = len(SNAKE_STYLES)
TARGET_POOL = 4
FADE_SECONDS = 0.2
HOME_PAUSE_SECONDS = 2.0
TARGET_LOOP_SECONDS = 60.0
MIN_STEP_SECONDS = 0.05
MAX_STEP_SECONDS = 0.12
MAX_STEPS = 20000

# FETCHES CONTRIBUTION CALENDAR --------------------------------------------------------------------------------------------------------------------|
CALENDAR_QUERY = """
query($login: String!) {
    user(login: $login) {
        contributionsCollection {
            contributionCalendar {
                totalContributions
                weeks {
                    contributionDays {
                        date
                        weekday
                        contributionLevel
                    }
                }
            }
        }
    }
}
"""

# SVG TEMPLATE -------------------------------------------------------------------------------------------------------------------------------------|
SVG_TEMPLATE = Template("""<svg xmlns="http://www.w3.org/2000/svg" width="1646" height="641" viewBox="64 103 1646 641" font-family="Inter, 'Segoe UI', Arial, Helvetica, sans-serif" role="img" aria-label="Contribution calendar card">
<style>$css</style>
<defs>
<pattern id="grid" x="$grid_x" y="$grid_y" width="28" height="28" patternUnits="userSpaceOnUse"><rect width="22" height="22" rx="5" fill="$empty"/></pattern>
<rect id="c" width="22" height="22" rx="5"/>
</defs>
<rect x="65.5" y="104.5" width="1643" height="638" rx="41" fill="$background" stroke="#1f4aa3" stroke-width="3"/>
<g transform="translate(129,145) scale(4.875)" fill="#ffffff"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></g>
<text x="245" y="203" font-size="58" font-weight="700" fill="#ffffff" textLength="592" lengthAdjust="spacingAndGlyphs">Contribution Calendar</text>
<g transform="translate(1603.2,151.2) scale(2.4)" fill="none" stroke="#4f7cff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8l4 -16l3 8h4"/></g>
<line x1="104" y1="243" x2="1670" y2="243" stroke="#1a2d52" stroke-width="2"/>
<text x="$grid_x" y="$stats_y" font-size="30" fill="#8ea2c6"><tspan font-size="36" font-weight="700" fill="#ffffff">$total</tspan> contributions in the last year</text>
$months
<rect x="$grid_x" y="$grid_y" width="$grid_width" height="190" fill="url(#grid)"/>
$missing
$cells
$legend
<g>$snake</g>
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
            "User-Agent": "github-contribution-calendar"
        }
    )
    with urllib.request.urlopen(request, timeout = 30) as response:
        payload = json.load(response)

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    return payload["data"]

# PARSES CALENDAR INTO LEVELS AND MONTHS -----------------------------------------------------------------------------------------------------------|
def parse_calendar(weeks: list) -> tuple[dict, list]:
    levels: dict[tuple[int, int], int] = {}
    months: list[int] = []

    for column, week in enumerate(weeks):
        days = week["contributionDays"]
        months.append(date.fromisoformat(days[0]["date"]).month)

        for day in days:
            levels[(column, day["weekday"])] = LEVEL_NAMES[day["contributionLevel"]]

    return levels, months

# PICKS THE HOME CELL ON THE LEFT SIDE -------------------------------------------------------------------------------------------------------------|
def pick_home(valid: set) -> tuple:
    first_column = min(column for column, _ in valid)
    rows = [row for column, row in valid if column == first_column]

    return first_column, min(rows, key = lambda row: abs(row - ROWS // 2))

# LISTS NEIGHBOUR CELLS INSIDE THE GRID ------------------------------------------------------------------------------------------------------------|
def neighbors(position: tuple, valid: set) -> list:
    column, row = position
    steps = ((1, 0), (-1, 0), (0, 1), (0, -1))

    return [(column + dx, row + dy) for dx, dy in steps if (column + dx, row + dy) in valid]

# MEASURES GRID DISTANCE TO EVERY CELL -------------------------------------------------------------------------------------------------------------|
def distances(start: tuple, valid: set) -> dict:
    found = {start: 0}
    queue = deque([start])

    while queue:
        current = queue.popleft()
        for option in neighbors(current, valid):
            if option not in found:
                found[option] = found[current] + 1
                queue.append(option)

    return found

# FINDS A RANDOMISED SHORTEST PATH -----------------------------------------------------------------------------------------------------------------|
def shortest_path(start: tuple, goal: tuple, valid: set, blocked: set, rng: random.Random) -> list | None:
    parents: dict = {start: None}
    queue = deque([start])

    while queue and goal not in parents:
        current = queue.popleft()
        options = [option for option in neighbors(current, valid) if option not in blocked and option not in parents]
        rng.shuffle(options)
        for option in options:
            parents[option] = current
            queue.append(option)

    if goal not in parents:
        return None

    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = parents[node]
    path.reverse()

    return path

# PICKS A RANDOM NEARBY CONTRIBUTION CELL ----------------------------------------------------------------------------------------------------------|
def pick_target(head: tuple, remaining: set, valid: set, rng: random.Random) -> tuple:
    reach = distances(head, valid)
    nearest = sorted(remaining, key = lambda cell: reach.get(cell, MAX_STEPS))

    return rng.choice(nearest[:TARGET_POOL])

# PLANS THE SNAKE ROUTE OVER THE GRID --------------------------------------------------------------------------------------------------------------|
def plan_route(cubes: set, valid: set, home: tuple, rng: random.Random) -> tuple[list, dict]:
    route = [home]
    eaten_at: dict[tuple, int] = {}
    remaining = set(cubes)
    trail = deque([home], maxlen = SNAKE_LENGTH)
    target = None

    if home in remaining:
        remaining.discard(home)
        eaten_at[home] = 0

    while len(route) < MAX_STEPS:
        head = route[-1]

        if not remaining and head == home:
            break

        if remaining:
            if target not in remaining:
                target = pick_target(head, remaining, valid, rng)
        else:
            target = home

        tail = trail[0] if len(trail) == SNAKE_LENGTH else None
        blocked = set(trail) - {head, tail}
        path = shortest_path(head, target, valid, blocked, rng) or shortest_path(head, target, valid, set(), rng)

        if path is None or len(path) < 2:
            if target not in remaining:
                break
            remaining.discard(target)
            target = None
            continue

        step = path[1]
        route.append(step)
        trail.append(step)

        if step in remaining:
            remaining.discard(step)
            eaten_at[step] = len(route) - 1

    return route, eaten_at

# KEEPS ONLY THE TURNING POINTS OF THE ROUTE -------------------------------------------------------------------------------------------------------|
def route_vertices(route: list) -> list:
    vertices = [0]

    for index in range(1, len(route) - 1):
        before = (route[index][0] - route[index - 1][0], route[index][1] - route[index - 1][1])
        after = (route[index + 1][0] - route[index][0], route[index + 1][1] - route[index][1])
        if before != after:
            vertices.append(index)

    if len(route) > 1:
        vertices.append(len(route) - 1)

    return vertices

# FORMATS A TIME AS A KEYFRAME PERCENT -------------------------------------------------------------------------------------------------------------|
def percent(seconds: float, period: float) -> str:
    return f"{seconds / period * 100:.3f}".rstrip("0").rstrip(".") + "%"

# BUILDS CSS FOR CELLS AND SNAKE ANIMATION ---------------------------------------------------------------------------------------------------------|
def build_css(route: list, eaten_at: dict, grid_x: int) -> str:
    steps = len(route) - 1
    tau = min(MAX_STEP_SECONDS, max(MIN_STEP_SECONDS, TARGET_LOOP_SECONDS / max(steps, 1)))
    period = steps * tau + (SNAKE_LENGTH - 1) * tau + HOME_PAUSE_SECONDS
    rules = [
        f"use{{fill:var(--b);animation-duration:{period:.3f}s;animation-iteration-count:infinite;animation-timing-function:linear}}",
        f".s{{animation:mv {period:.3f}s linear infinite}}"
    ]

    for level, color in enumerate(LEVEL_COLORS, 1):
        rules.append(f".l{level}{{--b:{color}}}")

    for index in range(1, SNAKE_LENGTH):
        rules.append(f".s{index}{{animation-delay:{index * tau:.3f}s}}")

    for number, cell in enumerate(sorted(eaten_at)):
        start = eaten_at[cell] * tau
        first = "0%" if start <= 0 else f"0%,{percent(start, period)}"
        rules.append(f".k{number}{{animation-name:k{number}}}")
        rules.append(
            f"@keyframes k{number}{{{first}{{fill:var(--b)}}"
            f"{percent(start + FADE_SECONDS, period)},100%{{fill:{EMPTY_COLOR}}}}}"
        )

    frames = []
    for index in route_vertices(route):
        x = grid_x + route[index][0] * PITCH + CELL // 2
        y = GRID_Y + route[index][1] * PITCH + CELL // 2
        frames.append(f"{percent(index * tau, period)}{{transform:translate({x}px,{y}px)}}")

    x = grid_x + route[-1][0] * PITCH + CELL // 2
    y = GRID_Y + route[-1][1] * PITCH + CELL // 2
    frames.append(f"100%{{transform:translate({x}px,{y}px)}}")
    rules.append("@keyframes mv{" + "".join(frames) + "}")
    rules.append("@media (prefers-reduced-motion:reduce){use,.s{animation:none}}")

    return "".join(rules)

# BUILD THE CONTRIBUTION CELLS ---------------------------------------------------------------------------------------------------------------------|
def build_cells(levels: dict, eaten_at: dict, grid_x: int) -> str:
    order = {cell: number for number, cell in enumerate(sorted(eaten_at))}
    cells = []

    for (column, row), level in sorted(levels.items()):
        if level == 0:
            continue
        classes = f"l{level}" + (f" k{order[(column, row)]}" if (column, row) in order else "")
        cells.append(f'<use href="#c" x="{grid_x + column * PITCH}" y="{GRID_Y + row * PITCH}" class="{classes}"/>')

    return "\n".join(cells)

# COVER GRID POSITIONS THAT HAVE NO DAY ------------------------------------------------------------------------------------------------------------|
def build_missing(levels: dict, columns: int, grid_x: int) -> str:
    missing = []

    for column in range(columns):
        for row in range(ROWS):
            if (column, row) not in levels:
                missing.append(
                    f'<rect x="{grid_x + column * PITCH - 1}" y="{GRID_Y + row * PITCH - 1}" '
                    f'width="{CELL + 2}" height="{CELL + 2}" rx="6" fill="{CARD_BACKGROUND}"/>'
                )

    return "".join(missing)

# BUILD THE MONTH LABELS ---------------------------------------------------------------------------------------------------------------------------|
def build_months(months: list, grid_x: int) -> str:
    labels = []
    previous = None

    for column, month in enumerate(months):
        if month != previous:
            crowded = column == 0 and any(other != month for other in months[1:3])
            if not crowded:
                labels.append(
                    f'<text x="{grid_x + column * PITCH}" y="{MONTHS_Y}" font-size="24" fill="#8493b6">'
                    f'{calendar.month_abbr[month]}</text>'
                )
            previous = month

    return "".join(labels)

# BUILD THE LESS TO MORE LEGEND --------------------------------------------------------------------------------------------------------------------|
def build_legend(grid_right: int) -> str:
    more_x = grid_right - 62
    squares_x = more_x - 10 - 114
    less_x = squares_x - 10 - 52
    colors = [EMPTY_COLOR] + LEVEL_COLORS
    parts = [
        f'<text x="{less_x}" y="{LEGEND_Y}" font-size="24" fill="#8493b6" textLength="52" lengthAdjust="spacingAndGlyphs">Less</text>'
    ]

    for index, color in enumerate(colors):
        parts.append(
            f'<rect x="{squares_x + index * 24}" y="{LEGEND_Y - 18}" width="18" height="18" rx="4" fill="{color}"/>'
        )

    parts.append(
        f'<text x="{more_x}" y="{LEGEND_Y}" font-size="24" fill="#8493b6" textLength="62" lengthAdjust="spacingAndGlyphs">More</text>'
    )

    return "".join(parts)

# BUILD THE SNAKE SEGMENTS -------------------------------------------------------------------------------------------------------------------------|
def build_snake() -> str:
    segments = []

    for index in range(SNAKE_LENGTH - 1, -1, -1):
        size, color = SNAKE_STYLES[index]
        classes = "s" + (f" s{index}" if index else "")
        segments.append(
            f'<rect class="{classes}" x="{-size // 2}" y="{-size // 2}" width="{size}" height="{size}" rx="6" fill="{color}"/>'
        )

    return "".join(segments)

# FILL AND RETURN THE FINAL SVG MARKUP -------------------------------------------------------------------------------------------------------------|
def render(total: int, levels: dict, months: list, route: list, eaten_at: dict) -> str:
    columns = len(months)
    grid_width = columns * PITCH - (PITCH - CELL)
    grid_x = round(CARD_CENTER_X - grid_width / 2)

    return SVG_TEMPLATE.substitute(
        css = build_css(route, eaten_at, grid_x),
        grid_x = grid_x,
        grid_y = GRID_Y,
        grid_width = grid_width,
        stats_y = STATS_Y,
        empty = EMPTY_COLOR,
        background = CARD_BACKGROUND,
        total = f"{total:,}",
        months = build_months(months, grid_x),
        missing = build_missing(levels, columns, grid_x),
        cells = build_cells(levels, eaten_at, grid_x),
        legend = build_legend(grid_x + grid_width),
        snake = build_snake()
    )

# WRITE SVG FILE -----------------------------------------------------------------------------------------------------------------------------------|
def main() -> None:
    token = os.environ["GH_TOKEN"]
    login = os.environ["GITHUB_USER"]
    output = Path(os.environ.get("OUTPUT_PATH", "assets/stats/github-contribution-calendar.svg"))

    data = graphql(token, CALENDAR_QUERY, {"login": login})
    calendar_data = data["user"]["contributionsCollection"]["contributionCalendar"]
    levels, months = parse_calendar(calendar_data["weeks"])

    valid = set(levels)
    cubes = {cell for cell, level in levels.items() if level > 0}
    rng = random.Random(f"{login}-{datetime.now(timezone.utc).date().isoformat()}")
    route, eaten_at = plan_route(cubes, valid, pick_home(valid), rng)

    output.parent.mkdir(parents = True, exist_ok = True)
    output.write_text(render(calendar_data["totalContributions"], levels, months, route, eaten_at), encoding = "utf-8")
    print(f"{login}: contributions = {calendar_data['totalContributions']} cubes = {len(cubes)} steps = {len(route) - 1}")

# MAIN FUNCTION ------------------------------------------------------------------------------------------------------------------------------------|
if __name__ == "__main__":
    main()
