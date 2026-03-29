from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .chat import DEFAULT_STATE_PATH, TeleportDog

try:
    import readline  # noqa: F401  # Enables line editing/history on supported platforms.
except ImportError:  # pragma: no cover
    readline = None

# Set up tab completion for readline if available
if readline:
    _COMMANDS = ['/help', '/mode', '/gen', '/learnglob', '/suggest', '/learn', '/save', '/quit', '/exit']

    def _completer(text, state):
        """Readline tab completion for teleportdog commands."""
        if state == 0:
            # First call: build the list of candidates
            if text.startswith('/'):
                candidates = [cmd for cmd in _COMMANDS if cmd.startswith(text.lower())]
            else:
                candidates = []
            _completer.candidates = candidates

        # Return the next candidate or None if exhausted
        if state < len(_completer.candidates):
            return _completer.candidates[state]
        return None

    _completer.candidates = []
    readline.set_completer(_completer)

HELP_TEXT = "\n".join(
    [
        "teleportdog commands:",
        "  /help                 show this help",
        "  /mode text            switch to plain text input",
        "  /mode t9              switch to T9 digit input",
        "  /mode gen             switch to local generative mode",
        "  /gen <text>           one-shot local generated reply",
        "  /learnglob <pattern>  import corpus files now (glob/file/dir)",
        "  /suggest <digits>     show candidates for one T9 sequence",
        "  /learn <text>         feed additional text to local model",
        "  /save                 persist model to default state path",
        "  /save <path>          persist model to custom path",
        "  /quit                 exit",
        "  /exit                 exit (alias for /quit)",
    ]
)


def run_chat(state_path: Path, corpus_inputs: list[str] | None = None) -> int:
    bot = TeleportDog.load_or_bootstrap(state_path, corpus_inputs=corpus_inputs)
    mode = "text"

    print("teleportdog: local tiny chat is online.")
    print(f"state: {state_path}")
    if corpus_inputs:
        print(f"corpus inputs: {', '.join(corpus_inputs)}")
    print("type /help for commands")

    while True:
        prompt = "you[t9]> " if mode == "t9" else ("you[gen]> " if mode == "gen" else "you> ")
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nteleportdog: bye")
            bot.save(state_path)
            return 0

        if not raw:
            continue

        if raw.startswith("/"):
            parts = raw.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "/help":
                print(HELP_TEXT)
                continue

            if cmd in {"/quit", "/exit"}:
                bot.save(state_path)
                print("teleportdog: state saved, bye")
                return 0

            if cmd == "/mode":
                if arg in {"text", "t9", "gen"}:
                    mode = arg
                    print(f"teleportdog: mode={mode}")
                else:
                    print("teleportdog: usage /mode text|t9|gen")
                continue

            if cmd == "/gen":
                if not arg:
                    print("teleportdog: usage /gen <text>")
                    continue
                reply = bot.generate_reply(arg)
                print(f"dog[gen]> {reply}")
                continue

            if cmd == "/suggest":
                if not arg:
                    print("teleportdog: usage /suggest <digits>")
                    continue
                cands = bot.t9.suggest(arg)
                if cands:
                    print("teleportdog:", ", ".join(cands))
                else:
                    print("teleportdog: no suggestions")
                continue

            if cmd == "/learn":
                if not arg:
                    print("teleportdog: usage /learn <text>")
                    continue
                bot.learn(arg)
                print("teleportdog: learned")
                continue

            if cmd == "/learnglob":
                if not arg:
                    print("teleportdog: usage /learnglob <globpattern>")
                    continue
                learned_files = bot.import_external_corpus([arg])
                if learned_files > 0:
                    print(f"teleportdog: learned from {learned_files} file(s)")
                else:
                    print("teleportdog: no new matching files")
                continue

            if cmd == "/save":
                save_path = Path(arg).expanduser() if arg else state_path
                bot.save(save_path)
                print(f"teleportdog: saved to {save_path}")
                continue

            print("teleportdog: unknown command. try /help")
            continue

        user_text = raw
        if mode == "t9":
            decoded, ambiguities = bot.t9.decode_phrase(raw)
            user_text = decoded
            print(f"you(decoded)> {user_text}")
            for digits, cands in ambiguities:
                print(f"teleportdog: {digits} could also be: {', '.join(cands[1:])}")

        if mode == "gen":
            reply = bot.generate_reply(user_text)
            print(f"dog[gen]> {reply}")
        else:
            reply = bot.reply(user_text)
            print(f"dog> {reply}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="teleportdog offline tiny chat")
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="state file path (default: ~/.teleportdog/state.json)",
    )
    parser.add_argument(
        "--corpus",
        action="append",
        default=[],
        metavar="PATH_OR_GLOB",
        help="optional corpus path or glob; pass multiple times for many sources",
    )
    args = parser.parse_args(argv)
    return run_chat(args.state.expanduser(), corpus_inputs=args.corpus)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
