"""Install and verify current stable engines, including migration from dev builds."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import re
import subprocess
import sys
from network import http_session

APP_DIR = Path(__file__).resolve().parent
MIN_GALLERY_VERSION = (1, 32, 18)


def stable_version(value):
    if not re.fullmatch(r'\d+(?:\.\d+)+', value):
        raise ValueError('Versione stabile non valida: ' + value)
    return tuple(int(part) for part in value.split('.'))


def engine_ready():
    try:
        return stable_version(metadata.version('gallery-dl')) >= MIN_GALLERY_VERSION
    except (metadata.PackageNotFoundError, ValueError):
        return False


def latest_releases():
    releases = {}
    with http_session() as session:
        for package in ('gallery-dl', 'yt-dlp'):
            response = session.get('https://pypi.org/pypi/' + package + '/json',
                                   timeout=(15, 30))
            response.raise_for_status()
            version = response.json()['info']['version']
            stable_version(version)
            releases[package] = version
    if stable_version(releases['gallery-dl']) < MIN_GALLERY_VERSION:
        raise RuntimeError('L’indice non offre ancora una versione gallery-dl compatibile.')
    return releases


def clear_instagram_cache():
    """Only extractor metadata is cleared; browser sessions are preserved."""
    subprocess.run(
        [sys.executable, '-m', 'gallery_dl', '--config-ignore',
         '--cache-clear', 'instagram'],
        check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )


def verify_engines(releases):
    for package, module, ignore in (('gallery-dl', 'gallery_dl', '--config-ignore'),
                                    ('yt-dlp', 'yt_dlp', '--ignore-config')):
        result = subprocess.run(
            [sys.executable, '-m', module, ignore, '--version'],
            capture_output=True, text=True, check=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        installed = result.stdout.strip()
        if stable_version(installed) != stable_version(releases[package]):
            raise RuntimeError(package + ': attesa ' + releases[package] +
                               ', trovata ' + installed)
        print(package + ' ' + installed + ': verificato.', flush=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    # A fresh interpreter ensures newly installed TLS/browser/image/EJS modules load.
    subprocess.run(
        [sys.executable, '-c', 'import network, requests, bs4, PIL, playwright, '
         'yt_dlp_ejs; from gallery_dl import extractor; '
         'assert extractor.find("https://www.instagram.com/instagram/") is not None'],
        cwd=APP_DIR, check=True,
    )


def update():
    releases = latest_releases()
    for package, target in releases.items():
        try:
            before = metadata.version(package)
        except metadata.PackageNotFoundError:
            before = 'non installato'
        print(package + ': ' + before + ' → stabile ufficiale ' + target, flush=True)
    # Exact stable targets intentionally replace the old 1.33.0.dev0 snapshot even
    # when its numerical version is higher than the current stable release.
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
         '--upgrade', '-r', str(APP_DIR / 'requirements.txt'),
         'gallery-dl==' + releases['gallery-dl'],
         'yt-dlp[default]==' + releases['yt-dlp']],
        check=True,
    )
    verify_engines(releases)
    clear_instagram_cache()
    print('Motori, dipendenze e cache Instagram aggiornati e verificati.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependencies-only', action='store_true')
    parser.add_argument('--restart-required', action='store_true')
    args = parser.parse_args()
    if not args.dependencies_only:
        from app_update import update_application
        if update_application():
            # Reload the updater and requirements just retrieved, not old code.
            result = subprocess.run(
                [sys.executable, '-u', str(APP_DIR / 'maintenance.py'),
                 '--dependencies-only', '--restart-required'])
            raise SystemExit(result.returncode)
    update()
    print(json.dumps({'type': 'update_result', 'restart_required': args.restart_required}),
          flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    try:
        main()
    except Exception as exc:
        print('Aggiornamento non riuscito: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
