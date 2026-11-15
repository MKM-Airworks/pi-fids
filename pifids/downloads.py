"""Serve only the credential-free Windows display distribution."""
import html
from pathlib import Path
import shutil
from urllib.parse import quote

DISPLAY_DOWNLOAD = '/downloads/windows-display.zip'


def serve_display_download(handler, path, package):
    if path not in ('/downloads', DISPLAY_DOWNLOAD):
        return False
    if package is None or not package.is_file():
        handler.send(404, {'error': 'Windows display package unavailable'})
        return True
    filename = package.name
    if path == '/downloads':
        body = f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<title>Pi-FIDS V2 Windows Display</title>
<style>body{{font:17px system-ui;max-width:44rem;margin:4rem auto;padding:0 1rem}}a{{display:inline-block;padding:1rem;color:white;background:#136b9e;border-radius:.4rem}}</style>
<h1>Pi-FIDS V2 表示端末 / Windows Display</h1>
<p>Windows 10 / 11 x64 · ZIP</p>
<p><a href="{DISPLAY_DOWNLOAD}">表示端末アプリをダウンロード / Download display app</a></p>
<p>{html.escape(filename)}</p>
<p>ZIPを展開して START-HERE.html を開いてください。接続設定は管理者から受け取ります。</p>
<p lang="en">Extract the ZIP and open START-HERE.html. Obtain your terminal connection file from your administrator.</p></html>"""
        handler.send(200, body.encode(), 'text/html; charset=utf-8')
        return True
    with package.open('rb') as source:
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/zip')
        handler.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{quote(filename)}")
        handler.send_header('Content-Length', str(package.stat().st_size))
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.end_headers()
        shutil.copyfileobj(source, handler.wfile)
    return True


def display_package(directory):
    packages = sorted(Path(directory).glob('Pi-FIDS-Display-*-win-x64.zip'))
    return packages[0] if len(packages) == 1 else None
