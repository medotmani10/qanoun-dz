const CACHE_NAME = 'qanoun-dz-pwa-v2';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/assets/tailwind.cdn.js',
  '/assets/hero_legal.jpg',
  '/assets/library_legal.jpg',
  '/assets/templates_legal.jpg',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
  '/assets/icon-maskable.png',
  '/assets/apple-touch-icon.png'
];

// Install Event: pre-cache assets reliably with Promise.allSettled
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        STATIC_ASSETS.map(url => {
          return cache.add(url).catch(err => {
            console.warn('[SW] Pre-caching asset failed (ignoring for offline resilience):', url, err);
          });
        })
      );
    }).then(() => self.skipWaiting())
  );
});

// Activate Event: clean up obsolete cache versions
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: Robust strategy for offline execution
self.addEventListener('fetch', event => {
  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);

  // 1. API Endpoints: Network-first with safe JSON offline fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({ 
          error: 'Hors connexion internet (Mode Offline).',
          status: 'offline'
        }), {
          status: 503,
          headers: { 'Content-Type': 'application/json; charset=utf-8' }
        });
      })
    );
    return;
  }

  // 2. Navigation (HTML Pages): Stale-While-Revalidate with app shell fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return networkResponse;
        })
        .catch(() => {
          return caches.match(event.request).then(cached => {
            return cached || caches.match('/') || caches.match('/index.html');
          });
        })
    );
    return;
  }

  // 3. Static Assets & External CDNs: Cache-first, fallback to network
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) {
        // Revalidate in background for fresher assets
        fetch(event.request).then(networkResponse => {
          if (networkResponse && (networkResponse.status === 200 || networkResponse.type === 'opaque')) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
        }).catch(() => {/* Offline, silent background failure */});

        return cachedResponse;
      }

      // Not in cache: fetch from network and save
      return fetch(event.request).then(networkResponse => {
        if (networkResponse && (networkResponse.status === 200 || networkResponse.type === 'opaque')) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return networkResponse;
      }).catch(err => {
        // Provide graceful fallback for style/script or app shell
        if (url.pathname.endsWith('.css') || url.hostname.includes('fonts.googleapis.com')) {
          return new Response('/* Offline fallback stylesheet */', {
            headers: { 'Content-Type': 'text/css' }
          });
        }
        return caches.match('/') || new Response('', { status: 408 });
      });
    })
  );
});
