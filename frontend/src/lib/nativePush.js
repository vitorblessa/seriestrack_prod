/**
 * Native push (FCM) for the installed Android app.
 *
 * The web/PWA push path (lib/push.js, VAPID/Web Push) is untouched and keeps
 * working everywhere, browsers included. This module is additive: on the
 * native Android build only, it also registers for FCM via
 * @capacitor/push-notifications and sends the device token to the backend's
 * /push/register_fcm_token, so the user gets native push even while the app
 * is fully closed (Web Push can't deliver to a closed WebView).
 *
 * Guarded by Capacitor.isNativePlatform() throughout, so this is a no-op
 * (and the plugin is never touched) in the browser/PWA build.
 */
import { Capacitor } from "@capacitor/core";
import api from "./api";

let installed = false;

/**
 * @param {boolean} manual When true (user tapped a "reactivate" button in
 * Settings), returns a Promise that resolves only once the token actually
 * reached the backend (or rejects with a human-readable reason) — unlike the
 * silent, fire-and-forget auto path below, the Settings UI needs a real
 * success/failure to report back to the user.
 */
async function doRegister(navigate, manual = false) {
    let PushNotifications;
    try {
        ({ PushNotifications } = await import("@capacitor/push-notifications"));
    } catch {
        if (manual) throw new Error("Push nativo não disponível nesta versão do app.");
        return; // plugin not bundled in this build — nothing to do
    }

    let perm = await PushNotifications.checkPermissions();
    if (perm.receive !== "granted") {
        perm = await PushNotifications.requestPermissions();
    }
    if (perm.receive !== "granted") {
        if (manual) throw new Error("Permissão de notificações negada nas configurações do Android.");
        return; // user declined — respect it, don't nag here
    }

    // Tapping a notification while the app is backgrounded/closed — route to
    // the series page the same way Web Push's `url` payload does. Registered
    // every call (auto or manual); harmless if it ends up attached twice.
    PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
        const url = action.notification?.data?.url;
        if (url && navigate) navigate(url);
    });

    if (!manual) {
        PushNotifications.addListener("registration", async (token) => {
            try {
                // Fails soft (e.g. 401 if the user hasn't logged in yet) — the
                // token is re-sent on the next app launch, no retry loop needed.
                await api.post("/push/register_fcm_token", { token: token.value });
            } catch {}
        });
        PushNotifications.addListener("registrationError", (err) => {
            console.warn("FCM registration failed:", err);
        });
        await PushNotifications.register();
        return;
    }

    // Manual path: wait for the real outcome instead of failing soft.
    return new Promise((resolve, reject) => {
        let settled = false;
        PushNotifications.addListener("registration", async (token) => {
            if (settled) return;
            try {
                await api.post("/push/register_fcm_token", { token: token.value });
                settled = true;
                resolve();
            } catch {
                settled = true;
                reject(new Error("Token obtido, mas o servidor recusou o registro."));
            }
        });
        PushNotifications.addListener("registrationError", () => {
            if (settled) return;
            settled = true;
            reject(new Error("Não foi possível obter um token de notificações do Google Play Services."));
        });
        PushNotifications.register();
    });
}

/** Auto path — called once on app launch (see App.js). Silent, best-effort. */
export async function registerNativePush(navigate) {
    if (installed || !Capacitor.isNativePlatform()) return;
    installed = true;
    try {
        await doRegister(navigate, false);
    } catch (e) {
        console.warn("Native push setup failed:", e);
    }
}

/**
 * Manual path — called from a "Reativar notificações" button in Settings so
 * the user (and support) can recover from the auto path failing silently
 * (e.g. the token arrived before login finished, so the backend POST 401'd
 * and was never retried). Throws with a message safe to show in a toast.
 */
export async function reregisterNativePush(navigate) {
    if (!Capacitor.isNativePlatform()) {
        throw new Error("Disponível só dentro do app instalado.");
    }
    await doRegister(navigate, true);
}
