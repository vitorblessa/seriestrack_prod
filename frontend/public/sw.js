// SeriesTrack Service Worker — handles push notifications + offline cache
// Bump CACHE_NAME on UI changes that need to invalidate prior cached HTML/assets
const CACHE_NAME = "seriestrack-v18";
const APP_SHELL = ["/manifest.json", "/favicon.ico"];

self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// Network-first for navigations; pass-through for JS/CSS (let CRA's content-hashed names
// handle versioning); cache-first for true static assets only.
self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api/")) return; // never cache API calls
    // Don't cache JS/CSS bundles — let the browser HTTP cache + CRA hashing handle them.
    // This prevents getting stuck on a stale bundle if anything goes wrong.
    if (/\.(js|css|map)$/i.test(url.pathname)) return;

    if (req.mode === "navigate") {
        event.respondWith(
            fetch(req)
                .then((res) => {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                    return res;
                })
                .catch(() => caches.match(req).then((c) => c || caches.match("/index.html")))
        );
        return;
    }
    event.respondWith(
        caches.match(req).then((cached) => {
            if (cached) return cached;
            return fetch(req).then((res) => {
                if (res && res.status === 200 && res.type === "basic") {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                }
                return res;
            }).catch(() => cached);
        })
    );
});

// Push notification handler
self.addEventListener("push", (event) => {
    let data = { title: "SeriesTrack", body: "Você tem novidades" };
    try { if (event.data) data = event.data.json(); } catch {}
    event.waitUntil(
        self.registration.showNotification(data.title || "SeriesTrack", {
            body: data.body || "",
            icon: data.icon || "/logo192.png",
            badge: "/logo192.png",
            data: { url: data.url || "/dashboard" },
            vibrate: [80, 40, 80],
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || "/dashboard";
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
            for (const w of wins) {
                if (w.url.includes(url) && "focus" in w) return w.focus();
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});

// Allow page to ask the SW to activate immediately
self.addEventListener("message", (event) => {
    if (event.data === "SKIP_WAITING") self.skipWaiting();
});
