#!/usr/bin/env python3
"""Refuse a shell command that runs inline Python outside the project guard (a pre-command hook for agent shells).

Refused: a Python interpreter (python, python3, python3.12, pypy3, ipython, by name or path) started with -c, with
- as its program (also after --), with a program read from a file descriptor (/dev/stdin, /dev/fd/N,
/proc/self/fd/N), or with no program at all, so that the code comes from a pipe, a here-document or the terminal;
also inside bash -c, sh -c, eval, env -S, flock -c, find -exec, coproc, $(...), backticks, <(...) and here-documents
a shell reads, and behind wrappers such as env, nice, timeout, taskset, nohup, sudo, xargs and 'uv run'. Allowed: a
script file, -m MODULE, --version and --help, and everything that runs under a guard named by --guard (the guard as
the command, or as the script given to a shell).

The command is read with the shell's own quoting rules: quotes, backslashes, line continuations, comments,
redirections with a file descriptor number (2>/dev/null), here-documents with quoted or escaped delimiters, and
nested substitutions. A command that cannot be read (an unclosed quote) is refused when it names a Python
interpreter at all.

Input: the JSON a Claude Code PreToolUse hook receives on stdin (the command of a Bash tool call; other tools pass),
or --command TEXT. Exit 0: allowed; 2: refused, with the reason on stderr, which the harness shows to the agent;
1: unreadable input (reported, not blocking).

Limits: the hook reads text; it does not run a shell. It knows the options of the wrappers named above and of
bash, env and the Python interpreter, and nothing else: a program it does not model that starts another program
(su -c, script -c, ssh, parallel, make, awk system(), perl -e and the like) passes; so do commands a shell reads
from a pipe (echo ... | bash), scripts the command writes and runs later, aliases and functions, variables that
expand to a command ($CMD -c ...), a program file that is a link to standard input or a FIFO, and a here-document
body unless a shell reads it. No list of patterns closes these: the hook is a guard rail against a habit, not a
sandbox.
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
# Operators, longest first; the redirections among them take the next word as their target.
OPERATORS = ("&>>", "<<<", "<<-", "<<", ">>", "<&", ">&", "<>", ">|", "&>", "&&", "||", ";;", "|&", "<", ">", ";",
             "&", "|", "(", ")")
REDIRECTIONS = {"&>>", "<<<", "<<-", "<<", ">>", "<&", ">&", "<>", ">|", "&>", "<", ">"}
WORD_END = " \t\r\n;&|()<>"
# A program read from a file descriptor: standard input or a here-document or pipe given to another descriptor.
FD_PROGRAM = re.compile(r"/dev/stdin|/dev/fd/[0-9]+|/proc/(?:self|thread-self|[0-9]+)/fd/[0-9]+")
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
# tool [global options] run [options] command
RUNNERS = {"uv", "uvx", "poetry", "pdm", "pipenv", "conda", "mamba", "micromamba", "pixi", "hatch", "rye"}
RUNNER_VALUED = {"-n", "--name", "-p", "--prefix", "--with", "--python", "--directory", "--project", "--env-file",
                 "-e", "--environment", "--from", "--group", "--extra", "--package", "--cache-dir", "--config-file",
                 "--color", "--index-url", "--root-prefix", "-r", "--manifest-path"}
# bash and sh long options that take a value; every other long option is a flag
SHELL_VALUED = {"--init-file", "--rcfile"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.S)
# For text that cannot be read: any Python interpreter named as a word.
UNREAD = re.compile(r"(?:^|[\s;&|(`'\"])(?:\S*/)?(?:i?python|pypy)[0-9.]*(?=$|[\s;&|()<>`'\"])")


class Refused(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(1, f"ERROR arguments: {message}\n")


class Lexer:
    """Split shell text into simple commands (lists of words) and the code it hands to other shells.

    Quotes and backslashes are removed as the shell removes them. A redirection and its target are dropped,
    except that a here-document on standard input leaves the word '<<' in the command. The bodies of $(...),
    backticks and <(...) and the here-documents of a command that names a shell are returned for checking.
    Raises ValueError on text the shell could not read either (an unclosed quote or substitution)."""

    def __init__(self, text):
        self.text, self.pos = text, 0
        self.commands, self.bodies = [], []
        self.words, self.word, self.skip_next = [], None, False
        self.pending, self.heredocs = [], []

    def run(self):
        text = self.text
        while self.pos < len(text):
            char = text[self.pos]
            if char == "\\":
                if text.startswith("\n", self.pos + 1):
                    self.pos += 2  # a line continuation joins the words around it
                else:
                    self.add(text[self.pos + 1:self.pos + 2])
                    self.pos += 2
            elif char == "'":
                end = text.find("'", self.pos + 1)
                if end == -1:
                    raise ValueError("unclosed single quote")
                self.add(text[self.pos + 1:end])
                self.pos = end + 1
            elif char == '"':
                self.pos = self.double_quoted(self.pos)
            elif text.startswith("$'", self.pos):
                self.pos = self.ansi_quoted(self.pos)
            elif text.startswith("$(", self.pos) or text.startswith(("<(", ">("), self.pos):
                body, end = self.parenthesized(self.pos + 2)
                self.bodies.append(body)
                self.add(text[self.pos:end] if char == "$" else "/dev/fd/63")
                self.pos = end
            elif char == "`":
                body, end = self.backticked(self.pos)
                self.bodies.append(body)
                self.add(text[self.pos:end])
                self.pos = end
            elif char == "#" and self.word is None:
                end = text.find("\n", self.pos)
                self.pos = len(text) if end == -1 else end  # a comment runs to the end of its line
            elif char in " \t\r":
                self.end_word()
                self.pos += 1
            elif char == "\n":
                self.end_command()
                self.pos += 1
                self.read_heredocs()
            else:
                operator = next((op for op in OPERATORS if text.startswith(op, self.pos)), None)
                if operator is None:
                    self.add(char)
                    self.pos += 1
                    continue
                if operator in REDIRECTIONS and self.word is not None and self.word.isdigit():
                    self.word = None  # a file descriptor number (2>/dev/null), not an argument
                else:
                    self.end_word()
                self.pos += len(operator)
                if operator in ("<<", "<<-"):
                    self.pending.append((self.words, self.delimiter(), operator == "<<-"))
                    self.words.append("<<")  # the command reads a here-document on standard input
                elif operator in REDIRECTIONS:
                    self.skip_next = True  # the next word is the redirection's target
                else:
                    self.end_command()
        self.end_command()
        for words, body in self.heredocs:
            if any(os.path.basename(word) in SHELLS for word in words):
                self.bodies.append(body)  # a shell runs the here-document as commands
        return self.commands, self.bodies

    def add(self, text):
        self.word = (self.word or "") + text

    def end_word(self):
        if self.word is not None:
            if self.skip_next:
                self.skip_next = False
            else:
                self.words.append(self.word)
        self.word = None

    def end_command(self):
        self.end_word()
        if self.words:
            self.commands.append(self.words)
        self.words, self.skip_next = [], False

    def double_quoted(self, start):
        text, index = self.text, start + 1
        self.add("")
        while index < len(text):
            char = text[index]
            if char == '"':
                return index + 1
            if char == "\\" and index + 1 < len(text) and text[index + 1] in '$`"\\\n':
                if text[index + 1] != "\n":
                    self.add(text[index + 1])
                index += 2
            elif text.startswith("$(", index):
                body, end = self.parenthesized(index + 2)
                self.bodies.append(body)
                self.add(text[index:end])
                index = end
            elif char == "`":
                body, end = self.backticked(index)
                self.bodies.append(body)
                self.add(text[index:end])
                index = end
            else:
                self.add(char)
                index += 1
        raise ValueError("unclosed double quote")

    def ansi_quoted(self, start):
        text, index = self.text, start + 2
        self.add("")
        while index < len(text):
            if text[index] == "\\":
                self.add(text[index:index + 2])
                index += 2
            elif text[index] == "'":
                return index + 1
            else:
                self.add(text[index])
                index += 1
        raise ValueError("unclosed $'...' quote")

    def parenthesized(self, start):
        """The body of a substitution opened before start, and the index after its closing parenthesis."""
        text, index, depth = self.text, start, 1
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
            elif char == "'":
                end = text.find("'", index + 1)
                if end == -1:
                    raise ValueError("unclosed single quote")
                index = end + 1
            elif char == '"':
                index = self.skip_double(index)
            elif char == "`":
                index = self.backticked(index)[1]
            elif char in "()":
                depth += 1 if char == "(" else -1
                index += 1
                if depth == 0:
                    return text[start:index - 1], index
            else:
                index += 1
        raise ValueError("unclosed substitution")

    def skip_double(self, start):
        text, index = self.text, start + 1
        while index < len(text):
            if text[index] == "\\":
                index += 2
            elif text[index] == '"':
                return index + 1
            elif text.startswith("$(", index):
                index = self.parenthesized(index + 2)[1]
            elif text[index] == "`":
                index = self.backticked(index)[1]
            else:
                index += 1
        raise ValueError("unclosed double quote")

    def backticked(self, start):
        text, index, body = self.text, start + 1, ""
        while index < len(text):
            if text[index] == "\\" and index + 1 < len(text):
                body += text[index + 1] if text[index + 1] in "$`\\" else text[index:index + 2]
                index += 2
            elif text[index] == "`":
                return body, index + 1
            else:
                body += text[index]
                index += 1
        raise ValueError("unclosed backtick")

    def delimiter(self):
        """The here-document delimiter after << with its quotes and backslashes removed."""
        text = self.text
        while self.pos < len(text) and text[self.pos] in " \t":
            self.pos += 1
        word = ""
        while self.pos < len(text) and text[self.pos] not in WORD_END:
            char = text[self.pos]
            if char in "'\"":
                end = text.find(char, self.pos + 1)
                if end == -1:
                    raise ValueError("unclosed quote in a here-document delimiter")
                word += text[self.pos + 1:end]
                self.pos = end + 1
            elif char == "\\":
                word += text[self.pos + 1:self.pos + 2]
                self.pos += 2
            else:
                word += char
                self.pos += 1
        if not word:
            raise ValueError("here-document without a delimiter")
        return word

    def read_heredocs(self):
        """Read the bodies of the here-documents opened on the line that just ended."""
        text = self.text
        for words, delimiter, strip in self.pending:
            body = []
            while self.pos < len(text):
                end = text.find("\n", self.pos)
                end = len(text) if end == -1 else end
                line, self.pos = text[self.pos:end], end + 1
                if (line.lstrip("\t") if strip else line) == delimiter:
                    break
                body.append(line)
            self.heredocs.append((words, "\n".join(body)))
        self.pending = []


class Checker:
    def __init__(self, guards):
        self.guards = [g.lstrip("./") for g in guards]

    def is_guard(self, word):
        word = word.lstrip("./")
        return any(word == g or word.endswith("/" + g) or os.path.basename(word) == g for g in self.guards)

    def check(self, text, depth=0):
        if depth > 8:
            return
        try:
            commands, bodies = Lexer(text).run()
        except ValueError as exc:
            # The shell cannot read it either, but it may run the lines before the error: refuse any interpreter.
            if UNREAD.search(text):
                raise Refused(f"a Python interpreter in a command that could not be read ({exc})")
            return
        for body in bodies:
            self.check(body, depth + 1)
        for words in commands:
            self.command(words, depth)

    def command(self, words, depth):
        index = 0
        while index < len(words):
            word = words[index]
            name = os.path.basename(word)
            if ASSIGNMENT.fullmatch(word) or word in KEYWORDS or word == "<<":
                index += 1  # an assignment, a keyword, or a here-document given before the command name
                continue
            if word == "coproc":
                # coproc [NAME] { commands; } or coproc command
                index += 2 if index + 2 < len(words) and words[index + 2] == "{" else 1
                continue
            if self.is_guard(word):
                return
            if name == "command" and any(w in {"-v", "-V"} for w in words[index + 1:index + 3]):
                return  # a lookup, not a run
            if name in WRAPPERS:
                index = self.skip_wrapper(name, words, index + 1, depth)
                continue
            if name in RUNNERS:
                after = self.skip_options(words, index + 1, RUNNER_VALUED)
                if after < len(words) and words[after] in {"run", "exec"}:
                    index = self.skip_options(words, after + 1, RUNNER_VALUED)
                    continue
                return
            if name == "eval":
                rest = words[index + 1:]
                self.check(" ".join(rest[1:] if rest[:1] == ["--"] else rest), depth + 1)  # eval -- ARGS
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

    def env_option(self, words, index, depth):
        """Index after one GNU env option at words[index], or None when -S/--split-string took the rest: its value,
        split, and the words after it form the command env runs."""
        option, following = words[index], words[index + 1] if index + 1 < len(words) else ""
        if option.startswith("--"):
            name, equals, value = option.partition("=")
            if name == "--split-string":
                taken = 1 if equals else 2
                self.check(" ".join([value if equals else following]
                                    + [shlex.quote(w) for w in words[index + taken:]]), depth + 1)
                return None
            return index + (2 if name in {"--unset", "--chdir"} and not equals else 1)
        for position, flag in enumerate(option[1:], 1):  # a cluster such as -iS or -iu NAME
            if flag in "uCS":
                rest = option[position + 1:]
                taken = 1 if rest else 2
                if flag == "S":
                    self.check(" ".join([rest or following] + [shlex.quote(w) for w in words[index + taken:]]),
                               depth + 1)
                    return None
                return index + taken
        return index + 1

    def skip_wrapper(self, name, words, index, depth):
        valued, positional = WRAPPERS[name]
        while index < len(words) and words[index].startswith("-") and words[index] != "-":
            option = words[index]
            if option == "--":
                index += 1
                break
            if name == "env":
                index = self.env_option(words, index, depth)
                if index is None:
                    return len(words)
                continue
            index += 2 if option in valued else 1
        if name == "env":
            while index < len(words) and ASSIGNMENT.fullmatch(words[index]):
                index += 1
        index += positional
        if name == "flock" and index < len(words) and words[index] in {"-c", "--command"}:
            if index + 1 < len(words):
                self.check(words[index + 1], depth + 1)  # flock FILE -c COMMAND runs COMMAND with sh -c
            return len(words)
        return index

    def find_exec(self, args, depth):
        for index, word in enumerate(args):
            if word in {"-exec", "-execdir", "-ok", "-okdir"}:
                end = next((i for i in range(index + 1, len(args)) if args[i] in {";", "+", "\\;"}), len(args))
                self.command(args[index + 1:end], depth)

    def shell(self, args, depth):
        index, inline = 0, False
        while index < len(args) and args[index][:1] in {"-", "+"} and args[index] not in {"-", "--"}:
            option = args[index]
            if option.startswith("--"):
                index += 2 if option in SHELL_VALUED else 1  # long options never hold -c
                continue
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
                index += 1  # standard input is a here-document; a program file may still follow
                continue
            if arg == "-":
                raise Refused(f"{word} - reads the program from standard input")
            if arg == "--":
                rest = [a for a in args[index + 1:] if a != "<<"]
                if rest and rest[0] != "-" and not FD_PROGRAM.fullmatch(rest[0]):
                    return
                if rest:
                    raise Refused(f"{word} -- {rest[0]} reads the program from standard input or a descriptor")
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
            if FD_PROGRAM.fullmatch(arg):
                raise Refused(f"{word} {arg} reads the program from standard input or a descriptor")
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
