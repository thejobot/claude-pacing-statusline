#!/usr/bin/env python3
"""Claude Code status line.

Line 1: Opus 4.8 (1M context) [high]  [bar] 5%  52k / 1000k tokens
Line 2: 5h  fill+time-cursor bar  33%  ↻ 47m   →39%
Line 3: 7d  fill+time-cursor bar  58%  ↻ Sat 5pm  →60%

The bar fill = % of the plan limit used. The bright cursor (┃) marks how far
through the reset window the *clock* is. Fill left of the cursor = under-pacing
(headroom); fill past the cursor = burning faster than the clock. →N% projects
usage at window close at the current burn rate.
"""
import sys, json, time, datetime

DIM, RESET, BOLD, WHITE = "\033[2m", "\033[0m", "\033[1m", "\033[97m"
HOUR = 3600
FIVE_HOUR = 5 * HOUR
SEVEN_DAY = 7 * 24 * HOUR


def grad(p):
    """24-bit green→yellow→red gradient for a 0..100 percentage."""
    p = max(0.0, min(100.0, p))
    if p < 50:
        t = p / 50
        r, g, b = int(60 + 170 * t), 200, int(90 - 50 * t)
    else:
        t = (p - 50) / 50
        r, g, b = 230, int(200 - 140 * t), int(40 + 20 * t)
    return f"\033[38;2;{r};{g};{b}m"


def k(n):
    return f"{round(n/1000)}k" if n >= 1000 else str(int(n))


def rel_secs(s):
    s = int(s)
    if s <= 0:
        return "now"
    m = s // 60
    if m < 60:
        return f"{m}m"
    h, mm = divmod(m, 60)
    if h < 24:
        return f"{h}h{mm:02d}m" if mm else f"{h}h"
    d, hh = divmod(h, 24)
    return f"{d}d{hh}h" if hh else f"{d}d"


def day_label(ts):
    t = datetime.datetime.fromtimestamp(ts)
    return t.strftime("%a ") + t.strftime("%I:%M%p").lstrip("0").lower()


def model_name(model):
    name = (model.get("display_name") or "").strip()
    if any(c.isdigit() for c in name):
        return name
    mid = (model.get("id") or "").strip()
    core = mid.replace("claude-", "").split("[")[0]
    parts = core.split("-")
    if parts and parts[0]:
        fam = parts[0].capitalize()
        ver = ".".join(p for p in parts[1:] if p.isdigit())
        return f"{fam} {ver}".strip() if ver else fam
    return "Claude"


def pick(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for kk in keys:
        if kk in obj:
            return obj[kk]
    return None


def usage_line(label, window, duration, reset_fmt):
    """Build one usage row: label + paced bar + % + reset + projection."""
    pct = pick(window, "used_percentage", "usedPercentage", "percent_used", "used")
    resets = pick(window, "resets_at", "resetsAt", "reset_at", "resets")
    if not isinstance(pct, (int, float)) or not isinstance(resets, (int, float)):
        return None
    pct = float(pct)
    now = time.time()
    remaining = resets - now
    elapsed_frac = max(0.0, min(1.0, 1 - remaining / duration))

    width = 18
    fill = max(0, min(width, round(pct / 100 * width)))
    cursor = max(0, min(width - 1, round(elapsed_frac * width)))
    fcol = grad(pct)

    cells = []
    for i in range(width):
        if i == cursor:
            cells.append(f"{WHITE}┃{RESET}")
        elif i < fill:
            cells.append(f"{fcol}█{RESET}")
        else:
            cells.append(f"{DIM}░{RESET}")
    bar = "".join(cells)

    # projection: extrapolate current burn to the window close
    proj_txt = ""
    if elapsed_frac > 0.04:
        proj = pct / elapsed_frac
        pcol = grad(proj)
        proj_txt = f"  {DIM}→{RESET}{pcol}{min(round(proj),999)}%{RESET}"

    reset_txt = reset_fmt(resets) if remaining > 0 else "now"
    return (f"  {DIM}{label}{RESET} {bar} {fcol}{round(pct)}%{RESET}"
            f"  {DIM}↻{RESET} {reset_txt}{proj_txt}")


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        print("")
        return

    name = model_name(d.get("model") or {})
    effort = (d.get("effort") or {}).get("level")
    effort_str = f" {DIM}[{effort}]{RESET}" if effort else ""

    # --- line 1: context window ---
    cw = d.get("context_window") or {}
    size = cw.get("context_window_size") or 0
    pct = cw.get("used_percentage")
    cu = cw.get("current_usage") or {}
    used = (cu.get("input_tokens", 0)
            + cu.get("cache_creation_input_tokens", 0)
            + cu.get("cache_read_input_tokens", 0))
    if pct is None and size:
        pct = used / size * 100
    pct = pct or 0

    width = 22
    filled = max(0, min(width, round(pct / 100 * width)))
    ccol = grad(pct)
    bar = f"{ccol}{'█'*filled}{RESET}{DIM}{'░'*(width-filled)}{RESET}"
    tokens = f"{k(used)} / {k(size)} tokens" if size else ""
    line1 = (f"{BOLD}{name}{RESET}{effort_str}  "
             f"[{bar}] {ccol}{round(pct)}%{RESET}  {DIM}{tokens}{RESET}")

    lines = [line1]

    # --- lines 2-3: plan usage limits (Pro/Max; present after first response) ---
    rl = d.get("rate_limits") or d.get("rateLimits") or {}
    sess = pick(rl, "five_hour", "fiveHour", "session")
    week = pick(rl, "seven_day", "sevenDay", "weekly", "week")
    if isinstance(sess, dict):
        ln = usage_line("5h", sess, FIVE_HOUR, lambda ts: rel_secs(ts - time.time()))
        if ln:
            lines.append(ln)
    if isinstance(week, dict):
        ln = usage_line("7d", week, SEVEN_DAY, day_label)
        if ln:
            lines.append(ln)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
