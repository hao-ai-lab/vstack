#!/usr/bin/env python3
"""Refuse a shell command that runs inline Python outside the project guard (a pre-command hook for agent shells).

Refused: a Python interpreter (python, python3, python3.12, pypy3, ipython, by name or path) started with -c, with
- as its program, or with no program at all, so that the code comes from a pipe, a here-document or the terminal;
also inside bash -c, sh -c, eval, env -S, find -exec, $(...) and backticks, and behind wrappers such as env, nice,
timeout, taskset, nohup, sudo, xargs and 'uv run'. Allowed: a script file, -m MODULE, --version and --help, and
everything that runs under a guard named by --guard (the guard as the command, or as the script given to a shell).

Input: the JSON a Claude Code PreToolUse hook receives on stdin (the command of a Bash tool call; other tools pass),
or --command TEXT. Exit 0: allowed; 2: refused, with the reason on stderr, which the harness shows to the agent;
1: unreadable input (reported, not blocking). Limits: commands that a shell reads from a pipe (echo ... | bash),
scripts the command writes and runs later, and aliases or functions are not seen; a here-document body is checked
only when a shell reads it. This is a guard rail against a habit, not a sandbox.
"""

import argparse
import json
import os
import re
import shlex
import sys

PYTHON = re.compile(r"(?:i?python|pypy)(?:[0-9]+(?:\.[0-9]+)*[a-z]?)?")
SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}
KEYWORDS = {"if", "then", "else", "elif", "while", "until", "do", "!", "{", "}"}
PUNCT = ";&|()<>\n"
# wrapper: (options that take a value, positional words before the command)
WRAPPERS = {
    "env": ({"-u", "--unset", "-C", "--chdir"}, 0),
    "nice": ({"-n", "--adjustment"}, 0),
    "nohup": (set(), 0),
    "timeout": ({"-s", "--signal", "-k", "--kill-after"}, 1),
    "taskset": (set(), 1),
    "ionice": ({"-c", "--class", "-n", "--classdata", "-t"}, 0),
    "chrt": (set(), 1),
    "stdbuf": ({"-i", "-o", "-e", "--input", "--output", "--error"}, 0),
    "setsid": (set(), 0),
    "time": ({"-f", "--format", "-o", "--output"}, 0),
    "command": (set(), 0),
    "builtin": (set(), 0),
    "exec": ({"-a"}, 0),
    "sudo": ({"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "-D", "--chdir", "-r", "-t"},
             0),
    "xargs": ({"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a", "--arg-file", "--delimiter", "--max-args",
               "--max-procs", "--max-lines", "--max-chars", "--replace", "--eof"}, 0),
    "numactl": ({"-C", "-N", "-m", "-p", "-i", "--physcpubind", "--cpunodebind", "--membind", "--preferred",
                 "--interleave"}, 0),
    "flock": ({"-w", "--timeout", "-E", "--conflict-exit-code"}, 1),
    "watch": ({"-n", "--interval"}, 0),
}
# tool run [options] command
RUNNERS = {"uv", "uvx", "poetry", "pdm", "pipenv", "conda", "mamba", "micromamba", "pixi", "hatch", "rye"}
RUNNER_VALUED = {"-n", "--name", "-p", "--prefix", "--with", "--python", "--directory", "--project", "--env-file",
                 "-e", "--environment", "--from", "--group", "--extra", "--package"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.S)
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z0-9_.-]+)\1")
BACKTICKS = re.compile(r"`([^`]*)`")


class Refused(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(1, f"ERROR arguments: {message}\n")


def substitutions(text):
    """The bodies of $(...) and backtick substitutions anywhere in the text, quoted or not."""
    bodies = BACKTICKS.findall(text)
    start = text.find("$(")
    while start != -1:
        depth, index = 0, start + 1
        while index < len(text):
            depth += {"(": 1, ")": -1}.get(text[index], 0)
            if depth == 0:
                break
            index += 1
        bodies.append(text[start + 2:index])
        start = text.find("$(", start + 2)
    return bodies


def drop_heredocs(text):
    """Remove here-document bodies, except those a shell reads, which stay as commands."""
    kept, closing = [], []
    for line in text.split("\n"):
        if closing:
            delimiter, keep = closing[0]
            if line.strip("\t") == delimiter:
                closing.pop(0)
            elif keep:
                kept.append(line)
            continue
        kept.append(line)
        for match in HEREDOC.finditer(line):
            before = line[:match.start()]
            words = re.findall(r"[^\s;&|()]+", before)
            closing.append((match.group(2), any(os.path.basename(w) in SHELLS for w in words)))
    return "\n".join(kept)


def simple_commands(text):
    # A backslash-newline continues the line; comments are not stripped, so a comment cannot hide a newline.
    lexer = shlex.shlex(drop_heredocs(text.replace("\\\n", " ")), posix=True, punctuation_chars=PUNCT)
    lexer.commenters = ""
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands, words, skip_next = [], [], False
    for token in lexer:
        if token and all(ch in PUNCT for ch in token):
            if any(ch in token for ch in "<>") and not any(ch in token for ch in ";|()\n"):
                skip_next = True  # a redirection: the next word is its target, not an argument
                if "<<" in token and "<<<" not in token:
                    words.append("<<")  # a here-document feeds the command's standard input
                continue
            if words:
                commands.append(words)
            words, skip_next = [], False
            continue
        if skip_next:
            skip_next = False
            continue
        words.append(token)
    if words:
        commands.append(words)
    return commands


class Checker:
    def __init__(self, guards):
        self.guards = [g.lstrip("./") for g in guards]

    def is_guard(self, word):
        word = word.lstrip("./")
        return any(word == g or word.endswith("/" + g) or os.path.basename(word) == g for g in self.guards)

    def check(self, text, depth=0):
        if depth > 8:
            return
        for body in substitutions(text):
            self.check(body, depth + 1)
        try:
            commands = simple_commands(text)
        except ValueError:
            # Unbalanced quotes: fall back to a plain search for the two refused forms.
            if re.search(r"(?:^|[\s;&|(`])(?:\S*/)?(?:i?python|pypy)[0-9.]*\s+(?:-[A-Za-z]*c|-(?=\s|$))", text):
                raise Refused("inline Python (-c or -) in a command that could not be parsed")
            return
        for words in commands:
            self.command(words, depth)

    def command(self, words, depth):
        index = 0
        while index < len(words):
            word = words[index]
            name = os.path.basename(word)
            if ASSIGNMENT.fullmatch(word) or word in KEYWORDS:
                index += 1
                continue
            if word == "<<":
                return
            if self.is_guard(word):
                return
            if name == "command" and any(w in {"-v", "-V"} for w in words[index + 1:index + 3]):
                return  # a lookup, not a run
            if name in WRAPPERS:
                index = self.skip_wrapper(name, words, index + 1, depth)
                continue
            if name in RUNNERS and index + 1 < len(words) and words[index + 1] in {"run", "exec"}:
                index = self.skip_options(words, index + 2, RUNNER_VALUED)
                continue
            if name == "eval":
                self.check(" ".join(words[index + 1:]), depth + 1)
                return
            if name == "find":
                self.find_exec(words[index + 1:], depth)
                return
            if name in SHELLS:
                self.shell(words[index + 1:], depth)
                return
            if PYTHON.fullmatch(name):
                self.python(word, words[index + 1:])
            return

    def skip_options(self, words, index, valued):
        while index < len(words) and words[index].startswith("-") and words[index] != "-":
            if words[index] == "--":
                return index + 1
            index += 2 if words[index] in valued else 1
        return index

    def skip_wrapper(self, name, words, index, depth):
        valued, positional = WRAPPERS[name]
        while index < len(words) and words[index].startswith("-") and words[index] != "-":
            option = words[index]
            if option == "--":
                index += 1
                break
            if name == "env" and option.split("=", 1)[0] in {"-S", "--split-string"}:
                value = option.split("=", 1)[1] if "=" in option else (words[index + 1] if index + 1 < len(words)
                                                                       else "")
                self.check(value, depth + 1)
                return len(words)
            index += 2 if option in valued else 1
        if name == "env":
            while index < len(words) and ASSIGNMENT.fullmatch(words[index]):
                index += 1
        return index + positional

    def find_exec(self, args, depth):
        for index, word in enumerate(args):
            if word in {"-exec", "-execdir", "-ok", "-okdir"}:
                end = next((i for i in range(index + 1, len(args)) if args[i] in {";", "+", "\\;"}), len(args))
                self.command(args[index + 1:end], depth)

    def shell(self, args, depth):
        index, inline = 0, False
        while index < len(args) and args[index][:1] in {"-", "+"} and args[index] not in {"-", "--"}:
            option = args[index]
            if option in {"-o", "+o", "-O", "+O"}:
                index += 2
                continue
            inline = inline or (option.startswith("-") and "c" in option[1:])
            index += 1
        if index < len(args) and args[index] == "--":
            index += 1
        if inline:
            if index < len(args):
                self.check(args[index], depth + 1)
        elif index < len(args) and self.is_guard(args[index]):
            return

    def python(self, word, args):
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "<<":
                break
            if arg == "-":
                raise Refused(f"{word} - reads the program from standard input")
            if arg == "--":
                if index + 1 < len(args) and args[index + 1] != "<<":
                    return
                break
            if arg.startswith("--"):
                if arg.split("=", 1)[0] in {"--version", "--help", "--help-env", "--help-xoptions", "--help-all"}:
                    return
                index += 2 if arg == "--check-hash-based-pycs" else 1
                continue
            if arg.startswith("-") and len(arg) > 1:
                flags = arg[1:]
                for position, flag in enumerate(flags):
                    if flag == "c":
                        raise Refused(f"{word} -c runs code given on the command line")
                    if flag in "mVh?":
                        return
                    if flag in "WX":
                        if position == len(flags) - 1:
                            index += 1
                        break
                index += 1
                continue
            return  # the program file
        raise Refused(f"{word} without a program file reads its code from standard input")


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                    formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--guard", action="append", default=[], metavar="PATH",
                        help="the project guard, as a path suffix such as compute/guard.sh (repeat for several)")
    parser.add_argument("--command", metavar="TEXT", help="check this command instead of reading hook JSON")
    parser.add_argument("--hint", metavar="TEXT", help="how to run Python through the guard, shown on refusal")
    args = parser.parse_args()
    if args.command is not None:
        command = args.command
    else:
        try:
            event = json.load(sys.stdin)
        except (ValueError, UnicodeError) as exc:
            print(f"ERROR hook input is not JSON: {exc}", file=sys.stderr)
            return 1
        tool_input = event.get("tool_input") if isinstance(event, dict) else None
        if not isinstance(tool_input, dict) or event.get("tool_name", "Bash") != "Bash":
            return 0
        command = tool_input.get("command")
        if not isinstance(command, str):
            return 0
    try:
        Checker(args.guard).check(command)
    except Refused as exc:
        guard = f" through the project guard ({', '.join(args.guard)})" if args.guard else ""
        hint = f" For example: {args.hint}" if args.hint else ""
        print(f"refused: inline Python outside the project guard: {exc}. Write the code to a file and run the "
              f"file{guard}.{hint}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
