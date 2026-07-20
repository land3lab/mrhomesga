const CACHE = "callnote-v2";
const SHARE_CACHE = "callnote-share";
const APP_SHELL = ["./", "./index.html", "./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE && k !== SHARE_CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // 안드로이드 공유 시트에서 "통화노트"로 공유된 녹음 파일/텍스트 수신 (Web Share Target)
  if (e.request.method === "POST" && url.pathname.endsWith("/share-target")) {
    e.respondWith(
      (async () => {
        try {
          const fd = await e.request.formData();
          const file = fd.get("audio");
          const text = [fd.get("title"), fd.get("text")].filter(Boolean).join("\n");
          const cache = await caches.open(SHARE_CACHE);
          if (file && file.size) {
            await cache.put(
              "./shared-file",
              new Response(file, {
                headers: {
                  "Content-Type": file.type || "application/octet-stream",
                  "X-File-Name": encodeURIComponent(file.name || "통화녹음"),
                },
              })
            );
          }
          if (text) await cache.put("./shared-text", new Response(text));
        } catch (err) {
          // 파싱 실패해도 앱은 열어준다
        }
        return Response.redirect("./?shared=1", 303);
      })()
    );
    return;
  }

  if (e.request.method !== "GET") return;
  if (url.origin !== location.origin) return; // Gemini API 등 외부 요청은 캐싱 없이 그대로 통과

  // 네트워크 우선: 온라인이면 항상 최신 버전을 받아 캐시를 갱신하고,
  // 오프라인일 때만 마지막으로 받아둔 캐시로 대체한다. (dongne와 동일한 정책)
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
