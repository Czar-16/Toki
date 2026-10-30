"""Small, local, current-month study totals; standard library only."""
from contextlib import contextmanager
from datetime import date, datetime, time as daytime, timedelta
import fcntl
import json
import math
import os
from pathlib import Path
import sys
import tempfile


DATA_DIR = Path(os.environ.get('TOKI_DATA_DIR') or
                str(Path(os.environ.get('XDG_DATA_HOME') or str(Path.home() / '.local/share')) / 'toki')).expanduser()
DEFAULT_PATH = DATA_DIR / 'stats.json'


class StatsError(Exception):
    pass


class Store:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def load(self):
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text())
            if payload.get('version') != 1 or not isinstance(payload.get('days'), dict):
                raise ValueError('unrecognized format')
            days = payload['days']
            for day, seconds in days.items():
                if date.fromisoformat(day).isoformat() != day:
                    raise ValueError('invalid date')
                if type(seconds) is not int or seconds < 0:
                    raise ValueError('invalid study time')
            return days
        except (ValueError, TypeError, AttributeError) as error:
            raise StatsError(f'Cannot read {self.path}: {error}. Existing data was preserved.') from error

    def write(self, days):
        fd, temporary = tempfile.mkstemp(prefix='.stats-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump({'version': 1, 'days': days}, output, sort_keys=True)
                output.write('\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def update(self, additions=None, today=None):
        today = today or date.today()
        month = today.strftime('%Y-%m-')
        with self.locked():
            original = self.load()
            days = {day: seconds for day, seconds in original.items() if day.startswith(month)}
            for day, seconds in (additions or {}).items():
                if day.startswith(month) and seconds > 0:
                    days[day] = days.get(day, 0) + seconds
            if days != original or not self.path.exists():
                self.write(days)
            return days

    def totals(self, today=None):
        today = today or date.today()
        days = self.update(today=today)
        week_start = (today - timedelta(days=6)).isoformat()
        day = today.isoformat()
        return (days.get(day, 0),
                sum(seconds for key, seconds in days.items() if week_start <= key <= day),
                sum(days.values()))


class Tracker:
    """Accumulate fractions in memory; persist whole seconds without double counting."""
    def __init__(self, store=None):
        self.store = store or Store()
        self.pending = {}
        self.store.update()

    def add(self, start, end, active_seconds):
        if active_seconds <= 0:
            return
        if end <= start:
            key = datetime.fromtimestamp(end).date().isoformat()
            self.pending[key] = self.pending.get(key, 0.0) + active_seconds
            return
        cursor = start
        while cursor < end:
            day = datetime.fromtimestamp(cursor).date()
            midnight = datetime.combine(day + timedelta(days=1), daytime.min).timestamp()
            boundary = min(midnight, end)
            portion = active_seconds * ((boundary - cursor) / (end - start))
            key = day.isoformat()
            self.pending[key] = self.pending.get(key, 0.0) + portion
            cursor = boundary

    def flush(self, today=None):
        additions = {day: int(math.floor(seconds + 1e-8)) for day, seconds in self.pending.items()}
        # Remove pending seconds only after the atomic write succeeds.
        self.store.update(additions, today=today)
        current = (today or date.today()).strftime('%Y-%m-')
        self.pending = {day: max(0.0, seconds - additions[day])
                        for day, seconds in self.pending.items() if day.startswith(current)}


def duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02}h {minutes:02}m {seconds:02}s'


def main():
    try:
        totals = Store().totals()
        for label, seconds in zip(('Today:', 'Last 7 days:', 'This month:'), totals):
            print(f'{label:<16}{duration(seconds)}')
        return 0
    except (OSError, StatsError) as error:
        print(f'Study stats error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
