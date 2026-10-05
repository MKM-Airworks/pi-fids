const shellCache='pifids-shell-v1';
self.addEventListener('install',event=>event.waitUntil(caches.open(shellCache).then(cache=>cache.addAll(['/display','/static/app.js','/static/style.css'])).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(url.origin!==self.location.origin||event.request.method!=='GET')return;
 const key=url.pathname==='/display'?'/display':url.pathname;
 if(!['/display','/static/app.js','/static/style.css'].includes(key))return;
 event.respondWith(fetch(event.request).then(response=>{if(response.ok){const copy=response.clone();event.waitUntil(caches.open(shellCache).then(cache=>cache.put(key,copy)));}return response;}).catch(()=>caches.open(shellCache).then(cache=>cache.match(key))));
});
