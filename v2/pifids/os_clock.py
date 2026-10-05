"""Local bridge to the privileged Windows clock helper. UI never runs elevated."""
import json
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Clock service redirects are forbidden')

class OsClock:
    def __init__(self,path):self.path=Path(path)
    def request(self,path,data=None):
        config=json.loads(self.path.read_text(encoding='utf-8-sig'));base=config.get('baseUrl','')
        url=urlparse(base)
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.path not in ('','/') or url.query or url.fragment or url.username or not url.port:
            raise ValueError('Clock service must be on IPv4 loopback')
        token=config.get('token')
        if not isinstance(token,str) or len(token)<32 or not token.isascii() or any(x.isspace() for x in token):raise ValueError('Invalid clock service configuration')
        body=json.dumps(data).encode() if data is not None else None
        request=Request(base.rstrip('/')+path,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=10) as response:
                raw=response.read(16385)
            if len(raw)>16384:raise ValueError()
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError()
            return result
        except Exception:
            raise ValueError('OS clock service is unavailable or rejected the operation') from None
    def status(self):return self.request('/status')
    def set_local(self,value):
        try:
            stamp=datetime.fromisoformat(value)
            if stamp.tzinfo is not None:raise ValueError()
            stamp=stamp.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
        except (ValueError,TypeError):raise ValueError('Enter a valid airport local date and time')
        return self.request('/set',{'utcNow':stamp.isoformat()})
