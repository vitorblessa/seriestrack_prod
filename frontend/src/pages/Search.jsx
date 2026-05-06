import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import PosterCard from "../components/PosterCard";
import { Search as SearchIcon, Loader2, Tv, Calendar as CalIcon, X } from "lucide-react";
import { brandFor } from "../lib/providers";

const STREAMINGS = [
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

function chipTestId(name) {
    return `streaming-btn-${name.toLowerCase().replace(/\s+/g, "-")}`;
}

export default function Search() {
    const [q, setQ] = useState("");
    const [results, setResults] = useState([]);
    const [popular, setPopular] = useState([]);
    const [loadingSeries, setLoadingSeries] = useState(false);

    const [selectedStreaming, setSelectedStreaming] = useState(null);
    const [streamingData, setStreamingData] = useState(null);
    const [loadingStreaming, setLoadingStreaming] = useState(false);

    const debounceRef = useRef(null);

    useEffect(() => {
        api.get("/series/popular").then((r) => setPopular(r.data)).catch(() => {});
    }, []);

    // Series search (typed query) — independent of streaming selection
    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        if (!q.trim()) {
            setResults([]);
            return;
        }
        debounceRef.current = setTimeout(async () => {
            setLoadingSeries(true);
            try {
                const { data } = await api.get("/series/search", { params: { q } });
                setResults(data);
            } finally {
                setLoadingSeries(false);
            }
        }, 350);
        return () => debounceRef.current && clearTimeout(debounceRef.current);
    }, [q]);

    // Streaming fetch when a streaming button is selected
    useEffect(() => {
        if (!selectedStreaming) {
            setStreamingData(null);
            return;
        }
        let cancelled = false;
        (async () => {
            setLoadingStreaming(true);
            try {
                const { data } = await api.get("/streaming/episodes", { params: { name: selectedStreaming } });
                if (!cancelled) setStreamingData(data);
            } finally {
                if (!cancelled) setLoadingStreaming(false);
            }
        })();
        return () => { cancelled = true; };
    }, [selectedStreaming]);

    const onSelectStreaming = (name) => {
        // toggle off if same, otherwise switch
        setSelectedStreaming((cur) => (cur === name ? null : name));
        // Clear typed query so the streaming view takes over
        setQ("");
    };

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Buscar</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">
                    Encontre sua próxima obsessão
                </h1>
                <p className="text-white/50 mt-3 max-w-2xl">
                    Digite o nome de uma série <span className="text-white/80">ou</span> clique em um streaming abaixo para ver os <span className="text-white/80">últimos episódios lançados</span> naquela plataforma.
                </p>

                <div className="mt-8 relative max-w-3xl">
                    <SearchIcon className="w-5 h-5 absolute left-5 top-1/2 -translate-y-1/2 text-white/40" />
                    <input
                        data-testid="search-input"
                        type="text"
                        value={q}
                        onChange={(e) => {
                            setQ(e.target.value);
                            // typing clears streaming selection
                            if (e.target.value && selectedStreaming) setSelectedStreaming(null);
                        }}
                        placeholder="Ex: Breaking Bad, House of the Dragon..."
                        className="w-full pl-14 pr-6 py-5 rounded-2xl bg-white/5 border border-white/10 focus:border-[#FF2A54] focus:bg-white/10 outline-none text-lg transition-all"
                    />
                    {loadingSeries && <Loader2 className="w-5 h-5 absolute right-5 top-1/2 -translate-y-1/2 animate-spin text-white/50" />}
                </div>

                {/* Fixed streaming buttons */}
                <div className="mt-5" data-testid="streaming-buttons-row">
                    <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-white/40 mb-2.5">Filtrar por streaming</p>
                    <div className="flex flex-wrap gap-2">
                        {STREAMINGS.map((p) => {
                            const b = brandFor(p);
                            const active = selectedStreaming === p;
                            return (
                                <button
                                    key={p}
                                    onClick={() => onSelectStreaming(p)}
                                    data-testid={chipTestId(p)}
                                    className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-all border inline-flex items-center gap-1.5 ${
                                        active ? "ring-2 ring-white/30 shadow-lg" : "hover:scale-105"
                                    }`}
                                    style={{
                                        background: active ? b.color : "rgba(255,255,255,0.05)",
                                        color: active ? b.text : "rgba(255,255,255,0.75)",
                                        borderColor: active ? b.color : "rgba(255,255,255,0.1)",
                                    }}
                                >
                                    <Tv className="w-3.5 h-3.5" />
                                    {p}
                                    {active && <X className="w-3 h-3 ml-0.5 opacity-80" />}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </section>

            <section className="px-6 md:px-10 mt-10" data-testid="search-results">
                {selectedStreaming ? (
                    <StreamingResults streaming={selectedStreaming} data={streamingData} loading={loadingStreaming} onClose={() => setSelectedStreaming(null)} />
                ) : q.trim() ? (
                    results.length === 0 && !loadingSeries ? (
                        <p className="text-white/50">Nenhuma série encontrada para "{q}".</p>
                    ) : (
                        <>
                            <h2 className="font-display text-xl font-bold mb-6 text-white/70">
                                {results.length} {results.length === 1 ? "resultado" : "resultados"} para "{q}"
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

function StreamingResults({ streaming, data, loading, onClose }) {
    const b = brandFor(streaming);
    if (loading || !data) {
        return (
            <div className="flex items-center gap-3 py-6">
                <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />
                <span className="text-white/60 text-sm">Buscando últimos episódios em {streaming}...</span>
            </div>
        );
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
                    Últimos episódios em {streaming}
                </h2>
                <button
                    onClick={onClose}
                    data-testid="streaming-clear-btn"
                    className="ml-auto inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-white/70"
                >
                    <X className="w-3.5 h-3.5" /> Limpar
                </button>
            </div>

            {eps.length === 0 ? (
                <div className="glass rounded-2xl py-16 px-6 text-center">
                    <CalIcon className="w-10 h-10 mx-auto text-white/30" />
                    <p className="font-display text-xl font-bold mt-4">Nenhum episódio recente em {streaming}</p>
                    <p className="text-white/60 mt-2 max-w-md mx-auto">
                        Não conseguimos encontrar episódios recentes ou próximos para essa plataforma na sua região.
                    </p>
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
                                        style={{
                                            background: e.kind === "upcoming" ? "rgba(255,42,84,0.2)" : "rgba(255,255,255,0.1)",
                                            color: e.kind === "upcoming" ? "#FF8a8a" : "rgba(255,255,255,0.7)",
                                        }}
                                    >
                                        {e.kind === "upcoming" ? "Próximo" : "Recém lançado"}
                                    </span>
                                    {e.in_library && (
                                        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/40 text-emerald-300">
                                            Na biblioteca
                                        </span>
                                    )}
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
