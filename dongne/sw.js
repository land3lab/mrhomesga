const CACHE = "dongne-v3";
const APP_SHELL = ["./", "./index.html", "./manifest.webmanifest", "./config.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);

  // output/auto.json: always try the network first so monthly data refreshes
  // reach the app, falling back to cache when offline.
  if (url.pathname.endsWith("/output/auto.json")) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // app shell: cache-first so the app opens instantly and works offline.
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request))
  );
});
