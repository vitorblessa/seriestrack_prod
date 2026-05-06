import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import PosterCard from "../components/PosterCard";
import { Search as SearchIcon, Loader2, Tv, Calendar as CalIcon } from "lucide-react";
import { PROVIDER_BRANDS, brandFor } from "../lib/providers";

const QUICK_STREAMINGS = [
    "Netflix",
    "Prime Video",
    "Disney+",
    "Max",
    "Apple TV+",
    "Paramount+",
    "Crunchyroll",
    "Globoplay",
    "Hulu",
];

function detectStreaming(query) {
    const ql = (query || "").trim().toLowerCase();
    if (ql.length < 2) return null;
    const names = Object.keys(PROVIDER_BRANDS);
    // exact / startsWith preferred
    let found = names.find((n) => n.toLowerCase() === ql);
    if (found) return found;
    found = names.find((n) => n.toLowerCase().startsWith(ql));
    if (found) return found;
    // contains either way
    found = names.find((n) => n.toLowerCase().includes(ql) || ql.includes(n.toLowerCase()));
    return found || null;
}

export default function Search() {
    const [q, setQ] = useState("");
    const [results, setResults] = useState([]);
    const [popular, setPopular] = useState([]);
    const [loading, setLoading] = useState(false);
    const [streamingData, setStreamingData] = useState(null); // {matched_providers, episodes}
    const debounceRef = useRef(null);

    const streamingMatch = useMemo(() => detectStreaming(q), [q]);

    useEffect(() => {
        api.get("/series/popular").then((r) => setPopular(r.data)).catch(() => {});
    }, []);

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        if (!q.trim()) {
            setResults([]);
            setStreamingData(null);
            return;
        }
        debounceRef.current = setTimeout(async () => {
            setLoading(true);
            try {
                if (streamingMatch) {
                    const { data } = await api.get("/streaming/episodes", { params: { name: streamingMatch } });
                    setStreamingData(data);
                    setResults([]);
                } else {
                    const { data } = await api.get("/series/search", { params: { q } });
                    setResults(data);
                    setStreamingData(null);
                }
            } finally {
                setLoading(false);
            }
        }, 350);
        return () => debounceRef.current && clearTimeout(debounceRef.current);
    }, [q, streamingMatch]);

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Buscar</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">
                    Encontre sua próxima obsessão
                </h1>
                <p className="text-white/50 mt-3 max-w-2xl">
                    Busque pelo nome da série <span className="text-white/80">ou</span> digite o nome de um streaming (ex: <span className="text-[#FF2A54] font-semibold">Netflix</span>) para ver os episódios mais recentes da sua biblioteca naquele streaming.
                </p>

                <div className="mt-8 relative max-w-3xl">
                    <SearchIcon className="w-5 h-5 absolute left-5 top-1/2 -translate-y-1/2 text-white/40" />
                    <input
                        data-testid="search-input"
                        type="text"
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="Ex: Breaking Bad, Netflix, Prime Video..."
                        className="w-full pl-14 pr-6 py-5 rounded-2xl bg-white/5 border border-white/10 focus:border-[#FF2A54] focus:bg-white/10 outline-none text-lg transition-all"
                        autoFocus
                    />
                    {loading && <Loader2 className="w-5 h-5 absolute right-5 top-1/2 -translate-y-1/2 animate-spin text-white/50" />}
                </div>

                {/* Quick streaming chips */}
                <div className="mt-5 flex flex-wrap gap-2" data-testid="search-quick-streamings">
                    <span className="text-[11px] font-bold uppercase tracking-[0.15em] text-white/40 self-center mr-1">Streamings:</span>
                    {QUICK_STREAMINGS.map((p) => {
                        const b = brandFor(p);
                        const active = streamingMatch === p;
                        return (
                            <button
                                key={p}
                                onClick={() => setQ(p)}
                                data-testid={`search-quick-${p.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                                className={`px-3.5 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all border ${active ? "ring-2 ring-white/30" : ""}`}
                                style={{
                                    background: active ? b.color : "rgba(255,255,255,0.05)",
                                    color: active ? b.text : "rgba(255,255,255,0.7)",
                                    borderColor: active ? b.color : "rgba(255,255,255,0.1)",
                                }}
                            >
                                {p}
                            </button>
                        );
                    })}
                </div>
            </section>

            <section className="px-6 md:px-10 mt-10" data-testid="search-results">
                {q.trim() && streamingMatch ? (
                    <StreamingResults streaming={streamingMatch} data={streamingData} loading={loading} />
                ) : q.trim() ? (
                    results.length === 0 && !loading ? (
                        <p className="text-white/50">Nenhum resultado para "{q}".</p>
                    ) : (
                        <>
                            <h2 className="font-display text-xl font-bold mb-6 text-white/70">
                                {results.length} {results.length === 1 ? "resultado" : "resultados"}
                            </h2>
                            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                                {results.map((s) => <PosterCard key={s.id} show={s} />)}
                            </div>
                        </>
                    )
                ) : (
                    <>
                        <h2 className="font-display text-xl font-bold mb-6 text-white/70">Populares para você descobrir</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                            {popular.map((s) => <PosterCard key={s.id} show={s} />)}
                        </div>
                    </>
                )}
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}

function StreamingResults({ streaming, data, loading }) {
    const b = brandFor(streaming);
    if (loading || !data) {
        return <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />;
    }
    const eps = data.episodes || [];
    return (
        <div data-testid="streaming-search-results">
            <div className="flex items-center gap-3 mb-6 flex-wrap">
                <span
                    className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider"
                    style={{ background: b.color, color: b.text }}
                >
                    <Tv className="w-3.5 h-3.5 mr-1.5" /> {streaming}
                </span>
                <h2 className="font-display text-xl font-bold text-white/80">
                    Episódios mais recentes da sua biblioteca em {streaming}
                </h2>
            </div>

            {eps.length === 0 ? (
                <div className="glass rounded-2xl py-16 px-6 text-center">
                    <CalIcon className="w-10 h-10 mx-auto text-white/30" />
                    <p className="font-display text-xl font-bold mt-4">Nada por aqui ainda</p>
                    <p className="text-white/60 mt-2 max-w-md mx-auto">
                        Você não tem séries na sua biblioteca disponíveis em {streaming}, ou nenhum episódio recente foi encontrado.
                    </p>
                    <Link to="/library" className="btn-glass mt-6 inline-flex text-sm">Ver minha biblioteca</Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {eps.map((e, i) => (
                        <Link
                            key={`${e.tmdb_id}-${e.season_number}-${e.episode_number}-${i}`}
                            to={`/series/${e.tmdb_id}`}
                            data-testid={`streaming-episode-${i}`}
                            className="glass rounded-xl overflow-hidden flex hover:border-white/20 transition-all"
                        >
                            <div className="w-32 aspect-[2/3] shrink-0 bg-surface">
                                {e.poster_url && <img src={e.poster_url} alt="" className="w-full h-full object-cover" />}
                            </div>
                            <div className="p-4 flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF2A54]">{e.air_date}</span>
                                    <span
                                        className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
                                        style={{ background: e.kind === "upcoming" ? "rgba(255,42,84,0.2)" : "rgba(255,255,255,0.1)", color: e.kind === "upcoming" ? "#FF8a8a" : "rgba(255,255,255,0.7)" }}
                                    >
                                        {e.kind === "upcoming" ? "Próximo" : "Recém lançado"}
                                    </span>
                                </div>
                                <p className="font-display font-bold text-base line-clamp-1 mt-1">{e.series_name}</p>
                                <p className="text-white/60 text-sm">T{e.season_number}·E{e.episode_number} — {e.episode_name}</p>
                                {e.overview && <p className="text-white/50 text-xs mt-1 line-clamp-2">{e.overview}</p>}
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
