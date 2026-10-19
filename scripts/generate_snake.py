
# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
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
EMPTY_COLOR = "#252A46"
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

# GRID SETTINGS -------------------------------------------------------------------------------------------------------------------------------------|
GRID_COLUMNS = 52
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

SNAKE_LENGTH = 5
SNAKE_DURATION = 42
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "contribution-snake.svg"

# GITHUB API FUNCTIONS ------------------------------------------------------------------------------------------------------------------------------|
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

def get_contributions():
    today = date.today()
    start_date = today - timedelta(days = 363)

    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
                contributionCalendar {
                    weeks {
                        contributionDays {
                            date
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
        "from": datetime.combine(
            start_date,
            datetime.min.time(),
            tzinfo = timezone.utc
        ).isoformat(),
        "to": datetime.combine(
            today,
            datetime.max.time(),
            tzinfo = timezone.utc
        ).isoformat()
    })

    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found.")

    weeks = (
        user["contributionsCollection"]["contributionCalendar"]["weeks"]
    )

    contributions = {}

    for week in weeks:
        for day in week["contributionDays"]:
            contributions[day["date"]] = day["contributionCount"]

    return contributions

# CONTRIBUTION GRID FUNCTIONS -----------------------------------------------------------------------------------------------------------------------|
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

def build_grid(contributions):
    today = date.today()
    start_date = today - timedelta(days = 363)
    start_date -= timedelta(days = (start_date.weekday() + 1) % 7)

    maximum = max(contributions.values(), default = 0)
    grid = []

    for column in range(GRID_COLUMNS):
        week = []

        for row in range(GRID_ROWS):
            current_date = start_date + timedelta(
                days = column * 7 + row
            )

            count = contributions.get(current_date.isoformat(), 0)
            level = contribution_level(count, maximum)

            week.append({
                "date": current_date,
                "count": count,
                "level": level
            })

        grid.append(week)

    return grid

def generate_grid_svg(grid):
    parts = []

    for column, week in enumerate(grid):
        x = GRID_X + column * GRID_CELL_STEP_X

        for row, cell in enumerate(week):
            y = GRID_Y + (GRID_ROWS - 1 - row) * GRID_CELL_STEP_Y
            color = LEVEL_COLORS[cell["level"]]

            parts.append(
                f'<rect x = "{x:.2f}" y = "{y:.2f}" '
                f'width = "{CELL_SIZE}" height = "{CELL_SIZE}" '
                f'rx = "3" fill = "{color}"/>'
            )

    return "".join(parts)

# SNAKE ANIMATION FUNCTIONS -------------------------------------------------------------------------------------------------------------------------|
def snake_path():
    points = []

    for column in range(GRID_COLUMNS):
        x = GRID_X + column * GRID_CELL_STEP_X + CELL_SIZE / 2

        if column % 2 == 0:
            rows = range(GRID_ROWS - 1, -1, -1)
        else:
            rows = range(GRID_ROWS)

        for row in rows:
            y = GRID_Y + row * GRID_CELL_STEP_Y + CELL_SIZE / 2
            points.append((x, y))

    path = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

    for x, y in points[1:]:
        path += f" L {x:.2f} {y:.2f}"

    path += f" L {points[0][0]:.2f} {points[0][1]:.2f}"

    return path

def generate_snake_svg():
    path = escape(snake_path(), quote = True)
    parts = [
        f'<path id = "snakeRoute" d = "{path}" fill = "none"/>'
    ]

    for index in range(SNAKE_LENGTH - 1, -1, -1):
        color = SNAKE_BODY_START if index % 2 == 0 else SNAKE_BODY_END
        begin = -(index * SNAKE_DURATION / (GRID_COLUMNS * GRID_ROWS))

        parts.append(
            f'<rect width = "{CELL_SIZE}" height = "{CELL_SIZE}" '
            f'rx = "3" fill = "{color}" opacity = ".98">'
            f'<animateMotion dur = "{SNAKE_DURATION}s" '
            f'begin = "{begin:.3f}s" repeatCount = "indefinite" '
            f'rotate = "0" calcMode = "discrete">'
            f'<mpath href = "#snakeRoute"/>'
            f'</animateMotion>'
            f'</rect>'
        )

    parts.append(
        f'<rect width = "{CELL_SIZE}" height = "{CELL_SIZE}" '
        f'rx = "3" fill = "{SNAKE_HEAD_START}" '
        f'stroke = "{SNAKE_HEAD_END}" stroke-width = "1.5">'
        f'<animateMotion dur = "{SNAKE_DURATION}s" '
        f'repeatCount = "indefinite" rotate = "0" calcMode = "discrete">'
        f'<mpath href = "#snakeRoute"/>'
        f'</animateMotion>'
        f'</rect>'
    )

    return "".join(parts)

# SVG GENERATION FUNCTIONS ---------------------------------------------------------------------------------------------------------------------------|
def generate_svg(grid):
    return f'''<svg xmlns = "http://www.w3.org/2000/svg" xmlns:xlink = "http://www.w3.org/1999/xlink" width = "{WIDTH}" height = "{HEIGHT}" viewBox = "0 0 {WIDTH} {HEIGHT}">
    <defs>
        <linearGradient id = "background" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "100%">
            <stop offset = "0%" stop-color = "{BACKGROUND_START}"/>
            <stop offset = "100%" stop-color = "{BACKGROUND_END}"/>
        </linearGradient>
        <linearGradient id = "snakeBody" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "0%">
            <stop offset = "0%" stop-color = "{SNAKE_BODY_START}"/>
            <stop offset = "100%" stop-color = "{SNAKE_BODY_END}"/>
        </linearGradient>
        <linearGradient id = "snakeHead" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "100%">
            <stop offset = "0%" stop-color = "{SNAKE_HEAD_START}"/>
            <stop offset = "100%" stop-color = "{SNAKE_HEAD_END}"/>
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
    {generate_grid_svg(grid)}
    <g filter = "url(#snakeGlow)">
        {generate_snake_svg()}
    </g>
</svg>
'''

# SCRIPT EXECUTION ----------------------------------------------------------------------------------------------------------------------------------|
def main():
    print(f"Fetching contribution data for {USERNAME}...")
    contributions = get_contributions()

    print("Building vertical contribution grid...")
    grid = build_grid(contributions)

    print("Generating contribution snake SVG...")
    svg = generate_svg(grid)

    OUTPUT_PATH.parent.mkdir(parents = True, exist_ok = True)
    OUTPUT_PATH.write_text(svg, encoding = "utf-8")

    print(f"Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
