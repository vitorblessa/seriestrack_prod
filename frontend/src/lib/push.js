// PWA + Push helpers
import api from "./api";

export function registerSW() {
    if (!("serviceWorker" in navigator)) return;

    let reloading = false;
    // When a new SW takes control, reload the page once so the user immediately sees fresh code
    navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (reloading) return;
        reloading = true;
        window.location.reload();
    });

    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").then((reg) => {
            // Force an update check on every load so users on stale builds catch up
            try { reg.update(); } catch {}
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
}

export async function unsubscribePush() {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    try { await api.delete(`/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`); } catch {}
    await sub.unsubscribe();
}

export async function sendTestPush() {
    return api.post("/push/test");
}
