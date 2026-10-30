# Toki command reference

After installing, run these commands in Fish from any folder. In bash or zsh,
use `~/.local/bin/toki` instead of `toki`; you do not need to change shells.

## Start studying

| Command | Action |
| --- | --- |
| `toki` | Ask for a work duration; leave it blank for open-ended study. |
| `toki 25` | Set a 25-minute work timer. |
| `toki 25m` | Set a 25-minute work timer with an explicit unit. |
| `toki 30s` | Set a 30-second work timer. |
| `toki 1h` | Set a one-hour work timer. |
| `toki 1.5h` | Set a 90-minute work timer. |
| `toki stats` | Show today's, last seven days', and this month's study totals. |
| `toki --help` | Show quick help (`toki -h` and `toki help` also work). |

A number without a unit means minutes. Supported units are `s`, `m`, and `h`.
Decimals are accepted; durations are rounded down to whole seconds and must
be at least one second. Use a single duration, such as `1.5h`, rather than
`1h30m`. Press Enter at the start prompt to begin the timer.

## During a session

| Key | Action |
| --- | --- |
| Space or `p` | Pause/resume a work or break timer. |
| Enter | Finish an open-ended work session. |
| `q` or Ctrl+C | Stop the current timer; time already studied stays in stats. |

After work, press Enter at the break prompt to start your break. Breaks are
20% of active work time, capped at 30 minutes; work shorter than one minute
does not receive a break. Stopping a break proceeds to the session summary.
At `Continue? (Y/n)`, press Enter or enter `y` to choose another session;
enter `n` to finish.

Pauses and breaks never add to study stats. Only the current calendar month
is retained, and old months are removed on the next stats read or update.
Near the beginning of a month, the seven-day total includes only days in
the new month.

## Original command names

`flow` supports the same commands as `toki`, including `flow stats`.
`flowmodoro` also starts sessions and accepts a duration, such as
`flowmodoro 25`; use `toki stats` or `flow stats` to view statistics.

## View this reference

```fish
cat ~/Toki/COMMANDS.md
```

## Reload commands after edits

Open a new Fish tab, or reload the functions in the current tab. These paths
assume you cloned into `~/Toki`; use your checkout's path if different:

```fish
source ~/Toki/fish/__toki_root.fish
source ~/Toki/fish/flowmodoro.fish
source ~/Toki/fish/flow.fish
source ~/Toki/fish/toki.fish
```

## Run the project checks

```fish
cd ~/Toki
python3 -m unittest discover -s tests -v
```

Checks use temporary data and do not change your study totals.

## Install, update, and uninstall

Run inside your checkout:

```sh
python3 install.py             # Install or repair links to this checkout.
git pull --ff-only            # Download updates, then run install.py again.
python3 install.py --force     # Back up conflicting files and install.
python3 install.py --uninstall # Remove commands; keep study stats.
python3 install.py --help      # Show installer options.
```

The installer links Fish functions into `$XDG_CONFIG_HOME/fish/functions`
(default `~/.config/fish/functions`) and creates `~/.local/bin/toki`.
Use `--config-dir /path/to/fish` or `--bin-dir /path/to/bin` for custom folders.
Use the same options when uninstalling. Conflicting files replaced with
`--force` are preserved under the Fish configuration folder's `toki-backups/`.

## Sound and data location

```sh
env TOKI_SOUND=0 ~/.local/bin/toki 25
env TOKI_DATA_DIR=/path/to/study-data ~/.local/bin/toki stats
```

`TOKI_SOUND=0` disables audio. `TOKI_DATA_DIR` overrides the stats folder.
Otherwise data goes into `$XDG_DATA_HOME/toki` (default `~/.local/share/toki`).
Use the same location for starting sessions and viewing their stats. Changing
this variable does not move existing data. There are no accounts or telemetry.

The project includes its WAV audio cues. macOS uses `afplay`; Linux tries
`paplay`, `ffplay`, `mpv`, then `aplay`. Missing players are fine: sessions
continue silently. The external `timer` command is not required.
