# claude-pacing-statusline

A custom [Claude Code](https://docs.claude.com/en/docs/claude-code) status line that keeps your **plan usage limits** in view at all times — with a twist no other status line has: a **time-cursor pacing bar** and a **burn projection**.

It turns the data behind the `/usage` command (and the desktop app's "Plan usage limits" panel) into three always-on lines at the bottom of your terminal.

```
Opus 4.8 (1M context) [high]  [█░░░░░░░░░░░░░░░░░░░░░] 5%  52k / 1000k tokens
  5h ██████░░░░░░░░░┃░░ 32%  ↻ 46m         →38%
  7d ██████████░░░░┃░░░ 57%  ↻ Sat 4:59pm  →61%
```

(Colors not shown above: the usage bars run a green → yellow → red gradient as they fill; the `┃` cursor is bright white.)

## What each line shows

- **Line 1** — model, reasoning effort, and the current conversation's context-window fill (`tokens used / context size`).
- **Line 2** — your **5-hour session** limit.
- **Line 3** — your **7-day weekly** (all-models) limit.

## How to read the pacing bars

Each usage bar packs three pieces of information into one row:

- **Colored fill** — how much of that plan limit you've used (green when low, red as you approach the cap).
- **`┃` time cursor** — how far the *clock* is through the reset window. This is the trick: if the fill is **left of** the cursor you're using slower than time is passing (you have headroom); if the fill **reaches or passes** the cursor you're burning faster than the clock.
- **`↻` reset** — a live countdown for the 5-hour window, an absolute day/time for the weekly window.
- **`→N%` projection** — where you'll land at the window's close if you keep your current pace. `→61%` weekly means "on track to use ~61% of my weekly allowance by reset."

So at a glance you know not just *how much* you've used, but whether you're on a sustainable pace and *when* the meter clears.

## Requirements

- **Claude Code** (the CLI).
- A **Claude Pro or Max** subscription — the plan-limit data (`rate_limits`) is only sent to the status line for subscription plans, and only after the first response in a session. On API-key usage or a brand-new session, lines 2–3 simply don't appear and you get the context line on its own.
- **Python 3** (uses only the standard library — no dependencies).
- A terminal with 24-bit "true color" support for the gradient (virtually all modern terminals; it degrades gracefully if not).

## Install

1. Save `statusline.py` somewhere stable, e.g.:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/thejobot/claude-pacing-statusline/main/statusline.py \
     -o ~/.claude/statusline.py
   chmod +x ~/.claude/statusline.py
   ```

2. Point Claude Code at it by adding a `statusLine` block to `~/.claude/settings.json`:

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
    "current_usage": { "input_tokens": ..., "cache_creation_input_tokens": ..., "cache_read_input_tokens": ... }
  },
  "rate_limits": {                      // Pro/Max only, present after the first response
    "five_hour": { "used_percentage": 32, "resets_at": 1781286600 },  // session window
    "seven_day": { "used_percentage": 57, "resets_at": 1781388000 }   // weekly (all models)
  }
}
```

`resets_at` is a Unix epoch (seconds). The window **start** is derived as `resets_at − window_length` (5 h / 7 d), which is what positions the time cursor and feeds the projection (`used% ÷ fraction_of_window_elapsed`).

You can preview it without Claude Code by piping a sample payload in:

```sh
echo '{"model":{"display_name":"Opus 4.8"},"context_window":{"context_window_size":1000000,"used_percentage":5},"rate_limits":{"five_hour":{"used_percentage":32,"resets_at":'$(($(date +%s)+2820))'},"seven_day":{"used_percentage":57,"resets_at":'$(($(date +%s)+126000))'}}}' | python3 statusline.py
```

## What it can't show

Two things from the desktop "Plan usage limits" panel are **not** passed to status line scripts, so they can't appear here:

- The **"Sonnet only"** weekly sub-limit.
- The plan tier label (e.g. **"Max (20x)"**).

Use the `/usage` command in Claude Code for those.

## Customizing

Everything's in one short Python file with no dependencies — easy to tweak:

- **Bar width** — `width = 18` in `usage_line()` (and `width = 22` for the context bar).
- **Drop the projection** — remove the `→N%` block in `usage_line()`.
- **Reset format** — `day_label()` controls the weekly timestamp; `rel_secs()` the countdown.
- **One line instead of three** — join the rows with `"  "` instead of `"\n"` at the end of `main()`.

## Credits / prior art

This combines two ideas that existed separately and adds a clean multi-line layout:

- The **time cursor** concept — [sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline) and [this jtbr gist](https://gist.github.com/jtbr/4f99671d1cee06b44106456958caba8b).
- The **burn projection** — [leeguooooo/claude-code-usage-bar](https://github.com/leeguooooo/claude-code-usage-bar).

If you want a heavily configurable, themed, maintained status line instead of a single hackable file, those projects (plus [Owloops/claude-powerline](https://github.com/Owloops/claude-powerline)) are excellent.

## License

MIT — see [LICENSE](LICENSE).
