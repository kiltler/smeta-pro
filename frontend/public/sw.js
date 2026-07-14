// Офлайн-заглушка: кэшируем оболочку приложения, при обрыве сети
// отдаём её из кэша; для навигации без кэша — офлайн-страница.
// Запросы к API не кэшируем никогда.
const CACHE = 'smeta-pro-v2'
const SHELL = ['/', '/manifest.webmanifest', '/icons/mark.svg', '/offline.html']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api')) return
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        const copy = resp.clone()
        caches.open(CACHE).then((cache) => cache.put(event.request, copy))
        return resp
      })
      .catch(async () => {
        const cached = await caches.match(event.request)
        if (cached) return cached
        // навигация без кэша → «Нет сети — смета подождёт»
        if (event.request.mode === 'navigate') return caches.match('/offline.html')
        return caches.match('/')
      })
  )
})
