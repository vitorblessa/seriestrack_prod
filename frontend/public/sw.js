// SeriesTrack Service Worker — handles push notifications + offline cache
// Bump CACHE_NAME on UI changes that need to invalidate prior cached HTML/assets
const CACHE_NAME = "seriestrack-v22";
const APP_SHELL = ["/manifest.json", "/favicon.ico"];
// Stable key used to always keep a fallback copy of the last successfully
// loaded HTML shell around — see networkFirstNavigate() below.
const SHELL_KEY = "/__app_shell__";

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
        event.respondWith(networkFirstNavigate(req));
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

// A PWA resumed from the background after sitting closed for a while sometimes
// fires its first navigation while the device's network is still reconnecting
// (waking from sleep). A single failed fetch used to fall straight through to
// `caches.match("/index.html")` — a key nothing ever actually wrote to, since
// navigations are cached under their own URL — so the SW handed the page an
// empty response and the user was stuck on a permanent blank screen until a
// manual reload. Now: retry once after a short delay (covers the typical
// reconnect blip), and keep a real fallback (the last successfully loaded
// shell, always from the current build) under a stable key so a genuine
// failure still serves something that renders instead of nothing at all.
async function networkFirstNavigate(req) {
    const cache = await caches.open(CACHE_NAME);
    try {
        const res = await fetch(req);
        cache.put(req, res.clone());
        cache.put(SHELL_KEY, res.clone());
        return res;
    } catch {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        try {
            const res = await fetch(req);
            cache.put(req, res.clone());
            cache.put(SHELL_KEY, res.clone());
            return res;
        } catch {
            const cached = (await cache.match(req)) || (await cache.match(SHELL_KEY));
            if (cached) return cached;
            // Never loaded successfully even once (first-ever offline launch) —
            // serve a tiny self-healing page instead of a dead blank screen.
            return new Response(
                '<!doctype html><html><body style="background:#0A0A0C"></body>' +
                "<script>setTimeout(function(){location.reload();},2000);</script></html>",
                { headers: { "Content-Type": "text/html" } }
            );
        }
    }
}

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
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
            for (const w of wins) {
                if ("focus" in w) {
                    return w.focus().then((focused) => focused.navigate ? focused.navigate(url) : focused);
                }
            }
            if (self.clients.openWindow) return self.clients.openWindow(url);
        })
    );
});

// Allow page to ask the SW to activate immediately
self.addEventListener("message", (event) => {
    if (event.data === "SKIP_WAITING") self.skipWaiting();
});
