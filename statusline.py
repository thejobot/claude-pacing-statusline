#!/usr/bin/env python3
"""Claude Code status line.

Line 1: Opus 4.8  ▁▂▄▆ xhigh  context 5%  52k / 1000k tokens   (effort gauge)
Line 2: 5h  used 33%  resets 47m  spend up to 22% per hour  [bar] using 60%
Line 3: 7d  used 58%  resets 6d12h / Sat 5pm  spend up to 14% per day  [bar] using 56%  on track

Every percentage is labeled so you always know what it measures:
  context     - how full THIS chat's context window is
  used        - % of this window's plan limit you've already spent
  resets      - when the window refills (countdown / wall-clock for 7d)
  spend up to - suggested limit: the most you can use per hour (5h) / day (7d)
                and still land at 100% by reset (the bar's full point)
  [bar] using - speedometer: how much of that limit your CURRENT pace is using.
                Bar + the using-% are the same value. Near empty = lots of room;
                full = right at the limit; past 100% pins red = overspending.

The 7d row ends with an adaptive verb -- the plain-English summary:
  go heavy / push / on track / ease off / ration
It digests the burn-rate projection so you don't have to. Green = headroom going
unused, spend more; red = overspending, back off. Re-reads every render.
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


# reasoning-effort tiers, low -> max, each with a ramp height and accent color.
# (ultracode/auto resolve to one of these; the status line reports the active tier.)
EFFORT_TIERS = ["low", "medium", "high", "xhigh", "max"]
EFFORT_COLOR = {
    "low":    "\033[38;2;130;200;130m",   # green
    "medium": "\033[38;2;90;180;235m",    # blue
    "high":   "\033[38;2;240;205;90m",    # amber
    "xhigh":  "\033[38;2;245;140;70m",    # orange
    "max":    "\033[38;2;240;75;75m",     # red (ceiling)
}
EFFORT_RAMP = "▁▂▄▆█"
EFFORT_LABEL = {"low": "low", "medium": "med", "high": "high",
                "xhigh": "xhigh", "max": "max"}


def effort_gauge(level):
    """A 4-step ramp lit up to the current reasoning-effort tier."""
    if not level:
        return ""
    if level not in EFFORT_TIERS:
        return f"{DIM}[{level}]{RESET}"
    n = EFFORT_TIERS.index(level) + 1
    col = EFFORT_COLOR[level]
    bars = "".join(
        f"{col}{ch}{RESET}" if i < n else f"{DIM}{ch}{RESET}"
        for i, ch in enumerate(EFFORT_RAMP)
    )
    return f"{bars} {col}{EFFORT_LABEL[level]}{RESET}"


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
    clock = t.strftime("%I:%M%p")
    if t.minute == 0:                       # 5:00pm -> 5pm
        clock = t.strftime("%I%p")
    return t.strftime("%a ") + clock.lstrip("0").lower()


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


CYAN = "\033[38;2;90;200;210m"

# adaptive daily strategy, keyed on the PROJECTION (where current pace lands you
# at reset). Low projection = lots of headroom left unused -> spend more; high =
# overspending -> back off. Re-reads every render, so it tracks the whole week.
STRAT = [  # (projection ceiling %, verb, color)
    (60,    "go heavy", "\033[38;2;60;200;90m"),    # bright green
    (80,    "push",     "\033[38;2;150;205;70m"),   # green
    (108,   "on track", "\033[38;2;230;200;60m"),   # yellow
    (145,   "ease off", "\033[38;2;240;150;70m"),   # orange
    (10**9, "ration",   "\033[38;2;240;75;75m"),    # red
]


def daily_strategy(proj):
    for lim, verb, col in STRAT:
        if proj <= lim:
            return verb, col


def pace_bar(ratio, width=10):
    """Speedometer: how close current pace is to the suggested limit.
    full = right at the limit (on track to use the whole plan); over = red."""
    fill = max(0, min(width, round(min(ratio, 1.0) * width)))
    col = grad(min(ratio, 1.3) * 80)       # green under, red at/over the limit
    return f"[{col}{'█' * fill}{RESET}{DIM}{'░' * (width - fill)}{RESET}]"


def usage_line(label, window, duration, reset_fmt, alloc_unit, alloc_secs,
               strategy=False):
    """One row: window + used% + reset + pace-vs-limit speedometer (+ strategy)."""
    pct = pick(window, "used_percentage", "usedPercentage", "percent_used", "used")
    resets = pick(window, "resets_at", "resetsAt", "reset_at", "resets")
    if not isinstance(pct, (int, float)) or not isinstance(resets, (int, float)):
        return None
    pct = float(pct)
    now = time.time()
    remaining = resets - now
    elapsed_frac = max(0.0, min(1.0, 1 - remaining / duration))

    reset_txt = reset_fmt(resets) if remaining > 0 else "now"
    row = (f"  {DIM}{label}{RESET} {DIM}used{RESET} {grad(pct)}{round(pct)}%{RESET}"
           f"  {DIM}resets{RESET} {reset_txt}")

    # how much of your suggested limit (budget left / time left) you're using.
    units_total = duration / alloc_secs
    units_elapsed = elapsed_frac * units_total
    units_left = remaining / alloc_secs
    if units_elapsed > 0.04 and units_left > 0.05:
        pace = pct / units_elapsed
        limit = max(0.0, 100 - pct) / units_left
        ratio = pace / limit if limit > 0 else 2.0
        pcol = grad(min(ratio, 1.3) * 80)
        row += (f"  {DIM}spend up to{RESET} {CYAN}{min(round(limit),999)}% per "
                f"{alloc_unit}{RESET}  {pace_bar(ratio)} "
                f"{DIM}using{RESET} {pcol}{min(round(ratio*100),999)}%{RESET}")

    if strategy and elapsed_frac > 0.04:     # adaptive verb from the projection
        verb, vcol = daily_strategy(pct / elapsed_frac)
        row += f"  {vcol}{BOLD}{verb}{RESET}"

    return row


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        print("")
        return

    name = model_name(d.get("model") or {})
    effort = (d.get("effort") or {}).get("level")
    gauge = effort_gauge(effort)
    effort_str = f"  {gauge}" if gauge else ""

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
             f"[{bar}] {DIM}context{RESET} {ccol}{round(pct)}%{RESET}  {DIM}{tokens}{RESET}")

    lines = [line1]

    # --- lines 2-3: plan usage limits (Pro/Max; present after first response) ---
    rl = d.get("rate_limits") or d.get("rateLimits") or {}
    sess = pick(rl, "five_hour", "fiveHour", "session")
    week = pick(rl, "seven_day", "sevenDay", "weekly", "week")
    if isinstance(sess, dict):
        ln = usage_line("5h", sess, FIVE_HOUR,
                        lambda ts: rel_secs(ts - time.time()), "hour", HOUR)
        if ln:
            lines.append(ln)
    if isinstance(week, dict):
        ln = usage_line(
            "7d", week, SEVEN_DAY,
            lambda ts: f"{rel_secs(ts - time.time())} / {day_label(ts)}",
            "day", 24 * HOUR, strategy=True)
        if ln:
            lines.append(ln)

    print("\n".join(lines))


if __name__ == "__main__":
    main()
