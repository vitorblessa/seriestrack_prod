import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import api, { formatApiError } from "../lib/api";
import { Loader2, AlertCircle, ArrowLeft } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
    const navigate = useNavigate();
    const location = useLocation();
    const { setSession } = useAuth();
    const processed = useRef(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;

        const hash = location.hash || window.location.hash;
        const m = hash.match(/session_id=([^&]+)/);
        if (!m) {
            setError("Sessão Google não encontrada na URL.");
            return;
        }
        const session_id = decodeURIComponent(m[1]);

        (async () => {
            try {
                const { data } = await api.post("/auth/google", { session_id });
                // Set user + token DIRECTLY — no extra /auth/me round-trip needed
                setSession(data.user, data.access_token);
                // Clear the hash from URL before navigating
                window.history.replaceState(null, "", window.location.pathname);
                navigate("/dashboard", { replace: true });
            } catch (e) {
                setError(formatApiError(e) || "Falha ao autenticar com Google.");
            }
        })();
    }, [location.hash, navigate, setSession]);

    if (error) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white p-6">
                <div className="glass rounded-2xl p-8 max-w-md w-full text-center">
                    <div className="w-14 h-14 rounded-full bg-red-500/15 border border-red-500/40 flex items-center justify-center mx-auto">
                        <AlertCircle className="w-7 h-7 text-red-400" />
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-4">Falha no login com Google</h1>
                    <p className="text-white/60 mt-2 text-sm">{error}</p>
                    <Link to="/login" className="btn-primary mt-6 inline-flex">
                        <ArrowLeft className="w-4 h-4" /> Voltar ao login
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white">
            <Loader2 className="w-10 h-10 animate-spin text-[#FF2A54]" />
            <p className="mt-6 font-display font-bold text-lg">Conectando sua conta Google...</p>
            <p className="text-white/50 text-sm mt-1">Só um instante</p>
        </div>
    );
}
