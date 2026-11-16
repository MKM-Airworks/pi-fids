"""Serve credential-free display kits from an explicitly configured folder."""
import html
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import quote

PACKAGES = {
    '/downloads/windows-display.zip': ('Windows x64', 'Pi-FIDS-Display-*-win-x64.zip', 'application/zip'),
    '/downloads/ubuntu-display.tar.gz': ('Ubuntu 24.04 LTS', 'Pi-FIDS-Display-*-ubuntu.tar.gz', 'application/gzip'),
}


def display_packages(directory):
    if directory is None:
        return {}
    result = {}
    for route, (label, pattern, mime) in PACKAGES.items():
        matches = [path for path in Path(directory).glob(pattern) if path.is_file() and not path.is_symlink()]
        if len(matches) == 1:
            result[route] = (label, matches[0], mime)
    return result


def serve_display_download(handler, path, packages):
    if path == '/downloads' and packages:
        links = ''.join(
            f'<li><a href="{route}">{html.escape(label)} — {html.escape(package.name)}</a></li>'
            for route, (label, package, _) in packages.items()
        )
        page = f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<title>Pi-FIDS V2 表示端末 / Display downloads</title>
<style>body{{font:17px system-ui;max-width:48rem;margin:4rem auto;padding:0 1rem}}li{{margin:1rem 0}}</style>
<h1>Pi-FIDS V2 表示端末 / Display downloads</h1><ul>{links}</ul>
<p>展開して START-HERE.html を開いてください。接続設定は管理者から受け取ります。</p>
<p lang="en">Extract the archive and open START-HERE.html. Ask the administrator for this terminal's connection file.</p></html>"""
        handler.send(200, page.encode(), 'text/html; charset=utf-8')
        return True
    if path not in packages:
        return False
    _, package, mime = packages[path]
    try:
        source = package.open('rb')
    except FileNotFoundError:
        handler.send(404, {'error': 'Display package unavailable'})
        return True
    with source:
        from os import fstat
        handler.send_response(200)
        handler.send_header('Content-Type', mime)
        handler.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(package.name))
        handler.send_header('Content-Length', str(fstat(source.fileno()).st_size))
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.end_headers()
        copyfileobj(source, handler.wfile)
    return True
