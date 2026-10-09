import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import api, { formatApiError } from "../lib/api";

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

/**
 * Renders the app's custom-styled Google button with the real, officially
 * rendered Google Identity Services button stacked invisibly on top of it
 * (same position/size), so a real user tap/click always lands directly on
 * Google's own interactive element.
 *
 * We used to render the real button off-screen and forward a synthetic
 * .click() to it from our visible button. That works on desktop but is
 * unreliable on mobile browsers, which require the click that opens an
 * OAuth popup to be a genuine, trusted user gesture on the real target —
 * a programmatic click doesn't reliably count. Overlaying the real button
 * (invisible but truly on top) avoids that problem entirely: nothing is
 * simulated, the tap the user makes IS the click on Google's button.
 */
export default function GoogleSignInButton({ className, children }) {
    const containerRef = useRef(null);
    const overlayRef = useRef(null);
    const { setSession } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState("");

    useEffect(() => {
        if (!GOOGLE_CLIENT_ID) {
            setError("Login com Google não configurado (falta REACT_APP_GOOGLE_CLIENT_ID).");
            return;
        }

        let cancelled = false;

        const init = () => {
            if (cancelled || !window.google?.accounts?.id || !overlayRef.current) return;
            window.google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
                // FedCM replaces the old third-party-cookie popup handoff with a
                // browser-mediated API. Firefox (with tracking protection) and
                // future Chrome versions block the legacy popup flow — without
                // this, the account picker opens but the credential never makes
                // it back to our callback. Firefox 133+ and modern Chrome both
                // support FedCM; browsers that don't fall back automatically.
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
            const measured = containerRef.current?.offsetWidth || 320;
            const width = Math.max(240, Math.min(400, Math.round(measured)));
            window.google.accounts.id.renderButton(overlayRef.current, {
                type: "standard",
                theme: "outline",
                size: "large",
                width,
            });

            // Google's button is an <iframe>. On mobile, the first tap on a
            // never-before-focused iframe is commonly swallowed by the browser
            // to just transfer page focus into it — the click itself only fires
            // on the *second* tap. That's exactly the "nothing happens the first
            // time, works after I tap the email field" symptom: tapping the email
            // input elsewhere on the page happened to pre-consume that first
            // focus-transfer tap. Pre-focusing the iframe ourselves as soon as
            // it exists means the user's real tap is already the "second" one.
            let focusAttempts = 0;
            const tryFocusIframe = () => {
                if (cancelled) return;
                const iframe = overlayRef.current?.querySelector("iframe");
                if (iframe) {
                    try { iframe.focus(); } catch {}
                    return;
                }
                focusAttempts += 1;
                if (focusAttempts < 20) setTimeout(tryFocusIframe, 100);
            };
            tryFocusIframe();
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

    return (
        <div ref={containerRef} className="relative">
            {/* Visual-only — the real tap target is the invisible Google button stacked on top */}
            <div className={className} aria-hidden="true">
                {children}
            </div>
            <div
                ref={overlayRef}
                className="absolute inset-0 overflow-hidden z-10"
                style={{ opacity: 0 }}
            />
            {error ? <p className="mt-2 text-xs text-red-400 text-center">{error}</p> : null}
        </div>
    );
}
