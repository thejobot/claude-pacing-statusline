# claude-pacing-statusline

A custom [Claude Code](https://docs.claude.com/en/docs/claude-code) status line that keeps your **plan usage limits** in view at all times, and turns them into an actionable **pacing strategy**. It answers the question raw usage bars don't: *am I on track to get the value I'm paying for, and how much can I spend right now?*

It turns the data behind the `/usage` command (and the desktop app's "Plan usage limits" panel) into three always-on lines at the bottom of your terminal.

```
Opus 4.8  ▁▂▄▆█ high  [█░░░░░░░░░░░░░░░░░░░░░] context 5%  52k / 1000k tokens
  5h used 32%  resets 46m                 spend up to 87% per hour  [█░░░░░░░░░] using 9%
  7d used 40%  resets 3d23h / Thu 11am    spend up to 15% per day   [█████████░] using 89%  on track
```

(Colors not shown above: every percentage runs a green → yellow → red gradient; the `▁▂▄▆█` effort gauge shifts green → blue → amber → orange → red by tier; the strategy verb is bold and colored by urgency.)

## What each line shows

- **Line 1:** model, a **`▁▂▄▆█` effort gauge** (a 5-step ramp that lights up to the current reasoning-effort tier: low / medium / high / xhigh / max, color-shifting green → blue → amber → orange → red), and the current conversation's **context-window** fill (`tokens used / context size`).
- **Line 2:** your **5-hour session** limit.
- **Line 3:** your **7-day weekly** (all-models) limit, ending with an adaptive **strategy verb**.

## How to read the rows

Every value is labeled in plain English, so nothing is left to guess:

- **`used N%`**: how much of that window's plan limit you've already spent.
- **`resets`**: when the window refills, shown as a live countdown for the 5-hour window, and `countdown / wall-clock` for the weekly one (e.g. `3d23h / Thu 11am`).
- **`spend up to N% per hour/day`**: your **suggested limit**, the most you can spend per hour (5h) or per day (7d) and still land exactly at 100% by reset. Spend up to it for full value; it grows when you under-use and shrinks when you overspend.
- **`[bar] using N%`**: a **speedometer** showing how much of that suggested limit your *current* pace is actually using. The bar and the `using` number are the same value. Near-empty = lots of room; full = right at the limit (on track to use the whole plan); past 100% the bar pins red = you're overspending and will run out early.

### The strategy verb

The weekly row ends with one word that digests your burn-rate projection so you don't have to:

| Verb | Meaning |
| --- | --- |
| **go heavy** | tons of headroom going unused, spend freely |
| **push** | comfortably under, room to spare |
| **on track** | pacing to use about your whole plan |
| **ease off** | overspending, slow down |
| **ration** | way over, you'll hit the wall early |

Green = headroom, red = overspending. It re-reads on every render, so it tracks the whole week and self-corrects each day.

## Requirements

- **Claude Code** (the CLI).
- A **Claude Pro or Max** subscription. The plan-limit data (`rate_limits`) is only sent to the status line for subscription plans, and only after the first response in a session. On API-key usage or a brand-new session, lines 2 and 3 simply don't appear and you get the context line on its own.
- **Python 3** (standard library only, no dependencies).
- A terminal with 24-bit "true color" support for the gradient (virtually all modern terminals; it degrades gracefully if not).

## Install

1. Save `statusline.py` somewhere stable, e.g.:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/thejobot/claude-pacing-statusline/main/statusline.py \
     -o ~/.claude/statusline.py
   chmod +x ~/.claude/statusline.py
   ```

2. Point Claude Code at it by adding a `statusLine` block to `~/.claude/settings.json` (see `settings.example.json`):

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ~/.claude/statusline.py",
       "padding": 0
     }
   }
   ```

3. Start (or restart) Claude Code. Send one message so the plan-limit data arrives, and the three lines appear.

## How it works

Claude Code runs your status line command on each redraw and pipes a JSON object to it on **stdin**. The relevant fields:

```jsonc
{
  "context_window": {
    "context_window_size": 1000000,
    "used_percentage": 5,
    "current_usage": { "input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0 }
  },
  "rate_limits": {                      // Pro/Max only, present after the first response
    "five_hour": { "used_percentage": 32, "resets_at": 1781286600 },  // session window
    "seven_day": { "used_percentage": 40, "resets_at": 1781388000 }   // weekly (all models)
  }
}
```

`resets_at` is a Unix epoch (seconds). The window **start** is `resets_at` minus the window length (5 h / 7 d). From that the script derives two rates:

- **suggested limit** = budget left ÷ time left (looking *forward*: what you can still afford per hour/day)
- **current pace** = used ÷ time elapsed (looking *back*: how fast you've actually been going)

The speedometer is `pace ÷ limit`; the strategy verb comes from the projection `used% ÷ fraction_of_window_elapsed`.

Preview it without Claude Code by piping a sample payload in:

```sh
echo '{"model":{"display_name":"Opus 4.8"},"effort":{"level":"high"},"context_window":{"context_window_size":1000000,"used_percentage":5},"rate_limits":{"five_hour":{"used_percentage":32,"resets_at":'$(($(date +%s)+2820))'},"seven_day":{"used_percentage":40,"resets_at":'$(($(date +%s)+345600))'}}}' | python3 statusline.py
```

## What it can't show

Two things from the desktop "Plan usage limits" panel are **not** passed to status line scripts, so they can't appear here:

- The **"Sonnet only"** weekly sub-limit.
- The plan tier label (e.g. **"Max (20x)"**).

Use the `/usage` command in Claude Code for those.

## Customizing

Everything's in one short Python file with no dependencies, so it's easy to tweak:

- **Speedometer width:** `width=10` in `pace_bar()` (and `width = 22` for the context bar).
- **Strategy thresholds / wording:** the `STRAT` table near the top.
- **Reset format:** `day_label()` controls the weekly timestamp; `rel_secs()` the countdown.
- **One line instead of three:** join the rows with `"  "` instead of `"\n"` at the end of `main()`.

## Credits / prior art

This builds on ideas that existed separately and adds the pacing speedometer, the adaptive strategy verb, and a plain-language layout:

- The **time-cursor** idea (an earlier version of this script used it), from [sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline) and [this jtbr gist](https://gist.github.com/jtbr/4f99671d1cee06b44106456958caba8b).
- The **burn projection**, from [leeguooooo/claude-code-usage-bar](https://github.com/leeguooooo/claude-code-usage-bar).

If you want a heavily configurable, themed, maintained status line instead of a single hackable file, those projects (plus [Owloops/claude-powerline](https://github.com/Owloops/claude-powerline)) are excellent.

## License

MIT. See [LICENSE](LICENSE).
