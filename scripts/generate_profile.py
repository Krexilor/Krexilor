# LIBRARIES ----------------------------------------------------------------------------------------------------------------------------------------|
from html import escape
from pathlib import Path

# EDITABLE PROFILE INFO ----------------------------------------------------------------------------------------------------------------------------|
NAME = "Aarav Malik"
ONLINE_NAME = "Krexilor"
DESCRIPTION = [
    "Building efficient software and exploring the fundamentals of C++.",
    "Interested in systems programming, backend development, and clean code.",
    "Known as Krexilor online, learning one concept at a time."
]
TITLES = ["SYSTEMS ENGINEER", "BACKEND DEVELOPER"]
SKILLS = {
    "LANGUAGES": ["C++", "JavaScript"],
    "FRAMEWORKS": ["React", "Vite"],
    "TOOLS": ["Git", "GitHub"]
}

# DESIGN SETTINGS ----------------------------------------------------------------------------------------------------------------------------------|
WIDTH = 900
BACKGROUND_START = "#191C36"
BACKGROUND_END = "#111321"
ACCENT_START = "#6C8CFF"
ACCENT_MIDDLE = "#A78BFA"
ACCENT_END = "#67DDFB"
BORDER_COLOR = "#343957"
TEXT_COLOR = "#E6E9F5"
DESCRIPTION_COLOR = "#C2C7DF"
PILL_BACKGROUND = "#1B1F38"
PILL_WIDTH = 120
PILL_HEIGHT = 34
PILL_GAP = 8
TITLE_GAP = 12
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "profile.svg"

# SVG GENERATION FUNCTIONS -------------------------------------------------------------------------------------------------------------------------|
def esc(value):
    return escape(str(value), quote = True)

def pill(x, y, label, stroke, color):
    cx = x + PILL_WIDTH / 2
    cy = y + PILL_HEIGHT / 2 + 4
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{PILL_WIDTH}" height="{PILL_HEIGHT}" '
        f'rx="7" fill="{PILL_BACKGROUND}" stroke="{stroke}" stroke-opacity=".7"/>'
        f'<text x="{cx:g}" y="{cy:g}" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="10" font-weight="600" '
        f'fill="{color}">{esc(label)}</text>'
    )

def generate_svg():
    lines = []
    for description in DESCRIPTION:
        words = description.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > 88 and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

    desc_y = 115
    desc_gap = 23
    description_svg = []
    for i, line in enumerate(lines):
        safe_line = esc(line)
        if ONLINE_NAME and ONLINE_NAME in line:
            before, after = line.split(ONLINE_NAME, 1)
            safe_line = (
                f'{esc(before)}<tspan fill="{ACCENT_MIDDLE}" font-weight="700">'
                f'{esc(ONLINE_NAME)}</tspan>{esc(after)}'
            )
        description_svg.append(
            f'<text x="450" y="{desc_y + i * desc_gap}" text-anchor="middle">{safe_line}</text>'
        )

    title_y = max(181, desc_y + len(lines) * desc_gap + 8)
    title_colors = [(ACCENT_START, "#8FA8FF"), (ACCENT_MIDDLE, "#BDA8FF"), (ACCENT_END, "#B9EFFB")]
    title_width = len(TITLES) * PILL_WIDTH + max(0, len(TITLES) - 1) * TITLE_GAP
    title_x = (WIDTH - title_width) / 2
    title_svg = []
    for i, title in enumerate(TITLES):
        stroke, color = title_colors[i % len(title_colors)]
        title_svg.append(pill(title_x + i * (PILL_WIDTH + TITLE_GAP), title_y, title, stroke, color))

    divider_y = title_y + PILL_HEIGHT + 18
    heading_y = divider_y + 47
    skill_y = heading_y + 20
    columns = [
        ("LANGUAGES", SKILLS.get("LANGUAGES", []), 170, ACCENT_START, "#C8D2FF"),
        ("FRAMEWORKS", SKILLS.get("FRAMEWORKS", []), 450, ACCENT_MIDDLE, "#D7C9FF"),
        ("TOOLS", SKILLS.get("TOOLS", []), 730, ACCENT_END, "#B9EFFB")
    ]
    skills_svg = []
    max_rows = 1
    for heading, items, center, stroke, color in columns:
        skills_svg.append(
            f'<text x="{center}" y="{heading_y}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="13" font-weight="700" '
            f'letter-spacing="1" fill="{color}">{esc(heading)}</text>'
        )
        max_rows = max(max_rows, (len(items) + 1) // 2)
        for i, item in enumerate(items):
            row, col = divmod(i, 2)
            count_in_row = min(2, len(items) - row * 2)
            row_width = count_in_row * PILL_WIDTH + (count_in_row - 1) * PILL_GAP
            x = center - row_width / 2 + col * (PILL_WIDTH + PILL_GAP)
            y = skill_y + row * (PILL_HEIGHT + 9)
            skills_svg.append(pill(x, y, item, stroke, color))

    height = max(430, int(skill_y + (max_rows - 1) * (PILL_HEIGHT + 9) + PILL_HEIGHT + 30))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}">
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
    <rect width="{WIDTH}" height="{height}" rx="18" fill="url(#bg)"/>
    <rect x="9" y="9" width="{WIDTH - 18}" height="{height - 18}" rx="15" fill="none" stroke="url(#border)" stroke-width="1.4">
        <animate attributeName="opacity" values="0.65;1;0.65" dur="5s" repeatCount="indefinite"/>
    </rect>
    <text x="450" y="65" text-anchor="middle" font-family="Arial, sans-serif" font-size="38" font-weight="700" fill="{TEXT_COLOR}">{esc(NAME)}</text>
    <rect x="405" y="82" width="90" height="3" rx="1.5" fill="url(#accent)" filter="url(#glow)">
        <animate attributeName="opacity" values="0.6;1;0.6" dur="3s" repeatCount="indefinite"/>
    </rect>
    <g font-family="Arial, sans-serif" font-size="14" text-anchor="middle" fill="{DESCRIPTION_COLOR}">
        {"".join(description_svg)}
    </g>
    {"".join(title_svg)}
    <line x1="35" y1="{divider_y}" x2="865" y2="{divider_y}" stroke="{BORDER_COLOR}" stroke-width="1" stroke-linecap="round"/>
    <line x1="310" y1="{divider_y + 20}" x2="310" y2="{height - 29}" stroke="{BORDER_COLOR}" stroke-width="1"/>
    <line x1="590" y1="{divider_y + 20}" x2="590" y2="{height - 29}" stroke="{BORDER_COLOR}" stroke-width="1"/>
    {"".join(skills_svg)}
</svg>
'''

# SCRIPT EXECUTION ---------------------------------------------------------------------------------------------------------------------------------|
if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents = True, exist_ok = True)
    OUTPUT_PATH.write_text(generate_svg(), encoding = "utf-8")
    print(f"Generated {OUTPUT_PATH}")
