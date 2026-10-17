"""Download worker: dedicated extractors plus ordinary web-page images."""
from __future__ import annotations
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
import requests
from bs4 import BeautifulSoup
from PIL import Image

APP_DIR = Path(__file__).resolve().parent
MAX_BYTES = 80 * 1024 * 1024
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
IMAGE_EXTENSIONS = frozenset({
    '.avif', '.bmp', '.gif', '.heic', '.heif', '.ico', '.jfif', '.jpeg', '.jpg',
    '.jxl', '.png', '.psd', '.svg', '.tif', '.tiff', '.webp',
})
VIDEO_EXTENSIONS = frozenset({
    '.3gp', '.avi', '.flv', '.m2ts', '.m4v', '.mkv', '.mov', '.mp4', '.mpeg',
    '.mpg', '.ogv', '.ts', '.vob', '.webm', '.wmv',
})


def emit(kind, **data):
    print(json.dumps({'type': kind, **data}, ensure_ascii=False), flush=True)


def normalize_urls(text):
    text = re.sub(r'\[[^\]\r\n]*\]\((https?://(?:[^\s()]|\([^\s()]*\))+)\)', r'\1', text.strip())
    found = re.findall(r'https?://[^\s<>"\x27`]+', text, re.I) or text.split()
    result = []
    for value in found:
        value = html.unescape(value.strip('<>"\x27`'))
        if '://' not in value and re.match(r'^(?:www\.)?[\w-]+(?:\.[\w-]+)+(?::\d+)?(?:/|$)', value):
            value = 'https://' + value
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Incolla un link web valido, per esempio https://www.repubblica.it/')
        try:
            parsed.port
        except ValueError:
            raise ValueError('La porta nel link non è valida.') from None
        value = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or '/', parsed.query, ''))
        if value not in result:
            result.append(value)
    if not result:
        raise ValueError('Incolla almeno un link.')
    return result


def folder_name_from_url(url):
    """Build a stable, Windows-safe collection name from host and path."""
    parsed = urlsplit(normalize_urls(url)[0])
    pieces = [parsed.hostname or 'web']
    pieces.extend(unquote(piece) for piece in parsed.path.split('/') if piece)
    clean = []
    for piece in pieces:
        piece = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', '-', piece)
        piece = re.sub(r'\s+', '-', piece).strip(' .-_')
        if piece:
            clean.append(piece[:60])
    name = '-'.join(clean)[:180].rstrip(' .-_') or 'download'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL'}:
        name = '_' + name
    return name


def image_urls(document, base):
    soup = BeautifulSoup(document, 'html.parser')
    base_tag = soup.find('base', href=True)
    if base_tag:
        base = urljoin(base, base_tag['href'])
    candidates = []
    def add(value):
        if isinstance(value, str) and value.strip():
            absolute = urljoin(base, html.unescape(value.strip()))
            if urlsplit(absolute).scheme in ('http', 'https') and absolute not in candidates:
                candidates.append(absolute)
    def srcset(value):
        entries = []
        for part in value.split(','):
            fields = part.strip().split()
            if fields:
                weight = re.sub(r'[^0-9.]', '', fields[-1]) if len(fields) > 1 else '1'
                try:
                    entries.append((float(weight or 1), fields[0]))
                except ValueError:
                    continue
        if entries:
            add(max(entries)[1])
    for node in soup.select('img, picture source'):
        responsive = node.get('data-srcset') or node.get('srcset')
        if responsive:
            srcset(responsive)
        else:
            for attr in ('data-original', 'data-lazy-src', 'data-src', 'src'):
                if node.get(attr) and not node[attr].startswith('data:'):
                    add(node[attr])
                    break
    for node in soup.select('meta[property="og:image"], meta[property="og:image:secure_url"], meta[name="twitter:image"]'):
        add(node.get('content'))
    for node in soup.select('[style]'):
        for value in re.findall(r'url\([\x27"]?([^\)\x27"]+)', node['style']):
            add(value)
    def structured(value, is_image=False):
        if isinstance(value, list):
            for item in value:
                structured(item, is_image)
        elif isinstance(value, dict):
            for key, item in value.items():
                structured(item, key in ('image', 'thumbnailUrl', 'contentUrl') or (is_image and key == 'url'))
        elif is_image:
            add(value)
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            structured(json.loads(node.string or node.get_text()))
        except (ValueError, TypeError):
            pass
    return candidates


def save_image(data, url, folder, filter_small=True):
    with Image.open(io.BytesIO(data)) as picture:
        if filter_small and (picture.width < 64 or picture.height < 64):
            return None
        fmt = picture.format
        picture.verify()
    extension = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif',
                 'AVIF': '.avif', 'TIFF': '.tiff', 'BMP': '.bmp'}.get(fmt)
    if not extension:
        return None
    name = re.sub(r'[^\w-]+', '-', Path(unquote(urlsplit(url).path)).stem).strip('-')[:70] or 'immagine'
    path = folder / (name + '-' + hashlib.sha256(data).hexdigest()[:16] + extension)
    existing = path.exists() and path.read_bytes() == data
    if not existing:
        folder.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.part')
        temporary.write_bytes(data)
        temporary.replace(path)
    return path, existing


def response_bytes(response):
    response.raise_for_status()
    result = bytearray()
    for chunk in response.iter_content(65536):
        result.extend(chunk)
        if len(result) > MAX_BYTES:
            raise ValueError('File troppo grande (oltre 80 MB).')
    return bytes(result)


def generic_download(url, destination):
    folder = destination
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    emit('status', text='Leggo la pagina e cerco le immagini…')
    with session.get(url, timeout=(15, 40), stream=True) as response:
        data = response_bytes(response)
        base = response.url
        content_type = response.headers.get('Content-Type', '').lower()
    if content_type.startswith('image/'):
        saved = save_image(data, base, folder, filter_small=False)
        if not saved:
            raise ValueError('Formato immagine non supportato.')
        emit('file', name=saved[0].name, existing=saved[1])
        return 1, 0
    candidates = image_urls(str(BeautifulSoup(data, 'html.parser')), base)
    if not candidates:
        emit('status', text='La pagina usa contenuti dinamici: avvio il browser automatico…')
        candidates = rendered_images(base)
    if not candidates:
        raise ValueError('Nessuna immagine trovata nella pagina. Il sito potrebbe richiedere l’accesso o bloccare il download.')
    emit('log', text=f'Trovati {len(candidates)} indirizzi immagine. Verifico e scarico i file…')
    session.headers['Referer'] = base
    count = failed = 0
    seen = set()
    for index, candidate in enumerate(candidates, 1):
        emit('status', text=f'Immagine {index} di {len(candidates)} · {count} file verificati')
        try:
            with session.get(candidate, timeout=(10, 25), stream=True) as response:
                data = response_bytes(response)
            digest = hashlib.sha256(data).digest()
            if digest in seen:
                continue
            saved = save_image(data, candidate, folder)
            if saved:
                seen.add(digest)
                count += 1
                emit('file', name=saved[0].name, existing=saved[1])
        except (requests.RequestException, OSError, ValueError, Image.DecompressionBombError) as exc:
            failed += 1
            emit('log', text=f'Immagine {index} non scaricabile ({type(exc).__name__}).')
    session.close()
    if not count:
        raise ValueError('Nessuna immagine scaricata: i file trovati non erano immagini valide o erano bloccati.')
    return count, failed


def video_download(url, destination):
    """Download videos with yt-dlp and report new/already present files."""
    destination.mkdir(parents=True, exist_ok=True)
    before = {path.resolve() for path in destination.rglob('*')
              if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS}
    command = [
        sys.executable, '-m', 'yt_dlp', '--no-colors', '--newline',
        '--windows-filenames', '--paths', str(destination), '--retries', '2',
        '--fragment-retries', '2', '--socket-timeout', '25',
        '--print', 'after_move:__YTDLP_DONE__%(filepath)s', url,
    ]
    emit('status', text='Cerco e scarico i video con yt-dlp…')
    marker = '__YTDLP_DONE__'
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        count = 0
        logs = []
        seen = set()
        for line in process.stdout:
            line = line.strip()
            if line.startswith(marker):
                path = Path(line[len(marker):])
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved in seen or not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                seen.add(resolved)
                count += 1
                emit('file', name=path.name, existing=resolved in before)
            elif line:
                logs.append(line)
                emit('log', text=line)
        return count, process.wait(), logs


def browser_context(playwright, host, headed=False):
    profile = browser_profile(host)
    profile.mkdir(parents=True, exist_ok=True)
    executable, _, _ = installed_browser()
    if not executable:
        raise ValueError('Installa Google Chrome, Microsoft Edge o Brave e riprova.')
    return playwright.chromium.launch_persistent_context(str(profile), headless=not headed,
        executable_path=str(executable), viewport={'width': 1150, 'height': 800},
        accept_downloads=False)


def default_browser():
    """Return Windows' default Chromium browser when Playwright can control it."""
    if sys.platform == 'win32':
        try:
            import winreg
            choice = r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, choice) as key:
                prog_id = winreg.QueryValueEx(key, 'ProgId')[0]
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + r'\shell\open\command') as key:
                command = os.path.expandvars(winreg.QueryValueEx(key, '')[0])
            match = re.search(r'"([^\"]+\.exe)"|([^\s]+\.exe)', command, re.I)
            if match:
                path = Path(match.group(1) or match.group(2))
                families = {
                    'chrome.exe': ('Google Chrome', 'chrome'),
                    'msedge.exe': ('Microsoft Edge', 'edge'),
                    'brave.exe': ('Brave', 'brave'),
                }
                if path.is_file() and path.name.lower() in families:
                    name, cookie_source = families[path.name.lower()]
                    return path, name, cookie_source
        except (OSError, ValueError):
            pass
    return None, None, None


def installed_browser():
    """Find an installed Chromium browser without downloading another copy."""
    roots = [value for value in (
        os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'),
        os.environ.get('LOCALAPPDATA')) if value]
    roots = [Path(root) for root in roots]
    candidates = [
        (root / relative, name, cookie_source)
        for relative, name, cookie_source in (
            ('Google/Chrome/Application/chrome.exe', 'Google Chrome', 'chrome'),
            ('Microsoft/Edge/Application/msedge.exe', 'Microsoft Edge', 'edge'),
            ('BraveSoftware/Brave-Browser/Application/brave.exe', 'Brave', 'brave'),
        )
        for root in roots
    ]
    for path, name, cookie_source in candidates:
        if path.is_file():
            return path, name, cookie_source
    selected = default_browser()
    if selected[0]:
        return selected
    return None, None, None


def browser_profile(host):
    return APP_DIR / '.browser-profile' / 'chromium' / re.sub(r'[^\w.-]', '_', host)


def rendered_images(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        with browser_context(playwright, urlsplit(url).hostname) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            previous = 0
            for _ in range(8):
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(600)
                height = page.evaluate('document.documentElement.scrollHeight')
                if height == previous and page.evaluate('window.scrollY + innerHeight >= document.documentElement.scrollHeight - 10'):
                    break
                previous = height
            return image_urls(page.content(), page.url)


def system_instagram_cookies():
    """Read only Instagram cookies from the installed browser when Windows allows it."""
    _, _, cookie_source = installed_browser()
    if not cookie_source:
        return []
    import logging
    cookie_logger = logging.getLogger('cookies')
    was_disabled = cookie_logger.disabled
    cookie_logger.disabled = True
    try:
        from gallery_dl.cookies import load_cookies
        cookies = load_cookies((cookie_source, None, None, None, '.instagram.com'))
    except Exception:
        return []
    finally:
        cookie_logger.disabled = was_disabled
    return [{'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain}
            for cookie in cookies]


def instagram_browser_cookies(url, interactive=False):
    """Return cookies from a separate profile driven by the installed browser."""
    from playwright.sync_api import sync_playwright
    if not interactive and not browser_profile('instagram.com').exists():
        return []
    with sync_playwright() as playwright:
        with browser_context(playwright, 'instagram.com', headed=interactive) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(1800)
            cookies = context.cookies('https://www.instagram.com/')
            if any(cookie['name'] == 'sessionid' for cookie in cookies) and '/accounts/login' not in page.url:
                return cookies
            if not interactive:
                return []
            _, browser_name, _ = installed_browser()
            emit('status', text=f'Instagram richiede l’accesso. Accedi nella nuova finestra di {browser_name}: il download ripartirà da solo.')
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if page.is_closed():
                    raise ValueError('Accesso non completato: finestra chiusa.')
                cookies = context.cookies('https://www.instagram.com/')
                if any(c['name'] == 'sessionid' for c in cookies) and '/accounts/login' not in page.url:
                    emit('status', text='Sessione rilevata. Riprendo il download…')
                    return cookies
                page.wait_for_timeout(1000)
            raise ValueError('Accesso non completato entro 5 minuti. Premi Scarica per riprovare.')


def gallery_download(url, destination, cookies=None, publish_logs=True,
                     images=True, videos=True, separate_media=False):
    urls = [url] if isinstance(url, str) else list(url)
    command = [sys.executable, '-u', str(APP_DIR / 'gallery_worker.py')]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        process.stdin.write(json.dumps({'urls': urls, 'destination': str(destination),
                                        'cookies': cookies or [], 'images': images,
                                        'videos': videos,
                                        'separate_media': separate_media}) + '\n')
        process.stdin.close()
        count = 0
        logs = []
        for line in process.stdout:
            line = line.strip()
            if line.startswith('__GDL_NEW__') or line.startswith('__GDL_OLD__'):
                path = Path(line[11:])
                if path.is_file() and path.stat().st_size:
                    count += 1
                    emit('file', name=path.name, existing=line.startswith('__GDL_OLD__'))
            elif line:
                logs.append(line)
                if publish_logs:
                    emit('log', text=line)
        return count, process.wait(), logs


def instagram_download(url, destination, images=True, videos=True, separate_media=False):
    """Use the corrected upstream extractor with a current browser session."""
    from maintenance import clear_instagram_cache, instagram_fix_available
    from gallery_dl.version import __version__
    emit('log', text='Motore Instagram: gallery-dl ' + __version__)
    if not instagram_fix_available():
        raise ValueError('Il motore Instagram richiede la correzione ufficiale del '
                         '15/10/2026. Premi Aggiorna oppure esegui INSTALL.bat.')
    cache_retried = False

    def download(cookies, publish_logs=True):
        nonlocal cache_retried
        options = dict(images=images, videos=videos, separate_media=separate_media)
        if not publish_logs:
            options['publish_logs'] = False
        result = gallery_download(url, destination, cookies, **options)
        if not result[0] and not cache_retried and any(
                'NotFoundError' in line for line in result[2]):
            cache_retried = True
            emit('log', text='Rinnovo la cache Instagram e riprovo una sola volta…')
            clear_instagram_cache()
            result = gallery_download(url, destination, cookies, **options)
        return result

    cookies = system_instagram_cookies()
    if any(cookie['name'] == 'sessionid' for cookie in cookies):
        downloaded, failed, logs = download(cookies, publish_logs=False)
        if downloaded:
            emit('log', text='Sessione Instagram riutilizzata dal browser installato.')
            for line in logs:
                emit('log', text=line)
            return downloaded, failed

    cookies = instagram_browser_cookies(url)
    if cookies:
        downloaded, failed, logs = download(cookies, publish_logs=False)
        if downloaded:
            for line in logs:
                emit('log', text=line)
            return downloaded, failed
        for line in logs[-2:]:
            emit('log', text=line)

    cookies = instagram_browser_cookies(url, interactive=True)
    downloaded, failed, logs = download(cookies)
    if not downloaded and any('NotFoundError' in line for line in logs):
        raise ValueError('Instagram non ha restituito il profilo anche dopo il rinnovo '
                         'della cache. Verifica che il link si apra nel browser e che '
                         'l’account con cui hai effettuato l’accesso possa vederlo.')
    return downloaded, failed


def run(payload):
    from gallery_dl import extractor
    destination = Path(payload['destination']).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    images = payload.get('images', True) is not False
    videos = bool(payload.get('videos', False))
    separate_media = payload.get('separate_media', True) is not False
    if not images and not videos:
        raise ValueError('Seleziona almeno Immagini oppure Video.')
    if separate_media:
        (destination / 'Immagini').mkdir(exist_ok=True)
        (destination / 'Video').mkdir(exist_ok=True)
    count = failures = warnings = 0
    for url in normalize_urls('\n'.join(payload['urls'])):
        host = urlsplit(url).hostname
        instagram = host == 'instagram.com' or host.endswith('.instagram.com')
        dedicated = instagram or extractor.find(url) is not None
        emit('log', text=f'Sito: {host}')
        try:
            if not dedicated:
                downloaded = failed = 0
                if images:
                    image_destination = destination / 'Immagini' if separate_media else destination
                    try:
                        image_count, image_failed = generic_download(url, image_destination)
                        downloaded += image_count
                        failed += image_failed
                    except Exception as exc:
                        failed += 1
                        emit('log', text=f'Immagini: {exc}')
                if videos:
                    video_destination = destination / 'Video' if separate_media else destination
                    video_count, video_failed, _ = video_download(url, video_destination)
                    downloaded += video_count
                    failed += bool(video_failed or not video_count)
                if not downloaded:
                    raise ValueError('Il sito non ha restituito immagini o video scaricabili con le opzioni selezionate.')
                warnings += failed
            else:
                emit('status', text='Scarico con il motore dedicato al sito…')
                if not instagram:
                    downloaded, failed, _ = gallery_download(
                        url, destination, images=images, videos=videos,
                        separate_media=separate_media)
                else:
                    downloaded, failed = instagram_download(
                        url, destination, images=images, videos=videos,
                        separate_media=separate_media)
                if not downloaded:
                    raise ValueError('Il sito non ha restituito file scaricabili. Potrebbe richiedere accesso, limitare le richieste o avere un link non più valido.')
            count += downloaded
            if dedicated:
                failures += bool(failed)
        except Exception as exc:
            failures += 1
            emit('error', text=str(exc) if isinstance(exc, ValueError) else f'Operazione non riuscita ({type(exc).__name__}). Verifica il collegamento e riprova.')
    if failures:
        text = f'Download incompleto: {count} file verificati; alcuni contenuti non scaricabili. Vedi dettagli.'
    elif warnings:
        text = f'Completato: {count} file verificati ({warnings} elementi non validi ignorati).'
    else:
        text = f'Completato: {count} file verificati nella cartella di destinazione.'
    emit('done', text=text)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(run(json.loads(sys.stdin.readline())))
    except (OSError, ValueError) as exc:
        emit('error', text=str(exc))
        raise SystemExit(1)
