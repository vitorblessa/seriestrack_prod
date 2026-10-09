import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import AppLayout from "../components/AppLayout";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { ShieldCheck, Search, Loader2, Crown, XCircle, Users, UserCheck, UserX, Library } from "lucide-react";

function StatCard({ icon: Icon, label, value }) {
    return (
        <div className="glass rounded-2xl p-5 flex items-center gap-4" data-testid={`admin-stat-${label}`}>
            <div className="w-11 h-11 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                <Icon className="w-5 h-5 text-[#FF2A54]" />
            </div>
            <div>
                <p className="text-2xl font-black font-display">{value ?? "–"}</p>
                <p className="text-white/50 text-xs mt-0.5">{label}</p>
            </div>
        </div>
    );
}

export default function Admin() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [query, setQuery] = useState("");
    const [results, setResults] = useState(null);
    const [searching, setSearching] = useState(false);
    const [busyEmail, setBusyEmail] = useState(null);
    const [days, setDays] = useState(365);

    const loadStats = async () => {
        try {
            const { data } = await api.get("/admin/stats");
            setStats(data);
        } catch {
            toast.error("Erro ao carregar estatísticas");
        }
    };

    useEffect(() => {
        if (user?.is_owner) loadStats();
    }, [user?.is_owner]);

    // Owner-only — the backend enforces this too (403), this is just so a
    // non-owner doesn't see an empty/broken page while waiting for that.
    if (user && !user.is_owner) {
        return <Navigate to="/dashboard" replace />;
    }

    const search = async (e) => {
        e.preventDefault();
        if (!query.trim()) return;
        setSearching(true);
        try {
            const { data } = await api.get("/auth/admin/search_users", { params: { q: query.trim() } });
            setResults(data.users);
        } catch {
            toast.error("Erro na busca");
        } finally {
            setSearching(false);
        }
    };

    const grantPro = async (email) => {
        setBusyEmail(email);
        try {
            const { data } = await api.post("/billing/admin/grant_pro", null, { params: { email, days } });
            toast.success(`Pro concedido a ${email} até ${new Date(data.subscription_renews_at).toLocaleDateString("pt-BR")}`);
            await search({ preventDefault: () => {} });
            loadStats();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Erro ao conceder Pro");
        } finally {
            setBusyEmail(null);
        }
    };

    const revokePro = async (email) => {
        setBusyEmail(email);
        try {
            await api.post("/admin/revoke_pro", null, { params: { email } });
            toast.success(`Pro revogado de ${email}`);
            await search({ preventDefault: () => {} });
            loadStats();
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Erro ao revogar Pro");
        } finally {
            setBusyEmail(null);
        }
    };

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54] flex items-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5" /> Admin
                </p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">Painel</h1>
            </section>

            <section className="px-6 md:px-10 mt-8 grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="admin-stats-grid">
                <StatCard icon={Users} label="Usuários" value={stats?.total_users} />
                <StatCard icon={Crown} label="Pro" value={stats?.pro_users} />
                <StatCard icon={UserX} label="Free" value={stats?.free_users} />
                <StatCard icon={UserCheck} label="Novos (7d)" value={stats?.new_users_7d} />
                <StatCard icon={Library} label="Itens na biblioteca (todos)" value={stats?.total_library_items} />
            </section>

            <section className="px-6 md:px-10 mt-10 max-w-3xl">
                <div className="glass rounded-2xl p-6 md:p-8">
                    <h2 className="font-display text-xl font-bold">Buscar usuário</h2>
                    <p className="text-white/60 text-sm mt-1">Busca parcial por e-mail — use para achar a conta certa antes de conceder/revogar Pro.</p>

                    <form onSubmit={search} className="mt-4 flex flex-col sm:flex-row gap-2">
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="parte do e-mail..."
                            data-testid="admin-search-input"
                            className="min-w-0 flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[#FF2A54]/50"
                        />
                        <div className="flex items-center gap-2">
                            <label className="text-xs text-white/50 whitespace-nowrap">dias Pro</label>
                            <input
                                type="number"
                                min="1"
                                value={days}
                                onChange={(e) => setDays(Number(e.target.value) || 1)}
                                data-testid="admin-grant-days-input"
                                className="w-20 min-w-0 bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[#FF2A54]/50"
                            />
                            <button type="submit" disabled={searching} data-testid="admin-search-btn" className="btn-primary text-sm shrink-0">
                                {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                            </button>
                        </div>
                    </form>

                    {results !== null && (
                        <div className="mt-5" data-testid="admin-search-results">
                            {results.length === 0 ? (
                                <p className="text-white/40 text-sm">Nenhum usuário encontrado.</p>
                            ) : (
                                <div className="space-y-2">
                                    {results.map((u) => (
                                        <div
                                            key={u._id}
                                            data-testid={`admin-user-row-${u._id}`}
                                            className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-white/[0.04] border border-white/10"
                                        >
                                            <div className="min-w-0">
                                                <p className="font-semibold text-sm truncate">{u.email}</p>
                                                <p className="text-white/50 text-xs mt-0.5">
                                                    {u.name || "—"} · {u.subscription_tier === "pro" ? (
                                                        <span className="text-amber-300">Pro{u.subscription_renews_at ? ` até ${new Date(u.subscription_renews_at).toLocaleDateString("pt-BR")}` : ""}</span>
                                                    ) : "Free"}
                                                    {u.google_linked ? " · Google" : ""}
                                                </p>
                                            </div>
                                            <div className="flex gap-2 shrink-0">
                                                <button
                                                    onClick={() => grantPro(u.email)}
                                                    disabled={busyEmail === u.email}
                                                    data-testid={`admin-grant-pro-${u._id}`}
                                                    className="btn-glass text-xs px-3 py-1.5"
                                                >
                                                    {busyEmail === u.email ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Crown className="w-3.5 h-3.5" />}
                                                    Conceder Pro
                                                </button>
                                                {u.subscription_tier === "pro" && (
                                                    <button
                                                        onClick={() => revokePro(u.email)}
                                                        disabled={busyEmail === u.email}
                                                        data-testid={`admin-revoke-pro-${u._id}`}
                                                        className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-red-500/30 text-red-300 hover:bg-red-500/10 transition"
                                                    >
                                                        {busyEmail === u.email ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                                                        Revogar Pro
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
