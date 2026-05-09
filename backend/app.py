import os
import re
import sys
import uuid
import time
import threading
import traceback
import requests
import yt_dlp
from urllib.parse import urljoin
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

# ── Optional: Playwright for JavaScript-rendered pages ──
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

if HAS_PLAYWRIGHT:
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception:
        print('[skool] WARNING: Playwright Chromium not installed. Run: playwright install chromium', file=sys.stderr)
        HAS_PLAYWRIGHT = False

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
COOKIE_PATH = os.path.join(BASE_DIR, 'cookies.txt')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

MAX_FILE_AGE = 3600
download_tasks = {}


# ═══════════════════════════════════════════════
# URL Validation
# ═══════════════════════════════════════════════

def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return re.match(r'^https?://(www\.)?(skool\.com|app\.skool\.com)/', url) is not None


# ═══════════════════════════════════════════════
# Server-Side Cookie Management
# ═══════════════════════════════════════════════
# Cookies are loaded from backend/cookies.txt (Netscape format).
# On Render, set the COOKIES_DATA env var with the full cookies.txt content.
# The app writes it to disk on startup for Playwright and yt-dlp to use.
#
# To generate cookies from Chrome:
#   1. Install "Get cookies.txt" extension
#   2. Log into Skool, export cookies as Netscape format
#   3. Copy the content into Render's COOKIES_DATA env var

# On startup, write COOKIES_DATA env var to disk if set
_cookies_env = os.environ.get('COOKIES_DATA', '').strip()
if _cookies_env:
    try:
        with open(COOKIE_PATH, 'w', encoding='utf-8') as f:
            f.write(_cookies_env)
        print(f'[skool] Cookies written from COOKIES_DATA env var ({len(_cookies_env)} bytes)', file=sys.stderr)
    except Exception as e:
        print(f'[skool] Failed to write COOKIES_DATA: {e}', file=sys.stderr)

def get_cookie_path():
    return COOKIE_PATH if os.path.exists(COOKIE_PATH) else None


def parse_netscape_cookies_for_playwright(cookie_path):
    """Load Netscape cookies.txt into a list of Playwright cookie dicts."""
    pw_cookies = []
    try:
        with open(cookie_path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    domain_raw = parts[0]
                    domain = domain_raw.lstrip('.') if domain_raw.startswith('.') else domain_raw
                    is_secure = parts[3].lower() == 'true'
                    pw_cookies.append({
                        'name': parts[5],
                        'value': parts[6],
                        'domain': domain,
                        'path': parts[2],
                        'httpOnly': False,
                        'secure': is_secure,
                    })
    except Exception:
        pass
    return pw_cookies


# ═══════════════════════════════════════════════
# Video URL Extraction
# ═══════════════════════════════════════════════

def extract_video_urls_from_page(page_url, cookie_path=None):
    """Extract video URLs from a Skool page.

    PRIMARY: Playwright headless browser (renders JavaScript, intercepts network).
    FALLBACK: requests.Session with cookies + regex on raw HTML.

    Returns (list_of_absolute_urls, warning_string_or_None)
    """
    found = []
    seen = set()

    def add_url(raw):
        abs_url = urljoin(page_url, raw.strip())
        abs_url = abs_url.split('?')[0].split('#')[0].rstrip('/')
        if abs_url and abs_url not in seen:
            seen.add(abs_url)
            found.append(abs_url)

    # ── PRIMARY: Playwright headless browser ──
    if HAS_PLAYWRIGHT:
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                    ],
                )

                context = browser.new_context(
                    user_agent=(
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/120.0.0.0 Safari/537.36'
                    ),
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                )

                if cookie_path and os.path.exists(cookie_path):
                    pw_cookies = parse_netscape_cookies_for_playwright(cookie_path)
                    if pw_cookies:
                        context.add_cookies(pw_cookies)

                page = context.new_page()

                # ── Network request/response interception ──
                captured_urls = set()

                def intercept_request(request):
                    url = request.url.lower()
                    if any(k in url for k in (
                        'loom.com', 'vimeo.com', 'wistia.com', 'wistia.net',
                        '.m3u8', '.mp4', '.webm', '.ts',
                    )):
                        captured_urls.add(request.url)

                def intercept_response(response):
                    url = response.url.lower()
                    if any(k in url for k in (
                        'loom.com', 'vimeo.com', 'wistia.com',
                        '.m3u8', '.mp4', '.webm', '.ts',
                    )):
                        captured_urls.add(response.url)

                page.on('request', intercept_request)
                page.on('response', intercept_response)

                page.goto(page_url, wait_until='networkidle', timeout=45000)
                page.wait_for_timeout(5000)

                try:
                    page.wait_for_selector(
                        'iframe[src*="loom"], iframe[src*="vimeo"], iframe[src*="wistia"], '
                        'iframe[src*="youtube"], video, [data-video-url]',
                        timeout=15000,
                    )
                except Exception:
                    pass

                try:
                    for s in page.eval_on_selector_all(
                        'iframe', 'els => els.map(e => e.src || e.getAttribute("data-src") || "").filter(Boolean)'
                    ):
                        add_url(s)
                except Exception:
                    pass

                for selector, attr in [('video', 'src'), ('source', 'src')]:
                    try:
                        for s in page.eval_on_selector_all(
                            selector, f'els => els.map(e => e.{attr} || e.getAttribute("data-{attr}") || "").filter(Boolean)'
                        ):
                            add_url(s)
                    except Exception:
                        pass

                try:
                    for v in page.evaluate('''() => {
                        const r = [];
                        document.querySelectorAll('[data-video-url],[data-src],[data-url],[data-embed]')
                            .forEach(el => { ['data-video-url','data-src','data-url','data-embed'].forEach(a => {
                                const v = el.getAttribute(a); if (v) r.push(v); }); });
                        return r;
                    }'''):
                        add_url(v)
                except Exception:
                    pass

                try:
                    for b in page.evaluate('''() => {
                        const r = [];
                        document.querySelectorAll('video').forEach(v => {
                            if (v.src && v.src.startsWith('blob:')) r.push(v.src);
                            v.querySelectorAll('source').forEach(s => { if (s.src && s.src.startsWith('blob:')) r.push(s.src); });
                        });
                        return r;
                    }'''):
                        add_url(b)
                except Exception:
                    pass

                try:
                    content = page.content()
                    for pat in [
                        r'https?://[^"\'<\s]*loom\.com[^"\'<\s]*',
                        r'https?://[^"\'<\s]+\.m3u8[^"\'<\s]*',
                        r'https?://[^"\'<\s]+\.(?:mp4|webm)(?:\?[^"\'<\s]*)?',
                    ]:
                        for m in re.finditer(pat, content, re.IGNORECASE):
                            add_url(m.group(0))
                except Exception:
                    pass

                for captured in captured_urls:
                    add_url(captured)

                try:
                    for v in page.evaluate('''(known) => {
                        const r = []; const s = new Set(known);
                        const V = ['loom.com','vimeo.com','wistia.com','wistia.net','youtube.com','youtu.be'];
                        document.querySelectorAll('*').forEach(el => {
                            for (let i = 0; i < el.attributes.length; i++) {
                                const a = el.attributes[i];
                                const v = a.value.toLowerCase();
                                if (V.some(x => v.includes(x)) && !s.has(a.value)) { s.add(a.value); r.push(a.value); }
                            }
                        }); return r;
                    }''', list(seen)):
                        add_url(v)
                except Exception:
                    pass

                browser.close()

        except Exception as pw_err:
            print(f'[skool] Playwright extraction failed: {pw_err}', file=sys.stderr)

    # ── FALLBACK: requests.Session + regex ──
    if not found:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        }

        session = requests.Session()
        session.headers.update(headers)
        if cookie_path and os.path.exists(cookie_path):
            try:
                with open(cookie_path, encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        parts = line.split('\t')
                        if len(parts) >= 7:
                            session.cookies.set(
                                parts[5], parts[6],
                                domain=parts[0], path=parts[2],
                            )
            except Exception:
                pass

        try:
            resp = session.get(page_url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            html = resp.text
        except requests.RequestException:
            return found, None

        login_hints = re.findall(
            r'(sign[-\s]?in|log[-\s]?in|auth|signup|register)',
            html[:3000], re.IGNORECASE
        )
        is_login_page = len(login_hints) >= 3

        for m in re.finditer(r'https?://[^"\'<\s]*loom\.com[^"\'<\s]*', html, re.IGNORECASE):
            add_url(m.group(0))
        for m in re.finditer(r'<iframe[^>]+src=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE):
            add_url(m.group(1))
        for tag in ('video', 'source', 'embed'):
            for m in re.finditer(rf'<{tag}[^>]+src=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE):
                add_url(m.group(1))
        for attr in ('data-video-url', 'data-src', 'data-url', 'data-embed', 'data-video'):
            for m in re.finditer(rf'{attr}=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE):
                add_url(m.group(1))
        for script_pattern in (
            r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.+?})</script>',
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>({.+?})</script>',
        ):
            for m in re.finditer(script_pattern, html, re.IGNORECASE | re.DOTALL):
                text = m.group(1)
                for url_key in ('url', 'src', 'videoUrl', 'embedUrl', 'video_url', 'file'):
                    for vm in re.finditer(rf'"{url_key}"\s*:\s*"([^"]+)"', text, re.IGNORECASE):
                        maybe = vm.group(1).replace('\\/', '/')
                        if any(k in maybe.lower() for k in (
                            'loom.com', 'vimeo.com', 'wistia.com',
                            '.mp4', '.m3u8', '.webm',
                        )):
                            add_url(maybe)
        for m in re.finditer(
            r'https?://[^"\'<\s]+\.(?:mp4|m3u8|webm)(?:\?[^"\'<\s]*)?',
            html, re.IGNORECASE
        ):
            add_url(m.group(0))

        if is_login_page and not found:
            return found, (
                'Page appears to be a login screen. '
                'The Skool session may have expired. Contact the site admin.'
            )

    return found, None


# ═══════════════════════════════════════════════
# Download Task
# ═══════════════════════════════════════════════

class DownloadTask:
    def __init__(self, task_id, url):
        self.task_id = task_id
        self.url = url
        self.status = 'queued'
        self.progress = 0
        self.filename = None
        self.filepath = None
        self.filesize = 0
        self.error = None
        self.created_at = time.time()
        self.info = None

    def start(self):
        self.status = 'downloading'
        thread = threading.Thread(target=self._run_download, daemon=True)
        thread.start()

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                self.progress = min(int(downloaded / total * 100), 99)
        elif d['status'] == 'finished':
            self.progress = 100

    def _run_download(self):
        safe_id = re.sub(r'[^\w\-]', '_', self.task_id)[:12]
        output_template = os.path.join(
            DOWNLOAD_FOLDER, f'{safe_id}_%(title)s.%(ext)s'
        )

        cookie_path = get_cookie_path()

        base_ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'progress_hooks': [self._progress_hook],
            'verbose': True,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }

        if cookie_path:
            base_ydl_opts['cookiefile'] = cookie_path

        def do_download(url, referer=None):
            opts = dict(base_ydl_opts)
            if referer:
                opts['referer'] = referer
            with yt_dlp.YoutubeDL(opts) as ydl:
                self.info = ydl.extract_info(url, download=True)
                raw_path = ydl.prepare_filename(self.info)
                actual_filename = os.path.basename(raw_path)
                self.filename = actual_filename
                self.filepath = os.path.join(DOWNLOAD_FOLDER, actual_filename)
                if os.path.exists(self.filepath):
                    self.filesize = os.path.getsize(self.filepath)
                self.status = 'completed'
                self.progress = 100

        try:
            do_download(self.url)
            return
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.UnsupportedError) as e:
            error_msg = str(e)

            if 'Unsupported URL' not in error_msg:
                self.status = 'error'
                if 'HTTP Error 403' in error_msg:
                    self.error = 'Authentication required. The server session may have expired.'
                elif 'HTTP Error 404' in error_msg:
                    self.error = 'Video not found. Please check the URL.'
                elif 'Unable to extract video data' in error_msg:
                    self.error = 'Could not extract video data.'
                else:
                    self.error = f'Download failed: {error_msg[:200]}'
                return

            self.status = 'downloading'
            self.progress = 5
            extracted_urls, fetch_err = extract_video_urls_from_page(
                self.url, cookie_path
            )

            if not extracted_urls:
                self.status = 'error'
                if fetch_err:
                    self.error = fetch_err
                else:
                    self.error = (
                        'No video source found on this Skool page. '
                        'The session may have expired.'
                    )
                return

            for video_url in extracted_urls:
                try:
                    do_download(video_url, referer=self.url)
                    return
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.UnsupportedError):
                    continue
                except Exception:
                    continue

            self.status = 'error'
            self.error = (
                f'Found {len(extracted_urls)} potential video source(s) '
                f'but none could be downloaded.'
            )
        except Exception as e:
            self.status = 'error'
            self.error = f'An unexpected error occurred: {str(e)[:200]}'


# ═══════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)


@app.route('/api/validate-url', methods=['POST'])
def validate_url_endpoint():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'valid': False, 'error': 'Please enter a URL'}), 400
    is_valid = is_valid_url(url)
    return jsonify({
        'valid': is_valid,
        'error': None if is_valid else 'Please enter a valid Skool URL'
    })


@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Video URL is required'}), 400
    if not is_valid_url(url):
        return jsonify({'error': 'Invalid URL. Must be a Skool.com URL.'}), 400

    task_id = str(uuid.uuid4())
    task = DownloadTask(task_id, url)
    download_tasks[task_id] = task
    task.start()

    return jsonify({
        'task_id': task_id,
        'status': 'queued',
        'message': 'Download task created successfully',
    })


@app.route('/api/download/<task_id>/status', methods=['GET'])
def get_download_status(task_id):
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    response = {
        'task_id': task.task_id,
        'status': task.status,
        'progress': task.progress,
        'error': task.error,
        'filename': task.filename,
        'filesize': task.filesize,
    }
    if task.status == 'completed' and task.filepath and os.path.exists(task.filepath):
        response['download_url'] = f'/api/download/{task_id}/file'
        response['filesize'] = os.path.getsize(task.filepath)
    return jsonify(response)


@app.route('/api/download/<task_id>/file', methods=['GET'])
def download_file(task_id):
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task.status != 'completed':
        return jsonify({'error': 'Download not yet completed'}), 400
    if not task.filepath or not os.path.exists(task.filepath):
        return jsonify({'error': 'File not found on server'}), 404
    download_name = task.filename or 'skool_video.mp4'
    return send_file(
        task.filepath,
        as_attachment=True,
        download_name=download_name,
        mimetype='video/mp4',
    )


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'version': '3.0.0',
        'active_tasks': len(download_tasks),
        'has_cookies': get_cookie_path() is not None,
        'cookies_source': 'env_var' if _cookies_env else ('file' if get_cookie_path() else 'none'),
    })


# ═══════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════

def cleanup_old_files():
    while True:
        time.sleep(300)
        now = time.time()
        if os.path.isdir(DOWNLOAD_FOLDER):
            for fname in os.listdir(DOWNLOAD_FOLDER):
                fpath = os.path.join(DOWNLOAD_FOLDER, fname)
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > MAX_FILE_AGE:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
        stale_tasks = [
            tid for tid, t in download_tasks.items()
            if t.status in ('completed', 'error') and now - t.created_at > MAX_FILE_AGE
        ]
        for tid in stale_tasks:
            del download_tasks[tid]


cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development').lower() == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
