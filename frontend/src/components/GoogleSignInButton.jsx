import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Capacitor } from "@capacitor/core";
import { useAuth } from "../lib/auth";
import api, { formatApiError } from "../lib/api";

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

/**
 * We used to render Google's own button and either (a) forward a synthetic
 * .click() to an off-screen copy of it, or (b) stack it invisibly on top of
 * our styled button so the user's tap landed directly on it. Both were
 * unreliable on mobile: (a) needs a trusted gesture a synthetic click can't
 * provide, and (b) needs the user's tap to land exactly on Google's <iframe>
 * at a moment it's actually ready to receive it — which on some mobile
 * browsers/PWAs took a first "warm-up" tap before it worked, reported as
 * "o botão só funciona no segundo clique".
 *
 * Simpler and documented by Google for custom buttons: skip rendering
 * their button entirely and call google.accounts.id.prompt() directly from
 * our own real <button>'s onClick. No overlay, no iframe, no timing window
 * where the tap can land on nothing — the click handler itself is the
 * trusted user gesture.
 *
 * NONE of the above runs inside the installed Android app, though: Google
 * blocks its Identity Services JS SDK inside embedded WebViews entirely
 * ("disallowed_useragent", a security policy since 2021) — prompt() just
 * silently fails to display there, web/PWA or not. On
 * Capacitor.isNativePlatform() we instead call the native Google Sign-In
 * plugin (@southdevs/capacitor-google-auth, see capacitor.config.ts), which
 * opens Android's own account picker and hands back an idToken we send to
 * the exact same backend endpoint as the web flow — no backend changes.
 */
export default function GoogleSignInButton({ className, children }) {
    const { setSession } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState("");
    const initializedRef = useRef(false);
    const isNative = Capacitor.isNativePlatform();

    const ensureInitialized = useCallback(() => {
        if (initializedRef.current || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            use_fedcm_for_button: true,
            callback: async (response) => {
                try {
                    const { data } = await api.post("/auth/google", { credential: response.credential });
                    setSession(data.user, data.access_token);
                    navigate("/dashboard", { replace: true });
                } catch (e) {
                    setError(formatApiError(e) || "Falha ao autenticar com Google.");
                }
            },
        });
        initializedRef.current = true;
    }, [navigate, setSession]);

    useEffect(() => {
        if (isNative) return; // native path needs no GSI script
        if (!GOOGLE_CLIENT_ID) {
            setError("Login com Google não configurado (falta REACT_APP_GOOGLE_CLIENT_ID).");
            return;
        }
        if (window.google?.accounts?.id) {
            ensureInitialized();
            return;
        }
        // The GSI script is loaded from public/index.html; it may not be ready yet.
        const t = setInterval(() => {
            if (window.google?.accounts?.id) {
                clearInterval(t);
                ensureInitialized();
            }
        }, 200);
        const timeout = setTimeout(() => clearInterval(t), 10000);
        return () => { clearInterval(t); clearTimeout(timeout); };
    }, [isNative, ensureInitialized]);

    const handleNativeClick = async () => {
        setError("");
        try {
            const { GoogleAuth } = await import("@southdevs/capacitor-google-auth");
            // Also configured in capacitor.config.ts (read automatically on
            // native) and strings.xml as a fallback — calling initialize()
            // explicitly here is what the plugin's own docs recommend and
            // costs nothing extra (it's a no-op if already initialized).
            await GoogleAuth.initialize({
                clientId: GOOGLE_CLIENT_ID,
                scopes: ["profile", "email"],
            });
            const user = await GoogleAuth.signIn();
            const idToken = user?.authentication?.idToken;
            if (!idToken) throw new Error("Google não retornou um token válido.");
            const { data } = await api.post("/auth/google", { credential: idToken });
            setSession(data.user, data.access_token);
            navigate("/dashboard", { replace: true });
        } catch (e) {
            // User closing the native account picker throws too — don't show
            // an error for a plain cancel.
            if (e?.message?.toLowerCase().includes("cancel")) return;
            setError(formatApiError(e) || "Falha ao autenticar com Google.");
        }
    };

    const handleWebClick = () => {
        setError("");
        if (!GOOGLE_CLIENT_ID) return;
        if (!window.google?.accounts?.id) {
            setError("Login com Google ainda carregando — toque de novo em um instante.");
            return;
        }
        ensureInitialized();
        window.google.accounts.id.prompt((notification) => {
            // Surface only genuine failures — a plain dismissal (user closed the
            // picker) shouldn't show an error.
            if (typeof notification.isNotDisplayed === "function" && notification.isNotDisplayed()) {
                setError("Não deu pra abrir o login do Google. Toque em Entrar com Google de novo.");
            }
        });
    };

    const handleClick = isNative ? handleNativeClick : handleWebClick;

    return (
        <div>
            <button type="button" onClick={handleClick} className={className}>
                {children}
            </button>
            {error ? <p className="mt-2 text-xs text-red-400 text-center">{error}</p> : null}
        </div>
    );
}
