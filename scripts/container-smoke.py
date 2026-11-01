#!/usr/bin/env python3
"""Isolated Linux container acceptance: host folders, setup, recreate and restore."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--image', required=True)
args = parser.parse_args()
name = 'split-smoke-' + secrets.token_hex(5)


def docker(*argv):
    result = subprocess.run(['docker', *map(str, argv)], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('Docker smoke command failed: ' + str(argv[0]))
    return result.stdout.strip()


def request(path, body=None, headers=None):
    # All endpoints and data are local to the new disposable instance.
    code = '''import urllib.request,json
path,body,headers=json.loads(__import__('sys').argv[1])
data=None if body is None else json.dumps(body).encode()
request=urllib.request.Request('http://127.0.0.1:8000'+path,data=data,headers=headers or {})
with urllib.request.urlopen(request,timeout=10) as response: print(response.read().decode())'''
    return docker('exec', name, 'python', '-c', code, json.dumps([path, body, headers]))


def start(data, backups):
    docker('run', '-d', '--name', name, '--network', 'none', '--read-only',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
           '--mount', f'type=bind,src={data},dst=/data',
           '--mount', f'type=bind,src={backups},dst=/backups',
           '-e', 'SPLIT_COMPANION_ALLOW_HTTP=true',
           '-e', 'SPLIT_COMPANION_PUSH_ENABLED=false',
           '-e', 'SPLIT_COMPANION_SCHEDULER=false', args.image)
    for _ in range(60):
        try:
            if json.loads(request('/api/ready')) == {'status': 'ready'}:
                return
        except RuntimeError:
            pass
        time.sleep(1)
    raise RuntimeError('Container did not become ready')


def stop():
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


with tempfile.TemporaryDirectory(prefix='split-container-test-') as folder:
    root = Path(folder)
    data, backups, restored = (root / n for n in ('data', 'backups', 'restored'))
    for p in (data, backups, restored):
        p.mkdir()
        docker('run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'chown',
               '--mount', f'type=bind,src={p},dst=/folder', args.image, '10001:10001', '/folder')
    try:
        start(data, backups)
        meta = json.loads(request('/api/meta'))
        assert meta['setup_required'] and meta['api_version'] == 1 and meta['source_available']
        # Source is served from a fixed file; verify archive license, no native app or Git metadata.
        source_check = "import tarfile; t=tarfile.open('/app/source.tar.gz'); n=t.getnames(); assert 'splitcompanion/LICENSE' in n; assert not any('/ios/' in x or '/.git/' in x or x.endswith('/.env') for x in n); print('source-ok')"
        assert docker('exec', name, 'python', '-c', source_check) == 'source-ok'
        token = docker('exec', name, 'python', '-m', 'app.cli', 'setup-token').splitlines()[-1]
        password = secrets.token_urlsafe(24)
        request('/api/setup/complete', {'username': 'smoke', 'display_name': 'Smoke test', 'password': password},
                {'Content-Type': 'application/json', 'X-Setup-Token': token})
        assert not json.loads(request('/api/meta'))['setup_required']
        digest = docker('exec', name, 'python', '-c', "import hashlib; print(hashlib.sha256(open('/data/secret.key','rb').read()).hexdigest())")
        archive = docker('exec', name, 'python', '-m', 'app.cli', 'backup-full', '--output-dir', '/backups', '--kind', 'manual')
        stop()
        start(data, backups)
        assert not json.loads(request('/api/meta'))['setup_required']
        assert digest == docker('exec', name, 'python', '-c', "import hashlib; print(hashlib.sha256(open('/data/secret.key','rb').read()).hexdigest())")
        stop()
        docker('run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
               '--mount', f'type=bind,src={restored},dst=/data', '--mount', f'type=bind,src={backups},dst=/backups,readonly',
               args.image, 'python', '-m', 'app.cli', 'restore', archive, '--confirm')
        start(restored, backups)
        assert not json.loads(request('/api/meta'))['setup_required']
        assert digest == docker('exec', name, 'python', '-c', "import hashlib; print(hashlib.sha256(open('/data/secret.key','rb').read()).hexdigest())")
        print('PASS: app-only image, source offer, setup, bind persistence, container recreation, offline restore.')
    finally:
        stop()
        # Clean only our newly created, disposable directories, including non-root image-owned files.
        docker('run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'chmod',
               '--mount', f'type=bind,src={root},dst=/folder', args.image, '-R', 'a+rwX', '/folder')
