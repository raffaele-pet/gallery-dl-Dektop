"""Update the local environment and apply verified upstream Instagram fixes."""
from importlib import metadata
from pathlib import Path
import subprocess
import sys

APP_DIR = Path(__file__).resolve().parent
INSTAGRAM_FIX_COMMIT = '569c0dfe9c1261a579492b9814293c83ff6dcc35'
INSTAGRAM_FIX_URL = (
    'https://codeberg.org/mikf/gallery-dl/archive/' + INSTAGRAM_FIX_COMMIT + '.tar.gz'
)


def instagram_fix_available():
    """Detect the official October 15 query changes, including in dev builds."""
    try:
        distribution = metadata.distribution('gallery-dl')
        source = Path(distribution.locate_file('gallery_dl/extractor/instagram.py'))
        source = source.read_text(encoding='utf-8')
        return all(flag in source for flag in (
            'PolarisProfileRingsGradientEnabledrelayprovider',
            'PolarisThreadsStyleCommentsEnabledrelayprovider',
        ))
    except (metadata.PackageNotFoundError, OSError):
        return False


def clear_instagram_cache():
    """Clear only extractor metadata; browser login sessions are preserved."""
    subprocess.run(
        [sys.executable, '-m', 'gallery_dl', '--config-ignore',
         '--cache-clear', 'instagram'],
        check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )


def update():
    print('Controllo gli aggiornamenti nell’ambiente locale…', flush=True)
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--upgrade',
         '--upgrade-strategy', 'eager', '-r', str(APP_DIR / 'requirements.txt')],
        check=True,
    )
    if not instagram_fix_available():
        print('Applico la correzione ufficiale Instagram del 15/10/2026 '
              '(versione di sviluppo, commit ' + INSTAGRAM_FIX_COMMIT[:10] + ')…',
              flush=True)
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', INSTAGRAM_FIX_URL],
            check=True,
        )
        if not instagram_fix_available():
            raise RuntimeError('La correzione Instagram non supera la verifica.')
    clear_instagram_cache()
    print('gallery-dl ' + metadata.version('gallery-dl') +
          ': correzione Instagram verificata; cache Instagram aggiornata.', flush=True)


if __name__ == '__main__':
    try:
        update()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Aggiornamento non riuscito: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
