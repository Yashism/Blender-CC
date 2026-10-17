"""Regenerate the calendar deliverables from calendar_data.py.

  python3 content-plan/build_calendar.py

Writes, next to this file:
  03_VIDEO_CALENDAR.md   the full 52-week calendar with per-episode briefs
  calendar.csv           one row per week, for Sheets/Excel/Notion import
  rams_video_plan.html   the shareable one-page plan (from page_template.html)
"""
import csv
import datetime as dt
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calendar_data as C  # noqa: E402


def dated_weeks():
    start = dt.date.fromisoformat(C.START)
    out = []
    for e in C.WEEKS:
        d = start + dt.timedelta(weeks=e["w"] - 1)
        season = next(s for s in C.SEASONS if s[0] <= e["w"] <= s[1])
        out.append(dict(e, date=d.isoformat(), date_label=d.strftime("%a %d %b %Y"),
                        format=C.FORMATS[e["fmt"]], season=season[2]))
    return out


def check(weeks):
    assert [e["w"] for e in weeks] == list(range(1, 53)), "weeks must be 1..52 in order"
    for e in weeks:
        assert e["fmt"] in C.FORMATS, e["w"]
        assert e["beats"] and e["hook"] and e["cta"], e["w"]


def write_md(weeks, path):
    mix = Counter(e["format"] for e in weeks)
    lines = [
        "# RAMS Rack Inspection: 52-Week Blender Video Calendar",
        "",
        "One video a week, published **Tuesdays**, from **Tue 3 Nov 2026** to **Tue 26 Oct 2027**.",
        "Generated from `calendar_data.py` by `build_calendar.py`; edit the data, not this file.",
        "",
        "Format mix: " + ", ".join(f"{k} x{v}" for k, v in mix.most_common()) + ".",
        "",
        "## At a glance",
        "",
        "| Wk | Date | Format | Title | Stage | Trigger |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in weeks:
        lines.append(f"| {e['w']} | {e['date']} | {e['format']} | {e['title']} | {e['stage']} | {e['trigger']} |")
    current = None
    for e in weeks:
        if e["season"] != current:
            current = e["season"]
            blurb = next(s[3] for s in C.SEASONS if s[2] == current)
            lines += ["", f"## {current}", "", f"_{blurb}_"]
        lines += [
            "",
            f"### Week {e['w']}: {e['title']}",
            "",
            f"**{e['date_label']}** · {e['format']} · {e['stage']} · {e['runtime']}",
            "",
            f"- **Audience:** {e['audience']}",
            f"- **Why this week:** {e['trigger']}",
            f"- **Hook (first 2 s):** {e['hook']}",
            "- **Beats:**",
        ]
        lines += [f"  {i}. {b}" for i, b in enumerate(e["beats"], 1)]
        lines += [
            f"- **Signature Blender shot:** {e['shot']}",
            f"- **CTA:** {e['cta']}",
        ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_csv(weeks, path):
    cols = ["w", "date", "season", "format", "stage", "title", "audience", "trigger", "hook",
            "beats", "shot", "runtime", "cta"]
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["week" if c == "w" else c for c in cols])
        for e in weeks:
            wr.writerow([" | ".join(e[c]) if c == "beats" else e[c] for c in cols])


def write_html(weeks, path):
    tpl = os.path.join(HERE, "page_template.html")
    if not os.path.exists(tpl):
        return False
    data = dict(weeks=weeks, formats=C.FORMATS,
                seasons=[dict(a=a, b=b, name=n, blurb=t) for a, b, n, t in C.SEASONS])
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    with open(tpl) as f:
        html = f.read().replace("/*__DATA__*/null", blob)
    with open(path, "w") as f:
        f.write(html)
    return True


if __name__ == "__main__":
    weeks = dated_weeks()
    check(weeks)
    write_md(weeks, os.path.join(HERE, "03_VIDEO_CALENDAR.md"))
    write_csv(weeks, os.path.join(HERE, "calendar.csv"))
    html = write_html(weeks, os.path.join(HERE, "rams_video_plan.html"))
    print(f"{len(weeks)} weeks, {weeks[0]['date']} to {weeks[-1]['date']}"
          + ("; html written" if html else "; no page_template.html, html skipped"))
