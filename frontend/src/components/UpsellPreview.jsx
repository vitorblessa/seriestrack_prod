import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Crown, ArrowRight, Lock } from "lucide-react";
import api from "../lib/api";

/**
 * Free-tier upsell shown on the Dashboard.
 * Calls /api/ai/preview_rec which returns ONE TMDB-recommendation seeded by user's library
 * (free, no LLM cost). The remaining 4 personalized AI recs require Pro.
 */
export default function UpsellPreview() {
    const [rec, setRec] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/ai/preview_rec");
                if (!cancelled) setRec(data.rec || null);
            } catch {
                if (!cancelled) setRec(null);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    if (loading || !rec) return null;

    return (
        <section className="px-6 md:px-10 mt-12" data-testid="upsell-preview-container">
            <div className="relative glass rounded-2xl overflow-hidden border border-primary/25">
                {/* Backdrop blur layer */}
                {rec.backdrop_url && (
                    <div className="absolute inset-0 opacity-20">
                        <img src={rec.backdrop_url} alt="" className="w-full h-full object-cover blur-2xl scale-110" />
                    </div>
                )}
                <div className="relative grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6 p-5 md:p-8">
                    <Link
                        to={`/series/${rec.tmdb_id}`}
                        className="w-32 md:w-40 aspect-[2/3] rounded-xl overflow-hidden bg-surface mx-auto md:mx-0 shadow-[0_20px_60px_-15px_hsl(var(--primary)/0.4)]"
                        data-testid="upsell-poster-link"
                    >
                        {rec.poster_url && <img src={rec.poster_url} alt={rec.name} className="w-full h-full object-cover" />}
                    </Link>

                    <div className="flex flex-col">
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary flex items-center gap-2">
                            <Sparkles className="w-3 h-3" /> IA escolheu pra você hoje
                        </p>
                        <Link to={`/series/${rec.tmdb_id}`} className="font-display text-2xl md:text-3xl font-black mt-2 hover:text-primary/80 transition-colors">
                            {rec.name}
                        </Link>
                        <div className="flex items-center gap-3 text-xs text-foreground/50 mt-1">
                            {rec.first_air_date && <span>{String(rec.first_air_date).slice(0, 4)}</span>}
                            {rec.vote_average ? <span>⭐ {Number(rec.vote_average).toFixed(1)}</span> : null}
                            {rec.seed_name && <span className="hidden md:inline">· Porque você assiste {rec.seed_name}</span>}
                        </div>
                        {rec.overview && (
                            <p className="text-foreground/70 text-sm mt-3 line-clamp-3 max-w-2xl">{rec.overview}</p>
                        )}

                        {/* Locked teaser slots */}
                        <div className="mt-5 grid grid-cols-4 gap-2 max-w-md">
                            {[0, 1, 2, 3].map((i) => (
                                <div
                                    key={i}
                                    className="aspect-[2/3] rounded-lg bg-foreground/[0.03] border border-border flex items-center justify-center backdrop-blur-sm relative overflow-hidden"
                                    data-testid={`upsell-locked-slot-${i}`}
                                >
                                    <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent" />
                                    <Lock className="w-4 h-4 text-foreground/40 relative z-10" />
                                </div>
                            ))}
                        </div>
                        <p className="text-foreground/40 text-[11px] mt-2">+ 4 recomendações 100% personalizadas com Claude AI no Pro</p>

                        <div className="mt-5 flex flex-wrap gap-3">
                            <Link
                                to="/pricing"
                                data-testid="upsell-pro-cta"
                                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-primary to-primary/60 hover:from-primary/90 text-white text-sm font-black uppercase tracking-wider shadow-[0_0_25px_hsl(var(--primary)/0.4)]"
                            >
                                <Crown className="w-4 h-4" /> Ver mais 4 no Pro
                                <ArrowRight className="w-4 h-4" />
                            </Link>
                            <Link
                                to={`/series/${rec.tmdb_id}`}
                                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-foreground/5 hover:bg-foreground/10 border border-border text-sm font-semibold"
                                data-testid="upsell-details-link"
                            >
                                Ver detalhes
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
