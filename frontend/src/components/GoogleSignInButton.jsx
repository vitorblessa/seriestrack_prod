import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import api, { formatApiError } from "../lib/api";

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

/**
 * Renders the app's custom-styled Google button, backed by a hidden, officially
 * rendered Google Identity Services button (clicks are forwarded to it). This
 * keeps our own look while using Google's real sign-in flow, which returns a
 * signed ID token we verify server-side in POST /auth/google.
 */
export default function GoogleSignInButton({ className, children }) {
    const hiddenBtnRef = useRef(null);
    const { setSession } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState("");
    const [ready, setReady] = useState(false);

    useEffect(() => {
        if (!GOOGLE_CLIENT_ID) {
            setError("Login com Google não configurado (falta REACT_APP_GOOGLE_CLIENT_ID).");
            return;
        }

        let cancelled = false;

        const init = () => {
            if (cancelled || !window.google?.accounts?.id || !hiddenBtnRef.current) return;
            window.google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
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
            window.google.accounts.id.renderButton(hiddenBtnRef.current, {
                type: "standard",
                theme: "outline",
                size: "large",
            });
            setReady(true);
        };

        // The GSI script is loaded from public/index.html; it may not be ready yet.
        if (window.google?.accounts?.id) {
            init();
        } else {
            const t = setInterval(() => {
                if (window.google?.accounts?.id) {
                    clearInterval(t);
                    init();
                }
            }, 200);
            const timeout = setTimeout(() => clearInterval(t), 10000);
            return () => { cancelled = true; clearInterval(t); clearTimeout(timeout); };
        }
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleClick = () => {
        if (error) return;
        const realBtn = hiddenBtnRef.current?.querySelector('div[role="button"]');
        if (realBtn) realBtn.click();
    };

    return (
        <div>
            <button type="button" data-testid="google-login-button" onClick={handleClick} className={className} disabled={!ready && !error}>
                {children}
            </button>
            {/* Real Google button, kept off-screen — its click is forwarded from the button above */}
            <div ref={hiddenBtnRef} style={{ position: "absolute", opacity: 0, pointerEvents: "none", top: -9999, left: -9999 }} />
            {error ? <p className="mt-2 text-xs text-red-400 text-center">{error}</p> : null}
        </div>
    );
}
