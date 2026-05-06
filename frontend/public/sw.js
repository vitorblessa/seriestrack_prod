// SeriesTrack Service Worker — handles push notifications + offline cache
const CACHE_NAME = "seriestrack-v1";
const APP_SHELL = ["/", "/index.html", "/manifest.json", "/favicon.ico"];

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

// Network-first for navigations; cache-first for static assets
self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api/")) return; // never cache API calls
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
