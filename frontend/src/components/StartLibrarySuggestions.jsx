import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api from "../lib/api";

/** Shown on the dashboard while the user's library is empty — a quick way to
 * seed it with one tap, instead of having to open each series' page first.
 * Fase 2 roadmap item: "Onboarding guiado". */
export default function StartLibrarySuggestions({ shows, onAdded }) {
    const [addingId, setAddingId] = useState(null);
    const [addedIds, setAddedIds] = useState(new Set());

    if (!shows || shows.length === 0) return null;

    const addToLibrary = async (show) => {
        const tmdbId = show.id || show.tmdb_id;
        setAddingId(tmdbId);
        try {
            await api.post("/library", {
                tmdb_id: tmdbId,
                status: "want",
                name: show.name,
                poster_url: show.poster_url,
                backdrop_url: show.backdrop_url,
                overview: show.overview,
            });
            setAddedIds((prev) => new Set(prev).add(tmdbId));
            toast.success(`"${show.name}" adicionada como "Quero ver"`);
            onAdded?.(tmdbId);
        } catch (e) {
            const detail = e?.response?.data?.detail;
            if (e?.response?.status === 402 && detail?.code === "library_cap_reached") {
                toast.error(detail.message, {
                    action: { label: "Fazer upgrade", onClick: () => { window.location.href = "/pricing"; } },
                    duration: 8000,
                });
            } else {
                toast.error("Erro ao adicionar");
            }
        } finally {
            setAddingId(null);
        }
    };

    return (
        <section className="px-6 md:px-10 mt-12" data-testid="start-library-suggestions">
            <div className="mb-5">
                <h2 className="font-display text-2xl md:text-3xl font-bold tracking-tight">Comece sua biblioteca</h2>
                <p className="text-white/50 text-sm mt-1">Clique no + para adicionar como "Quero ver" — sem precisar abrir a página da série</p>
            </div>
            <div className="flex overflow-x-auto gap-4 md:gap-5 pb-3 snap-x scrollbar-thin -mx-6 md:-mx-10 px-6 md:px-10">
                {shows.slice(0, 12).map((show) => {
                    const tmdbId = show.id || show.tmdb_id;
                    const isAdding = addingId === tmdbId;
                    const isAdded = addedIds.has(tmdbId);
                    return (
                        <div
                            key={tmdbId}
                            data-testid={`start-suggestion-${tmdbId}`}
                            className="group relative w-40 md:w-48 shrink-0 snap-start rounded-xl overflow-hidden border border-white/5 bg-white/5"
                        >
                            <Link to={`/series/${tmdbId}`} className="block aspect-[2/3] w-full relative overflow-hidden">
                                {show.poster_url ? (
                                    <img
                                        src={show.poster_url}
                                        alt={show.name}
                                        loading="lazy"
                                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center bg-surface text-white/30 text-xs">
                                        sem imagem
                                    </div>
                                )}
                                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                                <div className="absolute bottom-0 left-0 right-0 p-3 translate-y-2 group-hover:translate-y-0 opacity-0 group-hover:opacity-100 transition-all duration-300">
                                    <p className="text-sm font-bold leading-tight line-clamp-2">{show.name}</p>
                                </div>
                            </Link>
                            <button
                                type="button"
                                onClick={() => !isAdded && addToLibrary(show)}
                                disabled={isAdding || isAdded}
                                data-testid={`start-suggestion-add-${tmdbId}`}
                                aria-label={isAdded ? "Adicionada" : "Adicionar à biblioteca"}
                                className={`absolute top-2 right-2 w-8 h-8 rounded-full flex items-center justify-center transition-all shadow-lg ${
                                    isAdded ? "bg-emerald-500 text-white" : "bg-black/70 text-white hover:bg-[#FF2A54] backdrop-blur border border-white/10"
                                }`}
                            >
                                {isAdding ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : isAdded ? (
                                    <Check className="w-4 h-4" />
                                ) : (
                                    <Plus className="w-4 h-4" />
                                )}
                            </button>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}
