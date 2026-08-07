from __future__ import annotations

import argparse
import os
import sys

try:
    import fcntl  # type: ignore
    import termios  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore
    termios = None  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("ComfyUI-Pi PTY helper: no Pi command was supplied.", file=sys.stderr, flush=True)
        return 127
    if os.name != "posix" or fcntl is None or termios is None or not hasattr(termios, "TIOCSCTTY"):
        print("ComfyUI-Pi PTY helper: controlling-terminal support is unavailable.", file=sys.stderr, flush=True)
        return 126
    try:
        # This helper is a fresh, single-threaded process. Creating a new session here
        # is safe, and TIOCSCTTY makes the already-wired slave PTY the controlling
        # terminal before Pi replaces this process image.
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        try:
            os.tcsetpgrp(0, os.getpgrp())
        except OSError:
            pass
        os.chdir(args.cwd)
        os.execvpe(command[0], command, os.environ.copy())
    except BaseException as exc:
        print(f"ComfyUI-Pi failed to start Pi in its controlling terminal: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 127
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
