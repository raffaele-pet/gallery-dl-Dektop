"""Update application files from the user's official repository."""
from datetime import datetime
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from network import http_session

APP_DIR = Path(__file__).resolve().parent
REPOSITORY = 'raffaele-pet/gallery-dl-windows-gui'
ALLOWED_FILES = {
    'app.py', 'engine.py', 'gallery_worker.py', 'maintenance.py', 'network.py',
    'app_update.py', 'requirements.txt', 'INSTALL.bat', 'RUN.vbs', 'RUN_DEBUG.cmd',
    'README.md', 'LICENSE', '.gitignore', '.gitattributes',
}


def git(*arguments, check=True):
    result = subprocess.run(
        ['git', '-C', str(APP_DIR), *arguments], check=False,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=90, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Operazione Git non riuscita.')
    return result


def update_application():
    """Fast-forward clean Git installs; ZIP installs keep backups of replaced files."""
    if (APP_DIR / '.git').exists():
        remote = git('remote', 'get-url', 'origin').stdout.strip().removesuffix('.git')
        if remote not in ('https://github.com/' + REPOSITORY,
                          'git@github.com:' + REPOSITORY):
            raise RuntimeError('Il remote Git non corrisponde alla repository dell’app.')
        if git('status', '--porcelain', '--untracked-files=no').stdout.strip():
            raise RuntimeError('Ci sono modifiche locali al codice. Salvale con Git prima di aggiornare.')
        if git('branch', '--show-current').stdout.strip() != 'main':
            raise RuntimeError('L’aggiornamento automatico richiede il ramo main.')
        before = git('rev-parse', 'HEAD').stdout.strip()
        git('fetch', '--quiet', 'origin', 'main')
        git('merge', '--ff-only', 'FETCH_HEAD')
        after = git('rev-parse', 'HEAD').stdout.strip()
        print('Applicazione: ' + ('aggiornata a ' + after[:10] if before != after
                                 else 'già aggiornata (' + after[:10] + ')'), flush=True)
        return before != after

    with http_session() as session:
        response = session.get('https://api.github.com/repos/' + REPOSITORY +
                               '/commits/main', timeout=(15, 30))
        response.raise_for_status()
        commit = response.json()['sha']
        if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('Risposta GitHub non valida.')
        response = session.get('https://codeload.github.com/' + REPOSITORY +
                               '/zip/' + commit, timeout=(15, 60))
        response.raise_for_status()
    return install_archive(response.content, commit)


def install_archive(data, commit):
    """Only shipped source/assets are replaceable; downloads and sessions stay local."""
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            parts = entry.filename.split('/')[1:]
            relative = '/'.join(parts)
            if not relative or any(p in ('..', '') for p in parts):
                continue
            allowed_asset = (len(parts) == 2 and parts[0] == 'assets' and
                             Path(parts[1]).suffix.lower() in ('.png', '.ico'))
            allowed_module = len(parts) == 1 and Path(relative).suffix.lower() == '.py'
            if relative in ALLOWED_FILES or allowed_asset or allowed_module:
                content = archive.read(entry)
                if Path(relative).suffix.lower() in ('.bat', '.cmd'):
                    content = content.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                files[relative] = content
    required = {'app.py', 'engine.py', 'maintenance.py', 'requirements.txt'}
    if not required <= files.keys():
        raise ValueError('L’archivio dell’applicazione è incompleto.')
    changes = {name: content for name, content in files.items()
               if not (APP_DIR / name).is_file() or (APP_DIR / name).read_bytes() != content}
    if not changes:
        print('Applicazione già aggiornata.', flush=True)
        return False
    backup = APP_DIR / '.update-backups' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    # Stage and validate the complete archive before replacing any application file.
    staging = backup / 'new'
    for name, content in changes.items():
        staged = staging / name
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(content)
        if name.endswith('.py'):
            compile(content, name, 'exec')
    replaced = []
    try:
        for name in changes:
            target = APP_DIR / name
            old = backup / 'old' / name
            if target.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, old)
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(target)
            replaced.append(name)
    except OSError:
        for name in reversed(replaced):
            old, target = backup / 'old' / name, APP_DIR / name
            if old.exists():
                shutil.copy2(old, target)
            else:
                target.unlink(missing_ok=True)
        raise
    (backup / 'version.json').write_text(json.dumps({'commit': commit}), encoding='utf-8')
    print('Applicazione aggiornata a ' + commit[:10] + '; backup: ' + str(backup), flush=True)
    return True
