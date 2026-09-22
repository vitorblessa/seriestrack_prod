/**
 * Native Android integration for SeriesTrack.
 *
 * Wires:
 *   - Hardware/gesture back button → history.back() unless we're at the root, then confirm exit.
 *   - Deep links (seriestrack:// and https://show-notify.emergent.host/*) → SPA route push.
 *   - Splash screen hide once React is mounted.
 *
 * All calls are guarded by `Capacitor.isNativePlatform()` so the same bundle runs unchanged
 * in the browser.
 */
import { Capacitor } from "@capacitor/core";
import { App as CapApp } from "@capacitor/app";
import { SplashScreen } from "@capacitor/splash-screen";
import { StatusBar, Style } from "@capacitor/status-bar";

let backSubscription = null;
let deepLinkSubscription = null;
let installed = false;

/** Convert a full URL/scheme URL to an internal SPA path. */
function urlToPath(rawUrl) {
    if (!rawUrl) return null;
    try {
        // seriestrack://series/123 → /series/123
        if (rawUrl.startsWith("seriestrack://")) {
            const p = rawUrl.replace("seriestrack://", "");
            return "/" + p.replace(/^\/+/, "");
        }
        // https://show-notify.emergent.host/library → /library
        const u = new URL(rawUrl);
        return u.pathname + (u.search || "") + (u.hash || "");
    } catch (_) {
        return null;
    }
}

/**
 * Install native listeners. Idempotent — safe to call multiple times.
 * @param {import('react-router-dom').NavigateFunction} navigate  react-router navigate fn
 */
export function installNativeBridge(navigate) {
    if (installed || !Capacitor.isNativePlatform()) return;
    installed = true;

    // Status bar: solid dark, non-overlaying so content isn't hidden.
    StatusBar.setStyle({ style: Style.Dark }).catch(() => {});
    StatusBar.setBackgroundColor({ color: "#0A0A0C" }).catch(() => {});
    StatusBar.setOverlaysWebView({ overlay: false }).catch(() => {});

    // Hide splash once JS is ready (backup — capacitor.config also auto-hides).
    setTimeout(() => SplashScreen.hide().catch(() => {}), 300);

    // Hardware back button.
    CapApp.addListener("backButton", ({ canGoBack }) => {
        const path = window.location.pathname;
        const isRoot = path === "/" || path === "/dashboard" || path === "/login";
        if (!isRoot && canGoBack) {
            navigate(-1);
        } else {
            // Root screens → exit the app (Android convention).
            CapApp.exitApp();
        }
    }).then((sub) => { backSubscription = sub; });

    // Deep links (custom scheme + App Links).
    CapApp.addListener("appUrlOpen", ({ url }) => {
        const path = urlToPath(url);
        if (path) navigate(path);
    }).then((sub) => { deepLinkSubscription = sub; });
}

export function uninstallNativeBridge() {
    backSubscription?.remove?.();
    deepLinkSubscription?.remove?.();
    installed = false;
}
