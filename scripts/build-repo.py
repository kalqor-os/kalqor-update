#!/usr/bin/env python3
"""Build an APT repository. Only public data is written into docs/."""
import argparse
import datetime as dt
import email.utils
import gzip
import hashlib
import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = 'A7D7859659871390C7CBEEEAAD422A07D0AAE677'
URL = 'https://kalqor-os.github.io/kalqor-update/'

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)

def digest(data, algorithm='sha256'):
    return hashlib.new(algorithm, data).hexdigest()

def field(package, name):
    return subprocess.check_output(['dpkg-deb', '-f', str(package), name], text=True).strip()

def build(args):
    home = Path(args.gnupg_home).expanduser().resolve()
    if not home.is_dir():
        raise SystemExit(f'Signing-key directory not found: {home}. Set KALQOR_GNUPGHOME to your existing private GnuPG directory.')
    # A signing home must never be inside the public source repository.
    if home == ROOT or ROOT in home.parents:
        raise SystemExit('Keep the private GnuPG directory OUTSIDE this repository.')
    fingerprint = args.fingerprint.upper()
    if not re.fullmatch(r'[0-9A-F]{40}', fingerprint):
        raise SystemExit('A full 40-character signing-key fingerprint is required.')
    gpg = ['gpg', '--homedir', home]
    listing = subprocess.check_output([str(x) for x in gpg + ['--batch', '--with-colons', '--list-secret-keys', fingerprint]], text=True)
    if not any(line.startswith('fpr:') and line.split(':')[9] == fingerprint for line in listing.splitlines()):
        raise SystemExit('The expected private signing key was not found. No key was generated.')
    key = subprocess.check_output([str(x) for x in gpg + ['--batch', '--export-options', 'export-minimal', '--export', fingerprint]])
    if not key:
        raise SystemExit('Public-key export failed.')
    run(['dpkg', '--validate-version', args.version])
    scratch = ROOT / '.build'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='repository-', dir=scratch) as tmp:
        stage = Path(tmp) / 'docs'
        stage.mkdir()
        old = ROOT / 'docs'
        if old.exists():
            if any(p.is_symlink() for p in old.rglob('*')):
                raise SystemExit('Symlinks are not supported in the public repository.')
            shutil.copytree(old, stage, dirs_exist_ok=True)
        # Remove old signed entry points only in staging; preserve old by-hash data.
        suite = stage / 'dists/kalqor'
        suite.mkdir(parents=True, exist_ok=True)
        for name in ('Release', 'InRelease', 'Release.gpg'):
            (suite / name).unlink(missing_ok=True)
        (stage / 'kalqor-archive-keyring.gpg').write_bytes(key)
        (stage / 'SIGNING-KEY-FINGERPRINT.txt').write_text(fingerprint + '\n')
        (stage / '.nojekyll').touch()
        pkg = Path(tmp) / 'kalqor-release'
        (pkg / 'DEBIAN').mkdir(parents=True)
        (pkg / 'usr/share/kalqor').mkdir(parents=True)
        (pkg / 'DEBIAN/control').write_text(
            'Package: kalqor-release\nVersion: ' + args.version + '\nArchitecture: all\n'
            'Maintainer: Balaji Sangana\nSection: misc\nPriority: optional\n'
            'Description: KALQOR OS update-channel marker\n'
            ' A small package used to verify signed KALQOR package delivery.\n')
        (pkg / 'usr/share/kalqor/release-info').write_text('KALQOR OS\nUpdate channel: kalqor\nPackage version: ' + args.version + '\n')
        marker = Path(tmp) / 'kalqor-release.deb'
        run(['dpkg-deb', '--root-owner-group', '--build', pkg, marker], stdout=subprocess.DEVNULL, env={**os.environ, 'SOURCE_DATE_EPOCH': '1700000000'})
        for package in [marker] + [Path(p).expanduser().resolve() for p in args.add]:
            if not package.is_file() or package.is_symlink():
                raise SystemExit(f'Not a regular package file: {package}')
            name, version, arch = (field(package, key) for key in ('Package', 'Version', 'Architecture'))
            if not re.fullmatch(r'kalqor-[a-z0-9][a-z0-9+.-]*', name):
                raise SystemExit('This channel accepts only kalqor-* packages; retain Debian upstream for system packages.')
            if arch not in ('all', 'amd64'):
                raise SystemExit(f'Unsupported architecture: {arch}')
            run(['dpkg', '--validate-version', version])
            if any(c in version for c in '/\\\n\r'):
                raise SystemExit('Invalid version in filename.')
            if package.stat().st_size > 50 * 1024 * 1024:
                raise SystemExit('This starter accepts packages up to 50 MiB each.')
            dest = stage / 'pool/main' / name[:1] / name / f'{name}_{version}_{arch}.deb'
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and digest(dest.read_bytes()) != digest(package.read_bytes()):
                raise SystemExit(f'Package version already exists with different content: {dest.name}. Increase its version.')
            if not dest.exists():
                shutil.copyfile(package, dest)
            dest.chmod(0o644)
        index = suite / 'main/binary-amd64'
        index.mkdir(parents=True, exist_ok=True)
        packages = subprocess.check_output(['apt-ftparchive', 'packages', 'pool'], cwd=stage)
        files = {'main/binary-amd64/Packages': packages,
                 'main/binary-amd64/Packages.gz': gzip.compress(packages, mtime=0)}
        for relative, data in files.items():
            path = suite / relative
            path.write_bytes(data)
            hashed = path.parent / 'by-hash/SHA256' / digest(data)
            hashed.parent.mkdir(parents=True, exist_ok=True)
            hashed.write_bytes(data)
        now = dt.datetime.now(dt.timezone.utc)
        release = '\n'.join([
            'Origin: KALQOR OS', 'Label: KALQOR OS Updates',
            'Suite: kalqor', 'Codename: kalqor',
            'Date: ' + email.utils.format_datetime(now, usegmt=True),
            'Valid-Until: ' + email.utils.format_datetime(now + dt.timedelta(days=30), usegmt=True),
            'Architectures: amd64', 'Components: main',
            'Description: Signed KALQOR OS custom-package updates',
            'Acquire-By-Hash: yes', 'SHA256:',
        ]) + '\n'
        for relative, data in sorted(files.items()):
            release += f' {digest(data)} {len(data):16d} {relative}\n'
        release += 'SHA512:\n'
        for relative, data in sorted(files.items()):
            release += f' {digest(data, "sha512")} {len(data):16d} {relative}\n'
        (suite / 'Release').write_text(release)
        sign = gpg + ['--yes', '--local-user', fingerprint, '--digest-algo', 'SHA256']
        run(sign + ['--output', suite / 'InRelease', '--clearsign', suite / 'Release'])
        run(sign + ['--output', suite / 'Release.gpg', '--detach-sign', suite / 'Release'])
        run(['gpgv', '--keyring', stage / 'kalqor-archive-keyring.gpg', suite / 'InRelease'], stdout=subprocess.DEVNULL)
        run(['gpgv', '--keyring', stage / 'kalqor-archive-keyring.gpg', suite / 'Release.gpg', suite / 'Release'], stdout=subprocess.DEVNULL)
        (stage / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KALQOR OS Updates</title><style>body{font:16px/1.7 system-ui;background:#0c1b2c;color:#e4edf6;max-width:800px;margin:8vh auto;padding:24px}h1{font-size:42px}a{color:#e4b487}code{overflow-wrap:anywhere;color:#d4b28f}small{color:#94a7b9}</style><h1>KALQOR OS Updates</h1><p>Privacy. Choice. Control.</p><p>Signed APT packages for the KALQOR custom update channel. Debian repositories continue to supply Debian packages.</p><p><a href="kalqor-archive-keyring.gpg">Public signing key</a> · <a href="dists/kalqor/InRelease">Signed release metadata</a></p><p>Signing-key fingerprint:<br><code>''' + html.escape(fingerprint) + '''</code></p><p>Suite: <code>kalqor</code> · Component: <code>main</code> · Architecture: <code>amd64</code></p><p>Use the reviewed client installer from the source repository. Confirm the fingerprint through a trusted channel before adding this archive.</p><small>Developed by Balaji Sangana. Updated ''' + now.strftime('%Y-%m-%d %H:%M UTC') + '</small></html>')
        total = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
        if total > 900 * 1024 * 1024:
            raise SystemExit('Public repository exceeds the 900 MiB starter limit; review retention before publishing.')
        # Do not delete historical pool files: installed indexes may still reference them.
        shutil.copytree(stage, ROOT / 'docs', dirs_exist_ok=True)
    print('Built and signature-verified:', ROOT / 'docs')
    print('Expected Pages base URL after enabling Pages:', URL)
    print('Refresh/sign and publish the metadata at least every 30 days, before expiry.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gnupg-home', default=os.environ.get('KALQOR_GNUPGHOME', str(Path.home() / 'avuno-update-server/private/gnupg')))
    p.add_argument('--fingerprint', default=EXPECTED)
    p.add_argument('--version', default='0.1.0~preview1', help='Version of the safe kalqor-release marker package')
    p.add_argument('--add', action='append', default=[], metavar='PACKAGE.deb')
    build(p.parse_args())
