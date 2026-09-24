import { useEffect, useState } from "react";
import api from "../lib/api";
import { Star, Loader2, Trash2, MessageSquare, Crown } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import { Link } from "react-router-dom";

export default function SeriesReviews({ tmdbId }) {
    const { user } = useAuth();
    const [list, setList] = useState({ reviews: [], average: null, count: 0 });
    const [mine, setMine] = useState(null);
    const [rating, setRating] = useState(0);
    const [hover, setHover] = useState(0);
    const [comment, setComment] = useState("");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const reload = async () => {
        const [{ data: l }, { data: m }] = await Promise.all([
            api.get(`/reviews/${tmdbId}`),
            api.get(`/reviews/${tmdbId}/mine`).catch(() => ({ data: {} })),
        ]);
        setList(l);
        setMine(m && m.rating ? m : null);
        if (m && m.rating) {
            setRating(m.rating);
            setComment(m.comment || "");
        } else {
            setRating(0);
            setComment("");
        }
        setLoading(false);
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { reload(); }, [tmdbId]);

    const save = async () => {
        if (rating < 1) {
            toast.error("Escolha uma nota de 1 a 5");
            return;
        }
        setSaving(true);
        try {
            await api.post("/reviews", { tmdb_id: Number(tmdbId), rating, comment });
            toast.success("Avaliação salva");
            await reload();
        } catch (e) {
            toast.error("Erro ao salvar");
        } finally {
            setSaving(false);
        }
    };

    const remove = async () => {
        setSaving(true);
        try {
            await api.delete(`/reviews/${tmdbId}`);
            toast.success("Avaliação removida");
            await reload();
        } finally {
            setSaving(false);
        }
    };

    return (
        <section className="px-6 md:px-10 mt-16" data-testid="series-reviews">
            <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
                <div>
                    <h2 className="font-display text-2xl md:text-3xl font-bold">Avaliações da comunidade</h2>
                    {list.average !== null && (
                        <p className="text-white/60 text-sm mt-1 flex items-center gap-2">
                            <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                            <span className="text-white font-bold">{list.average}</span> · {list.count} {list.count === 1 ? "avaliação" : "avaliações"}
                        </p>
                    )}
                </div>
            </div>

            {/* User's review form */}
            <div className="glass rounded-2xl p-5 md:p-6 max-w-3xl">
                <p className="text-xs font-bold uppercase tracking-wider text-white/60">{mine ? "Sua avaliação" : "Avaliar esta série"}</p>
                <div className="mt-3 flex gap-1.5" data-testid="review-stars">
                    {[1, 2, 3, 4, 5].map((n) => (
                        <button
                            key={n}
                            type="button"
                            onMouseEnter={() => setHover(n)}
                            onMouseLeave={() => setHover(0)}
                            onClick={() => setRating(n)}
                            data-testid={`review-star-${n}`}
                            className="p-1 transition-transform hover:scale-110"
                        >
                            <Star className={`w-7 h-7 ${(hover || rating) >= n ? "fill-amber-400 text-amber-400" : "text-white/20"}`} />
                        </button>
                    ))}
                </div>
                <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Deixe um comentário (opcional)..."
                    maxLength={1000}
                    data-testid="review-comment"
                    className="mt-4 w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 focus:border-[#FF2A54] outline-none text-sm resize-none"
                    rows={3}
                />
                <div className="mt-4 flex gap-2">
                    <button onClick={save} disabled={saving} data-testid="review-save" className="btn-primary text-sm">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Star className="w-4 h-4" />}
                        {mine ? "Atualizar" : "Publicar"}
                    </button>
                    {mine && (
                        <button onClick={remove} disabled={saving} data-testid="review-delete" className="btn-glass text-sm">
                            <Trash2 className="w-4 h-4" /> Remover
                        </button>
                    )}
                </div>
            </div>

            {/* Other reviews */}
            <div className="mt-8 space-y-3 max-w-3xl">
                {loading ? (
                    <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />
                ) : list.reviews.filter((r) => r.user_id !== (user?.id || "")).length === 0 ? (
                    <p className="text-white/50 text-sm flex items-center gap-2">
                        <MessageSquare className="w-4 h-4" /> Seja o primeiro da comunidade a comentar.
                    </p>
                ) : (
                    list.reviews.filter((r) => r.user_id !== (user?.id || "")).map((r, i) => (
                        <div key={i} className="glass rounded-xl p-4">
                            <div className="flex items-center justify-between flex-wrap gap-2">
                                <Link to={`/u/${r.user_id}`} className="flex items-center gap-2 hover:underline" data-testid={`review-author-${r.user_id}`}>
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${r.user_is_pro ? "bg-gradient-to-br from-amber-400 to-[#FF2A54] ring-2 ring-amber-400/40" : "bg-gradient-to-br from-[#FF2A54] to-[#7c1531]"}`}>
                                        {r.user_avatar
                                            ? <img src={r.user_avatar} alt={r.user_name} className="w-full h-full rounded-full object-cover" />
                                            : (r.user_name || "?").charAt(0).toUpperCase()}
                                    </div>
                                    <span className="font-semibold text-sm flex items-center gap-1">
                                        {r.user_name}
                                        {r.user_is_pro && (
                                            <span title="Assinante Pro" data-testid={`review-pro-badge-${r.user_id}`} className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-gradient-to-br from-amber-400 to-[#FF2A54]">
                                                <Crown className="w-2.5 h-2.5 text-white" strokeWidth={3} />
                                            </span>
                                        )}
                                    </span>
                                </Link>
                                <div className="flex">
                                    {[1, 2, 3, 4, 5].map((n) => (
                                        <Star key={n} className={`w-4 h-4 ${n <= r.rating ? "fill-amber-400 text-amber-400" : "text-white/20"}`} />
                                    ))}
                                </div>
                            </div>
                            {r.comment && <p className="text-white/80 text-sm mt-3">{r.comment}</p>}
                            <p className="text-white/40 text-xs mt-2">{(r.updated_at || "").slice(0, 10)}</p>
                        </div>
                    ))
                )}
            </div>
        </section>
    );
}
