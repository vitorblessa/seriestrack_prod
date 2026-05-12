import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import Rail from "../components/Rail";
import PosterCard from "../components/PosterCard";
import UpsellPreview from "../components/UpsellPreview";
import { useAuth } from "../lib/auth";
import { Sparkles, TrendingUp, Loader2, Calendar as CalIcon, Play } from "lucide-react";
import { brandFor } from "../lib/providers";

export default function Dashboard() {
    const { user } = useAuth();
    const [trending, setTrending] = useState([]);
    const [popular, setPopular] = useState([]);
    const [airing, setAiring] = useState([]);
    const [topRated, setTopRated] = useState([]);
    const [library, setLibrary] = useState([]);
    const [calendarEvents, setCalendarEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [kind, setKind] = useState("upcoming"); // 'upcoming' | 'recent'
    const [providerFilter, setProviderFilter] = useState("all");

    useEffect(() => {
        let cancelled = false;
        async function load() {
            try {
                const [t, p, a, tr, lib] = await Promise.all([
                    api.get("/series/trending"),
                    api.get("/series/popular"),
                    api.get("/series/airing_today"),
                    api.get("/series/top_rated"),
                    api.get("/library"),
                ]);
                if (cancelled) return;
                setTrending(t.data);
                setPopular(p.data);
                setAiring(a.data);
                setTopRated(tr.data);
                setLibrary(lib.data);
            } finally {
                if (!cancelled) setLoading(false);
            }
            try {
                const u = await api.get("/calendar/upcoming");
                if (!cancelled) setCalendarEvents(u.data || []);
            } catch {}
        }
        load();
        return () => { cancelled = true; };
    }, []);

    const watching = library.filter((x) => x.status === "watching").map((x) => ({ id: x.tmdb_id, ...x }));
    const featured = trending[0];

    // Provider chips derived from current kind only
    const eventsOfKind = useMemo(
        () => calendarEvents.filter((e) => e.kind === kind),
        [calendarEvents, kind]
    );
    const availableProviders = useMemo(() => {
        const s = new Set();
        eventsOfKind.forEach((e) => (e.providers || []).forEach((p) => s.add(p)));
        return Array.from(s).sort();
    }, [eventsOfKind]);
    const filteredEvents = useMemo(() => {
        const sorted = [...eventsOfKind].sort((a, b) => {
            const ax = a.air_date || "";
            const bx = b.air_date || "";
            return kind === "upcoming" ? ax.localeCompare(bx) : bx.localeCompare(ax);
        });
        if (providerFilter === "all") return sorted.slice(0, 9);
        return sorted.filter((e) => (e.providers || []).includes(providerFilter)).slice(0, 9);
    }, [eventsOfKind, providerFilter, kind]);

    // Reset provider filter if no longer in available list when switching kinds
    useEffect(() => {
        if (providerFilter !== "all" && !availableProviders.includes(providerFilter)) {
            setProviderFilter("all");
        }
    }, [availableProviders, providerFilter]);

    if (loading) {
        return (
            <AppLayout>
                <div className="min-h-[60vh] flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
                </div>
            </AppLayout>
        );
    }

    return (
        <AppLayout>
            {/* Featured hero */}
            {featured && (
                <section className="relative h-[60vh] md:h-[72vh] -mb-8" data-testid="dashboard-featured">
                    <div className="absolute inset-0">
                        {featured.backdrop_url ? (
                            <img src={featured.backdrop_url} alt="" className="w-full h-full object-cover" />
                        ) : null}
                        <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/60 to-transparent" />
                        <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0C] via-[#0A0A0C]/50 to-transparent" />
                    </div>
                    <div className="relative h-full flex items-end px-6 md:px-10 pb-12 md:pb-16">
                        <div className="max-w-2xl animate-fade-up">
                            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">
                                <Sparkles className="w-3 h-3" /> Em destaque agora
                            </span>
                            <h1 className="font-display text-4xl md:text-6xl font-black mt-3 tracking-tight leading-tight">
                                {featured.name}
                            </h1>
                            <p className="text-white/70 mt-4 line-clamp-3 text-base md:text-lg leading-relaxed">
                                {featured.overview}
                            </p>
                            <div className="mt-6 flex gap-3">
                                <Link to={`/series/${featured.id}`} className="btn-primary" data-testid="featured-cta">
                                    <Play className="w-4 h-4 fill-white" /> Ver detalhes
                                </Link>
                                <Link to="/search" className="btn-glass">Explorar mais</Link>
                            </div>
                        </div>
                    </div>
                </section>
            )}

            {/* Greeting */}
            <section className="px-6 md:px-10 mt-8">
                <h2 className="font-display text-2xl md:text-3xl font-bold">
                    Olá, <span className="text-[#FF2A54]">{user?.name?.split(" ")[0] || "fã de séries"}</span>!
                </h2>
                <p className="text-white/50 text-sm mt-1">{new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}</p>
            </section>

            {/* Continue Watching */}
            {watching.length > 0 && (
                <Rail
                    title="Continue assistindo"
                    subtitle="Suas séries em andamento"
                    items={watching}
                    testid="rail-watching-container"
                />
            )}

            {/* Free-tier upsell hook (hidden for Pro users) */}
            {user?.subscription_tier !== "pro" && library.length > 0 && <UpsellPreview />}

            {/* Upcoming / Recent episodes with streaming filter */}
            {calendarEvents.length > 0 && (
                <section className="px-6 md:px-10 mt-12" data-testid="rail-upcoming-container">
                    <div className="flex items-end justify-between flex-wrap gap-4 mb-5">
                        <div>
                            <h2 className="font-display text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2">
                                <CalIcon className="w-6 h-6 text-[#FF2A54]" />
                                {kind === "upcoming" ? "Próximos episódios" : "Recém lançados"}
                            </h2>
                            <p className="text-white/50 text-sm mt-1">Da sua biblioteca</p>
                        </div>
                        <div className="inline-flex p-1 rounded-full bg-white/5 border border-white/10" data-testid="dashboard-kind-toggle">
                            <button
                                onClick={() => setKind("upcoming")}
                                data-testid="dashboard-kind-upcoming"
                                className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider transition-all ${
                                    kind === "upcoming" ? "bg-white text-black" : "text-white/60 hover:text-white"
                                }`}
                            >
                                Próximos
                            </button>
                            <button
                                onClick={() => setKind("recent")}
                                data-testid="dashboard-kind-recent"
                                className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider transition-all ${
                                    kind === "recent" ? "bg-white text-black" : "text-white/60 hover:text-white"
                                }`}
                            >
                                Recém lançados
                            </button>
                        </div>
                    </div>

                    {availableProviders.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-5" data-testid="dashboard-provider-filters">
                            <button
                                onClick={() => setProviderFilter("all")}
                                data-testid="dashboard-filter-all"
                                className={`px-3.5 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all ${
                                    providerFilter === "all" ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"
                                }`}
                            >
                                Todos ({eventsOfKind.length})
                            </button>
                            {availableProviders.map((p) => {
                                const b = brandFor(p);
                                const active = providerFilter === p;
                                const count = eventsOfKind.filter((e) => (e.providers || []).includes(p)).length;
                                return (
                                    <button
                                        key={p}
                                        onClick={() => setProviderFilter(p)}
                                        data-testid={`dashboard-filter-${p.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                                        className={`px-3.5 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all border ${
                                            active ? "ring-2 ring-white/30" : ""
                                        }`}
                                        style={{
                                            background: active ? b.color : "rgba(255,255,255,0.05)",
                                            color: active ? b.text : "rgba(255,255,255,0.7)",
                                            borderColor: active ? b.color : "rgba(255,255,255,0.1)",
                                        }}
                                    >
                                        {p} ({count})
                                    </button>
                                );
                            })}
                        </div>
                    )}

                    {filteredEvents.length === 0 ? (
                        <div className="glass rounded-xl py-10 text-center text-white/50 text-sm" data-testid="dashboard-events-empty">
                            Nenhum episódio {kind === "upcoming" ? "próximo" : "recente"} {providerFilter !== "all" ? `em ${providerFilter}` : ""}.
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="dashboard-events-grid">
                            {filteredEvents.map((e, i) => (
                                <Link key={`${e.tmdb_id}-${e.season_number}-${e.episode_number}-${i}`} to={`/series/${e.tmdb_id}`} className="glass rounded-xl overflow-hidden flex hover:border-white/20 transition-all">
                                    <div className="w-28 aspect-[2/3] shrink-0 bg-surface">
                                        {e.poster_url && <img src={e.poster_url} alt="" className="w-full h-full object-cover" />}
                                    </div>
                                    <div className="p-4 flex-1 min-w-0">
                                        <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF2A54]">{e.air_date}</p>
                                        <p className="font-display font-bold text-base line-clamp-1 mt-1">{e.series_name}</p>
                                        <p className="text-white/60 text-sm">T{e.season_number}·E{e.episode_number}</p>
                                        <p className="text-white/50 text-xs mt-1 line-clamp-2">{e.episode_name}</p>
                                        {e.providers?.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-2">
                                                {e.providers.slice(0, 3).map((p) => {
                                                    const b = brandFor(p);
                                                    return (
                                                        <span key={p} className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: b.color, color: b.text }}>
                                                            {p}
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </section>
            )}

            <Rail title="Em alta" subtitle="O que está bombando essa semana" items={trending} testid="rail-trending-container" />
            <Rail title="Estreando hoje" subtitle="Episódios saindo agora" items={airing} testid="rail-airing-container" />
            <Rail title="Mais populares" subtitle="Os queridinhos do momento" items={popular} testid="rail-popular-container" />
            <Rail title="Aclamadas pela crítica" subtitle="Top rated de todos os tempos" items={topRated} testid="rail-toprated-container" />

            <div className="h-16" />
        </AppLayout>
    );
}
