"""Write a small Git repository object by object, for tests of the scripts that read Git history.

The objects, refs and HEAD are written as files, so a test needs no Git command that changes state and no user
configuration (identity, signing, hooks). Git itself only reads the result.
"""

import hashlib
from pathlib import Path
import zlib

AUTHOR = 'Test Author <test@example.com> 1700000000 +0000'


class Repo:
    def __init__(self, root):
        self.root = Path(root)
        self.dot = self.root / '.git'
        for name in ('objects', 'refs/heads', 'refs/tags'):
            (self.dot / name).mkdir(parents=True, exist_ok=True)
        (self.dot / 'HEAD').write_text('ref: refs/heads/main\n')
        (self.dot / 'config').write_text('[core]\n\trepositoryformatversion = 0\n\tbare = false\n')
        self.head = None

    def write_object(self, kind, body):
        data = f'{kind} {len(body)}'.encode() + b'\0' + body
        sha = hashlib.sha1(data).hexdigest()
        path = self.dot / 'objects' / sha[:2] / sha[2:]
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(zlib.compress(data))
        return sha

    def tree(self, files):
        """files: {'dir/name': bytes | str | ('link', target) | ('exec', bytes)}"""
        here, below = {}, {}
        for path, content in files.items():
            head, _, rest = path.partition('/')
            if rest:
                below.setdefault(head, {})[rest] = content
            else:
                here[head] = content
        items = []
        for name, content in here.items():
            mode = '100644'
            if isinstance(content, tuple):
                mode = {'link': '120000', 'exec': '100755'}[content[0]]
                content = content[1]
            if isinstance(content, str):
                content = content.encode()
            items.append((name, mode, self.write_object('blob', content)))
        for name, children in below.items():
            items.append((name, '40000', self.tree(children)))
        # Git orders entries by name, comparing a directory's name as if it ended with '/'.
        items.sort(key=lambda item: item[0].encode() + (b'/' if item[1] == '40000' else b''))
        body = b''.join(f'{mode} {name}'.encode() + b'\0' + bytes.fromhex(sha) for name, mode, sha in items)
        return self.write_object('tree', body)

    def commit(self, files, message, parents=None, ref='main'):
        """Commit a whole tree; parents default to the current head of the branch."""
        if parents is None:
            current = self.ref(ref)
            parents = [current] if current else []
        lines = [f'tree {self.tree(files)}', *[f'parent {p}' for p in parents],
                 f'author {AUTHOR}', f'committer {AUTHOR}', '', message]
        sha = self.write_object('commit', ('\n'.join(lines) + '\n').encode())
        (self.dot / 'refs' / 'heads' / ref).write_text(sha + '\n')
        return sha

    def ref(self, name='main'):
        path = self.dot / 'refs' / 'heads' / name
        return path.read_text().strip() if path.exists() else None

    def checkout_files(self, files):
        """Write the files of a tree into the working directory (no index is written)."""
        for path, content in files.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, tuple):
                if content[0] == 'link':
                    target.symlink_to(content[1])
                    continue
                content = content[1]
            target.write_bytes(content.encode() if isinstance(content, str) else content)
