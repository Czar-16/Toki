from datetime import date, datetime
import multiprocessing
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stats


def add_many(path, count):
    for _ in range(count):
        stats.Store(path).update({'2026-10-30': 1}, today=date(2026, 10, 30))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'stats.json'
        self.store = stats.Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_totals_and_retention(self):
        self.store.write({'2026-09-30': 600, '2026-10-01': 3600,
                          '2026-10-24': 7200, '2026-10-30': 90061})
        self.assertEqual(self.store.totals(date(2026, 10, 30)), (90061, 97261, 100861))
        self.assertNotIn('2026-09-30', self.store.load())
        self.assertEqual(stats.duration(100861), '28h 01m 01s')
        self.assertLess(self.path.stat().st_size, 5000)

    def test_month_year_leap_and_long_absence(self):
        for before, after in [('2028-02-29', '2028-03-01'),
                              ('2026-12-31', '2027-01-01'),
                              ('2026-01-01', '2026-10-30')]:
            self.store.write({before: 100})
            self.assertEqual(self.store.totals(date.fromisoformat(after)), (0, 0, 0))
            self.assertEqual(self.store.load(), {})

    def test_week_is_limited_to_retained_month(self):
        self.store.write({'2026-09-30': 100, '2026-10-01': 50})
        self.assertEqual(self.store.totals(date(2026, 10, 1)), (50, 50, 50))

    def test_midnight_and_month_boundary(self):
        for start, end, today, expected in [
            ('2026-10-29T23:59:58', '2026-10-30T00:00:03', date(2026, 10, 30),
             {'2026-10-29': 2, '2026-10-30': 3}),
            ('2026-10-31T23:59:58', '2026-11-01T00:00:03', date(2026, 11, 1),
             {'2026-11-01': 3})]:
            self.path.unlink(missing_ok=True)
            tracker = stats.Tracker(self.store)
            tracker.add(datetime.fromisoformat(start).timestamp(),
                        datetime.fromisoformat(end).timestamp(), 5)
            tracker.flush(today=today)
            self.assertEqual(self.store.load(), expected)

    def test_fractional_checkpoints_do_not_duplicate_or_lose_seconds(self):
        tracker = stats.Tracker(self.store)
        start = datetime(2026, 10, 30, 12).timestamp()
        for index in range(30):
            tracker.add(start + index / 10, start + (index + 1) / 10, 0.1)
            tracker.flush(today=date(2026, 10, 30))
        tracker.flush(today=date(2026, 10, 30))
        self.assertEqual(self.store.load(), {'2026-10-30': 3})

    def test_corrupt_data_is_preserved(self):
        self.path.write_text('broken JSON')
        with self.assertRaises(stats.StatsError):
            self.store.update()
        self.assertEqual(self.path.read_text(), 'broken JSON')

    def test_failed_write_preserves_existing_and_pending(self):
        tracker = stats.Tracker(self.store)
        start = datetime(2026, 10, 30, 12).timestamp()
        tracker.add(start, start + 3, 3)
        before = self.path.read_text()
        with patch.object(stats.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                tracker.flush(today=date(2026, 10, 30))
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(sum(tracker.pending.values()), 3)
        tracker.flush(today=date(2026, 10, 30))
        self.assertEqual(self.store.load(), {'2026-10-30': 3})

    def test_concurrent_updates(self):
        workers = [multiprocessing.Process(target=add_many, args=(self.path, 30)) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(self.store.load(), {'2026-10-30': 120})


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'stats.json'
        self.result = Path(self.temp.name) / 'result'
        self.children = []

    def tearDown(self):
        for process, fd in self.children:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            os.close(fd)
        self.temp.cleanup()

    def launch(self, duration=2, label='Work'):
        # Avoid forkpty, which can hang in a macOS process that has run other
        # libraries. Popen executes the actual CLI without Python after fork.
        environment = dict(os.environ, TOKI_DATA_DIR=str(self.path.parent))
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'countdown.py'),
                   str(duration), label, str(self.result)]
        fd, slave = pty.openpty()
        try:
            process = subprocess.Popen(command, stdin=slave, stdout=slave,
                                       stderr=slave, env=environment, start_new_session=True)
        finally:
            os.close(slave)
        self.children.append((process, fd))
        self.until(fd, b'RUNNING')
        return process.pid, fd

    def process(self, pid):
        return next(process for process, _ in self.children if process.pid == pid)

    def until(self, fd, marker, timeout=8):
        end = time.monotonic() + timeout
        output = b''
        while marker not in output:
            self.assertLess(time.monotonic(), end, (marker, output[-500:]))
            if select.select([fd], [], [], 0.05)[0]:
                output += os.read(fd, 65536)
        return output

    def drain(self, fd, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if select.select([fd], [], [], min(.05, max(0, end-time.monotonic())))[0]:
                os.read(fd, 65536)

    def finish(self, pid, fd, code):
        process = self.process(pid)
        deadline = time.monotonic() + 5
        while process.poll() is None:
            self.assertLess(time.monotonic(), deadline, 'Timer did not exit after finishing')
            if select.select([fd], [], [], .05)[0]:
                try:
                    os.read(fd, 65536)
                except OSError:
                    pass  # Linux reports EIO when the slave has closed.
        self.assertEqual(process.returncode, code)
        self.assertTrue(termios.tcgetattr(fd)[3] & termios.ECHO)

    def total(self):
        return stats.Store(self.path).totals()[0]

    def test_pause_resume_and_completed_work(self):
        pid, fd = self.launch()
        os.write(fd, b' ')
        self.until(fd, b'PAUSED')
        self.drain(fd, 2.2)
        self.assertIsNone(self.process(pid).poll())
        self.assertEqual(self.total(), 0)
        os.write(fd, b' ')
        self.until(fd, b'COMPLETE')
        self.finish(pid, fd, 0)
        self.assertEqual(self.total(), 2)
        self.assertEqual(self.result.read_text(), '2')

    def test_stopped_work_q_ctrlc_and_hangup(self):
        for action in ('q', 'ctrlc', 'hup'):
            with self.subTest(action=action):
                self.path.unlink(missing_ok=True)
                pid, fd = self.launch(10)
                self.drain(fd, 1.1)
                if action == 'hup':
                    os.kill(pid, signal.SIGHUP)
                else:
                    os.write(fd, b'q' if action == 'q' else b'\x03')
                self.until(fd, b'STOPPED')
                self.finish(pid, fd, 130)
                self.assertEqual(self.total(), 1)

    def test_break_excluded(self):
        pid, fd = self.launch(1, 'Break')
        self.until(fd, b'COMPLETE')
        self.finish(pid, fd, 0)
        self.assertFalse(self.path.exists())

    def test_open_ended_enter_and_pause(self):
        pid, fd = self.launch(0)
        self.drain(fd, 1.1)
        os.write(fd, b' ')
        self.until(fd, b'PAUSED')
        self.drain(fd, 1.2)
        os.write(fd, b'\r')
        self.until(fd, b'COMPLETE')
        self.finish(pid, fd, 0)
        self.assertEqual(self.total(), 1)

    def test_checkpoint_survives_forced_termination(self):
        pid, fd = self.launch(20)
        self.drain(fd, 5.3)
        os.kill(pid, signal.SIGKILL)
        self.process(pid).wait(timeout=5)
        self.assertEqual(self.total(), 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
