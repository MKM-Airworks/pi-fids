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
        self.lock = threading.RLock()
        self.users_path = self.path.with_name(self.path.stem + ".users.json")
        config = self.config()
        if not self.users_path.exists():
            users = {} if config['username'] == 'unused-lan-only' else {config['username']:dict(salt=config['salt'], passwordHash=config['passwordHash'],role='admin',active=True)}
            try:
                write_private(self.users_path, users, exclusive=True)
            except FileExistsError:
                pass

    def users(self):
        return json.loads(self.users_path.read_text(encoding='utf-8'))

    def setup_required(self):
        return not self.users()

    @staticmethod
    def validate_user(username, password, role):
        if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}',username):
            raise ValueError('Use 1–100 letters, numbers or _.@- for the username')
        if role not in ('admin','operator'):
            raise ValueError('Invalid role')
        if not isinstance(password,str) or not 12 <= len(password) <= 1024:
            raise ValueError('Password must contain 12–1024 characters')

    def bootstrap(self, username, password):
        self.validate_user(username,password,'admin')
        with self.lock:
            if self.users():
                raise ValueError('Initial administrator is already registered')
            salt=secrets.token_hex(16)
            write_private(self.users_path,{username:dict(salt=salt,passwordHash=password_hash(password,salt),role='admin',active=True)})

    def listing(self):
        with self.lock:
            return [dict(username=name,role=user['role'],active=user['active']) for name,user in sorted(self.users().items())]

    def change_user(self, data):
        with self.lock:
            users=self.users(); name=data.get('username'); action=data.get('action')
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{1,100}',name):
                raise ValueError('Invalid username')
            before={k:v for k,v in users.get(name,{}).items() if k in ('role','active')}
            if action=='create':
                if name in users: raise ValueError('Username already exists')
                self.validate_user(name,data.get('password'),data.get('role'))
                salt=secrets.token_hex(16)
                users[name]=dict(salt=salt,passwordHash=password_hash(data['password'],salt),role=data['role'],active=True)
            elif action in ('update','reset','delete'):
                if name not in users: raise ValueError('User not found')
                if action=='delete':del users[name]
                elif action=='reset':
                    self.validate_user(name,data.get('password'),users[name]['role'])
                    salt=secrets.token_hex(16);users[name].update(salt=salt,passwordHash=password_hash(data['password'],salt))
                else:
                    if data.get('role') not in ('admin','operator') or type(data.get('active')) is not bool:raise ValueError('Invalid user settings')
                    users[name].update(role=data['role'],active=data['active'])
            else:raise ValueError('Invalid user operation')
            if not any(u['role']=='admin' and u['active'] for u in users.values()):
                raise ValueError('Keep at least one active administrator')
            write_private(self.users_path,users)
            # Account changes invalidate all of that account's existing sessions.
            self.sessions={t:v for t,v in self.sessions.items() if v['username']!=name}
            after={k:v for k,v in users.get(name,{}).items() if k in ('role','active')}
            return before,after

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
            user = self.users().get(username)
            salt = user['salt'] if user else '00'*16
            candidate = password_hash(password, salt)
            if not user or not user['active'] or not hmac.compare_digest(candidate,user['passwordHash']):
                return None
            self.sessions = {key: value for key, value in self.sessions.items() if value['expires'] > now}
            token = secrets.token_urlsafe(32)
            self.sessions[token] = dict(username=username,expires=now+8*3600,fingerprint=user['passwordHash'])
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

    def identity(self, headers):
        token=self.cookie_token(headers)
        with self.lock:
            session=self.sessions.get(token)
            if not session or session['expires'] <= time.monotonic():return None
            user=self.users().get(session['username'])
            if not user or not user['active'] or not hmac.compare_digest(session['fingerprint'],user['passwordHash']):return None
            return dict(username=session['username'],role=user['role'])

    def session(self, headers):
        return self.identity(headers) is not None

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
