"""Scoped login session over stdin, never exported to a cookie file."""
import json
import sys
import network  # Configure system certificate verification before gallery-dl.
from gallery_dl import config, main

IMAGE_EXTENSIONS = (
    'avif', 'bmp', 'gif', 'heic', 'heif', 'ico', 'jfif', 'jpeg', 'jpg',
    'jxl', 'png', 'psd', 'svg', 'tif', 'tiff', 'webp',
)
VIDEO_EXTENSIONS = (
    '3gp', 'avi', 'flv', 'm2ts', 'm4v', 'mkv', 'mov', 'mp4', 'mpeg',
    'mpg', 'ogv', 'ts', 'vob', 'webm', 'wmv',
)


def run(payload):
    cookies = {c['name']: c['value'] for c in payload.get('cookies', [])
               if c['domain'].lstrip('.') == 'instagram.com' or c['domain'].endswith('.instagram.com')}
    if cookies:
        config.set(('extractor', 'instagram'), 'cookies', cookies)
    images = payload.get('images', True) is not False
    videos = bool(payload.get('videos', False))
    allowed = (() if not images else IMAGE_EXTENSIONS) + (() if not videos else VIDEO_EXTENSIONS)
    config.set((), 'file-filter', f'extension in {allowed!r}')
    if payload.get('separate_media', True):
        mapping = {}
        if images:
            mapping[payload.get('image_directory', 'Images')] = IMAGE_EXTENSIONS
        if videos:
            mapping[payload.get('video_directory', 'Videos')] = VIDEO_EXTENSIONS
        config.set(('extractor',), 'postprocessors', [{'name': 'classify', 'mapping': mapping}])
    sys.argv = ['gallery-dl', '--config-ignore', '--no-input', '--no-colors',
                '--directory', payload['destination'], '--retries', '2', '--http-timeout', '25',
                '--Print', 'after:__GDL_NEW__{_path}', '--Print', 'skip:__GDL_OLD__{_path}']
    sys.argv.extend(payload['urls'])
    return main()


if __name__ == '__main__':
    # gallery-dl reconfigures stdin: do not start its text decoder first.
    payload = json.loads(sys.stdin.buffer.readline().decode('utf-8'))
    config.set(('output',), 'stdout', 'utf-8')
    config.set(('output',), 'stderr', 'utf-8')
    raise SystemExit(run(payload))
