#!/usr/bin/env python3
"""Install Toki's Fish functions and a launcher for bash/zsh, without sudo."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
FUNCTIONS = ('__toki_root.fish', 'flowmodoro.fish', 'flow.fish', 'toki.fish')


def managed(path):
    try:
        first_lines = path.read_text().splitlines()[:2]
        return any(line.startswith('# Toki managed ') for line in first_lines)
    except (OSError, UnicodeError):
        return False


def present(path):
    return path.exists() or path.is_symlink()


def launcher(fish):
    script = 'set -p fish_function_path "$argv[1]/fish"; toki $argv[2..-1]'
    return ('#!/bin/sh\n# Toki managed launcher. Re-run install.py after moving the checkout.\n'
            f'exec {shlex.quote(fish)} --no-config -c {shlex.quote(script)} -- '
            f'{shlex.quote(str(ROOT))} "$@"\n')


def install(args):
    config = args.config_dir.expanduser().resolve()
    bin_dir = args.bin_dir.expanduser().resolve()
    targets = [(config / 'functions' / name, ROOT / 'fish' / name) for name in FUNCTIONS]
    executable = bin_dir / 'toki'

    if args.uninstall:
        for target, _ in targets + [(executable, None)]:
            if managed(target) or (target.is_symlink() and target.resolve() in
                                   [source for _, source in targets]):
                target.unlink()
                print(f'Removed {target}')
        print('Toki uninstalled. Study data is kept; see README.md for its location.')
        print('Open a new terminal tab to discard already-loaded Fish functions.')
        return 0

    if sys.platform != 'darwin' and not sys.platform.startswith('linux'):
        raise RuntimeError('Toki supports Linux and macOS.')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required.')
    fish = shutil.which('fish')
    if not fish:
        raise RuntimeError('Fish is required. Install it using the commands in README.md.')
    version = subprocess.run([fish, '--version'], check=True, capture_output=True, text=True).stdout
    match = re.search(r'version (\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (3, 6):
        raise RuntimeError('Fish 3.6 or newer is required.')

    all_targets = [target for target, _ in targets] + [executable]
    conflicts = [target for target in all_targets if present(target) and not managed(target)]
    if conflicts and not args.force:
        names = '\n'.join(str(path) for path in conflicts)
        raise RuntimeError(f'Existing files were left untouched:\n{names}\n'
                           'Use --force to back them up before installing.')
    for directory in (config / 'functions', bin_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if conflicts:
        backup = config / 'toki-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        for index, target in enumerate(conflicts):
            shutil.move(str(target), str(backup / f'{index}-{target.name}'))
        print(f'Existing files backed up to {backup}')
    for target, source in targets:
        temporary = target.with_name(target.name + f'.toki-{os.getpid()}')
        try:
            temporary.symlink_to(source)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix='.toki-', dir=bin_dir)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(launcher(fish))
        temporary.chmod(0o755)
        os.replace(temporary, executable)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Toki installed from {ROOT}')
    print('In Fish: open a new tab and run toki')
    print(f'From bash/zsh: run {executable}')
    print('No default-shell settings or study data were changed.')
    return 0


def main():
    config_base = Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true', help='remove Toki commands, keeping study data')
    parser.add_argument('--force', action='store_true', help='back up conflicting files before replacing them')
    parser.add_argument('--config-dir', type=Path, default=config_base / 'fish', help='Fish configuration folder')
    parser.add_argument('--bin-dir', type=Path, default=Path.home() / '.local/bin', help='launcher installation folder')
    args = parser.parse_args()
    try:
        return install(args)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Installation error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
