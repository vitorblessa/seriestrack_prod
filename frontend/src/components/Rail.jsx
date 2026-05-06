import PosterCard from "./PosterCard";

export default function Rail({ title, subtitle, items, testid, emptyText = "Nada por aqui ainda." }) {
    return (
        <section className="px-6 md:px-10 mt-12">
            <div className="flex items-end justify-between mb-4">
                <div>
                    <h2 className="font-display text-2xl md:text-3xl font-bold tracking-tight">{title}</h2>
                    {subtitle && <p className="text-white/50 text-sm mt-1">{subtitle}</p>}
                </div>
            </div>
            {(!items || items.length === 0) ? (
                <p className="text-white/40 text-sm">{emptyText}</p>
            ) : (
                <div
                    data-testid={testid}
                    className="flex overflow-x-auto gap-4 md:gap-5 pb-4 snap-x scrollbar-hide -mx-6 md:-mx-10 px-6 md:px-10"
                >
                    {items.map((s) => (
                        <PosterCard key={s.id || s.tmdb_id} show={s} />
                    ))}
                </div>
            )}
        </section>
    );
}
