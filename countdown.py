#!/usr/bin/env python3
"""Interactive countdown with active-time accounting and a progress bar."""
import argparse
import math
import os
from pathlib import Path
import select
import signal
import sys
import termios
import time
import tty
from stats import StatsError, Tracker


def clock(seconds):
    seconds = max(0, math.ceil(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def countdown(duration, label, result):
    elapsed = 0.0
    paused = False
    status = 130
    tracker = Tracker() if label == 'Work' else None
    fd = os.open('/dev/tty', os.O_RDWR)
    original = termios.tcgetattr(fd)
    last = time.monotonic()
    last_wall = time.time()
    last_save = last

    def advance():
        nonlocal elapsed, last, last_wall
        now, wall = time.monotonic(), time.time()
        if not paused:
            active = max(0.0, now - last)
            if duration:
                active = min(active, max(0.0, duration - elapsed))
            elapsed += active
            if tracker:
                tracker.add(last_wall, wall, active)
        last, last_wall = now, wall

    def write(text):
        os.write(fd, text.encode())

    def draw(state):
        width = min(76, max(8, (os.get_terminal_size(fd).columns or 80) - 10))
        fraction = min(1.0, elapsed / duration) if duration else 0
        filled = int(width * fraction)
        bar = []
        for index in range(width):
            if index < filled:
                blend = index / max(1, width - 1)
                red = round(90 + (238 - 90) * blend)
                green = round(86 + (111 - 86) * blend)
                blue = round(224 + (248 - 224) * blend)
                bar.append(f'\033[38;2;{red};{green};{blue}m█')
            else:
                bar.append('\033[38;2;96;96;96m░')
        header = (f'{label} · {state} · {clock(duration - elapsed)} remaining' if duration
                  else f'{label} · {state} · {clock(elapsed)} studied')
        hint = 'Space: pause/resume  ·  Ctrl+C or q: stop'
        if not duration:
            hint = 'Enter: finish  ·  Space: pause/resume  ·  q: stop'
        progress = f'{"".join(bar)}\033[0m {fraction:4.0%}' if duration else 'Open-ended study session'
        write(f'\r\033[2K{header}\n\r\033[2K{progress}'
              f'\n\r\033[2K{hint}\033[2A\r')

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old_signals = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        tty.setcbreak(fd)
        write('\033[?25l')
        last, last_wall = time.monotonic(), time.time()
        while True:
            advance()
            if tracker and last - last_save >= 5:
                tracker.flush()
                last_save = last
            if duration and elapsed >= duration:
                status = 0
                break
            draw('PAUSED' if paused else 'RUNNING')
            readable, _, _ = select.select([fd], [], [], 0.05)
            if readable:
                keys = os.read(fd, 128)
                advance()
                if not keys or b'q' in keys or b'\x03' in keys:
                    break
                if not duration and (b'\r' in keys or b'\n' in keys):
                    status = 0
                    break
                for key in keys:
                    if key in (ord(' '), ord('p')):
                        paused = not paused
                        if tracker:
                            tracker.flush()
                            last_save = last
    except KeyboardInterrupt:
        pass
    finally:
        advance()
        try:
            try:
                draw('COMPLETE' if status == 0 else 'STOPPED')
                write('\033[2B\r\n\033[0m\033[?25h')
            except OSError:
                pass  # The terminal may have been closed.
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, original)
            except OSError:
                pass
            os.close(fd)
            for sig, handler in old_signals.items():
                signal.signal(sig, handler)
            try:
                result.write_text(str(int(elapsed + 1e-8)))
            finally:
                if tracker:
                    tracker.flush()
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('duration', type=float)
    parser.add_argument('label')
    parser.add_argument('result', type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration < 0:
        parser.error('duration must be nonnegative and finite; zero means open-ended')
    try:
        return countdown(args.duration, args.label, args.result)
    except (OSError, StatsError) as error:
        print(f'Countdown error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
