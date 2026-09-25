import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Loader2, AlertCircle, ArrowLeft, CheckCircle2 } from "lucide-react";

const REDIRECT_URI = () => window.location.origin + "/calendar/google/callback";

export default function CalendarGoogleCallback() {
    const navigate = useNavigate();
    const processed = useRef(false);
    const [error, setError] = useState("");
    const [synced, setSynced] = useState(null);

    useEffect(() => {
        if (processed.current) return;
        processed.current = true;

        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        const oauthError = params.get("error");
        if (oauthError) {
            setError(oauthError === "access_denied" ? "Permissão não concedida." : oauthError);
            return;
        }
        if (!code) {
            setError("Código de autorização não encontrado na URL.");
            return;
        }

        (async () => {
            try {
                const { data } = await api.post("/calendar/google/connect", {
                    code,
                    redirect_uri: REDIRECT_URI(),
                });
                window.history.replaceState(null, "", window.location.pathname);
                setSynced(data.synced ?? 0);
                setTimeout(() => navigate("/settings", { replace: true }), 1800);
            } catch (e) {
                setError(formatApiError(e) || "Falha ao conectar com o Google Calendar.");
            }
        })();
    }, [navigate]);

    if (error) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white p-6">
                <div className="glass rounded-2xl p-8 max-w-md w-full text-center">
                    <div className="w-14 h-14 rounded-full bg-red-500/15 border border-red-500/40 flex items-center justify-center mx-auto">
                        <AlertCircle className="w-7 h-7 text-red-400" />
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-4">Falha ao conectar</h1>
                    <p className="text-white/60 mt-2 text-sm">{error}</p>
                    <Link to="/settings" className="btn-glass mt-6 inline-flex text-sm" data-testid="back-to-settings-link">
                        <ArrowLeft className="w-4 h-4" /> Voltar às configurações
                    </Link>
                </div>
            </div>
        );
    }

    if (synced !== null) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white p-6">
                <div className="glass rounded-2xl p-8 max-w-md w-full text-center">
                    <div className="w-14 h-14 rounded-full bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center mx-auto">
                        <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                    </div>
                    <h1 className="font-display text-2xl font-bold mt-4">Google Calendar conectado!</h1>
                    <p className="text-white/60 mt-2 text-sm">
                        {synced > 0 ? `${synced} série(s) já sincronizada(s).` : "Tudo pronto — próximas séries adicionadas já aparecem automaticamente."}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-obsidian text-white">
            <Loader2 className="w-10 h-10 animate-spin text-[#FF2A54]" />
            <p className="mt-6 font-display font-bold text-lg">Conectando ao Google Calendar...</p>
            <p className="text-white/50 text-sm mt-1">Só um instante</p>
        </div>
    );
}
