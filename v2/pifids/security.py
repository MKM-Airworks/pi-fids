"""Local manager sessions and airport/screen-scoped LAN receiver credentials."""
import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import tempfile
import time
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlparse

from .store import Store
from . import sites


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 300000).hex()


def write_private(path, data, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2)
    else:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    if os.name != 'nt':
        path.chmod(0o600)


def validate_source(source):
    parsed = urlparse(source)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Source must be an http/https origin')
    return source.rstrip('/')


class Security:
    def __init__(self, path):
        self.path = Path(path)
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.Lock()
        self.config()

    def config(self):
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('airport'),str) or not re.fullmatch('[A-Z]{3}',data['airport']) or not isinstance(data.get('terminals'), dict):
            raise ValueError('Invalid authentication configuration')
        if not isinstance(data.get('username'), str) or not 1 <= len(data['username']) <= 100:
            raise ValueError('Invalid manager username')
        sites.timezone_name(data.get('timezone',sites.DEFAULT_ZONES.get(data['airport'],'UTC')))
        for key, length in (('salt',32), ('passwordHash',64)):
            if not isinstance(data.get(key), str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}', data[key]):
                raise ValueError('Invalid password configuration')
        for display_id, digest in data['terminals'].items():
            Store.validate_display_id(display_id)
            if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                raise ValueError('Invalid terminal configuration')
        return data

    def login(self, username, password, peer):
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 1024:
            return None
        with self.lock:
            now = time.monotonic()
            self.attempts = {key: values for key, values in self.attempts.items() if values and values[-1] > now - 60}
            attempts = [stamp for stamp in self.attempts.get(peer, []) if stamp > now - 60]
            if len(attempts) >= 5:
                return None
            attempts.append(now)
            self.attempts[peer] = attempts
            config = self.config()
            candidate = password_hash(password, config['salt'])
            if not hmac.compare_digest(candidate, config['passwordHash']) or not hmac.compare_digest(username.encode(), config['username'].encode()):
                return None
            self.sessions = {key: value for key, value in self.sessions.items() if value > now}
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + 8 * 3600
            self.attempts.pop(peer, None)
            return token

    @staticmethod
    def cookie_token(headers):
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get('Cookie', ''))
        except CookieError:
            return ''
        return cookie['pifids_session'].value if 'pifids_session' in cookie else ''

    def session(self, headers):
        token = self.cookie_token(headers)
        with self.lock:
            return self.sessions.get(token, 0) > time.monotonic()

    def logout(self, headers):
        with self.lock:
            self.sessions.pop(self.cookie_token(headers), None)

    def terminal(self, headers):
        authorization = headers.get('Authorization', '')
        if not authorization.startswith('Bearer ') or len(authorization) > 256:
            return None
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        config = self.config()
        for display_id, saved_hash in config['terminals'].items():
            if hmac.compare_digest(digest, saved_hash):
                return config['airport'], display_id
        return None


def main():
    parser = argparse.ArgumentParser(description='Configure local manager login and LAN display connections')
    commands = parser.add_subparsers(dest='command', required=True)
    initial = commands.add_parser('init')
    initial.add_argument('--config', required=True)
    initial.add_argument('--airport', type=sites.airport_code, required=True)
    initial.add_argument('--timezone', type=sites.timezone_name)
    initial.add_argument('--username', default='admin')
    terminal = commands.add_parser('terminal')
    terminal.add_argument('--config', required=True)
    terminal.add_argument('--display-id', required=True)
    terminal.add_argument('--source', required=True)
    terminal.add_argument('--output', required=True)
    revoke = commands.add_parser('revoke')
    revoke.add_argument('--config', required=True)
    revoke.add_argument('--display-id', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        if not 1 <= len(args.username) <= 100:
            parser.error('Username must contain 1..100 characters')
        password = getpass.getpass('Manager password (12 or more characters): ')
        if len(password) < 12 or len(password) > 1024 or password != getpass.getpass('Confirm password: '):
            parser.error('Passwords must match and contain 12..1024 characters')
        salt = secrets.token_hex(16)
        write_private(args.config, {'airport':args.airport, 'timezone':args.timezone or sites.DEFAULT_ZONES.get(args.airport,'UTC'), 'username':args.username, 'salt':salt, 'passwordHash':password_hash(password,salt), 'terminals':{}}, exclusive=True)
    else:
        security = Security(args.config)
        config = security.config()
        Store.validate_display_id(args.display_id)
        if args.command == 'revoke':
            config['terminals'].pop(args.display_id, None)
        else:
            source = validate_source(args.source)
            if Path(args.output).resolve() == Path(args.config).resolve():
                parser.error('Connection output must differ from manager configuration')
            token = secrets.token_urlsafe(32)
            write_private(args.output, {'source':source, 'airport':config['airport'], 'timezone':config.get('timezone',sites.DEFAULT_ZONES.get(config['airport'],'UTC')), 'displayId':args.display_id, 'token':token}, exclusive=True)
            config['terminals'][args.display_id] = hashlib.sha256(token.encode()).hexdigest()
        write_private(args.config, config)
    print('Configuration saved. Keep credential files private.')


if __name__ == '__main__':
    main()
