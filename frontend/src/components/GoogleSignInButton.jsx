import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
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
 */
export default function GoogleSignInButton({ className, children }) {
    const { setSession } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState("");
    const initializedRef = useRef(false);

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
    }, [ensureInitialized]);

    const handleClick = () => {
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

    return (
        <div>
            <button type="button" onClick={handleClick} className={className}>
                {children}
            </button>
            {error ? <p className="mt-2 text-xs text-red-400 text-center">{error}</p> : null}
        </div>
    );
}
