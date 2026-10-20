# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import json
import os
import random
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

# EDITABLE GITHUB SETTINGS -------------------------------------------------------------------------------------------------------------------------|
USERNAME = "Krexilor"
TITLE = "CONTRIBUTION CALENDAR"
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

# DESIGN SETTINGS ----------------------------------------------------------------------------------------------------------------------------------|
WIDTH = 900
HEIGHT = 260
BACKGROUND_START = "#191C36"
BACKGROUND_END = "#111321"
ACCENT_START = "#6C8CFF"
ACCENT_MIDDLE = "#A78BFA"
ACCENT_END = "#67DDFB"
BORDER_COLOR = "#343957"
TEXT_COLOR = "#E6E9F5"
LEVEL_COLORS = [
    "#252A46",
    "#343D69",
    "#5269B5",
    "#6C8CFF",
    "#67DDFB"
]
SNAKE_BODY_START = "#6C8CFF"
SNAKE_BODY_END = "#A78BFA"
SNAKE_HEAD_START = "#67DDFB"
SNAKE_HEAD_END = "#6C8CFF"

# GRID SETTINGS ------------------------------------------------------------------------------------------------------------------------------------|
GRID_COLUMNS = 53
GRID_ROWS = 7
CELL_SIZE = 13
CELL_GAP_X = 3
CELL_GAP_Y = 4
GRID_CELL_STEP_X = CELL_SIZE + CELL_GAP_X
GRID_CELL_STEP_Y = CELL_SIZE + CELL_GAP_Y
GRID_WIDTH = GRID_COLUMNS * CELL_SIZE + (GRID_COLUMNS - 1) * CELL_GAP_X
GRID_X = (WIDTH - GRID_WIDTH) / 2
GRID_Y = 104

# SNAKE SETTINGS -----------------------------------------------------------------------------------------------------------------------------------|
SNAKE_LENGTH = 5
HEAD_SIZE = CELL_SIZE + 3
SNAKE_STEP_SECONDS = 0.2
WANDER_CHANCE = 0.15
STRAIGHT_CHANCE = 0.6
FREE_STEPS = 30
MAX_STEPS = 3000
EAT_FADE = 0.25
RESET_PAUSE = 0.4
RESET_FADE = 0.8
DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "contribution-snake.svg"

# GITHUB API FUNCTIONS -----------------------------------------------------------------------------------------------------------------------------|
def graphql(query, variables):
    if not TOKEN:
        raise RuntimeError(
            "Missing GitHub token. Configure the GH_TOKEN repository secret."
        )

    payload = json.dumps({
        "query": query,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data = payload,
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Krexilor-Contribution-Snake"
        },
        method = "POST"
    )

    try:
        with urllib.request.urlopen(request, timeout = 30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors = "replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Unable to connect to GitHub API: {error}"
        ) from error

    if result.get("errors"):
        messages = "; ".join(
            item.get("message", "Unknown GraphQL error")
            for item in result["errors"]
        )
        raise RuntimeError(f"GitHub GraphQL error: {messages}")

    return result["data"]

def get_contribution_weeks():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days = 364)

    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
                contributionCalendar {
                    weeks {
                        contributionDays {
                            weekday
                            contributionCount
                        }
                    }
                }
            }
        }
    }
    """

    data = graphql(query, {
        "username": USERNAME,
        "from": start.isoformat(),
        "to": now.isoformat()
    })

    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found.")

    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    columns = []

    for week in weeks[-GRID_COLUMNS:]:
        column = [None] * GRID_ROWS

        for day in week["contributionDays"]:
            column[day["weekday"]] = day["contributionCount"]

        columns.append(column)

    return columns

# SNAKE ROUTE FUNCTIONS ----------------------------------------------------------------------------------------------------------------------------|
def in_bounds(cell):
    return 0 <= cell[0] < GRID_COLUMNS and 0 <= cell[1] < GRID_ROWS

def move(cell, direction):
    return (cell[0] + direction[0], cell[1] + direction[1])

def step_options(route):
    head = route[-1]

    for blocked in (set(route[-SNAKE_LENGTH:]), set(route[-2:-1]), set()):
        options = [
            direction for direction in DIRECTIONS
            if in_bounds(move(head, direction)) and move(head, direction) not in blocked
        ]

        if options:
            return options

def choose_direction(route, direction, goal):
    head = route[-1]
    options = step_options(route)

    if goal and random.random() > WANDER_CHANCE:
        def distance(option):
            cell = move(head, option)
            return abs(cell[0] - goal[0]) + abs(cell[1] - goal[1])

        best = min(distance(option) for option in options)
        options = [option for option in options if distance(option) == best]

    if direction in options and random.random() < STRAIGHT_CHANCE:
        return direction

    return random.choice(options)

def path_back(start, goal):
    queue = deque([start])
    previous = {start: None}

    while queue:
        current = queue.popleft()

        if current == goal:
            break

        for direction in DIRECTIONS:
            target = move(current, direction)

            if in_bounds(target) and target not in previous:
                previous[target] = current
                queue.append(target)

    path = []
    current = goal

    while current is not None:
        path.append(current)
        current = previous[current]

    return path[::-1]

def build_route(columns):
    cells = [(c, r) for c in range(GRID_COLUMNS) for r in range(GRID_ROWS)]
    targets = {
        (c, r) for c, column in enumerate(columns)
        for r, count in enumerate(column) if count
    }

    start = random.choice([cell for cell in cells if cell not in targets] or cells)
    route = [start]
    direction = random.choice(DIRECTIONS)
    remaining = set(targets)
    eaten = {}

    if start in remaining:
        remaining.remove(start)
        eaten[start] = 0

    while remaining and len(route) < MAX_STEPS:
        head = route[-1]
        goal = min(remaining, key = lambda t: abs(t[0] - head[0]) + abs(t[1] - head[1]))
        direction = choose_direction(route, direction, goal)
        route.append(move(head, direction))

        if route[-1] in remaining:
            remaining.remove(route[-1])
            eaten[route[-1]] = len(route) - 1

    reset_step = len(route) - 1

    for _ in range(FREE_STEPS):
        direction = choose_direction(route, direction, None)
        route.append(move(route[-1], direction))

    route += path_back(route[-1], route[0])[1:]

    return route, eaten, reset_step

# SVG GENERATION FUNCTIONS -------------------------------------------------------------------------------------------------------------------------|
def esc(value):
    return escape(str(value), quote = True)

def contribution_level(count, maximum):
    if count <= 0:
        return 0

    if maximum <= 1:
        return 4

    ratio = count / maximum

    if ratio <= 0.25:
        return 1
    if ratio <= 0.50:
        return 2
    if ratio <= 0.75:
        return 3

    return 4

def cell_position(column, row):
    return (
        GRID_X + column * GRID_CELL_STEP_X,
        GRID_Y + row * GRID_CELL_STEP_Y
    )

def eat_animation(eaten_step, duration, reset_time):
    start = max(0, eaten_step * SNAKE_STEP_SECONDS - SNAKE_STEP_SECONDS / 2)
    times = [0, start, start + EAT_FADE, reset_time, reset_time + RESET_FADE, duration]
    key_times = ";".join(f"{time / duration:.4f}" for time in times)

    return (
        f'<animate attributeName="opacity" values="1;1;0;0;1;1" '
        f'keyTimes="{key_times}" dur="{duration:.2f}s" repeatCount="indefinite"/>'
    )

def generate_grid_svg(columns, eaten, duration, reset_time):
    maximum = max(
        (count for column in columns for count in column if count is not None),
        default = 0
    )
    parts = []

    for column_index, column in enumerate(columns):
        for row_index, count in enumerate(column):
            if count is None:
                continue

            x, y = cell_position(column_index, row_index)
            color = LEVEL_COLORS[contribution_level(count, maximum)]
            cell = (column_index, row_index)
            animation = ""

            if count > 0 and cell in eaten:
                animation = eat_animation(eaten[cell], duration, reset_time)

            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
                f'rx="3" fill="{color}">{animation}</rect>'
            )

    return "".join(parts)

def generate_snake_svg(route, duration):
    def segment(index, size, fill, extra = ""):
        cycle = route[:-1]
        shifted = cycle[-index:] + cycle[:-index] if index else cycle

        values = ";".join(
            "{:.2f},{:.2f}".format(*cell_position(column, row))
            for column, row in shifted + shifted[:1]
        )

        return (
            f'<rect x="{offset:g}" y="{offset:g}" width="{size}" height="{size}" '
            f'rx="3" fill="{fill}"{extra}>'
            f'<animateMotion dur="{duration:.2f}s" '
            f'repeatCount="indefinite" calcMode="linear" values="{values}"/>'
            f'</rect>'
        )

    parts = []

    for index in range(SNAKE_LENGTH - 1, 0, -1):
        color = SNAKE_BODY_START if index % 2 == 0 else SNAKE_BODY_END
        parts.append(segment(index, CELL_SIZE, color))

    parts.append(
        segment(0, HEAD_SIZE, SNAKE_HEAD_START, f' stroke="{SNAKE_HEAD_END}" stroke-width="1.5"')
    )

    return "".join(parts)

def generate_svg(columns):
    route, eaten, reset_step = build_route(columns)
    duration = (len(route) - 1) * SNAKE_STEP_SECONDS
    reset_time = reset_step * SNAKE_STEP_SECONDS + RESET_PAUSE
    grid_svg = generate_grid_svg(columns, eaten, duration, reset_time)
    snake_svg = generate_snake_svg(route, duration)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
    <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="{BACKGROUND_START}"/>
            <stop offset="100%" stop-color="{BACKGROUND_END}"/>
        </linearGradient>
        <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="{ACCENT_START}"/>
            <stop offset="50%" stop-color="{ACCENT_MIDDLE}"/>
            <stop offset="100%" stop-color="{ACCENT_END}"/>
        </linearGradient>
        <linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="{ACCENT_START}"/>
            <stop offset="50%" stop-color="{BORDER_COLOR}"/>
            <stop offset="100%" stop-color="{ACCENT_MIDDLE}"/>
        </linearGradient>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
    </defs>
    <rect width="{WIDTH}" height="{HEIGHT}" rx="18" fill="url(#bg)"/>
    <rect x="9" y="9" width="{WIDTH - 18}" height="{HEIGHT - 18}" rx="15" fill="none" stroke="url(#border)" stroke-width="1.4">
        <animate attributeName="opacity" values="0.65;1;0.65" dur="5s" repeatCount="indefinite"/>
    </rect>
    <text x="450" y="58" text-anchor="middle" font-family="Arial, sans-serif" font-size="26" font-weight="700" letter-spacing="2" fill="{TEXT_COLOR}">{esc(TITLE)}</text>
    <rect x="405" y="72" width="90" height="3" rx="1.5" fill="url(#accent)" filter="url(#glow)">
        <animate attributeName="opacity" values="0.6;1;0.6" dur="3s" repeatCount="indefinite"/>
    </rect>
    {grid_svg}
    {snake_svg}
</svg>
'''

# SCRIPT EXECUTION ---------------------------------------------------------------------------------------------------------------------------------|
def main():
    print(f"Fetching contribution data for {USERNAME}...")
    columns = get_contribution_weeks()

    if len(columns) != GRID_COLUMNS:
        raise RuntimeError(
            f"Expected {GRID_COLUMNS} weeks, GitHub returned {len(columns)}."
        )

    print("Generating contribution snake SVG...")
    svg = generate_svg(columns)

    OUTPUT_PATH.parent.mkdir(parents = True, exist_ok = True)
    OUTPUT_PATH.write_text(svg, encoding = "utf-8")

    print(f"Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
