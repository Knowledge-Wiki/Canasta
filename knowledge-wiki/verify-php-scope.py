#!/usr/bin/env python3
"""CI-only comparison with the exact image previously deployed on AK PROD/TEST.

This is not copied into the image and does not run during wiki startup.
Docker exports are streamed so two complete filesystem copies need not fit on disk.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

BASE = 'ghcr.io/canastawiki/canasta@sha256:e2d3f9ca1441ac3ec8d2aa8e972abc493984af1a4cc16fe2b17c866ec3954e84'
DEPLOYED = 'ghcr.io/canastawiki/canasta@sha256:52b756f614823d56a359d1182b30998a6e629d46d41c388c4234232dcb1b0920'
PHP_VERSION = '8.2.35-1~deb12u1'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def packages(image):
    raw = docker('run', '--rm', '--network', 'none', '--entrypoint', 'dpkg-query',
                 image, '-W', '-f=${binary:Package}\t${source:Package}\t${Version}\n')
    return {fields[0]: fields[1:] for row in raw.splitlines()
            if len(fields := row.split('\t')) == 3}


def filesystem(image):
    container = docker('create', '--entrypoint', '/bin/true', image)
    result = {}
    try:
        with subprocess.Popen(['docker', 'export', container], stdout=subprocess.PIPE) as process:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    name = member.name.lstrip('./')
                    # Docker supplies these per-container, independently of the image.
                    if name in ('etc/hostname', 'etc/hosts', 'etc/resolv.conf'):
                        continue
                    digest = None
                    if member.isfile():
                        h = hashlib.sha256()
                        with archive.extractfile(member) as source:
                            for block in iter(lambda: source.read(1024 * 1024), b''):
                                h.update(block)
                        digest = h.hexdigest()
                    result[name] = (member.type.decode(), member.mode, member.uid,
                                    member.gid, member.linkname, digest)
            if process.wait() != 0:
                raise RuntimeError('docker export failed')
    finally:
        docker('rm', '-v', container)
    return result


def main():
    candidate = sys.argv[1]
    output = Path(sys.argv[2] if len(sys.argv) > 2 else 'validation/php-scope.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(docker('manifest', 'inspect', DEPLOYED))
    assert any(x['digest'] == BASE.split('@')[1] and
               x['platform']['architecture'] == 'amd64' and x['platform']['os'] == 'linux'
               for x in manifest['manifests']), 'Base is not the deployed AMD64 member'
    docker('pull', '--platform', 'linux/amd64', BASE)
    before, after = [json.loads(docker('image', 'inspect', image))[0] for image in (BASE, candidate)]
    assert before['Architecture'] == after['Architecture'] == 'amd64'
    assert before['Os'] == after['Os'] == 'linux'
    assert after['RootFS']['Layers'][:-1] == before['RootFS']['Layers'], 'Expected exactly one PHP upgrade layer'
    a, b = before['Config'].copy(), after['Config'].copy()
    allowed_labels = {'org.opencontainers.image.source', 'org.opencontainers.image.revision',
                      'org.opencontainers.image.title'}
    for config in (a, b):
        config['Labels'] = {k: v for k, v in (config.get('Labels') or {}).items() if k not in allowed_labels}
    assert a == b, 'Runtime image configuration changed (environment, command, user, volumes, etc.)'

    p, q = packages(BASE), packages(candidate)
    changed = {name: {'before': p.get(name), 'after': q.get(name)}
               for name in p.keys() | q.keys() if p.get(name) != q.get(name)}
    php = [name for name, (source, version) in p.items() if source == 'php8.2']
    assert changed and set(changed) == set(php), 'Package changes extend beyond the installed php8.2 source packages'
    assert all(q[name] == ['php8.2', PHP_VERSION] for name in php), 'Unexpected PHP package version'
    owned = set()
    for image in (BASE, candidate):
        owned.update(line.lstrip('/') for line in docker(
            'run', '--rm', '--network', 'none', '--entrypoint', 'dpkg-query', image, '-L', *php
        ).splitlines() if line.startswith('/'))

    print('Comparing complete image filesystems with the deployed baseline...', flush=True)
    old, new = filesystem(BASE), filesystem(candidate)
    changes = []
    forbidden = []
    for name in sorted(old.keys() | new.keys()):
        if old.get(name) == new.get(name):
            continue
        if name.startswith('var/www/mediawiki/') or name.endswith('.sh') and '/' not in name:
            reason = None  # Application files and startup scripts must be byte-for-byte identical.
        elif name in owned:
            reason = 'PHP package-owned file'
        elif name.startswith(('var/lib/dpkg/info/php8.2', 'var/lib/apt/lists/',
                              'var/cache/apt/', 'var/log/apt/')):
            reason = 'Package-manager metadata/cache/log'
        elif name in {'var/lib/dpkg/status', 'var/lib/dpkg/status-old',
                      'var/lib/dpkg/triggers/File', 'var/lib/apt/extended_states', 'var/log/dpkg.log',
                      'var/log/alternatives.log', 'etc/ld.so.cache',
                      'var/cache/ldconfig/aux-cache'}:
            reason = 'Package-manager bookkeeping / linker cache'
        else:
            reason = None
        changes.append({'path': name, 'reason': reason,
                        'change': 'added' if name not in old else 'removed' if name not in new else 'modified'})
        if reason is None:
            forbidden.append(name)
    report = {'deployed_baseline': DEPLOYED, 'amd64_baseline': BASE,
              'candidate': candidate, 'runtime_config_unchanged': True,
              'package_changes': changed, 'filesystem_changes': changes,
              'unexpected_files': forbidden, 'passed': not forbidden}
    output.write_text(json.dumps(report, indent=2) + '\n')
    assert not forbidden, 'Unexpected non-PHP filesystem changes: ' + ', '.join(forbidden)
    print(f'PASS: {len(changed)} PHP packages upgraded; {len(changes)} reviewed file changes; '
          'application files, startup scripts and runtime settings unchanged', flush=True)


if __name__ == '__main__':
    main()
