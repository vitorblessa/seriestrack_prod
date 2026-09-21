import { useEffect, useRef, useState, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import PosterCard from "./PosterCard";

export default function Rail({ title, subtitle, items, testid, emptyText = "Nada por aqui ainda." }) {
    const scrollerRef = useRef(null);
    const [canLeft, setCanLeft] = useState(false);
    const [canRight, setCanRight] = useState(false);
    const [hovering, setHovering] = useState(false);

    const updateEdges = useCallback(() => {
        const el = scrollerRef.current;
        if (!el) return;
        const max = el.scrollWidth - el.clientWidth;
        setCanLeft(el.scrollLeft > 4);
        setCanRight(el.scrollLeft < max - 4);
    }, []);

    useEffect(() => {
        const el = scrollerRef.current;
        if (!el) return;
        updateEdges();
        el.addEventListener("scroll", updateEdges, { passive: true });
        const ro = new ResizeObserver(updateEdges);
        ro.observe(el);
        return () => {
            el.removeEventListener("scroll", updateEdges);
            ro.disconnect();
        };
    }, [items, updateEdges]);

    const scrollBy = (dir) => {
        const el = scrollerRef.current;
        if (!el) return;
        // Slide by ~85% of the visible width so the last-visible card becomes the anchor
        // of the next page — feels smoother than a full-viewport jump.
        const delta = Math.round(el.clientWidth * 0.85) * dir;
        el.scrollBy({ left: delta, behavior: "smooth" });
    };

    return (
        <section
            className="px-6 md:px-10 mt-12 relative group/rail"
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
        >
            <div className="flex items-end justify-between mb-4">
                <div>
                    <h2 className="font-display text-2xl md:text-3xl font-bold tracking-tight">{title}</h2>
                    {subtitle && <p className="text-white/50 text-sm mt-1">{subtitle}</p>}
                </div>
            </div>
            {(!items || items.length === 0) ? (
                <p className="text-white/40 text-sm">{emptyText}</p>
            ) : (
                <div className="relative">
                    <div
                        ref={scrollerRef}
                        data-testid={testid}
                        className="flex overflow-x-auto gap-4 md:gap-5 pb-3 snap-x scrollbar-thin -mx-6 md:-mx-10 px-6 md:px-10"
                    >
                        {items.map((s) => (
                            <PosterCard key={s.id || s.tmdb_id} show={s} />
                        ))}
                    </div>

                    {/* Desktop-only nav arrows — appear on rail hover, fade when at edge */}
                    <button
                        type="button"
                        aria-label="Anterior"
                        data-testid={`${testid}-prev`}
                        onClick={() => scrollBy(-1)}
                        className={`hidden md:flex absolute top-1/2 -translate-y-1/2 left-1 z-10 w-11 h-11 items-center justify-center rounded-full bg-black/70 backdrop-blur border border-white/10 text-white/90 hover:bg-black hover:scale-105 transition-all duration-200 ${
                            hovering && canLeft ? "opacity-100" : "opacity-0 pointer-events-none"
                        }`}
                        style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.5)" }}
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <button
                        type="button"
                        aria-label="Próximo"
                        data-testid={`${testid}-next`}
                        onClick={() => scrollBy(1)}
                        className={`hidden md:flex absolute top-1/2 -translate-y-1/2 right-1 z-10 w-11 h-11 items-center justify-center rounded-full bg-black/70 backdrop-blur border border-white/10 text-white/90 hover:bg-black hover:scale-105 transition-all duration-200 ${
                            hovering && canRight ? "opacity-100" : "opacity-0 pointer-events-none"
                        }`}
                        style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.5)" }}
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>

                    {/* Edge fades — hint that content continues off-screen */}
                    <div
                        className={`hidden md:block pointer-events-none absolute inset-y-0 left-0 w-12 -ml-6 md:-ml-10 bg-gradient-to-r from-[#0A0A0C] to-transparent transition-opacity duration-200 ${
                            canLeft ? "opacity-100" : "opacity-0"
                        }`}
                    />
                    <div
                        className={`hidden md:block pointer-events-none absolute inset-y-0 right-0 w-12 -mr-6 md:-mr-10 bg-gradient-to-l from-[#0A0A0C] to-transparent transition-opacity duration-200 ${
                            canRight ? "opacity-100" : "opacity-0"
                        }`}
                    />
                </div>
            )}
        </section>
    );
}
