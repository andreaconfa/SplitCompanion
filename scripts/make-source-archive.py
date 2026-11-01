#!/usr/bin/env python3
"""Make the corresponding source archive from an explicit public-file allowlist."""
import argparse
import gzip
from pathlib import Path
import tarfile

ROOT_FILES = {
    'Dockerfile', '.dockerignore', '.gitignore', '.env.example', 'compose.yaml',
    'README.md', 'ROADMAP.md', 'LICENSE', 'NOTICE', 'SECURITY.md', 'CONTRIBUTING.md', 'pyproject.toml',
}
ROOT_DIRS = {'backend', 'frontend', 'scripts', 'docs', 'wiki', '.github'}
EXCLUDED = {'.git', '.venv', 'node_modules', 'dist', '__pycache__', '.pytest_cache',
            '.ruff_cache', 'data', 'backups', 'artifacts', '.DS_Store'}


def source_files(root):
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if set(rel.parts) & EXCLUDED:
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink not allowed in release source: {rel}')
        if not path.is_file():
            continue
        if rel.parts[0] not in ROOT_DIRS and str(rel) not in ROOT_FILES:
            continue
        if path.name.startswith('.env') and str(rel) != '.env.example':
            continue
        if path.suffix in {'.db', '.key', '.pem', '.pyc', '.tar', '.gz'} or '.db-' in path.name:
            continue
        yield path, rel


def build(root, output):
    with output.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for path, rel in source_files(root):
                info = archive.gettarinfo(str(path), arcname=f'splitcompanion/{rel}')
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                with path.open('rb') as data:
                    archive.addfile(info, data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.root.resolve(), args.output.resolve())
