import importlib.util
from pathlib import Path
import tarfile


def test_archive_excludes_private_inputs_and_has_reproducible_metadata(tmp_path):
    script = Path(__file__).resolve().parents[2] / 'scripts/make-source-archive.py'
    spec = importlib.util.spec_from_file_location('source_archive', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / 'root'
    for name in ['README.md', 'LICENSE', '.env', 'private.key', 'ios/Private.swift',
                 'frontend/src/App.tsx', 'frontend/node_modules/private/package.json',
                 'backend/app/main.py', 'data/user.db', '.git/config']:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic')
    (root / 'frontend/node_modules/private/link').symlink_to(root / '.env')
    first, second = tmp_path / 'first.tar.gz', tmp_path / 'second.tar.gz'
    module.build(root, first)
    module.build(root, second)
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as archive:
        assert set(archive.getnames()) == {
            'splitcompanion/LICENSE', 'splitcompanion/README.md',
            'splitcompanion/backend/app/main.py', 'splitcompanion/frontend/src/App.tsx',
        }
        assert all(m.uid == m.gid == m.mtime == 0 and m.uname == m.gname == '' for m in archive)
