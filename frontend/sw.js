const CACHE = 'holy-planner-shell-v5-0';
const SHELL = ['/', '/index.html', '/style.css', '/responsive.css', '/finance.css', '/theme.css',
    '/workspace.css', '/workouts.css', '/workouts.js', '/planning.css', '/planning.js', '/life.css', '/life.js', '/icons.js', '/finance.js', '/app.js', '/productivity.js', '/bridge.js',
    '/manifest.webmanifest', '/app-icon.svg', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener('activate', event => event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('holy-planner-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())
));
// Nenhuma resposta da API ou informação pessoal é guardada no cache.
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    if (event.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request).then(response => response || caches.match('/'))));
});
