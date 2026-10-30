"""Play bundled cues with an available Linux or macOS player; audio is optional."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


PLAYERS = (
    ('afplay', []),
    ('paplay', []),
    ('ffplay', ['-nodisp', '-autoexit', '-loglevel', 'quiet']),
    ('mpv', ['--no-terminal', '--no-audio-display']),
    ('aplay', ['-q']),
)
CUES = ('startwork', 'workstatus', 'startbreak', 'breakstatus', 'focus', 'welltried', 'didgreat')


def main():
    if os.environ.get('TOKI_SOUND', '1') == '0':
        return 0
    if len(sys.argv) != 2 or sys.argv[1] not in CUES:
        print('Unknown Toki audio cue.', file=sys.stderr)
        return 2
    sound = Path(__file__).resolve().parent / 'sounds' / (sys.argv[1] + '.wav')
    for name, options in PLAYERS:
        player = shutil.which(name)
        if player:
            try:
                subprocess.Popen([player, *options, str(sound)], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                return 0
            except OSError:
                continue
    return 0


if __name__ == '__main__':
    sys.exit(main())
