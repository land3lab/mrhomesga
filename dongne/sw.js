const CACHE = "dongne-v4";
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
  if (url.origin !== location.origin) return; // 공공데이터 API 등 외부 요청은 캐싱 없이 그대로 통과

  // 네트워크 우선: 온라인이면 항상 최신 버전을 받아 캐시를 갱신하고,
  // 오프라인일 때만 마지막으로 받아둔 캐시로 대체한다.
  // (이전의 캐시 우선 방식은 sw.js 자체가 안 바뀐 배포에서 앱 화면이
  //  갱신되지 않는 문제가 있었다 — 그래서 네트워크 우선으로 변경)
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
