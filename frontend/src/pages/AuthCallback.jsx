import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import api, { setToken } from "../lib/api";
import { Loader2 } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
    const navigate = useNavigate();
    const location = useLocation();
    const { refresh } = useAuth();
    const processed = useRef(false);

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;

        const hash = location.hash || window.location.hash;
        const m = hash.match(/session_id=([^&]+)/);
        if (!m) {
            navigate("/login", { replace: true });
            return;
        }
        const session_id = decodeURIComponent(m[1]);

        (async () => {
            try {
                const { data } = await api.post("/auth/google", { session_id });
                setToken(data.access_token);
                await refresh();
                navigate("/dashboard", { replace: true });
            } catch (e) {
                navigate("/login?error=oauth", { replace: true });
            }
        })();
    }, [location.hash, navigate, refresh]);

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white">
            <Loader2 className="w-10 h-10 animate-spin text-[#FF2A54]" />
            <p className="mt-6 font-display font-bold text-lg">Conectando sua conta Google...</p>
            <p className="text-white/50 text-sm mt-1">Só um instante</p>
        </div>
    );
}
