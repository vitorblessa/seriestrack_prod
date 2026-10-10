// PWA + Push helpers
import api from "./api";

// Incremented/decremented around subscribePush()/unsubscribePush() below so
// registerSW()'s auto-reload (see hasController note) never fires mid-request
// and silently drops the in-flight /push/subscribe call — see reloadWhenIdle().
let criticalOpInFlight = 0;

export function registerSW() {
    if (!("serviceWorker" in navigator)) return;

    // Whether this page was already controlled by an active SW before this
    // call. sw.js calls skipWaiting()+clients.claim(), so even a brand-new
    // install "acquires" control and fires controllerchange — not just a
    // genuine update swapping out an already-active worker. On a first-ever
    // visit there's no previous controller, so the page's own JS/HTML is
    // already the version being looked at: nothing to refresh for, and
    // reloading there used to be able to abort whatever the user was doing
    // right then (reported bug: tapping "Ativar notificações" in Settings
    // right as the SW first claimed the page silently dropped the
    // subscribe request mid-flight — permission stayed granted, but the
    // backend never got the subscription, until a second click succeeded
    // cleanly once the SW had already settled). Only reload for an actual
    // later update within the same session, once a controller already
    // existed once before.
    let hasController = !!navigator.serviceWorker.controller;

    let reloading = false;
    function reloadWhenIdle() {
        if (criticalOpInFlight > 0) {
            setTimeout(reloadWhenIdle, 250);
            return;
        }
        window.location.reload();
    }
    // When a new SW takes control, reload the page once so the user immediately sees fresh code
    navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (!hasController) {
            // First-ever activation claiming this page — treat any later
            // controllerchange in this session as a real update again.
            hasController = true;
            return;
        }
        if (reloading) return;
        reloading = true;
        reloadWhenIdle();
    });

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").then((reg) => {
            const checkForUpdate = () => { try { reg.update(); } catch {} };

            // Force an update check on every load so users on stale builds catch up
            checkForUpdate();

            // A PWA opened as a standalone app often never fires "load" again — it
            // stays resident in the background instead of being closed/reopened —
            // so without this, someone could sit on a stale bundle for days.
            // Re-check whenever the app comes back to the foreground instead.
            document.addEventListener("visibilitychange", () => {
                if (document.visibilityState === "visible") checkForUpdate();
            });
            window.addEventListener("focus", checkForUpdate);

            reg.addEventListener("updatefound", () => {
                const sw = reg.installing;
                if (!sw) return;
                sw.addEventListener("statechange", () => {
                    if (sw.state === "installed" && navigator.serviceWorker.controller) {
                        // New SW ready; tell it to skip waiting → activates → controllerchange → reload
                        sw.postMessage("SKIP_WAITING");
                    }
                });
            });
        }).catch(() => {});
    });
}

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export async function getPushStatus() {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        return { supported: false, permission: "denied", subscribed: false };
    }
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    return {
        supported: true,
        permission: Notification.permission,
        subscribed: !!sub,
        subscription: sub,
    };
}

export async function subscribePush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        throw new Error("Push não suportado neste navegador.");
    }
    criticalOpInFlight++;
    try {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") throw new Error("Permissão negada para notificações.");
        const { data } = await api.get("/push/public_key");
        if (!data.available || !data.public_key) throw new Error("Servidor de push não configurado.");
        const reg = await navigator.serviceWorker.ready;
        let sub = await reg.pushManager.getSubscription();
        if (!sub) {
            sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(data.public_key),
            });
        }
        const json = sub.toJSON();
        await api.post("/push/subscribe", { endpoint: json.endpoint, keys: json.keys });
        return sub;
    } finally {
        criticalOpInFlight--;
    }
}

export async function unsubscribePush() {
    criticalOpInFlight++;
    try {
        const reg = await navigator.serviceWorker.getRegistration();
        if (!reg) return;
        const sub = await reg.pushManager.getSubscription();
        if (!sub) return;
        try { await api.delete(`/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`); } catch {}
        await sub.unsubscribe();
    } finally {
        criticalOpInFlight--;
    }
}

export async function sendTestPush() {
    return api.post("/push/test");
}
