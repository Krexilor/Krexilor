# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
import os
import json
import urllib.error
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path
from collections import Counter
from datetime import date, datetime, timedelta, timezone

# EDITABLE GITHUB SETTINGS -------------------------------------------------------------------------------------------------------------------------|
USERNAME = "Krexilor"
TOKEN = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

# EDITABLE DESIGN SETTINGS --------------------------------------------------------------------------------------------------------------------------|
WIDTH = 860
HEIGHT = 440
PANEL_BACKGROUND = "#1D2035"
BACKGROUND_START = "#191C36"
BACKGROUND_END = "#111321"
ACCENT_START = "#6C8CFF"
ACCENT_MIDDLE = "#A78BFA"
ACCENT_END = "#67DDFB"
BORDER_COLOR = "#343957"
TEXT_COLOR = "#E6E9F5"
DESCRIPTION_COLOR = "#C2C7DF"
MUTED_COLOR = "#343D69"
EMPTY_COLOR = "#252A46"
LANGUAGE_COLORS = [
    "#6C8CFF",
    "#A78BFA",
    "#67DDFB",
    "#526080",
    "#7D86A8",
    "#343957"
]

# EDITABLE LAYOUT SETTINGS --------------------------------------------------------------------------------------------------------------------------|
STATS_PANEL = {"x": 20, "y": 20, "width": 400, "height": 180}
STREAK_PANEL = {"x": 440, "y": 20, "width": 400, "height": 180}
LANGUAGES_PANEL = {"x": 220, "y": 220, "width": 420, "height": 200}

GRID_COLUMNS = 21
GRID_ROWS = 4
GRID_CELL_SIZE = 10
GRID_COLUMN_GAP = 4
GRID_ROW_GAP = 5
GRID_X = 495
GRID_Y = 126

LANGUAGE_BAR_X = 244
LANGUAGE_BAR_Y = 278
LANGUAGE_BAR_WIDTH = 372
LANGUAGE_BAR_HEIGHT = 8

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "development-telemetry.svg"

# API REQUEST FUNCTIONS -----------------------------------------------------------------------------------------------------------------------------|
def request_json(url, headers = None):
    request_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Krexilor-Development-Telemetry"
    }

    if TOKEN:
        request_headers["Authorization"] = f"Bearer {TOKEN}"

    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, headers = request_headers)

    try:
        with urllib.request.urlopen(request, timeout = 30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors = "replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to connect to GitHub API: {error}") from error

def graphql(query, variables = None):
    if not TOKEN:
        raise RuntimeError(
            "A GitHub token is required. Configure GH_TOKEN or GITHUB_TOKEN."
        )

    payload = json.dumps({
        "query": query,
        "variables": variables or {}
    }).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data = payload,
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Krexilor-Development-Telemetry"
        },
        method = "POST"
    )

    try:
        with urllib.request.urlopen(request, timeout = 30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors = "replace")
        raise RuntimeError(
            f"GitHub GraphQL API returned HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to connect to GitHub GraphQL API: {error}") from error

    if result.get("errors"):
        messages = "; ".join(
            item.get("message", "Unknown GraphQL error")
            for item in result["errors"]
        )
        raise RuntimeError(f"GitHub GraphQL error: {messages}")

    return result["data"]

# GITHUB DATA FUNCTIONS -----------------------------------------------------------------------------------------------------------------------------|
def get_profile():
    return request_json(f"{API_URL}/users/{urllib.parse.quote(USERNAME)}")

def get_repositories():
    repositories = []
    page = 1

    while True:
        url = (
            f"{API_URL}/users/{urllib.parse.quote(USERNAME)}/repos"
            f"?type=owner&per_page=100&page={page}&sort=updated"
        )
        page_data = request_json(url)

        if not page_data:
            break

        repositories.extend(
            repository for repository in page_data
            if not repository.get("fork")
            and not repository.get("archived")
            and not repository.get("disabled")
        )

        if len(page_data) < 100:
            break

        page += 1

    return repositories

def get_contribution_data():
    today = date.today()
    start_date = today - timedelta(days = 364)

    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $username) {
            contributionsCollection(from: $from, to: $to) {
                totalCommitContributions
                totalIssueContributions
                totalPullRequestContributions
                contributionCalendar {
                    totalContributions
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
            start_date, datetime.min.time(), tzinfo = timezone.utc
        ).isoformat(),
        "to": datetime.combine(
            today, datetime.max.time(), tzinfo = timezone.utc
        ).isoformat()
    })

    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found.")

    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]

    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])

    return {
        "total_contributions": calendar["totalContributions"],
        "commits": collection["totalCommitContributions"],
        "issues": collection["totalIssueContributions"],
        "pull_requests": collection["totalPullRequestContributions"],
        "days": days,
        "start_date": start_date,
        "end_date": today
    }

def get_language_totals(repositories):
    totals = Counter()

    for repository in repositories:
        languages_url = repository.get("languages_url")
        if not languages_url:
            continue

        languages = request_json(languages_url)
        for language, byte_count in languages.items():
            totals[language] += byte_count

    return totals

# STATISTICS CALCULATION FUNCTIONS ---------------------------------------------------------------------------------------------------------------|
def calculate_streaks(days):
    contributions_by_date = {
        day["date"]: day["contributionCount"]
        for day in days
    }

    today = date.today()
    current_streak = 0
    longest_streak = 0
    running_streak = 0

    first_day = min(
        (date.fromisoformat(day) for day in contributions_by_date),
        default = today
    )
    last_day = max(
        (date.fromisoformat(day) for day in contributions_by_date),
        default = today
    )

    day = first_day
    while day <= last_day:
        if contributions_by_date.get(day.isoformat(), 0) > 0:
            running_streak += 1
            longest_streak = max(longest_streak, running_streak)
        else:
            running_streak = 0
        day += timedelta(days = 1)

    streak_day = today
    if contributions_by_date.get(today.isoformat(), 0) == 0:
        streak_day = today - timedelta(days = 1)

    while contributions_by_date.get(streak_day.isoformat(), 0) > 0:
        current_streak += 1
        streak_day -= timedelta(days = 1)

    return current_streak, longest_streak

def calculate_languages(language_totals):
    total_bytes = sum(language_totals.values())

    if total_bytes == 0:
        return []

    sorted_languages = language_totals.most_common()
    top_languages = sorted_languages[:5]
    other_bytes = sum(
        byte_count for _, byte_count in sorted_languages[5:]
    )

    entries = [
        {
            "name": name,
            "bytes": byte_count,
            "percentage": byte_count / total_bytes * 100
        }
        for name, byte_count in top_languages
    ]

    if other_bytes > 0:
        entries.append({
            "name": "Others",
            "bytes": other_bytes,
            "percentage": other_bytes / total_bytes * 100
        })

    return entries

def activity_color(count, maximum):
    if count <= 0:
        return EMPTY_COLOR

    ratio = count / max(maximum, 1)

    if ratio <= 0.25:
        return "#343D69"
    if ratio <= 0.50:
        return "#5269B5"
    if ratio <= 0.75:
        return ACCENT_START
    return ACCENT_END

# SVG HELPER FUNCTIONS --------------------------------------------------------------------------------------------------------------------------------|
def esc(value):
    return escape(str(value), quote = True)


def svg_text(x, y, value, size = 11, color = DESCRIPTION_COLOR,
             anchor = "start", weight = "400"):
    return (
        f'<text x = "{x:g}" y = "{y:g}" text-anchor = "{anchor}" '
        f'font-family = "Arial, sans-serif" font-size = "{size}" '
        f'font-weight = "{weight}" fill = "{color}">{esc(value)}</text>'
    )

def panel_frame(panel, title):
    x = panel["x"]
    y = panel["y"]
    width = panel["width"]
    height = panel["height"]

    return (
        f'<rect x = "{x}" y = "{y}" width = "{width}" height = "{height}" '
        f'rx = "12" fill = "{PANEL_BACKGROUND}" stroke = "url(#border)"/>'
        f'{svg_text(x + 20, y + 30, title, size = 16, color = TEXT_COLOR, weight = "600")}'
        f'<line x1 = "{x + 20}" y1 = "{y + 44}" '
        f'x2 = "{x + width - 20}" y2 = "{y + 44}" '
        f'stroke = "{BORDER_COLOR}"/>'
    )

# GITHUB STATS PANEL --------------------------------------------------------------------------------------------------------------------------------|
def generate_stats_panel(stats):
    panel = STATS_PANEL
    x = panel["x"]
    y = panel["y"]
    width = panel["width"]

    rows = [
        ("Total contributions", stats["total_contributions"]),
        ("Public repositories", stats["public_repositories"]),
        ("Pull requests", stats["pull_requests"]),
        ("Issues opened", stats["issues"])
    ]

    parts = [panel_frame(panel, "GitHub Stats")]

    for index, (label, value) in enumerate(rows):
        row_y = y + 71 + index * 28
        parts.append(svg_text(x + 20, row_y, label, size = 11))
        parts.append(svg_text(
            x + width - 20,
            row_y,
            f"{value:,}",
            size = 11,
            color = ACCENT_END,
            anchor = "end",
            weight = "600"
        ))

    return "".join(parts)

# CONTRIBUTION GRID AND STREAK PANEL ---------------------------------------------------------------------------------------------------------------|
def generate_contribution_grid(days):
    ordered_days = sorted(days, key = lambda item: item["date"])
    recent_days = ordered_days[-(GRID_COLUMNS * GRID_ROWS):]
    recent_days = [
        {"date": "", "contributionCount": 0}
        for _ in range(GRID_COLUMNS * GRID_ROWS - len(recent_days))
    ] + recent_days

    maximum = max(
        (day["contributionCount"] for day in recent_days),
        default = 1
    )

    parts = []

    for index, day in enumerate(recent_days):
        row, column = divmod(index, GRID_COLUMNS)
        x = GRID_X + column * (GRID_CELL_SIZE + GRID_COLUMN_GAP)
        y = GRID_Y + row * (GRID_CELL_SIZE + GRID_ROW_GAP)
        count = day["contributionCount"]
        color = activity_color(count, maximum)

        parts.append(
            f'<rect x = "{x}" y = "{y}" '
            f'width = "{GRID_CELL_SIZE}" height = "{GRID_CELL_SIZE}" '
            f'rx = "2" fill = "{color}">'
            f'<title>{esc(day["date"])}: {count} contributions</title>'
            f'</rect>'
        )

    return "".join(parts)

def generate_streak_panel(stats):
    panel = STREAK_PANEL
    x = panel["x"]
    y = panel["y"]
    width = panel["width"]

    current_streak = stats["current_streak"]
    longest_streak = stats["longest_streak"]
    total_contributions = stats["total_contributions"]

    center_x = x + width / 2
    center_y = y + 100
    radius = 23
    circumference = 2 * 3.141592653589793 * radius
    progress = min(current_streak / max(longest_streak, 1), 1)
    progress_length = circumference * progress

    left_center = x + 75
    right_center = x + width - 75

    parts = [panel_frame(panel, "Streak Stats")]

    parts.append(
        f'<line x1 = "{x + 130}" y1 = "{y + 60}" '
        f'x2 = "{x + 130}" y2 = "{y + 158}" stroke = "{BORDER_COLOR}"/>'
    )
    parts.append(
        f'<line x1 = "{x + width - 130}" y1 = "{y + 60}" '
        f'x2 = "{x + width - 130}" y2 = "{y + 158}" stroke = "{BORDER_COLOR}"/>'
    )

    parts.append(svg_text(
        left_center, y + 91, f"{total_contributions:,}",
        size = 25, color = ACCENT_START, anchor = "middle", weight = "700"
    ))
    parts.append(svg_text(
        left_center, y + 115, "Total Contributions",
        size = 10, anchor = "middle"
    ))
    parts.append(svg_text(
        left_center, y + 137, "Past Year",
        size = 10, color = ACCENT_END, anchor = "middle"
    ))

    parts.append(
        f'<circle cx = "{center_x}" cy = "{center_y}" r = "{radius}" '
        f'fill = "none" stroke = "{MUTED_COLOR}" stroke-width = "5"/>'
    )
    parts.append(
        f'<circle cx = "{center_x}" cy = "{center_y}" r = "{radius}" '
        f'fill = "none" stroke = "{ACCENT_START}" stroke-width = "5" '
        f'stroke-linecap = "round" stroke-dasharray = "{progress_length:.2f} {circumference:.2f}" '
        f'transform = "rotate(-90 {center_x} {center_y})"/>'
    )
    parts.append(
        f'<path d = "M {center_x} {center_y - radius - 13} '
        f'C {center_x - 8} {center_y - radius - 3}, '
        f'{center_x - 6} {center_y - radius + 3}, '
        f'{center_x} {center_y - radius + 6} '
        f'C {center_x + 6} {center_y - radius + 3}, '
        f'{center_x + 8} {center_y - radius - 3}, '
        f'{center_x} {center_y - radius - 13} Z" fill = "{ACCENT_START}"/>'
    )
    parts.append(svg_text(
        center_x, center_y + 7, current_streak,
        size = 22, color = ACCENT_MIDDLE, anchor = "middle", weight = "700"
    ))
    parts.append(svg_text(
        center_x, y + 153, "Current Streak",
        size = 11, color = ACCENT_MIDDLE, anchor = "middle", weight = "600"
    ))

    parts.append(svg_text(
        right_center, y + 91, longest_streak,
        size = 25, color = ACCENT_START, anchor = "middle", weight = "700"
    ))
    parts.append(svg_text(
        right_center, y + 115, "Longest Streak",
        size = 10, anchor = "middle"
    ))
    parts.append(svg_text(
        right_center, y + 137, "Days",
        size = 10, color = ACCENT_END, anchor = "middle"
    ))

    return "".join(parts)

# MOST USED LANGUAGES PANEL --------------------------------------------------------------------------------------------------------------------------|
def generate_language_bar(languages):
    if not languages:
        return (
            f'<rect x = "{LANGUAGE_BAR_X}" y = "{LANGUAGE_BAR_Y}" '
            f'width = "{LANGUAGE_BAR_WIDTH}" height = "{LANGUAGE_BAR_HEIGHT}" '
            f'rx = "4" fill = "{EMPTY_COLOR}"/>'
        )

    total_bytes = sum(language["bytes"] for language in languages)
    parts = [
        f'<defs><clipPath id = "languageBarClip">'
        f'<rect x = "{LANGUAGE_BAR_X}" y = "{LANGUAGE_BAR_Y}" '
        f'width = "{LANGUAGE_BAR_WIDTH}" height = "{LANGUAGE_BAR_HEIGHT}" '
        f'rx = "4"/></clipPath></defs>',
        '<g clip-path = "url(#languageBarClip)">'
    ]

    cursor_x = LANGUAGE_BAR_X

    for index, language in enumerate(languages):
        if index == len(languages) - 1:
            segment_width = LANGUAGE_BAR_X + LANGUAGE_BAR_WIDTH - cursor_x
        else:
            segment_width = LANGUAGE_BAR_WIDTH * language["bytes"] / total_bytes

        parts.append(
            f'<rect x = "{cursor_x:.3f}" y = "{LANGUAGE_BAR_Y}" '
            f'width = "{segment_width:.3f}" height = "{LANGUAGE_BAR_HEIGHT}" '
            f'fill = "{LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)]}"/>'
        )
        cursor_x += segment_width

    parts.append("</g>")
    return "".join(parts)

def generate_language_legend(languages):
    parts = []

    entries = languages[:6]
    if not entries:
        return svg_text(
            430, 330, "No language data available",
            size = 11, anchor = "middle"
        )

    for index, language in enumerate(entries):
        row, column = divmod(index, 2)
        center_x = 250 if column == 0 else 440
        row_y = 316 + row * 32
        color = LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)]

        parts.append(
            f'<circle cx = "{center_x}" cy = "{row_y - 4}" '
            f'r = "4" fill = "{color}"/>'
        )

        label = language["name"]
        if len(label) > 16:
            label = label[:15] + "…"

        parts.append(svg_text(
            center_x + 12, row_y, label, size = 11
        ))

        parts.append(svg_text(
            405 if column == 0 else 605,
            row_y,
            f'{language["percentage"]:.0f}%',
            size = 11,
            color = TEXT_COLOR,
            anchor = "end"
        ))

    return "".join(parts)

def generate_languages_panel(languages):
    panel = LANGUAGES_PANEL

    parts = [panel_frame(panel, "Most Used Languages")]

    parts.append(generate_language_bar(languages))
    parts.append(generate_language_legend(languages))

    return "".join(parts)

# SVG GENERATION FUNCTION ----------------------------------------------------------------------------------------------------------------------------|
def generate_svg(stats, languages):
    return f'''<svg xmlns = "http://www.w3.org/2000/svg" width = "{WIDTH}" height = "{HEIGHT}" viewBox = "0 0 {WIDTH} {HEIGHT}">
    <defs>
        <linearGradient id = "background" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "100%">
            <stop offset = "0%" stop-color = "{BACKGROUND_START}"/>
            <stop offset = "100%" stop-color = "{BACKGROUND_END}"/>
        </linearGradient>
        <linearGradient id = "border" x1 = "0%" y1 = "0%" x2 = "100%" y2 = "100%">
            <stop offset = "0%" stop-color = "{ACCENT_START}"/>
            <stop offset = "100%" stop-color = "{BORDER_COLOR}"/>
        </linearGradient>
    </defs>
    <rect width = "{WIDTH}" height = "{HEIGHT}" rx = "22" fill = "url(#background)"/>
    <rect x = "1" y = "1" width = "{WIDTH - 2}" height = "{HEIGHT - 2}" rx = "21" fill = "none" stroke = "{BORDER_COLOR}"/>
    {generate_stats_panel(stats)}
    {generate_streak_panel(stats)}
    {generate_languages_panel(languages)}
</svg>
'''

# SCRIPT EXECUTION ----------------------------------------------------------------------------------------------------------------------------------|
def main():
    if not TOKEN:
        raise RuntimeError(
            "Missing GitHub token. Add a GH_TOKEN repository secret."
        )

    print("Fetching GitHub profile...")
    profile = get_profile()

    print("Fetching repositories...")
    repositories = get_repositories()

    public_repositories = sum(
        1 for repository in repositories
        if not repository.get("private", False)
    )

    print("Fetching contribution activity...")
    contributions = get_contribution_data()
    current_streak, longest_streak = calculate_streaks(
        contributions["days"]
    )

    stats = {
        "total_contributions": contributions["total_contributions"],
        "public_repositories": public_repositories,
        "pull_requests": contributions["pull_requests"],
        "issues": contributions["issues"],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "days": contributions["days"]
    }

    print("Calculating language usage...")
    language_totals = get_language_totals(repositories)
    languages = calculate_languages(language_totals)

    print(f"Generating telemetry for {profile['login']}...")
    svg = generate_svg(stats, languages)

    OUTPUT_PATH.parent.mkdir(parents = True, exist_ok = True)
    OUTPUT_PATH.write_text(svg, encoding = "utf-8")

    print(f"Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
