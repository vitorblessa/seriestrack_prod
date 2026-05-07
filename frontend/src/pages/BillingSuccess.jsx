import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { Loader2, Crown, CheckCircle2, AlertCircle, ArrowRight, Sparkles } from "lucide-react";

export default function BillingSuccess() {
    const location = useLocation();
    const navigate = useNavigate();
    const { refresh } = useAuth();
    const [phase, setPhase] = useState("polling"); // 'polling'|'success'|'expired'|'error'
    const [info, setInfo] = useState(null);
    const attemptsRef = useRef(0);
    const timerRef = useRef(null);

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const sessionId = params.get("session_id");
        if (!sessionId) {
            setPhase("error");
            return;
        }

        const poll = async () => {
            attemptsRef.current += 1;
            try {
                const { data } = await api.get(`/billing/status/${sessionId}`);
                setInfo(data);
                if (data.payment_status === "paid") {
                    setPhase("success");
                    refresh();
                    return;
                }
                if (data.status === "expired") {
                    setPhase("expired");
                    return;
                }
                if (attemptsRef.current >= 12) {
                    setPhase("error");
                    return;
                }
                timerRef.current = setTimeout(poll, 2500);
            } catch {
                if (attemptsRef.current >= 12) {
                    setPhase("error");
                    return;
                }
                timerRef.current = setTimeout(poll, 2500);
            }
        };
        poll();
        return () => timerRef.current && clearTimeout(timerRef.current);
    }, [location.search, refresh]);

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-16 pb-24 max-w-2xl mx-auto text-center" data-testid="billing-success-page">
                {phase === "polling" && (
                    <>
                        <Loader2 className="w-12 h-12 mx-auto animate-spin text-[#FF2A54]" />
                        <h1 className="font-display text-3xl md:text-4xl font-black mt-8">Confirmando seu pagamento...</h1>
                        <p className="text-white/60 mt-3">Isso leva alguns segundos. Não feche a página.</p>
                    </>
                )}
                {phase === "success" && (
                    <>
                        <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shadow-[0_30px_80px_-20px_rgba(255,42,84,0.5)]">
                            <Crown className="w-10 h-10 text-white" strokeWidth={2.5} />
                        </div>
                        <span className="inline-flex items-center gap-2 mt-6 px-4 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-bold uppercase tracking-[0.2em]" data-testid="billing-success-badge">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Pagamento confirmado
                        </span>
                        <h1 className="font-display text-4xl md:text-5xl font-black mt-6 tracking-tight">
                            Bem-vindo ao <span className="bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] bg-clip-text text-transparent">Pro 💎</span>
                        </h1>
                        <p className="text-white/70 mt-4 text-lg">Sua biblioteca acaba de ficar ilimitada.</p>
                        {info?.new_renews_at && (
                            <p className="text-white/50 text-sm mt-2">
                                Sua assinatura é válida até <span className="text-white font-semibold">{info.new_renews_at.slice(0, 10)}</span>
                            </p>
                        )}
                        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
                            {[
                                "Alertas 24h e 1h antes",
                                "Recomendações com IA",
                                "Listas privadas ilimitadas",
                                "Estatísticas avançadas",
                            ].map((f) => (
                                <div key={f} className="glass rounded-xl p-4 flex items-center gap-3">
                                    <Sparkles className="w-4 h-4 text-[#FF2A54]" />
                                    <span className="text-sm font-semibold">{f}</span>
                                </div>
                            ))}
                        </div>
                        <Link to="/dashboard" data-testid="billing-success-cta" className="btn-primary mt-10 inline-flex">
                            Voltar ao app <ArrowRight className="w-4 h-4" />
                        </Link>
                    </>
                )}
                {(phase === "expired" || phase === "error") && (
                    <>
                        <div className="w-16 h-16 mx-auto rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center">
                            <AlertCircle className="w-8 h-8 text-amber-400" />
                        </div>
                        <h1 className="font-display text-3xl md:text-4xl font-black mt-6">
                            {phase === "expired" ? "Sessão expirada" : "Não foi possível confirmar"}
                        </h1>
                        <p className="text-white/60 mt-3 max-w-md mx-auto">
                            Se você foi cobrado, sua assinatura aparecerá no seu perfil em alguns minutos. Se não, tente novamente.
                        </p>
                        <button onClick={() => navigate("/pricing")} className="btn-primary mt-8 inline-flex">
                            Tentar novamente
                        </button>
                    </>
                )}
            </section>
        </AppLayout>
    );
}
