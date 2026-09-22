import type { CapacitorConfig } from '@capacitor/cli';

/**
 * SeriesTrack — Capacitor native shell config.
 *
 * IMPORTANT:
 * - `appId` MUST match the Application ID declared to Google Play (com.vitorblessa.seriestrack).
 *   Never change this once the app is published — Play Console rejects reused package names.
 * - `webDir` corresponds to CRA's default production build folder (frontend/build).
 * - `androidScheme: 'https'` disables cleartext + tells Android the WebView origin is HTTPS.
 *   No `server.url` is configured — the app ships bundled JS/CSS, not a remote URL.
 */
const config: CapacitorConfig = {
  appId: 'com.vitorblessa.seriestrack',
  appName: 'SeriesTrack',
  webDir: 'build',
  android: {
    // WebView origin protocol. `https` prevents cleartext HTTP traffic from the WebView.
    // Do NOT change to `http` — it would let the app load insecure resources in production.
    // Ref: https://capacitorjs.com/docs/config#androidscheme
    // (Capacitor default was `http` up to v3; `https` is the modern recommendation.)
    // The scheme applied to the WebView's origin — the actual API calls still hit
    // your production backend at REACT_APP_BACKEND_URL over HTTPS.
    // eslint-disable-next-line @typescript-eslint/naming-convention
    // @ts-ignore — androidScheme is valid at runtime, older type defs may lag.
    androidScheme: 'https',
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      launchAutoHide: true,
      launchFadeOutDuration: 300,
      backgroundColor: '#0A0A0C',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
      splashFullScreen: true,
      splashImmersive: true,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0A0A0C',
      overlaysWebView: false,
    },
  },
};

export default config;
