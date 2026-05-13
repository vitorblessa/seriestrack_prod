import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { Sparkles, Loader2, Share2, Tv, Clock, Flame, Calendar, Trophy, Star, ChevronRight } from "lucide-react";
import { toast } from "sonner";

const CURRENT_YEAR = new Date().getFullYear();

export default function Wrapped() {
    const { year: yearParam, userId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const isShareView = location.pathname.startsWith("/wrapped/share/");
    const year = parseInt(yearParam || CURRENT_YEAR, 10);

    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError("");
            try {
                const path = isShareView
                    ? `/wrapped/${year}/share/${userId}`
                    : `/wrapped/${year}`;
                const { data: res } = await api.get(path);
                if (!cancelled) setData(res);
            } catch (e) {
                if (!cancelled) setError(e?.response?.data?.detail || "Não foi possível carregar seu Wrapped");
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [year, userId, isShareView]);

    const share = async () => {
        if (!data || data.empty) return;
        const shareUserId = data?.user?.id;
        const targetUrl = shareUserId
            ? `${window.location.origin}/wrapped/share/${shareUserId}/${year}`
            : window.location.href;
        if (navigator.share) {
            try {
                await navigator.share({
                    title: `Meu SeriesTrack Wrapped ${year}`,
                    text: `Assisti ${data.totals?.episodes} episódios em ${year}!`,
                    url: targetUrl,
                });
                return;
            } catch {/* user canceled */}
        }
        try {
            await navigator.clipboard.writeText(targetUrl);
            toast.success("Link copiado!");
        } catch {
            toast.error("Não foi possível copiar");
        }
    };

    const Layout = isShareView ? ShareLayout : AppLayout;

    if (loading) {
        return (
            <Layout>
                <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
                    <Loader2 className="w-10 h-10 animate-spin text-[#FF2A54]" />
                    <p className="text-white/60 text-sm">Montando seu ano em séries...</p>
                </div>
            </Layout>
        );
    }

    if (error || !data) {
        return (
            <Layout>
                <div className="px-6 md:px-10 py-20 text-center max-w-md mx-auto" data-testid="wrapped-error">
                    <p className="text-white/70">{error || "Sem dados."}</p>
                    <button onClick={() => navigate("/dashboard")} className="btn-primary mt-6 inline-flex">Voltar</button>
                </div>
            </Layout>
        );
    }

    if (data.empty) {
        return (
            <Layout>
                <section className="px-6 md:px-10 pt-16 pb-24 max-w-2xl mx-auto text-center" data-testid="wrapped-empty">
                    <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center mb-8 shadow-[0_30px_80px_-20px_rgba(255,42,84,0.5)]">
                        <Sparkles className="w-12 h-12 text-white" strokeWidth={2.5} />
                    </div>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Wrapped {year}</p>
                    <h1 className="font-display text-4xl md:text-5xl font-black mt-3 tracking-tight">
                        Ainda sem dados pra {year}
                    </h1>
                    <p className="text-white/70 mt-5 text-lg">
                        {data.message || "Marque episódios como assistidos durante o ano e seu Wrapped vai brilhar aqui."}
                    </p>
                    <Link to="/library" className="btn-primary mt-10 inline-flex" data-testid="wrapped-empty-cta">
                        Ir pra biblioteca <ChevronRight className="w-4 h-4" />
                    </Link>
                </section>
            </Layout>
        );
    }

    const { totals, top_series, top_genres, top_day_of_week, top_month, longest_streak_days, biggest_binge, first_episode, last_episode, reviews } = data;

    return (
        <Layout>
            <section className="px-6 md:px-10 pt-10 max-w-5xl mx-auto" data-testid="wrapped-container">
                {/* Hero */}
                <div className="text-center wrapped-fadeup">
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">
                        {isShareView && data.user ? `${data.user.name} · Wrapped ${year}` : `Seu Wrapped ${year}`}
                    </p>
                    <h1 className="font-display text-5xl md:text-7xl font-black tracking-tight mt-4 leading-none">
                        Seu ano em <span className="text-[#FF2A54]">séries</span>.
                    </h1>
                    {!isShareView && (
                        <button onClick={share} className="btn-glass mt-6 inline-flex" data-testid="wrapped-share-btn">
                            <Share2 className="w-4 h-4" /> Compartilhar
                        </button>
                    )}
                </div>

                {/* Big number */}
                <div className="mt-16 grid md:grid-cols-2 gap-5 wrapped-stagger">
                    <StatCard
                        testid="wrapped-total-eps"
                        icon={<Tv className="w-6 h-6" />}
                        label="Episódios assistidos"
                        big={totals.episodes.toLocaleString("pt-BR")}
                        sub={`em ${totals.unique_series} séries diferentes`}
                    />
                    <StatCard
                        testid="wrapped-total-hours"
                        icon={<Clock className="w-6 h-6" />}
                        label="Horas no sofá"
                        big={totals.estimated_hours.toLocaleString("pt-BR")}
                        sub={`= ${totals.estimated_days} dias direto`}
                    />
                </div>

                {/* Top series */}
                <div className="mt-12 wrapped-stagger">
                    <h2 className="font-display text-3xl md:text-4xl font-black tracking-tight mb-6 flex items-center gap-3">
                        <Trophy className="w-7 h-7 text-amber-400" /> Top {top_series.length} séries
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="wrapped-top-series">
                        {top_series.map((s, i) => (
                            <Link
                                key={s.tmdb_id}
                                to={isShareView ? "#" : `/series/${s.tmdb_id}`}
                                className="relative rounded-xl overflow-hidden glass aspect-[2/3] group"
                                data-testid={`wrapped-top-series-${i}`}
                            >
                                {s.poster_url ? (
                                    <img src={s.poster_url} alt={s.name} className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform" />
                                ) : null}
                                <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
                                <span className="absolute top-2 left-2 w-9 h-9 rounded-full bg-[#FF2A54] text-white text-base font-black flex items-center justify-center shadow-lg">
                                    {i + 1}
                                </span>
                                <div className="absolute bottom-0 left-0 right-0 p-3">
                                    <p className="font-display font-bold text-sm leading-tight line-clamp-2">{s.name}</p>
                                    <p className="text-white/70 text-xs mt-1">{s.episodes} eps · {s.estimated_hours}h</p>
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>

                {/* Streak + biggest binge */}
                <div className="mt-12 grid md:grid-cols-2 gap-5 wrapped-stagger">
                    <StatCard
                        testid="wrapped-streak"
                        icon={<Flame className="w-6 h-6 text-orange-400" />}
                        label="Maior sequência"
                        big={`${longest_streak_days} dia${longest_streak_days === 1 ? "" : "s"}`}
                        sub="consecutivos assistindo"
                    />
                    {biggest_binge && (
                        <StatCard
                            testid="wrapped-binge"
                            icon={<Sparkles className="w-6 h-6 text-amber-300" />}
                            label="Maratona do ano"
                            big={`${biggest_binge.episodes} eps`}
                            sub={`em ${formatDatePt(biggest_binge.date)}`}
                        />
                    )}
                </div>

                {/* When + genres */}
                <div className="mt-12 grid md:grid-cols-2 gap-5 wrapped-stagger">
                    <StatCard
                        testid="wrapped-top-month"
                        icon={<Calendar className="w-6 h-6 text-violet-300" />}
                        label="Mês mais ativo"
                        big={top_month.label}
                        sub={`${top_month.count} episódios`}
                    />
                    <StatCard
                        testid="wrapped-top-dow"
                        icon={<Calendar className="w-6 h-6 text-cyan-300" />}
                        label="Seu dia preferido"
                        big={top_day_of_week.label}
                        sub={`${top_day_of_week.count} episódios`}
                    />
                </div>

                {top_genres?.length > 0 && (
                    <div className="mt-12 wrapped-stagger" data-testid="wrapped-genres-card">
                        <h2 className="font-display text-3xl md:text-4xl font-black tracking-tight mb-6">
                            Você é fã de <span className="text-[#FF2A54]">{top_genres[0].genre}</span>
                        </h2>
                        <div className="flex flex-wrap gap-2">
                            {top_genres.map((g, i) => (
                                <span
                                    key={g.genre}
                                    className="px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wider"
                                    style={{
                                        background: i === 0 ? "#FF2A54" : "rgba(255,255,255,0.06)",
                                        color: i === 0 ? "#fff" : "rgba(255,255,255,0.8)",
                                        border: i === 0 ? "none" : "1px solid rgba(255,255,255,0.1)",
                                    }}
                                    data-testid={`wrapped-genre-${i}`}
                                >
                                    {g.genre}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Reviews */}
                {reviews?.count > 0 && (
                    <div className="mt-12 wrapped-stagger" data-testid="wrapped-reviews-card">
                        <StatCard
                            icon={<Star className="w-6 h-6 fill-amber-400 text-amber-400" />}
                            label="Suas avaliações"
                            big={`${reviews.count}`}
                            sub={reviews.average_rating ? `nota média ${reviews.average_rating}/5` : ""}
                        />
                    </div>
                )}

                {/* First + last */}
                <div className="mt-12 wrapped-stagger" data-testid="wrapped-bookends">
                    <h2 className="font-display text-3xl md:text-4xl font-black tracking-tight mb-6">
                        Do começo ao fim
                    </h2>
                    <div className="grid md:grid-cols-2 gap-5">
                        <EpisodeBookend label="Primeiro episódio do ano" ep={first_episode} />
                        <EpisodeBookend label="Último episódio assistido" ep={last_episode} />
                    </div>
                </div>

                {/* Outro */}
                <div className="mt-16 mb-16 text-center wrapped-fadeup">
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">SeriesTrack Wrapped</p>
                    <h2 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-3">
                        Bora pra mais um ano <span className="text-[#FF2A54]">memorável</span>?
                    </h2>
                    {!isShareView && (
                        <div className="mt-8 flex flex-wrap gap-3 justify-center">
                            <button onClick={share} className="btn-primary" data-testid="wrapped-share-bottom-btn">
                                <Share2 className="w-4 h-4" /> Compartilhar meu Wrapped
                            </button>
                            <Link to="/dashboard" className="btn-glass">Voltar pro dashboard</Link>
                        </div>
                    )}
                </div>
            </section>

            <style>{`
                .wrapped-fadeup { animation: wfade 0.7s ease both; }
                .wrapped-stagger { animation: wfade 0.8s ease both; }
                .wrapped-stagger:nth-child(2) { animation-delay: 0.05s; }
                .wrapped-stagger:nth-child(3) { animation-delay: 0.1s; }
                .wrapped-stagger:nth-child(4) { animation-delay: 0.15s; }
                .wrapped-stagger:nth-child(5) { animation-delay: 0.2s; }
                .wrapped-stagger:nth-child(6) { animation-delay: 0.25s; }
                @keyframes wfade { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
            `}</style>
        </Layout>
    );
}

function StatCard({ icon, label, big, sub, testid }) {
    return (
        <div className="glass rounded-2xl p-6 md:p-8" data-testid={testid}>
            <div className="flex items-center gap-3 text-white/60 text-xs font-bold uppercase tracking-wider">
                {icon} {label}
            </div>
            <p className="font-display text-5xl md:text-6xl font-black mt-3 leading-none tracking-tight">{big}</p>
            {sub && <p className="text-white/50 text-sm mt-2">{sub}</p>}
        </div>
    );
}

function EpisodeBookend({ label, ep }) {
    if (!ep) return null;
    return (
        <div className="glass rounded-2xl p-5 flex gap-4 items-center">
            <div className="w-16 h-24 rounded-lg overflow-hidden bg-surface shrink-0">
                {ep.poster_url && <img src={ep.poster_url} alt="" className="w-full h-full object-cover" />}
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF2A54]">{label}</p>
                <p className="font-display font-bold text-base line-clamp-1 mt-1">{ep.name}</p>
                <p className="text-white/60 text-xs">T{ep.season}·E{ep.episode}</p>
                <p className="text-white/40 text-xs mt-1">{formatDatePt(ep.watched_at)}</p>
            </div>
        </div>
    );
}

function ShareLayout({ children }) {
    return (
        <div className="min-h-screen bg-obsidian text-white">
            <header className="border-b border-white/5 px-6 md:px-10 py-4 flex items-center justify-between">
                <Link to="/" className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center">
                        <Tv className="w-4 h-4 text-white" />
                    </div>
                    <span className="font-display font-black text-lg">SeriesTrack</span>
                </Link>
                <Link to="/register" className="btn-primary text-sm" data-testid="wrapped-share-cta">
                    Criar meu Wrapped
                </Link>
            </header>
            <main className="max-w-[1200px] mx-auto">{children}</main>
        </div>
    );
}

function formatDatePt(iso) {
    if (!iso) return "";
    try {
        const d = new Date(iso + "T12:00:00Z");
        return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
    } catch {
        return iso;
    }
}
