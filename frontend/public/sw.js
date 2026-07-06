// SeriesTrack Service Worker — handles push notifications + offline cache
// Bump CACHE_NAME on UI changes that need to invalidate prior cached HTML/assets
const CACHE_NAME = "seriestrack-v19";
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

// Push notification handler — runs even when app is fully closed (that's the point of web push).
self.addEventListener("push", (event) => {
    let data = { title: "SeriesTrack", body: "Você tem novidades" };
    try { if (event.data) data = event.data.json(); } catch {}
    const isEpisode = !!data.tmdb_id || (data.body || "").includes("estreia");
    event.waitUntil(
        self.registration.showNotification(data.title || "SeriesTrack", {
            body: data.body || "",
            icon: data.icon || "/logo192.png",
            badge: "/logo192.png",              // small monochrome icon on Android status bar
            image: data.image || data.icon,     // large hero image (Android expanded view)
            data: { url: data.url || "/dashboard", tmdb_id: data.tmdb_id },
            vibrate: [120, 60, 120],
            // Group by series id so multiple episode notifications for the same show don't stack
            tag: data.tmdb_id ? `series-${data.tmdb_id}` : (data.tag || "seriestrack"),
            renotify: true,
            // Episode alerts stay visible until user acts — feels more app-like than a fleeting toast
            requireInteraction: isEpisode,
            actions: isEpisode ? [
                { action: "open", title: "Ver detalhes" },
                { action: "dismiss", title: "Depois" },
            ] : [],
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    if (event.action === "dismiss") return;
    const url = (event.notification.data && event.notification.data.url) || "/dashboard";
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
            for (const w of wins) {
                if ("focus" in w) {
                    return w.focus().then((focused) => focused.navigate ? focused.navigate(url) : focused);
                }
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});

// Allow page to ask the SW to activate immediately
self.addEventListener("message", (event) => {
    if (event.data === "SKIP_WAITING") self.skipWaiting();
});
