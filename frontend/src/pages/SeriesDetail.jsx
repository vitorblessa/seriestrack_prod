import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import PosterCard from "../components/PosterCard";
import StreamBadge from "../components/StreamBadge";
import {
    Star, Calendar, Tv, Loader2, Plus, Check, Heart, Pause, CheckCircle2, Clock, Trash2, Play
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { toast } from "sonner";
import SeriesReviews from "../components/SeriesReviews";
import { useAuth } from "../lib/auth";

const STATUSES = [
    { key: "watching", label: "Assistindo", icon: Play },
    { key: "want", label: "Quero assistir", icon: Heart },
    { key: "paused", label: "Pausada", icon: Pause },
    { key: "finished", label: "Finalizada", icon: CheckCircle2 },
];

export default function SeriesDetail() {
    const { id } = useParams();
    const { user } = useAuth();
    const [series, setSeries] = useState(null);
    const [loading, setLoading] = useState(true);
    const [seasonNum, setSeasonNum] = useState(1);
    const [season, setSeason] = useState(null);
    const [seasonLoading, setSeasonLoading] = useState(false);
    const [inLib, setInLib] = useState(null); // null=unknown, item or false
    const [actLoading, setActLoading] = useState(false);
    const [progress, setProgress] = useState(new Set()); // "S-E"
    const [progressSummary, setProgressSummary] = useState(null);

    useEffect(() => {
        let cancelled = false;
        async function load() {
            setLoading(true);
            try {
                const { data } = await api.get(`/series/${id}`);
                if (cancelled) return;
                setSeries(data);
                if (data.seasons && data.seasons.length > 0) {
                    setSeasonNum(data.seasons[0].season_number);
                }
            } catch {
                toast.error("Não foi possível carregar a série");
            } finally {
                if (!cancelled) setLoading(false);
            }
            try {
                const { data: lib } = await api.get(`/library/contains/${id}`);
                if (!cancelled) setInLib(lib.in_library ? lib.item : false);
            } catch {
                if (!cancelled) setInLib(false);
            }
            // Load episode progress (only if logged in)
            if (user) {
                try {
                    const [{ data: prog }, { data: sum }] = await Promise.all([
                        api.get(`/progress/${id}`),
                        api.get(`/progress/${id}/summary`),
                    ]);
                    if (!cancelled) {
                        setProgress(new Set(prog.map((p) => `${p.season}-${p.episode}`)));
                        setProgressSummary(sum);
                    }
                } catch {}
            }
        }
        load();
        return () => { cancelled = true; };
    }, [id, user]);

    useEffect(() => {
        if (!series) return;
        let cancelled = false;
        async function loadSeason() {
            setSeasonLoading(true);
            try {
                const { data } = await api.get(`/series/${id}/season/${seasonNum}`);
                if (!cancelled) setSeason(data);
            } finally {
                if (!cancelled) setSeasonLoading(false);
            }
        }
        loadSeason();
        return () => { cancelled = true; };
    }, [series, id, seasonNum]);

    const setStatus = async (status) => {
        setActLoading(true);
        try {
            await api.post("/library", {
                tmdb_id: Number(id),
                status,
                name: series.name,
                poster_url: series.poster_url,
                backdrop_url: series.backdrop_url,
                overview: series.overview,
            });
            setInLib({ tmdb_id: Number(id), status, name: series.name });
            toast.success(`Adicionada como "${STATUSES.find((s) => s.key === status).label}"`);
        } catch {
            toast.error("Erro ao salvar");
        } finally {
            setActLoading(false);
        }
    };

    const remove = async () => {
        setActLoading(true);
        try {
            await api.delete(`/library/${id}`);
            setInLib(false);
            toast.success("Removida da biblioteca");
        } catch {
            toast.error("Erro ao remover");
        } finally {
            setActLoading(false);
        }
    };

    const toggleWatched = async (s, e) => {
        const key = `${s}-${e}`;
        const next = new Set(progress);
        const willWatch = !next.has(key);
        if (willWatch) next.add(key); else next.delete(key);
        setProgress(next);
        try {
            await api.post("/progress", { tmdb_id: Number(id), season: s, episode: e, watched: willWatch });
            const { data: sum } = await api.get(`/progress/${id}/summary`);
            setProgressSummary(sum);
        } catch {
            // revert
            const r = new Set(progress);
            setProgress(r);
            toast.error("Erro ao salvar progresso");
        }
    };

    const [bulkLoading, setBulkLoading] = useState(false);

    const toggleSeasonWatched = async (s) => {
        const sum = progressSummary?.seasons?.find((x) => x.season_number === s);
        const allWatched = sum && sum.total > 0 && sum.watched >= sum.total;
        const willWatch = !allWatched;
        setBulkLoading(true);
        try {
            await api.post("/progress/bulk", { tmdb_id: Number(id), season: s, watched: willWatch });
            // Refresh both progress set and summary
            const [{ data: prog }, { data: newSum }] = await Promise.all([
                api.get(`/progress/${id}`),
                api.get(`/progress/${id}/summary`),
            ]);
            setProgress(new Set(prog.map((p) => `${p.season}-${p.episode}`)));
            setProgressSummary(newSum);
            toast.success(willWatch ? `Temporada ${s} marcada como assistida` : `Temporada ${s} desmarcada`);
        } catch {
            toast.error("Erro ao atualizar temporada");
        } finally {
            setBulkLoading(false);
        }
    };

    const currentSeasonProgress = progressSummary?.seasons?.find((x) => x.season_number === seasonNum);

    if (loading) {
        return (
            <AppLayout>
                <div className="min-h-[60vh] flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
                </div>
            </AppLayout>
        );
    }
    if (!series) return null;

    return (
        <AppLayout>
            {/* Hero */}
            <section className="relative -mb-12">
                <div className="relative h-[55vh] md:h-[70vh]">
                    {series.backdrop_url && (
                        <img src={series.backdrop_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/70 to-transparent" />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0C] via-[#0A0A0C]/40 to-transparent" />
                </div>

                <div className="relative px-6 md:px-10 -mt-48 md:-mt-64">
                    <div className="flex flex-col md:flex-row gap-8">
                        <div className="w-40 md:w-56 shrink-0 mx-auto md:mx-0">
                            {series.poster_url && (
                                <img src={series.poster_url} alt={series.name} className="w-full rounded-2xl shadow-2xl border border-white/10" />
                            )}
                        </div>
                        <div className="flex-1 min-w-0 animate-fade-up">
                            {series.tagline && (
                                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">{series.tagline}</p>
                            )}
                            <h1 className="font-display text-4xl md:text-6xl font-black tracking-tight leading-tight mt-2">
                                {series.name}
                            </h1>

                            <div className="flex flex-wrap items-center gap-4 mt-4 text-sm text-white/70">
                                {series.vote_average ? (
                                    <span className="flex items-center gap-1.5">
                                        <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                                        <span className="font-bold text-white">{Number(series.vote_average).toFixed(1)}</span>
                                    </span>
                                ) : null}
                                {series.first_air_date && (
                                    <span className="flex items-center gap-1.5">
                                        <Calendar className="w-4 h-4" /> {series.first_air_date.slice(0, 4)}
                                    </span>
                                )}
                                {series.number_of_seasons ? (
                                    <span className="flex items-center gap-1.5">
                                        <Tv className="w-4 h-4" /> {series.number_of_seasons} temporada{series.number_of_seasons > 1 ? "s" : ""} · {series.number_of_episodes} eps
                                    </span>
                                ) : null}
                                {series.status && (
                                    <span className="px-2 py-0.5 rounded border border-white/10 bg-white/5 text-[10px] font-bold uppercase">
                                        {series.status === "Returning Series" ? "Em produção" : series.status}
                                    </span>
                                )}
                            </div>

                            {series.genres?.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-4">
                                    {series.genres.map((g) => (
                                        <span key={g} className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-semibold text-white/80">
                                            {g}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Streaming providers */}
                            {series.providers?.length > 0 && (
                                <div className="mt-6">
                                    <p className="text-xs font-bold uppercase tracking-wider text-white/50 mb-2">Disponível em</p>
                                    <div className="flex flex-wrap gap-2">
                                        {series.providers.map((p) => (
                                            <StreamBadge key={p.provider_id} name={p.provider_name} logoUrl={p.logo_url} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            <p className="mt-6 text-white/80 leading-relaxed text-base max-w-3xl">{series.overview}</p>

                            {/* Action buttons */}
                            <div className="mt-8 flex flex-wrap gap-2" data-testid="series-detail-actions">
                                {STATUSES.map((s) => {
                                    const active = inLib && inLib.status === s.key;
                                    const Icon = s.icon;
                                    return (
                                        <button
                                            key={s.key}
                                            onClick={() => setStatus(s.key)}
                                            disabled={actLoading}
                                            data-testid={`series-action-${s.key}`}
                                            className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold transition-all border ${
                                                active
                                                    ? "bg-[#FF2A54] border-[#FF2A54] text-white shadow-[0_0_20px_rgba(255,42,84,0.4)]"
                                                    : "bg-white/5 border-white/10 hover:bg-white/10"
                                            }`}
                                        >
                                            {active ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                                            {s.label}
                                        </button>
                                    );
                                })}
                                {inLib && (
                                    <button
                                        onClick={remove}
                                        disabled={actLoading}
                                        data-testid="series-action-remove"
                                        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold bg-white/5 border border-white/10 hover:bg-red-500/20 hover:border-red-500/40 text-white/70"
                                    >
                                        <Trash2 className="w-4 h-4" /> Remover
                                    </button>
                                )}
                            </div>

                            {/* Overall progress */}
                            {progressSummary && progressSummary.total_episodes > 0 && (progressSummary.total_watched > 0 || inLib) && (
                                <div className="mt-6 max-w-xl" data-testid="series-overall-progress">
                                    <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-white/60 mb-2">
                                        <span>Seu progresso geral</span>
                                        <span>{progressSummary.total_watched}/{progressSummary.total_episodes} eps · {progressSummary.percent}%</span>
                                    </div>
                                    <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                                        <div className="h-full bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] transition-all duration-500" style={{ width: `${progressSummary.percent}%` }} />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </section>

            {/* Next episode */}
            {series.next_episode_to_air && (
                <section className="px-6 md:px-10 mt-16">
                    <div className="glass rounded-2xl p-6 md:p-8 flex items-center gap-4 md:gap-6">
                        <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                            <Clock className="w-5 h-5 text-[#FF2A54] animate-pulse-glow" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Próximo episódio</p>
                            <p className="font-display text-xl md:text-2xl font-bold mt-1">
                                T{series.next_episode_to_air.season_number}·E{series.next_episode_to_air.episode_number} — {series.next_episode_to_air.name}
                            </p>
                            <p className="text-white/60 text-sm mt-1">Estreia em {series.next_episode_to_air.air_date}</p>
                        </div>
                    </div>
                </section>
            )}

            {/* Seasons & Episodes */}
            {series.seasons?.length > 0 && (
                <section className="px-6 md:px-10 mt-16" data-testid="series-detail-seasons">
                    <h2 className="font-display text-2xl md:text-3xl font-bold mb-6">Temporadas & Episódios</h2>
                    <Tabs value={String(seasonNum)} onValueChange={(v) => setSeasonNum(Number(v))}>
                        <TabsList className="bg-white/5 border border-white/10 flex flex-wrap h-auto">
                            {series.seasons.map((se) => (
                                <TabsTrigger
                                    key={se.season_number}
                                    value={String(se.season_number)}
                                    data-testid={`season-tab-${se.season_number}`}
                                    className="data-[state=active]:bg-white data-[state=active]:text-black"
                                >
                                    T{se.season_number}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                        <TabsContent value={String(seasonNum)} className="mt-6">
                            {currentSeasonProgress && (
                                <div className="glass rounded-xl p-4 mb-4 flex items-center gap-4 flex-wrap" data-testid="season-progress">
                                    <div className="flex-1 min-w-[200px]">
                                        <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-white/60">
                                            <span>Progresso da temporada</span>
                                            <span>{currentSeasonProgress.watched}/{currentSeasonProgress.total} · {currentSeasonProgress.percent}%</span>
                                        </div>
                                        <div className="mt-2 h-2 rounded-full bg-white/5 overflow-hidden">
                                            <div className="h-full bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] transition-all duration-500" style={{ width: `${currentSeasonProgress.percent}%` }} />
                                        </div>
                                    </div>
                                    {inLib && currentSeasonProgress.total > 0 && (
                                        (() => {
                                            const allWatched = currentSeasonProgress.watched >= currentSeasonProgress.total;
                                            return (
                                                <button
                                                    onClick={() => toggleSeasonWatched(seasonNum)}
                                                    disabled={bulkLoading}
                                                    data-testid={`season-bulk-toggle-${seasonNum}`}
                                                    className={`shrink-0 inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider border transition-all ${
                                                        allWatched
                                                            ? "bg-white/5 border-white/15 text-white/70 hover:bg-white/10"
                                                            : "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25"
                                                    } disabled:opacity-60`}
                                                >
                                                    {bulkLoading ? (
                                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                    ) : allWatched ? (
                                                        <><Trash2 className="w-3.5 h-3.5" /> Desmarcar temporada</>
                                                    ) : (
                                                        <><CheckCircle2 className="w-3.5 h-3.5" /> Marcar temporada como assistida</>
                                                    )}
                                                </button>
                                            );
                                        })()
                                    )}
                                </div>
                            )}
                            {seasonLoading ? (
                                <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />
                            ) : season ? (
                                <div className="space-y-3">
                                    {season.episodes.map((ep) => {
                                        const watched = progress.has(`${ep.season_number}-${ep.episode_number}`);
                                        return (
                                            <div key={ep.id} className={`glass rounded-xl p-4 flex flex-col md:flex-row gap-4 transition-all ${watched ? "opacity-70" : ""}`}>
                                                {ep.still_url ? (
                                                    <img src={ep.still_url} alt="" className="w-full md:w-44 aspect-video object-cover rounded-lg" />
                                                ) : (
                                                    <div className="w-full md:w-44 aspect-video bg-surface rounded-lg" />
                                                )}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-baseline gap-3 flex-wrap">
                                                        <span className="text-xs font-bold uppercase tracking-wider text-[#FF2A54]">EP {ep.episode_number}</span>
                                                        <h3 className="font-display font-bold text-lg">{ep.name}</h3>
                                                        {ep.air_date && <span className="text-xs text-white/50">{ep.air_date}</span>}
                                                    </div>
                                                    <p className="text-white/60 text-sm mt-2 line-clamp-3">{ep.overview || "Sem descrição."}</p>
                                                </div>
                                                {user && (
                                                    <button
                                                        onClick={() => toggleWatched(ep.season_number, ep.episode_number)}
                                                        data-testid={`episode-toggle-${ep.season_number}-${ep.episode_number}`}
                                                        className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold uppercase tracking-wider border transition-all ${
                                                            watched
                                                                ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                                                                : "bg-white/5 border-white/10 hover:bg-white/10 text-white/70"
                                                        }`}
                                                    >
                                                        {watched ? <><Check className="w-3.5 h-3.5" /> Assistido</> : <><Plus className="w-3.5 h-3.5" /> Marcar</>}
                                                    </button>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : null}
                        </TabsContent>
                    </Tabs>
                </section>
            )}

            {/* Cast */}
            {series.cast?.length > 0 && (
                <section className="px-6 md:px-10 mt-16">
                    <h2 className="font-display text-2xl md:text-3xl font-bold mb-6">Elenco</h2>
                    <div className="flex overflow-x-auto gap-4 pb-4 scrollbar-hide -mx-6 md:-mx-10 px-6 md:px-10">
                        {series.cast.map((c, i) => (
                            <div key={i} className="w-32 shrink-0 text-center">
                                <div className="w-32 h-32 rounded-full bg-surface overflow-hidden border border-white/10 mx-auto">
                                    {c.profile_url && <img src={c.profile_url} alt={c.name} className="w-full h-full object-cover" />}
                                </div>
                                <p className="font-semibold text-sm mt-3 line-clamp-2">{c.name}</p>
                                <p className="text-white/50 text-xs line-clamp-1">{c.character}</p>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* Reviews */}
            <SeriesReviews tmdbId={Number(id)} />

            {/* Recommendations */}
            {series.recommendations?.length > 0 && (
                <section className="px-6 md:px-10 mt-16 mb-20">
                    <h2 className="font-display text-2xl md:text-3xl font-bold mb-6">Você também pode gostar</h2>
                    <div className="flex overflow-x-auto gap-4 pb-4 scrollbar-hide -mx-6 md:-mx-10 px-6 md:px-10">
                        {series.recommendations.map((s) => <PosterCard key={s.id} show={s} />)}
                    </div>
                </section>
            )}
        </AppLayout>
    );
}
