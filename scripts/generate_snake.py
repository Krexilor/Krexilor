# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import json
import os
import random
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

# EDITABLE GITHUB SETTINGS -------------------------------------------------------------------------------------------------------------------------|
USERNAME = "Krexilor"
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
GRAPHQL_URL = "https://api.github.com/graphql"

# DESIGN SETTINGS ----------------------------------------------------------------------------------------------------------------------------------|
WIDTH = 900
HEIGHT = 260
BACKGROUND_START = "#191C36"
BACKGROUND_END = "#111321"
BORDER_COLOR = "#343957"
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
GRID_HEIGHT = GRID_ROWS * CELL_SIZE + (GRID_ROWS - 1) * CELL_GAP_Y
GRID_X = (WIDTH - GRID_WIDTH) / 2
GRID_Y = (HEIGHT - GRID_HEIGHT) / 2

# SNAKE SETTINGS -----------------------------------------------------------------------------------------------------------------------------------|
SNAKE_LENGTH = 5
SNAKE_WALK_STEPS = 160
SNAKE_STEP_SECONDS = 0.25
SNAKE_STRAIGHT_CHANCE = 0.6
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

# CONTRIBUTION GRID FUNCTIONS ----------------------------------------------------------------------------------------------------------------------|
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

def generate_grid_svg(columns):
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

            parts.append(
                f'<rect x = "{x:.2f}" y = "{y:.2f}" '
                f'width = "{CELL_SIZE}" height = "{CELL_SIZE}" '
                f'rx = "3" fill = "{color}"/>'
            )

    return "".join(parts)

# SNAKE ROUTE FUNCTIONS ----------------------------------------------------------------------------------------------------------------------------|
def in_bounds(cell):
    return 0 <= cell[0] < GRID_COLUMNS and 0 <= cell[1] < GRID_ROWS

def random_walk():
    head = (random.randrange(GRID_COLUMNS), random.randrange(GRID_ROWS))
    direction = random.choice(DIRECTIONS)
    route = [head]

    while len(route) < SNAKE_WALK_STEPS:
        body = set(route[-SNAKE_LENGTH:])
        options = []

        for option in DIRECTIONS:
            target = (head[0] + option[0], head[1] + option[1])

            if in_bounds(target) and target not in body:
                options.append(option)

        if not options:
            break

        if direction in options and random.random() < SNAKE_STRAIGHT_CHANCE:
            pass
        else:
            direction = random.choice(options)

        head = (head[0] + direction[0], head[1] + direction[1])
        route.append(head)

    return route

def path_back(start, goal):
    queue = deque([start])
    previous = {start: None}

    while queue:
        current = queue.popleft()

        if current == goal:
            break

        for direction in DIRECTIONS:
            target = (current[0] + direction[0], current[1] + direction[1])

            if in_bounds(target) and target not in previous:
                previous[target] = current
                queue.append(target)

    path = []
    current = goal

    while current is not None:
        path.append(current)
        current = previous[current]

    return path[::-1]

def snake_route():
    walk = random_walk()
    return_path = path_back(walk[-1], walk[0])

    return walk + return_path[1:-1]

# SNAKE SVG FUNCTIONS ------------------------------------------------------------------------------------------------------------------------------|
def generate_snake_svg():
    route = snake_route()
    duration = len(route) * SNAKE_STEP_SECONDS
    values = ";".join(
        "{:.2f},{:.2f}".format(*cell_position(column, row))
        for column, row in route
    )

    def segment(index, fill, extra = ""):
        begin = -index * SNAKE_STEP_SECONDS

        return (
            f'<rect width = "{CELL_SIZE}" height = "{CELL_SIZE}" '
            f'rx = "3" fill = "{fill}" {extra}>'
            f'<animateMotion dur = "{duration:.2f}s" begin = "{begin:.2f}s" '
            f'repeatCount = "indefinite" calcMode = "discrete" '
            f'values = "{values}"/>'
            f'</rect>'
        )

    parts = []

    for index in range(SNAKE_LENGTH - 1, 0, -1):
        color = SNAKE_BODY_START if index % 2 == 0 else SNAKE_BODY_END
        parts.append(segment(index, color))

    parts.append(
        segment(
            0,
            SNAKE_HEAD_START,
            f'stroke = "{SNAKE_HEAD_END}" stroke-width = "1.5"'
        )
    )

    return "".join(parts)

# SVG GENERATION FUNCTIONS -------------------------------------------------------------------------------------------------------------------------|
def generate_svg(columns):
    return f'''<svg xmlns = "http://www.w3.org/2000/svg" width = "{WIDTH}" height = "{HEIGHT}" viewBox = "0 0 {WIDTH} {HEIGHT}">
    <defs>
        <linearGradient id = "background" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "100%">
            <stop offset = "0%" stop-color = "{BACKGROUND_START}"/>
            <stop offset = "100%" stop-color = "{BACKGROUND_END}"/>
        </linearGradient>
        <filter id = "snakeGlow" x = "-50%" y = "-50%" width = "200%" height = "200%">
            <feGaussianBlur stdDeviation = "2" result = "blur"/>
            <feMerge>
                <feMergeNode in = "blur"/>
                <feMergeNode in = "SourceGraphic"/>
            </feMerge>
        </filter>
    </defs>
    <rect width = "{WIDTH}" height = "{HEIGHT}" rx = "20" fill = "url(#background)"/>
    <rect x = "1" y = "1" width = "{WIDTH - 2}" height = "{HEIGHT - 2}" rx = "19" fill = "none" stroke = "{BORDER_COLOR}"/>
    {generate_grid_svg(columns)}
    <g filter = "url(#snakeGlow)">
        {generate_snake_svg()}
    </g>
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
