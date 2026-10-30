# Contributing to Toki

Issues and pull requests are welcome at https://github.com/Czar-16/Toki.

1. Fork and clone the repository.
2. Install Python 3.10+ and Fish 3.6+ using the README instructions.
3. Make your change and update the command reference if behavior changes.
4. Run `fish -n fish/*.fish` and `python3 -m unittest discover -s tests -v`.
5. Open a pull request describing the change and how you checked it.

No pip packages are needed. Tests isolate their statistics in temporary folders.
GitHub Actions runs the checks on Linux and macOS. Include your operating
system, `python3 --version`, `fish --version`, command, and error output in
bug reports. Please do not attach personal study data unless you intend to share it.

Code is licensed under MIT. Keep the original copyright and attribution notices.
