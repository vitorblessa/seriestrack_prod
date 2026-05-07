import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { BarChart3, Clock, Loader2, Crown, TrendingUp, Calendar as CalIcon, Tv } from "lucide-react";

export default function AdvancedStats() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const isPro = user?.subscription_tier === "pro";

    useEffect(() => {
        if (!isPro) { setLoading(false); return; }
        api.get("/stats/advanced").then((r) => setStats(r.data)).catch(() => {}).finally(() => setLoading(false));
    }, [isPro]);

    const heatGrid = useMemo(() => {
        if (!stats?.heatmap) return null;
        const map = Object.fromEntries(stats.heatmap.map((h) => [h.date, h.count]));
        const today = new Date();
        const cells = [];
        // 53 weeks × 7 days = 371 days back
        const start = new Date(today);
        start.setDate(start.getDate() - 364);
        // align to Sunday
        start.setDate(start.getDate() - start.getDay());
        for (let w = 0; w < 53; w++) {
            const col = [];
            for (let d = 0; d < 7; d++) {
                const dt = new Date(start);
                dt.setDate(dt.getDate() + w * 7 + d);
                const iso = dt.toISOString().slice(0, 10);
                col.push({ date: iso, count: map[iso] || 0 });
            }
            cells.push(col);
        }
        const max = Math.max(...cells.flat().map((c) => c.count), 1);
        return { cells, max };
    }, [stats]);

    if (!isPro) {
        return (
            <AppLayout>
                <section className="px-6 md:px-10 pt-16 pb-24 max-w-2xl mx-auto text-center" data-testid="stats-paywall">
                    <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shadow-[0_30px_80px_-20px_rgba(255,42,84,0.5)]">
                        <BarChart3 className="w-10 h-10 text-white" strokeWidth={2.5} />
                    </div>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54] mt-8">Recurso Pro</p>
                    <h1 className="font-display text-4xl md:text-5xl font-black mt-3 tracking-tight">Sua história em números</h1>
                    <p className="text-white/70 mt-5 text-lg max-w-md mx-auto">
                        Heatmap anual de assistidos, top gêneros, séries que mais consumiu, horas totais — tudo num só lugar.
                    </p>
                    <Link to="/pricing" className="btn-primary mt-10 inline-flex" data-testid="stats-paywall-cta">
                        <Crown className="w-4 h-4" /> Fazer upgrade pra Pro
                    </Link>
                </section>
            </AppLayout>
        );
    }

    if (loading) {
        return (
            <AppLayout>
                <div className="min-h-[60vh] flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
                </div>
            </AppLayout>
        );
    }

    if (!stats) {
        return (
            <AppLayout>
                <div className="px-6 md:px-10 py-20 text-center text-white/60">Sem dados ainda. Marque alguns episódios como assistidos.</div>
            </AppLayout>
        );
    }

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Pro · Estatísticas avançadas</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">Sua história</h1>
            </section>

            {/* Big numbers */}
            <section className="px-6 md:px-10 mt-10 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="stats-big-numbers">
                <BigStat label="Episódios" value={stats.total_episodes_watched} icon={Tv} />
                <BigStat label="Horas" value={stats.estimated_hours} icon={Clock} accent />
                <BigStat label="Dias inteiros" value={stats.estimated_days} icon={CalIcon} />
                <BigStat label="Séries" value={stats.library_size} icon={TrendingUp} />
            </section>

            {/* Heatmap */}
            {heatGrid && (
                <section className="px-6 md:px-10 mt-12" data-testid="stats-heatmap">
                    <h2 className="font-display text-2xl font-bold mb-4">Atividade nos últimos 12 meses</h2>
                    <div className="glass rounded-2xl p-5 overflow-x-auto">
                        <div className="flex gap-1 min-w-max">
                            {heatGrid.cells.map((col, ci) => (
                                <div key={ci} className="flex flex-col gap-1">
                                    {col.map((c, di) => {
                                        const intensity = c.count === 0 ? 0 : Math.ceil((c.count / heatGrid.max) * 4);
                                        const bg = [
                                            "rgba(255,255,255,0.04)",
                                            "rgba(255,42,84,0.25)",
                                            "rgba(255,42,84,0.45)",
                                            "rgba(255,42,84,0.7)",
                                            "rgba(255,42,84,1)",
                                        ][intensity];
                                        return (
                                            <div
                                                key={di}
                                                className="w-3 h-3 rounded-sm"
                                                style={{ background: bg }}
                                                title={`${c.date}: ${c.count} ep${c.count !== 1 ? "s" : ""}`}
                                            />
                                        );
                                    })}
                                </div>
                            ))}
                        </div>
                        <div className="mt-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-white/50">
                            menos
                            {[0, 1, 2, 3, 4].map((i) => (
                                <span key={i} className="w-3 h-3 rounded-sm" style={{
                                    background: ["rgba(255,255,255,0.04)", "rgba(255,42,84,0.25)", "rgba(255,42,84,0.45)", "rgba(255,42,84,0.7)", "rgba(255,42,84,1)"][i],
                                }} />
                            ))}
                            mais
                        </div>
                    </div>
                </section>
            )}

            {/* Top genres */}
            {stats.top_genres?.length > 0 && (
                <section className="px-6 md:px-10 mt-12" data-testid="stats-top-genres">
                    <h2 className="font-display text-2xl font-bold mb-4">Gêneros favoritos</h2>
                    <div className="glass rounded-2xl p-6 space-y-3">
                        {stats.top_genres.slice(0, 8).map((g) => {
                            const max = Math.max(...stats.top_genres.map((x) => x.count));
                            const pct = (g.count / max) * 100;
                            return (
                                <div key={g.genre}>
                                    <div className="flex items-center justify-between text-sm mb-1">
                                        <span className="font-semibold">{g.genre}</span>
                                        <span className="text-white/50 text-xs font-bold">{g.count}</span>
                                    </div>
                                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                                        <div className="h-full bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] transition-all duration-700" style={{ width: `${pct}%` }} />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            {/* Top series */}
            {stats.top_series?.length > 0 && (
                <section className="px-6 md:px-10 mt-12 mb-20" data-testid="stats-top-series">
                    <h2 className="font-display text-2xl font-bold mb-4">Séries que você mais consumiu</h2>
                    <div className="space-y-2">
                        {stats.top_series.map((s, i) => (
                            <Link key={s.tmdb_id} to={`/series/${s.tmdb_id}`} className="glass rounded-xl p-4 flex items-center gap-4 hover:border-white/20 transition-all">
                                <span className="font-display text-3xl font-black text-white/30 w-10">{i + 1}</span>
                                <div className="flex-1">
                                    <p className="font-bold">{s.name}</p>
                                    <p className="text-xs text-white/50 mt-0.5">{s.episodes} episódio{s.episodes !== 1 ? "s" : ""} assistido{s.episodes !== 1 ? "s" : ""}</p>
                                </div>
                            </Link>
                        ))}
                    </div>
                </section>
            )}
        </AppLayout>
    );
}

function BigStat({ label, value, icon: Icon, accent }) {
    return (
        <div className={`rounded-2xl p-5 border ${accent ? "bg-gradient-to-br from-[#FF2A54]/10 to-transparent border-[#FF2A54]/30" : "bg-white/5 border-white/10"}`}>
            <Icon className={`w-5 h-5 ${accent ? "text-[#FF2A54]" : "text-white/40"}`} />
            <p className="font-display text-3xl md:text-4xl font-black mt-3 tracking-tight">{value ?? 0}</p>
            <p className="text-[10px] font-bold uppercase tracking-wider text-white/60 mt-1">{label}</p>
        </div>
    );
}
