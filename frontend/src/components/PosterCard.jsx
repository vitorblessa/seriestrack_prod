import { Link } from "react-router-dom";
import { Star } from "lucide-react";

export default function PosterCard({ show, size = "md" }) {
    const widths = {
        sm: "w-32 md:w-36",
        md: "w-40 md:w-48",
        lg: "w-48 md:w-56",
    };
    return (
        <Link
            to={`/series/${show.id || show.tmdb_id}`}
            data-testid={`series-poster-card-${show.id || show.tmdb_id}`}
            className={`group relative ${widths[size]} shrink-0 snap-start rounded-xl overflow-hidden poster-card border border-white/5 bg-white/5 block`}
        >
            <div className="aspect-[2/3] w-full relative overflow-hidden">
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
                <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <div className="absolute bottom-0 left-0 right-0 p-3 translate-y-2 group-hover:translate-y-0 opacity-0 group-hover:opacity-100 transition-all duration-300">
                    <p className="text-sm font-bold leading-tight line-clamp-2">{show.name}</p>
                    {show.vote_average ? (
                        <p className="text-[11px] text-white/70 mt-1 flex items-center gap-1">
                            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                            {Number(show.vote_average).toFixed(1)}
                        </p>
                    ) : null}
                </div>
            </div>
        </Link>
    );
}
