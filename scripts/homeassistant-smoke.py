#!/usr/bin/env python3
"""Exercise the Home Assistant adapter with Supervisor-like storage/options, offline."""
import argparse
import json
from pathlib import Path
import secrets
import re
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--image', required=True)
args = parser.parse_args()
name = 'split-ha-smoke-' + secrets.token_hex(5)
network = name + '-network'


def docker(*args):
    result = subprocess.run(['docker', *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Home Assistant smoke command failed: ' + str(args[0]))
    return result.stdout.strip()


def request(path, body=None, headers=None, expected_status=None):
    code = '''import json,urllib.request,urllib.error
path,body,headers,expected_status=json.loads(__import__('sys').argv[1])
data=None if body is None else json.dumps(body).encode()
r=urllib.request.Request('http://127.0.0.1:8000'+path,data=data,headers=headers or {})
try:
    with urllib.request.urlopen(r,timeout=10) as response:
        assert expected_status is None or response.status == expected_status
        print(response.read().decode())
except urllib.error.HTTPError as error:
    assert error.code == expected_status, error.code
    print(json.dumps({'status': error.code}))'''
    return json.loads(docker('exec', name, 'python', '-c', code, json.dumps([path, body, headers, expected_status])))


def stop():
    subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start(data):
    docker('run', '-d', '--name', name, '--network', network, '--ip', '172.30.32.3', '--read-only',
           '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
           '--mount', f'type=bind,src={data},dst=/data', args.image)
    for _ in range(60):
        try:
            if request('/api/ready') == {'status': 'ready'}:
                return
        except RuntimeError:
            pass
        time.sleep(1)
    raise RuntimeError('Home Assistant adapter did not become ready')


def ingress_checks(password):
    # A disposable client uses the documented Supervisor peer address. No host ports.
    code = r'''import json,re,sys,urllib.request,urllib.error
prefix='/api/hassio_ingress/smoke_token'
headers={'X-Ingress-Path':prefix,'X-Forwarded-Host':'ha.example:8123','X-Forwarded-Proto':'http'}
def req(path,body=None,extra=None,expected=200):
    data=None if body is None else json.dumps(body).encode()
    h={**headers,**(extra or {})}
    if data is not None: h['Content-Type']='application/json'
    r=urllib.request.Request('http://172.30.32.3:8099'+path,data=data,headers=h)
    try:
        with urllib.request.urlopen(r,timeout=10) as response:
            assert response.status==expected
            return response.read(),response.headers
    except urllib.error.HTTPError as error:
        assert error.code==expected,error.code
        return error.read(),error.headers
body,h=req('/groups/1')
assert ('<base href="'+prefix+'/"').encode() in body
assert b'<meta name="split-ingress" content="true">' in body
assert h['X-Frame-Options']=='SAMEORIGIN'
for asset in re.findall(r'(?:src|href)="(\./[^\"]+)"',body.decode()):
    req('/'+asset[2:])
req('/api/auth/me',expected=401)
body,h=req('/api/auth/login',{'username':'ha-smoke','password':sys.argv[1]}, {'Origin':'http://ha.example:8123'})
assert 'split_ingress_session=' in h['Set-Cookie'] and ('Path='+prefix+'/') in h['Set-Cookie']
headers['Cookie']=h['Set-Cookie'].split(';',1)[0]
csrf=json.loads(body)['csrf_token']
req('/api/auth/me')
req('/api/auth/logout',{},expected=403)
headers['X-CSRF-Token']=csrf
req('/api/auth/logout',{}, {'Origin':'https://evil.example'},expected=403)
_,h=req('/api/auth/logout',{}, {'Origin':'http://ha.example:8123'})
assert ('Path='+prefix+'/') in h['Set-Cookie']
req('/api/auth/me',expected=401)
print('PASS: trusted Ingress assets, account session, CSRF and logout')'''
    print(docker('run', '--rm', '--network', network, '--ip', '172.30.32.2',
                 '--read-only', '--entrypoint', 'python', args.image, '-c', code, password))
    # Even localhost must not reach the Ingress listener by spoofing proxy headers.
    reject = '''import urllib.request,urllib.error
try:
    urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8099/api/meta',headers={'X-Forwarded-For':'172.30.32.2'}))
    raise AssertionError('Ingress accepted an untrusted peer')
except urllib.error.HTTPError as e: assert e.code==403'''
    docker('exec', name, 'python', '-c', reject)

with tempfile.TemporaryDirectory(prefix='split-ha-test-') as folder:
    data = Path(folder)
    (data / 'options.json').write_text(json.dumps({'allow_http': True, 'initial_setup_code': 'legacy!invalid', 'mfa_required': False}))
    # Match Supervisor's readable volume root; only instance/backups are privately owned.
    data.chmod(0o755)
    try:
        docker('network', 'create', '--internal', '--subnet', '172.30.32.0/24', '--gateway', '172.30.32.1', network)
        start(data)
        assert request('/api/meta')['setup_required']
        status = docker('exec', name, 'python', '-c', "print(open('/proc/1/status').read())")
        assert 'Uid:\t10001\t10001\t10001\t10001' in status
        code = re.search(r'initial setup code: ([A-Za-z0-9_-]{43})', docker('logs', name)).group(1)
        stop()
        start(data)
        renewed = re.search(r'initial setup code: ([A-Za-z0-9_-]{43})', docker('logs', name)).group(1)
        assert renewed != code
        request('/api/setup/complete', {'username': 'ha-smoke', 'display_name': 'Demo', 'password': secrets.token_urlsafe(24)},
                {'Content-Type': 'application/json', 'X-Setup-Token': code}, expected_status=403)
        code = renewed
        password = secrets.token_urlsafe(24)
        request('/api/setup/complete', {'username': 'ha-smoke', 'display_name': 'Demo', 'password': password},
                {'Content-Type': 'application/json', 'X-Setup-Token': code})
        assert not request('/api/meta')['setup_required']
        ingress_checks(password)
        check = "import hashlib; print(hashlib.sha256(open('/data/instance/secret.key','rb').read()).hexdigest())"
        digest = docker('exec', name, 'python', '-c', check)
        archive = docker('exec', name, 'python', '/app/homeassistant.py',
                         'backup-full', '--output-dir', '/data/backups', '--kind', 'manual')
        assert archive.startswith('/data/backups/')
        owner_check = "import os,sys; assert os.stat(sys.argv[1]).st_uid == 10001"
        docker('exec', name, 'python', '-c', owner_check, archive)
        stop()
        start(data)
        assert not request('/api/meta')['setup_required']
        assert docker('exec', name, 'python', '-c', check) == digest
        assert 'initial setup code:' not in docker('logs', name)
        stop()
        # Restore offline to a second empty Supervisor volume, keeping options separate.
        restored = data / 'restore-target'
        restored.mkdir(mode=0o755)
        (restored / 'options.json').write_text(json.dumps({'allow_http': True}))
        docker('run', '--rm', '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
               '--mount', f'type=bind,src={restored},dst=/data',
               '--mount', f'type=bind,src={data / "backups"},dst=/restore-source,readonly',
               args.image, 'python', '/app/homeassistant.py', 'restore',
               '/restore-source/' + Path(archive).name, '--confirm')
        start(restored)
        assert not request('/api/meta')['setup_required']
        assert docker('exec', name, 'python', '-c', check) == digest
        assert 'initial setup code:' not in docker('logs', name)
        print('PASS: Home Assistant options, non-root server, private data, setup, backup, recreation and offline restore.')
    finally:
        stop()
        subprocess.run(['docker', 'network', 'rm', network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        docker('run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'chmod',
               '--mount', f'type=bind,src={data},dst=/folder', args.image, '-R', 'a+rwX', '/folder')
