import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { Check, Sparkles, Loader2, Zap, Crown, Flame } from "lucide-react";
import { toast } from "sonner";

const FEATURES_FREE = [
    "Biblioteca até 50 séries",
    "Calendário do mês atual",
    "Push notifications no dia da estreia",
    "Estatísticas básicas",
    "Reviews & comentários",
    "Compartilhar perfil público",
];
const FEATURES_PRO = [
    "Biblioteca ilimitada",
    "Alertas 24h e 1h antes da estreia",
    "Estatísticas avançadas + Wrapped anual",
    "Recomendações com IA personalizada",
    "Calendário 6 meses + export iCal",
    "Listas customizadas e privadas ilimitadas",
    "Importar Trakt / CSV / JSON + backup automático",
    "Integração com Plex e Jellyfin",
    "Selo Pro 💎 no perfil",
    "Sem anúncios, sempre",
    "Suporte prioritário",
    "Acesso antecipado a novas features",
];

export default function Pricing() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [period, setPeriod] = useState("monthly"); // 'monthly' | 'yearly'
    const [plans, setPlans] = useState([]);
    const [me, setMe] = useState(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        api.get("/billing/plans").then((r) => setPlans(r.data.plans || [])).catch(() => {});
        if (user) api.get("/billing/me").then((r) => setMe(r.data)).catch(() => {});
    }, [user]);

    const planId = period === "monthly" ? "pro_monthly" : "pro_yearly";
    const plan = plans.find((p) => p.id === planId);
    const monthly = plans.find((p) => p.id === "pro_monthly");
    const yearly = plans.find((p) => p.id === "pro_yearly");
    const yearlyMonthEq = yearly ? (yearly.amount / 12).toFixed(2).replace(".", ",") : null;
    const yearlyDiscount = monthly && yearly ? Math.round((1 - yearly.amount / (monthly.amount * 12)) * 100) : 0;

    const startCheckout = async () => {
        if (!user) {
            navigate("/login");
            return;
        }
        setBusy(true);
        try {
            const { data } = await api.post("/billing/checkout", {
                plan: planId,
                origin_url: window.location.origin,
            });
            window.location.href = data.url;
        } catch (e) {
            toast.error(formatApiError(e) || "Erro ao iniciar checkout");
            setBusy(false);
        }
    };

    const isPro = me?.tier === "pro";

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10 pb-6 text-center max-w-4xl mx-auto">
                <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass text-xs font-bold uppercase tracking-[0.2em] text-white/80">
                    <Sparkles className="w-3 h-3 text-[#FF2A54]" /> Planos
                </span>
                <h1 className="font-display text-5xl md:text-7xl font-black tracking-tighter leading-[0.95] mt-6">
                    Pra quem é fã <span className="bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] bg-clip-text text-transparent">de verdade</span>.
                </h1>
                <p className="text-white/60 mt-6 text-lg max-w-2xl mx-auto">
                    Comece grátis. Faça upgrade quando seus 50 lugares na biblioteca acabarem ou quando quiser as features avançadas.
                </p>

                {/* Period toggle */}
                <div className="mt-10 inline-flex p-1 rounded-full bg-white/5 border border-white/10" data-testid="pricing-period-toggle">
                    <button
                        onClick={() => setPeriod("monthly")}
                        data-testid="pricing-period-monthly"
                        className={`px-5 py-2 rounded-full text-sm font-bold uppercase tracking-wider transition-all ${
                            period === "monthly" ? "bg-white text-black" : "text-white/60 hover:text-white"
                        }`}
                    >
                        Mensal
                    </button>
                    <button
                        onClick={() => setPeriod("yearly")}
                        data-testid="pricing-period-yearly"
                        className={`px-5 py-2 rounded-full text-sm font-bold uppercase tracking-wider transition-all relative ${
                            period === "yearly" ? "bg-white text-black" : "text-white/60 hover:text-white"
                        }`}
                    >
                        Anual
                        {yearlyDiscount > 0 && (
                            <span className="absolute -top-2 -right-2 px-1.5 py-0.5 rounded-full bg-[#FF2A54] text-white text-[9px] font-black tracking-wide">
                                -{yearlyDiscount}%
                            </span>
                        )}
                    </button>
                </div>
            </section>

            <section className="px-6 md:px-10 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
                {/* Free */}
                <div className="glass rounded-2xl p-8 flex flex-col" data-testid="plan-card-free">
                    <div className="flex items-center gap-2 text-white/60 text-xs font-bold uppercase tracking-[0.2em]">
                        <Zap className="w-4 h-4" /> Free
                    </div>
                    <h2 className="font-display text-3xl font-black mt-4">Grátis</h2>
                    <p className="text-white/50 text-sm mt-2">Pra começar a organizar</p>
                    <div className="mt-6 mb-2">
                        <span className="font-display text-5xl font-black">R$ 0</span>
                        <span className="text-white/50 text-sm">/mês</span>
                    </div>
                    <ul className="mt-6 space-y-2.5 flex-1">
                        {FEATURES_FREE.map((f) => (
                            <li key={f} className="text-white/70 text-sm flex items-start gap-2">
                                <Check className="w-4 h-4 text-white/40 shrink-0 mt-0.5" />
                                {f}
                            </li>
                        ))}
                    </ul>
                    <button
                        disabled
                        className="mt-8 w-full px-6 py-3 rounded-full bg-white/5 border border-white/10 text-white/50 text-sm font-bold cursor-not-allowed"
                    >
                        {user ? "Plano atual" : "Começar grátis"}
                    </button>
                </div>

                {/* Pro */}
                <div className="rounded-2xl p-8 flex flex-col relative bg-gradient-to-br from-[#FF2A54]/10 via-[#FF2A54]/5 to-transparent border border-[#FF2A54]/30 shadow-[0_30px_80px_-30px_rgba(255,42,84,0.4)]" data-testid="plan-card-pro">
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-[#FF2A54] text-white text-[10px] font-black tracking-[0.2em] uppercase shadow-lg">
                        <Flame className="w-3 h-3 inline mr-1" /> Mais escolhido
                    </div>
                    <div className="flex items-center gap-2 text-[#FF2A54] text-xs font-bold uppercase tracking-[0.2em]">
                        <Crown className="w-4 h-4" /> Pro
                    </div>
                    <h2 className="font-display text-3xl font-black mt-4">SeriesTrack Pro</h2>
                    <p className="text-white/60 text-sm mt-2">Tudo do Free + features avançadas</p>
                    {plan ? (
                        <div className="mt-6 mb-2">
                            {period === "yearly" && monthly && (
                                <div className="text-white/40 text-sm line-through">
                                    R$ {(monthly.amount * 12).toFixed(2).replace(".", ",")}/ano
                                </div>
                            )}
                            <div>
                                <span className="font-display text-5xl font-black">
                                    R$ {plan.amount.toFixed(2).replace(".", ",")}
                                </span>
                                <span className="text-white/60 text-sm">/{period === "monthly" ? "mês" : "ano"}</span>
                            </div>
                            {period === "yearly" && yearlyMonthEq && (
                                <p className="text-[#FF8a8a] text-xs font-semibold mt-1">
                                    Apenas R$ {yearlyMonthEq}/mês — economize {yearlyDiscount}%
                                </p>
                            )}
                        </div>
                    ) : (
                        <Loader2 className="w-5 h-5 animate-spin text-white/40 mt-6" />
                    )}
                    <ul className="mt-6 space-y-2.5 flex-1">
                        {FEATURES_PRO.map((f) => (
                            <li key={f} className="text-white text-sm flex items-start gap-2">
                                <Check className="w-4 h-4 text-[#FF2A54] shrink-0 mt-0.5" />
                                {f}
                            </li>
                        ))}
                    </ul>
                    <button
                        onClick={startCheckout}
                        disabled={busy || isPro}
                        data-testid="pricing-cta-pro"
                        className="mt-8 w-full px-6 py-3.5 rounded-full bg-[#FF2A54] hover:bg-[#FF4D71] text-white text-sm font-black tracking-wide uppercase transition-all disabled:opacity-60 inline-flex items-center justify-center gap-2 shadow-[0_10px_40px_-10px_rgba(255,42,84,0.6)]"
                    >
                        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Crown className="w-4 h-4" />}
                        {isPro ? "Você já é Pro 💎" : "Assinar Pro agora"}
                    </button>
                    {!user && (
                        <p className="text-center text-xs text-white/50 mt-3">Você precisa de uma conta. Vamos te levar.</p>
                    )}
                </div>
            </section>

            <section className="px-6 md:px-10 mt-16 max-w-3xl mx-auto text-center">
                <h3 className="font-display text-2xl md:text-3xl font-bold">Pagamento via Stripe — cartão e PIX</h3>
                <p className="text-white/60 mt-4">
                    Cancele quando quiser direto pelo seu perfil. Sem multas, sem complicações.
                    Pagamento processado pela Stripe — uma das maiores plataformas de pagamento do mundo.
                </p>
            </section>
            <div className="h-24" />
        </AppLayout>
    );
}
