"""Disk-backed display receiver for the local V2 prototype protocol."""
import argparse
import base64
import hashlib
import json
import logging
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

from .__main__ import handler
from .store import Store, validate


class ReceiverStore(Store):
    def accept(self, airport, display_id, state, control, images):
        if state.get('airport') != airport or control.get('displayId') != display_id:
            raise ValueError('Receiver identity mismatch')
        self.validate_display_id(display_id)
        flights = state.get('flights')
        if not isinstance(flights, list) or len(flights) > 100:
            raise ValueError('Invalid flights')
        flights = [validate(flight) for flight in flights]
        if any(flight['airport'] != airport for flight in flights):
            raise ValueError('Flight airport mismatch')
        for version in (state.get('version'), control.get('version')):
            if type(version) is not int or not 0 <= version <= 2147483647:
                raise ValueError('Invalid version')
        mode, airline = control.get('mode'), control.get('airline')
        if mode not in ('board', 'counter', 'gate') or not isinstance(airline, str) or len(airline) > 100 or (mode != 'board' and not airline.strip()):
            raise ValueError('Invalid display instruction')
        refs = [control.get(key, '') for key in ('logo', 'image')]
        for digest in refs:
            if not isinstance(digest, str):
                raise ValueError('Invalid image ID')
            if digest:
                body = images.get(digest)
                if body is not None:
                    if hashlib.sha256(body).hexdigest() != digest:
                        raise ValueError('Image integrity failure')
                    self.upload_asset({'airport':airport, 'name':digest+'.png', 'body':base64.b64encode(body).decode()})
                self.asset(airport, digest)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT version FROM state WHERE airport=?', (airport,)).fetchone()[0]
            previous = db.execute('SELECT version FROM displays WHERE airport=? AND display_id=?', (airport,display_id)).fetchone()
            if state['version'] < old or (previous and control['version'] < previous[0]):
                raise ValueError('Older publication rejected')
            db.execute('UPDATE state SET published=?,version=? WHERE airport=?', (json.dumps(flights,ensure_ascii=False),state['version'],airport))
            db.execute('INSERT INTO displays VALUES (?,?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET mode=excluded.mode,airline=excluded.airline,version=excluded.version', (airport,display_id,mode,airline,control['version']))
            db.execute('INSERT INTO display_assets VALUES (?,?,?,?) ON CONFLICT(airport,display_id) DO UPDATE SET logo=excluded.logo,image=excluded.image', (airport,display_id,*refs))


def sync_once(store, source, airport, display_id):
    def fetch(path, params, limit):
        with urlopen(source + path + '?' + urlencode(params), timeout=5) as response:
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Response exceeds limit')
        return body
    state = json.loads(fetch('/api/state', {'airport':airport}, 256*1024))
    control = json.loads(fetch('/api/display', {'airport':airport, 'displayId':display_id}, 16384))
    images = {}
    for key in ('logo', 'image'):
        digest = control.get(key, '')
        if digest:
            try:
                store.asset(airport, digest)
            except ValueError:
                images[digest] = fetch('/asset', {'airport':airport, 'id':digest}, 2*1024*1024)
    store.accept(airport, display_id, state, control, images)


def receiver_handler(store):
    class ReadOnlyHandler(handler(store)):
        def do_POST(self):
            self.send(403, {'error':'Display receiver is read-only'})

        def do_GET(self):
            if urlparse(self.path).path == '/':
                return self.send(404, {'error':'Display receiver has no manager UI'})
            return super().do_GET()
    return ReadOnlyHandler


def main():
    parser = argparse.ArgumentParser(description='Pi-FIDS localhost display receiver prototype')
    parser.add_argument('--source', required=True)
    parser.add_argument('--airport', choices=('SHI','ROR'), required=True)
    parser.add_argument('--display-id', required=True)
    parser.add_argument('--port', type=int, default=8801)
    parser.add_argument('--database', default=str(Path.home()/'.pifids-v2'/'receiver.sqlite'))
    args = parser.parse_args()
    source = urlparse(args.source)
    if source.scheme not in ('http','https') or not source.hostname or source.username or source.password or source.query or source.fragment or source.path not in ('','/'):
        parser.error('Source must be an http/https origin')
    Store.validate_display_id(args.display_id)
    store = ReceiverStore(args.database)
    def poll():
        while True:
            try:
                sync_once(store,args.source.rstrip('/'),args.airport,args.display_id)
            except Exception as error:
                logging.warning('Sync failed; keeping disk snapshot: %s', type(error).__name__)
            time.sleep(5)
    server = ThreadingHTTPServer(('127.0.0.1',args.port),receiver_handler(store))
    threading.Thread(target=poll,daemon=True).start()
    print('Receiver: http://127.0.0.1:%s/display?%s' % (args.port,urlencode({'airport':args.airport,'displayId':args.display_id,'kiosk':'1'})),flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
