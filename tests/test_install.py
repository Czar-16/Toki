"""Portable installation and command integration; no real user data is changed."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import audio


@unittest.skipUnless(shutil.which('fish'), 'Fish is required for integration checks')
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='toki install ')
        self.base = Path(self.temp.name)
        self.project = self.base / "Toki user's checkout"
        shutil.copytree(ROOT, self.project,
                        ignore=shutil.ignore_patterns('.git', '__pycache__', '.venv'))
        self.config = self.base / 'fish config'
        self.bin = self.base / 'bin'
        self.data = self.base / 'study data'
        self.env = dict(os.environ, TOKI_DATA_DIR=str(self.data), TOKI_SOUND='0')

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *options):
        return subprocess.run([sys.executable, str(self.project / 'install.py'),
                               '--config-dir', str(self.config), '--bin-dir', str(self.bin),
                               *options], capture_output=True, text=True, env=self.env, timeout=10)

    def run_toki(self, *args):
        return subprocess.run([str(self.bin / 'toki'), *args], cwd=self.base,
                              capture_output=True, text=True, env=self.env, timeout=10)

    def test_fresh_install_launcher_spaces_and_stats(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_toki('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Usage: toki', result.stdout)
        result = self.run_toki('stats')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('This month:     00h 00m 00s', result.stdout)
        self.assertTrue((self.data / 'stats.json').exists())
        # Also resolve the root through installed Fish autoload links.
        result = subprocess.run(['fish', '--no-config', '-c',
                                 'set -p fish_function_path $argv[1]; toki --help', '--',
                                 str(self.config / 'functions')], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Usage: toki', result.stdout)

    def test_uninstall_keeps_stats_and_other_functions(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.run_toki('stats').returncode, 0)
        other = self.config / 'functions' / 'personal.fish'
        other.write_text('function personal; end\n')
        snapshot = (self.data / 'stats.json').read_bytes()
        result = self.install('--uninstall')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.bin / 'toki').exists())
        self.assertFalse((self.config / 'functions' / 'toki.fish').exists())
        self.assertTrue(other.exists())
        self.assertEqual((self.data / 'stats.json').read_bytes(), snapshot)

    def test_conflicts_are_preserved_and_force_creates_backup(self):
        target = self.config / 'functions' / 'toki.fish'
        target.parent.mkdir(parents=True)
        original = 'function toki; echo personal; end\n'
        target.write_text(original)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), original)
        self.assertFalse((self.bin / 'toki').exists())
        self.assertFalse((target.parent / 'flow.fish').exists())
        result = self.install('--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.config / 'toki-backups').glob('*/*toki.fish'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(self.run_toki('--help').returncode, 0)

    def test_move_and_reinstall(self):
        self.assertEqual(self.install().returncode, 0)
        destination = self.base / 'moved Toki'
        self.project.rename(destination)
        self.project = destination
        result = self.install('--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_toki('stats').returncode, 0)

    def test_invalid_duration_is_rejected_without_creating_stats(self):
        self.assertEqual(self.install().returncode, 0)
        for value in ('0', '-5', 'oops', '1h30m'):
            with self.subTest(value=value):
                result = self.run_toki(value)
                self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.data.exists())


class AudioTests(unittest.TestCase):
    def test_mac_and_linux_player_arguments(self):
        for player in ('afplay', 'paplay', 'ffplay', 'mpv', 'aplay'):
            with self.subTest(player=player), patch.dict(os.environ, TOKI_SOUND='1'), \
                    patch.object(sys, 'argv', ['audio.py', 'startwork']), \
                    patch.object(audio.shutil, 'which', side_effect=lambda name: '/bin/' + name if name == player else None), \
                    patch.object(audio.subprocess, 'Popen') as popen:
                self.assertEqual(audio.main(), 0)
                command = popen.call_args.args[0]
                self.assertEqual(command[0], '/bin/' + player)
                self.assertTrue(command[-1].endswith('sounds/startwork.wav'))
                self.assertTrue(Path(command[-1]).is_file())

    def test_silent_and_no_player_are_optional(self):
        with patch.dict(os.environ, TOKI_SOUND='0'), patch.object(audio.subprocess, 'Popen') as popen:
            self.assertEqual(audio.main(), 0)
            popen.assert_not_called()
        with patch.dict(os.environ, TOKI_SOUND='1'), patch.object(sys, 'argv', ['audio.py', 'focus']), \
                patch.object(audio.shutil, 'which', return_value=None), \
                patch.object(audio.subprocess, 'Popen') as popen:
            self.assertEqual(audio.main(), 0)
            popen.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
