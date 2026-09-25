import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { Sparkles, Loader2, Crown, Plus, Check, Star } from "lucide-react";
import { toast } from "sonner";

export default function AIRecommendations() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [recs, setRecs] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const isPro = user?.subscription_tier === "pro";

    useEffect(() => {
        if (!isPro) return;
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isPro]);

    const load = async () => {
        setLoading(true);
        setError("");
        try {
            const { data } = await api.post("/ai/recommendations");
            setRecs(data.recommendations || []);
        } catch (e) {
            if (e?.response?.status === 402) {
                navigate("/pricing");
                return;
            }
            setError("Não foi possível gerar recomendações. Tente novamente em instantes.");
        } finally {
            setLoading(false);
        }
    };

    const addToLib = async (rec) => {
        try {
            await api.post("/library", {
                tmdb_id: rec.tmdb_id,
                status: "want",
                name: rec.name,
                poster_url: rec.poster_url,
                backdrop_url: rec.backdrop_url,
            });
            toast.success(`${rec.name} adicionada como "Quero assistir"`);
            setRecs((p) => p.map((r) => (r.tmdb_id === rec.tmdb_id ? { ...r, in_library: true } : r)));
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
        }
    };

    if (!isPro) {
        return (
            <AppLayout>
                <section className="px-6 md:px-10 pt-16 pb-24 max-w-2xl mx-auto text-center" data-testid="ai-paywall">
                    <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shadow-[0_30px_80px_-20px_rgba(255,42,84,0.5)]">
                        <Sparkles className="w-10 h-10 text-white" strokeWidth={2.5} />
                    </div>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54] mt-8">Recurso Pro</p>
                    <h1 className="font-display text-4xl md:text-5xl font-black mt-3 tracking-tight">
                        IA que conhece seu gosto
                    </h1>
                    <p className="text-white/70 mt-5 text-lg max-w-md mx-auto">
                        Google Gemini analisa sua biblioteca e avaliações para sugerir 5 séries que você vai amar — com explicação personalizada do porquê.
                    </p>
                    <Link to="/pricing" className="btn-primary mt-10 inline-flex" data-testid="ai-paywall-cta">
                        <Crown className="w-4 h-4" /> Fazer upgrade pra Pro
                    </Link>
                </section>
            </AppLayout>
        );
    }

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <div className="flex items-end justify-between flex-wrap gap-4">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54] flex items-center gap-2">
                            <Sparkles className="w-3 h-3" /> Pro · Recomendações IA
                        </p>
                        <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">
                            Pra você assistir agora
                        </h1>
                        <p className="text-white/60 mt-2 max-w-2xl">
                            Geradas com Google Gemini baseadas no que você já tem na biblioteca e nas suas avaliações.
                        </p>
                    </div>
                    <button onClick={load} disabled={loading} className="btn-glass text-sm" data-testid="ai-regenerate-btn">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        Gerar novas
                    </button>
                </div>
            </section>

            <section className="px-6 md:px-10 mt-10" data-testid="ai-recs-list">
                {loading && !recs ? (
                    <div className="flex flex-col items-center py-20 gap-4">
                        <Loader2 className="w-10 h-10 animate-spin text-[#FF2A54]" />
                        <p className="text-white/60 text-sm">Analisando seu gosto...</p>
                    </div>
                ) : error ? (
                    <div className="glass rounded-2xl py-12 text-center max-w-md mx-auto">
                        <p className="text-white/70">{error}</p>
                        <button onClick={load} className="btn-primary mt-6 inline-flex">Tentar novamente</button>
                    </div>
                ) : !recs || recs.length === 0 ? (
                    <div className="glass rounded-2xl py-16 text-center max-w-2xl mx-auto">
                        <p className="font-display text-xl font-bold">Adicione algumas séries primeiro</p>
                        <p className="text-white/60 mt-2">A IA precisa do seu histórico para recomendar.</p>
                        <Link to="/search" className="btn-primary mt-6 inline-flex">Explorar séries</Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        {recs.map((r, i) => (
                            <div key={r.tmdb_id} className="glass rounded-2xl overflow-hidden flex" data-testid={`ai-rec-${i}`}>
                                <Link to={`/series/${r.tmdb_id}`} className="w-32 aspect-[2/3] shrink-0 bg-surface relative">
                                    {r.poster_url && <img src={r.poster_url} alt="" className="w-full h-full object-cover" />}
                                </Link>
                                <div className="flex-1 p-5 flex flex-col">
                                    <Link to={`/series/${r.tmdb_id}`} className="font-display font-black text-lg leading-tight hover:text-[#FF2A54] transition-colors">
                                        {r.name}
                                    </Link>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-white/50">
                                        {r.first_air_date && <span>{r.first_air_date.slice(0, 4)}</span>}
                                        {r.vote_average ? (
                                            <span className="flex items-center gap-1">
                                                <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                                                {Number(r.vote_average).toFixed(1)}
                                            </span>
                                        ) : null}
                                    </div>
                                    <div className="mt-3 px-3 py-2 rounded-lg bg-[#FF2A54]/10 border border-[#FF2A54]/20">
                                        <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF2A54] mb-1 flex items-center gap-1">
                                            <Sparkles className="w-3 h-3" /> Por que você vai gostar
                                        </p>
                                        <p className="text-sm text-white/80 leading-snug">{r.ai_why}</p>
                                    </div>
                                    <div className="mt-auto pt-4">
                                        {r.in_library ? (
                                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-bold uppercase tracking-wider">
                                                <Check className="w-3.5 h-3.5" /> Na biblioteca
                                            </span>
                                        ) : (
                                            <button
                                                onClick={() => addToLib(r)}
                                                data-testid={`ai-add-${r.tmdb_id}`}
                                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-white/10 hover:bg-white/15 border border-white/15 text-xs font-bold uppercase tracking-wider"
                                            >
                                                <Plus className="w-3.5 h-3.5" /> Quero assistir
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
