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

let listenersAttached = false;
// True once a token has actually reached the backend successfully. Used to
// skip redundant retries — e.g. App.js calls ensureNativePushRegistered()
// again on every login, but there's nothing to do once it already worked.
let registered = false;

/**
 * Always waits for the real outcome (token requested → backend accepted it)
 * instead of firing-and-forgetting — the original auto path used to resolve
 * as soon as PushNotifications.register() was *called*, without waiting to
 * see whether the token ever reached the backend. That silently dropped the
 * registration whenever it ran before login finished (the POST 401'd with
 * nothing retrying it), which is exactly why notifications only worked after
 * manually tapping "Reativar notificações" in Settings — not intuitive, and
 * now fixed by retrying automatically on login (see ensureNativePushRegistered).
 */
async function doRegister(navigate) {
    let PushNotifications;
    try {
        ({ PushNotifications } = await import("@capacitor/push-notifications"));
    } catch {
        throw new Error("Push nativo não disponível nesta versão do app.");
    }

    let perm = await PushNotifications.checkPermissions();
    if (perm.receive !== "granted") {
        perm = await PushNotifications.requestPermissions();
    }
    if (perm.receive !== "granted") {
        throw new Error("Permissão de notificações negada nas configurações do Android.");
    }

    if (!listenersAttached) {
        listenersAttached = true;
        // Tapping a notification while the app is backgrounded/closed — route
        // to the series page the same way Web Push's `url` payload does.
        PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
            const url = action.notification?.data?.url;
            if (url && navigate) navigate(url);
        });
    }

    return new Promise((resolve, reject) => {
        let settled = false;
        let regHandle, errHandle;
        const cleanup = () => {
            regHandle?.then((h) => h.remove()).catch(() => {});
            errHandle?.then((h) => h.remove()).catch(() => {});
        };

        regHandle = PushNotifications.addListener("registration", async (token) => {
            if (settled) return;
            settled = true;
            try {
                await api.post("/push/register_fcm_token", { token: token.value });
                registered = true;
                resolve();
            } catch {
                reject(new Error("Token obtido, mas o servidor recusou o registro."));
            } finally {
                cleanup();
            }
        });
        errHandle = PushNotifications.addListener("registrationError", () => {
            if (settled) return;
            settled = true;
            reject(new Error("Não foi possível obter um token de notificações do Google Play Services."));
            cleanup();
        });
        PushNotifications.register();
    });
}

/**
 * Called once on app launch (see App.js) — silent, best-effort. Often runs
 * before the user is logged in (token POST would 401), so this alone isn't
 * enough; ensureNativePushRegistered() below covers that case.
 */
export async function registerNativePush(navigate) {
    if (!Capacitor.isNativePlatform()) return;
    try {
        await doRegister(navigate);
    } catch (e) {
        console.warn("Native push setup failed:", e);
    }
}

/**
 * Called whenever the user becomes authenticated (see App.js's effect on
 * `user` from useAuth()) — covers both a fresh login/register and a token
 * restored from storage on relaunch. Silent no-op once already registered
 * successfully, so this is safe to call on every login.
 */
export async function ensureNativePushRegistered(navigate) {
    if (registered || !Capacitor.isNativePlatform()) return;
    try {
        await doRegister(navigate);
    } catch (e) {
        console.warn("Native push registration retry failed:", e);
    }
}

/**
 * Manual path — the "Reativar notificações" button in Settings. Same logic
 * as the two above, but throws so the UI can show a real error (denied
 * permission, no Play Services, etc.) instead of failing silently.
 */
export async function reregisterNativePush(navigate) {
    if (!Capacitor.isNativePlatform()) {
        throw new Error("Disponível só dentro do app instalado.");
    }
    await doRegister(navigate);
}
