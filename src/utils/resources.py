import os
import sys


def _src_dir():
    """Directory containing the application's Python modules (src/ in a checkout)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_dir():
    """Directory for user-editable files (config, logs).

    Frozen: next to the executable, so the shipped config.yml is found regardless
    of the working directory a shortcut launches us with.
    Source checkout: src/, which is where config.yml lives.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _src_dir()


def resource_path(relative_path):
    """Absolute path to a bundled read-only resource (icons, logo)."""
    base = getattr(sys, "_MEIPASS", None) or _src_dir()
    return os.path.join(base, relative_path)
