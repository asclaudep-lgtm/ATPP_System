// Service Worker for ATPP PWA — caches static assets for offline access.
const CACHE = 'atpp-v11'
const ASSETS = [
  '/',
  '/static/index.html',
  '/static/manifest.json',
]

self.addEventListener('install', evt => {
  evt.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(ASSETS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', evt => {
  evt.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', evt => {
  if (evt.request.method !== 'GET') return
  evt.respondWith(
    caches.match(evt.request).then(cached =>
      cached || fetch(evt.request).then(resp => {
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone()
          caches.open(CACHE).then(cache => cache.put(evt.request, clone))
        }
        return resp
      }).catch(() => cached)
    )
  )
})
