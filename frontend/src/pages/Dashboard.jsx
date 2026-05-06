import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import Rail from "../components/Rail";
import PosterCard from "../components/PosterCard";
import { useAuth } from "../lib/auth";
import { Sparkles, TrendingUp, Loader2, Calendar as CalIcon, Play } from "lucide-react";

export default function Dashboard() {
    const { user } = useAuth();
    const [trending, setTrending] = useState([]);
    const [popular, setPopular] = useState([]);
    const [airing, setAiring] = useState([]);
    const [topRated, setTopRated] = useState([]);
    const [library, setLibrary] = useState([]);
    const [upcoming, setUpcoming] = useState([]);
    const [loading, setLoading] = useState(true);

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
                if (!cancelled) setUpcoming(u.data.filter((e) => e.kind === "upcoming").slice(0, 6));
            } catch {}
        }
        load();
        return () => { cancelled = true; };
    }, []);

    const watching = library.filter((x) => x.status === "watching").map((x) => ({ id: x.tmdb_id, ...x }));
    const featured = trending[0];

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

            {/* Upcoming */}
            {upcoming.length > 0 && (
                <section className="px-6 md:px-10 mt-12" data-testid="rail-upcoming-container">
                    <div className="mb-4">
                        <h2 className="font-display text-2xl md:text-3xl font-bold tracking-tight flex items-center gap-2">
                            <CalIcon className="w-6 h-6 text-[#FF2A54]" />
                            Próximos episódios
                        </h2>
                        <p className="text-white/50 text-sm mt-1">Da sua biblioteca</p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {upcoming.map((e, i) => (
                            <Link key={i} to={`/series/${e.tmdb_id}`} className="glass rounded-xl overflow-hidden flex hover:border-white/20 transition-all">
                                <div className="w-32 aspect-[2/3] shrink-0 bg-surface">
                                    {e.poster_url && <img src={e.poster_url} alt="" className="w-full h-full object-cover" />}
                                </div>
                                <div className="p-4 flex-1 min-w-0">
                                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF2A54]">{e.air_date}</p>
                                    <p className="font-display font-bold text-base line-clamp-1 mt-1">{e.series_name}</p>
                                    <p className="text-white/60 text-sm mt-1">T{e.season_number}·E{e.episode_number}</p>
                                    <p className="text-white/50 text-xs mt-1 line-clamp-2">{e.episode_name}</p>
                                </div>
                            </Link>
                        ))}
                    </div>
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
