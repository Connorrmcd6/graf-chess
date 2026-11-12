const CACHE = "chess-v5";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname === "/sw.js") return;
  event.respondWith(networkFirst(req));
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok) await cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = (await cache.match(req)) || (req.mode === "navigate" && (await cache.match(req, { ignoreSearch: true })));
    if (!hit) throw err;
    if (!new URL(req.url).pathname.startsWith("/api/")) return hit;
    const headers = new Headers(hit.headers);
    headers.set("X-Chess-Cached", "1");
    return new Response(await hit.blob(), { status: hit.status, headers });
  }
}
