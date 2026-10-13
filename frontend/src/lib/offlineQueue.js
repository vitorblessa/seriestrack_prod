/**
 * Offline-first support for the Android app: a local cache of the library
 * list/stats/progress so the UI still has something to show with no
 * connection, plus a queue for the handful of mutations users make while
 * browsing (add/remove from library, mark episode(s) watched).
 *
 * Why this is safe to "just replay later": every one of these backend
 * endpoints (routes/library.py) is an idempotent upsert or delete keyed by a
 * natural key — (user_id, tmdb_id) for library, (user_id, tmdb_id, season,
 * episode) for progress. There's no version/conflict check today even for
 * two devices racing online, so replaying a queued action later is exactly
 * as safe as if the user had just been slow to click. Last write wins.
 *
 * Reviews are intentionally NOT covered — writing a review while offline is
 * rare, and it still just fails with a normal error toast like before.
 */
import { Capacitor } from "@capacitor/core";
import api from "./api";

const QUEUE_KEY = "offline_queue_v1";
const CACHE_PREFIX = "offline_cache_v1:";

// ---- pending-action queue, persisted so it survives an app restart ----

let queueListeners = [];
export function subscribeQueue(fn) {
    queueListeners.push(fn);
    fn(getQueue());
    return () => { queueListeners = queueListeners.filter((l) => l !== fn); };
}
function notifyQueue() {
    const q = getQueue();
    queueListeners.forEach((l) => l(q));
}

export function getQueue() {
    try {
        return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
    } catch {
        return [];
    }
}
function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch {}
    notifyQueue();
}
function enqueue(action) {
    const q = getQueue();
    q.push({ id: `${Date.now()}_${Math.random().toString(36).slice(2)}`, ts: Date.now(), ...action });
    saveQueue(q);
}

let dropHandlers = [];
export function onActionDropped(fn) {
    dropHandlers.push(fn);
    return () => { dropHandlers = dropHandlers.filter((f) => f !== fn); };
}

// ---- tiny read cache (library list, stats, per-series progress) ----

export function getCache(key, fallback = null) {
    try {
        const raw = localStorage.getItem(CACHE_PREFIX + key);
        return raw ? JSON.parse(raw) : fallback;
    } catch {
        return fallback;
    }
}
export function setCache(key, value) {
    try { localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(value)); } catch {}
}

// ---- connectivity ----

export async function isOnline() {
    if (Capacitor.isNativePlatform()) {
        try {
            const { Network } = await import("@capacitor/network");
            const status = await Network.getStatus();
            return status.connected;
        } catch { /* plugin missing on this build — fall back below */ }
    }
    return typeof navigator === "undefined" ? true : navigator.onLine;
}

let watching = false;
export async function watchNetwork() {
    if (watching) return;
    watching = true;
    if (Capacitor.isNativePlatform()) {
        try {
            const { Network } = await import("@capacitor/network");
            Network.addListener("networkStatusChange", (status) => {
                if (status.connected) flushQueue();
            });
            return;
        } catch { /* fall through to the web listener below */ }
    }
    window.addEventListener("online", flushQueue);
}

// `e.response` only exists once a server actually answered (even with an
// error status) — a response-less failure is the WebView/OS saying it
// couldn't reach the backend at all, which is the only case worth queuing.
function isNetworkError(e) {
    return !e?.response;
}

async function send(action) {
    switch (action.type) {
        case "library_upsert":
            return api.post("/library", action.payload);
        case "library_remove":
            return api.delete(`/library/${action.payload.tmdb_id}`);
        case "progress_set":
            return api.post("/progress", action.payload);
        case "progress_bulk":
            return api.post("/progress/bulk", action.payload);
        default:
            return null;
    }
}

let flushing = false;
export async function flushQueue() {
    if (flushing) return;
    flushing = true;
    try {
        let q = getQueue();
        while (q.length) {
            const action = q[0];
            try {
                await send(action);
            } catch (e) {
                if (isNetworkError(e)) break; // still offline — stop, keep the rest queued
                // A real rejection from the server (e.g. 402 library cap
                // reached) — this one can never succeed as-is. Drop it and
                // tell whoever's listening (UI re-syncs from the server,
                // which is now reachable, to correct any optimistic state).
                dropHandlers.forEach((f) => f(action, e));
            }
            q = q.slice(1);
            saveQueue(q);
        }
    } finally {
        flushing = false;
    }
}

// ---- mutation helpers: try live, queue silently on a network failure ----

export async function addOrUpdateLibrary(payload) {
    try {
        await api.post("/library", payload);
        return { queued: false };
    } catch (e) {
        if (!isNetworkError(e)) throw e;
        enqueue({ type: "library_upsert", payload });
        return { queued: true };
    }
}

export async function removeFromLibraryQueued(tmdbId) {
    try {
        await api.delete(`/library/${tmdbId}`);
        return { queued: false };
    } catch (e) {
        if (!isNetworkError(e)) throw e;
        enqueue({ type: "library_remove", payload: { tmdb_id: tmdbId } });
        return { queued: true };
    }
}

export async function setProgressQueued(payload) {
    try {
        await api.post("/progress", payload);
        return { queued: false };
    } catch (e) {
        if (!isNetworkError(e)) throw e;
        enqueue({ type: "progress_set", payload });
        return { queued: true };
    }
}

export async function bulkProgressQueued(payload) {
    try {
        await api.post("/progress/bulk", payload);
        return { queued: false };
    } catch (e) {
        if (!isNetworkError(e)) throw e;
        enqueue({ type: "progress_bulk", payload });
        return { queued: true };
    }
}
