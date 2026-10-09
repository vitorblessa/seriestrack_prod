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

export async function registerNativePush(navigate) {
    if (installed || !Capacitor.isNativePlatform()) return;
    installed = true;

    let PushNotifications;
    try {
        ({ PushNotifications } = await import("@capacitor/push-notifications"));
    } catch {
        return; // plugin not bundled in this build — nothing to do
    }

    try {
        let perm = await PushNotifications.checkPermissions();
        if (perm.receive !== "granted") {
            perm = await PushNotifications.requestPermissions();
        }
        if (perm.receive !== "granted") return; // user declined — respect it, don't nag here

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

        // Tapping a notification while the app is backgrounded/closed — route
        // to the series page the same way Web Push's `url` payload does.
        PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
            const url = action.notification?.data?.url;
            if (url && navigate) navigate(url);
        });

        await PushNotifications.register();
    } catch (e) {
        console.warn("Native push setup failed:", e);
    }
}
