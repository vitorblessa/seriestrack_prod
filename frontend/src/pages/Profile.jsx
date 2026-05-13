import { useEffect, useState } from "react";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { Mail, Calendar, LogOut, Trophy, ExternalLink, Settings as SettingsIcon, Crown, X, RotateCcw, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

export default function Profile() {
    const { user, logout } = useAuth();
    const [stats, setStats] = useState(null);
    const [billing, setBilling] = useState(null);
    const [busy, setBusy] = useState(false);
    const [confirming, setConfirming] = useState(false);

    const loadBilling = async () => {
        try {
            const { data } = await api.get("/billing/me");
            setBilling(data);
        } catch {/* ignore */}
    };

    useEffect(() => {
        api.get("/stats").then((r) => setStats(r.data)).catch(() => {});
        loadBilling();
    }, []);

    const handleCancel = async () => {
        setBusy(true);
        try {
            await api.post("/billing/cancel");
            toast.success("Renovação automática desativada. Você fica Pro até o fim do período.");
            await loadBilling();
            setConfirming(false);
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Erro ao cancelar");
        } finally {
            setBusy(false);
        }
    };

    const handleReactivate = async () => {
        setBusy(true);
        try {
            await api.post("/billing/reactivate");
            toast.success("Assinatura reativada — bom te ver de volta! 🎉");
            await loadBilling();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Erro ao reativar");
        } finally {
            setBusy(false);
        }
    };

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Perfil</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">Sua conta</h1>
            </section>

            <section className="px-6 md:px-10 mt-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="glass rounded-2xl p-8 text-center">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center mx-auto text-3xl font-display font-black shadow-[0_0_40px_rgba(255,42,84,0.4)]">
                        {(user?.name || "?").charAt(0).toUpperCase()}
                    </div>
                    <h2 className="font-display text-2xl font-bold mt-5">{user?.name}</h2>
                    <p className="text-white/50 text-sm mt-1 flex items-center justify-center gap-1">
                        <Mail className="w-3.5 h-3.5" /> {user?.email}
                    </p>
                    {user?.subscription_tier === "pro" ? (
                        <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-amber-500/20 to-[#FF2A54]/20 border border-amber-400/50 text-amber-200 text-xs font-black uppercase tracking-wider" data-testid="profile-pro-badge">
                            <Crown className="w-3.5 h-3.5" /> Pro 💎
                        </div>
                    ) : (
                        <Link to="/pricing" data-testid="profile-upgrade-link" className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#FF2A54]/15 border border-[#FF2A54]/40 text-[#FF8a8a] text-xs font-bold uppercase tracking-wider hover:bg-[#FF2A54]/25">
                            <Crown className="w-3.5 h-3.5" /> Fazer upgrade
                        </Link>
                    )}
                    {user?.created_at && (
                        <p className="text-white/40 text-xs mt-3 flex items-center justify-center gap-1">
                            <Calendar className="w-3 h-3" /> Membro desde {String(user.created_at).slice(0, 10)}
                        </p>
                    )}
                    <button onClick={logout} data-testid="profile-logout" className="btn-glass mt-6 text-sm w-full">
                        <LogOut className="w-4 h-4" /> Sair da conta
                    </button>
                    {user?.id && (
                        <Link to={`/u/${user.id}`} data-testid="profile-public-link" className="btn-glass mt-3 text-sm w-full">
                            <ExternalLink className="w-4 h-4" /> Ver perfil público
                        </Link>
                    )}
                    <Link to="/settings" data-testid="profile-settings-link" className="btn-glass mt-3 text-sm w-full">
                        <SettingsIcon className="w-4 h-4" /> Configurações
                    </Link>
                </div>

                <div className="lg:col-span-2 glass rounded-2xl p-8">
                    <div className="flex items-center gap-2 mb-6">
                        <Trophy className="w-5 h-5 text-[#FF2A54]" />
                        <h2 className="font-display text-2xl font-bold">Suas estatísticas</h2>
                    </div>
                    {stats ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4" data-testid="profile-stats">
                            <Stat label="Total" value={stats.total} accent />
                            <Stat label="Assistindo" value={stats.watching} />
                            <Stat label="Quero assistir" value={stats.want} />
                            <Stat label="Pausadas" value={stats.paused} />
                            <Stat label="Finalizadas" value={stats.finished} />
                        </div>
                    ) : (
                        <p className="text-white/50">Carregando...</p>
                    )}
                </div>
            </section>

            {/* Subscription management — only when Pro */}
            {billing?.tier === "pro" && (
                <section className="px-6 md:px-10 mt-6" data-testid="subscription-card">
                    <div className="glass rounded-2xl p-6 md:p-8 max-w-5xl">
                        <div className="flex items-start gap-4 flex-wrap">
                            <div className="w-12 h-12 rounded-xl bg-amber-400/15 border border-amber-400/30 flex items-center justify-center shrink-0">
                                <Crown className="w-5 h-5 text-amber-300" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <h2 className="font-display text-xl font-bold">Assinatura Pro</h2>
                                {billing.cancel_pending ? (
                                    <p className="text-amber-300/90 text-sm mt-1" data-testid="subscription-cancel-pending">
                                        ⚠️ Renovação automática desativada. Você fica Pro até {formatDate(billing.renews_at)}
                                        {billing.days_left !== null && billing.days_left !== undefined && ` (faltam ${billing.days_left} ${billing.days_left === 1 ? "dia" : "dias"})`}, depois volta pro plano Free.
                                    </p>
                                ) : (
                                    <p className="text-white/60 text-sm mt-1" data-testid="subscription-active">
                                        Próxima renovação em {formatDate(billing.renews_at)}
                                        {billing.days_left !== null && billing.days_left !== undefined && ` · ${billing.days_left} ${billing.days_left === 1 ? "dia restante" : "dias restantes"}`}
                                    </p>
                                )}

                                <div className="mt-5 flex flex-wrap gap-3">
                                    {billing.cancel_pending ? (
                                        <button
                                            onClick={handleReactivate}
                                            disabled={busy}
                                            data-testid="subscription-reactivate-btn"
                                            className="btn-primary text-sm"
                                        >
                                            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                                            Reativar assinatura
                                        </button>
                                    ) : !confirming ? (
                                        <button
                                            onClick={() => setConfirming(true)}
                                            data-testid="subscription-cancel-btn"
                                            className="btn-glass text-sm"
                                        >
                                            <X className="w-4 h-4" /> Cancelar renovação
                                        </button>
                                    ) : (
                                        <div className="w-full rounded-xl border border-amber-400/30 bg-amber-400/5 p-4" data-testid="subscription-cancel-confirm">
                                            <p className="text-sm text-white/80">
                                                Tem certeza? Você <b>continua Pro até {formatDate(billing.renews_at)}</b>, mas não renovamos depois disso. Sem cobrança extra, sem reembolso do período pago.
                                            </p>
                                            <div className="mt-3 flex gap-2">
                                                <button
                                                    onClick={handleCancel}
                                                    disabled={busy}
                                                    data-testid="subscription-cancel-confirm-btn"
                                                    className="px-4 py-2 rounded-full bg-red-500/20 hover:bg-red-500/30 border border-red-400/40 text-red-200 text-xs font-bold uppercase tracking-wider"
                                                >
                                                    {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin inline" /> : "Sim, cancelar"}
                                                </button>
                                                <button
                                                    onClick={() => setConfirming(false)}
                                                    disabled={busy}
                                                    data-testid="subscription-cancel-keep-btn"
                                                    className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold uppercase tracking-wider"
                                                >
                                                    Voltar
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </section>
            )}
            <div className="h-20" />
        </AppLayout>
    );
}

function Stat({ label, value, accent }) {
    return (
        <div className={`rounded-xl p-5 border ${accent ? "bg-[#FF2A54]/10 border-[#FF2A54]/30" : "bg-white/5 border-white/10"}`}>
            <p className="text-xs font-bold uppercase tracking-wider text-white/60">{label}</p>
            <p className="font-display text-4xl font-black mt-2">{value || 0}</p>
        </div>
    );
}

function formatDate(iso) {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
    } catch {
        return iso;
    }
}
