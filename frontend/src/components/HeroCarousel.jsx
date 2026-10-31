import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import useEmblaCarousel from "embla-carousel-react";
import { Sparkles, Play, ChevronLeft, ChevronRight } from "lucide-react";

const AUTOPLAY_MS = 6000;

// The API hands back TMDB's "original" backdrop (often 3-4 MB). A hero that
// spans at most ~1280px of screen doesn't need that — w1280 is ~10x lighter,
// which matters with 5 slides on a phone.
const lightBackdrop = (url) => (url ? url.replace("/original/", "/w1280/") : url);

/**
 * Dashboard hero as a swipeable carousel: slow autoplay + drag/swipe.
 * Autoplay is paused while the user hovers/touches it, when the tab is hidden,
 * and disabled entirely for prefers-reduced-motion.
 */
export default function HeroCarousel({ items }) {
    const [emblaRef, embla] = useEmblaCarousel({ loop: true, align: "start" });
    const [selected, setSelected] = useState(0);
    const [paused, setPaused] = useState(false);

    useEffect(() => {
        if (!embla) return undefined;
        const onSelect = () => setSelected(embla.selectedScrollSnap());
        onSelect();
        embla.on("select", onSelect);
        embla.on("pointerDown", () => setPaused(true));
        embla.on("pointerUp", () => setPaused(false));
        return () => { embla.off("select", onSelect); };
    }, [embla]);

    // Re-armed on every slide change, so a manual swipe gets a full interval
    // before the next automatic advance.
    useEffect(() => {
        if (!embla || paused || items.length < 2) return undefined;
        let reduce = false;
        try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* noop */ }
        if (reduce) return undefined;
        const id = setInterval(() => {
            if (!document.hidden) embla.scrollNext();
        }, AUTOPLAY_MS);
        return () => clearInterval(id);
    }, [embla, paused, selected, items.length]);

    const prev = useCallback(() => embla && embla.scrollPrev(), [embla]);
    const next = useCallback(() => embla && embla.scrollNext(), [embla]);

    if (!items.length) return null;

    return (
        <section
            className="relative h-[60vh] md:h-[72vh] -mb-8 group"
            data-testid="dashboard-featured"
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
            onFocus={() => setPaused(true)}
            onBlur={() => setPaused(false)}
            aria-roledescription="carousel"
            aria-label="Séries em destaque"
        >
            <div className="h-full overflow-hidden" ref={emblaRef}>
                <div className="flex h-full touch-pan-y">
                    {items.map((s, i) => (
                        <div
                            key={s.id}
                            className="relative h-full flex-[0_0_100%] min-w-0"
                            role="group"
                            aria-roledescription="slide"
                            aria-label={`${i + 1} de ${items.length}`}
                            data-testid={`featured-slide-${i}`}
                        >
                            <div className="absolute inset-0">
                                {s.backdrop_url ? (
                                    <img
                                        src={lightBackdrop(s.backdrop_url)}
                                        alt=""
                                        loading={i === 0 ? "eager" : "lazy"}
                                        draggable={false}
                                        className="w-full h-full object-cover"
                                    />
                                ) : null}
                                <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/60 to-transparent" />
                                <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0C] via-[#0A0A0C]/50 to-transparent" />
                            </div>
                            <div className="relative h-full flex items-end px-6 md:px-10 pb-16 md:pb-20">
                                <div className="max-w-2xl">
                                    <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-primary">
                                        <Sparkles className="w-3 h-3" /> Em destaque agora
                                    </span>
                                    <h1 className="font-display text-4xl md:text-6xl font-black mt-3 tracking-tight leading-tight">
                                        {s.name}
                                    </h1>
                                    <p className="text-white/70 mt-4 line-clamp-3 text-base md:text-lg leading-relaxed">
                                        {s.overview}
                                    </p>
                                    <div className="mt-6 flex gap-3">
                                        <Link
                                            to={`/series/${s.id}`}
                                            className="btn-primary"
                                            data-testid={i === 0 ? "featured-cta" : `featured-cta-${i}`}
                                        >
                                            <Play className="w-4 h-4 fill-white" /> Ver detalhes
                                        </Link>
                                        <Link to="/search" className="btn-glass">Explorar mais</Link>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {items.length > 1 && (
                <>
                    <button
                        type="button"
                        onClick={prev}
                        aria-label="Destaque anterior"
                        data-testid="featured-prev"
                        className="hidden md:flex absolute left-4 top-1/2 -translate-y-1/2 w-11 h-11 items-center justify-center rounded-full bg-black/40 hover:bg-black/60 backdrop-blur text-white opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
                    >
                        <ChevronLeft className="w-6 h-6" />
                    </button>
                    <button
                        type="button"
                        onClick={next}
                        aria-label="Próximo destaque"
                        data-testid="featured-next"
                        className="hidden md:flex absolute right-4 top-1/2 -translate-y-1/2 w-11 h-11 items-center justify-center rounded-full bg-black/40 hover:bg-black/60 backdrop-blur text-white opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
                    >
                        <ChevronRight className="w-6 h-6" />
                    </button>
                    <div className="absolute bottom-10 md:bottom-12 left-0 right-0 flex justify-center gap-1" data-testid="featured-dots">
                        {items.map((s, i) => (
                            <button
                                key={s.id}
                                type="button"
                                onClick={() => embla && embla.scrollTo(i)}
                                aria-label={`Ir para o destaque ${i + 1}`}
                                aria-current={i === selected}
                                className="h-6 px-1 flex items-center"
                            >
                                <span
                                    className={`block h-1.5 rounded-full transition-all ${
                                        i === selected ? "w-6 bg-primary" : "w-1.5 bg-white/40"
                                    }`}
                                />
                            </button>
                        ))}
                    </div>
                </>
            )}
        </section>
    );
}
