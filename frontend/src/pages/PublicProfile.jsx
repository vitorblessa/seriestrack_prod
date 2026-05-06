import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import PosterCard from "../components/PosterCard";
import { Loader2, User as UserIcon, Star, Calendar } from "lucide-react";

export default function PublicProfile() {
    const { id } = useParams();
    const [profile, setProfile] = useState(null);
    const [library, setLibrary] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        async function load() {
            try {
                const [{ data: p }, { data: lib }] = await Promise.all([
                    api.get(`/users/${id}/public`),
                    api.get(`/users/${id}/library`),
                ]);
                if (cancelled) return;
                setProfile(p);
                setLibrary(lib);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        load();
        return () => { cancelled = true; };
    }, [id]);

    if (loading) {
        return (
            <AppLayout>
                <div className="min-h-[60vh] flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
                </div>
            </AppLayout>
        );
    }
    if (!profile) {
        return (
            <AppLayout>
                <div className="px-6 md:px-10 py-20 text-center">
                    <p className="font-display text-2xl font-bold">Usuário não encontrado</p>
                </div>
            </AppLayout>
        );
    }

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Perfil público</p>
                <div className="mt-6 flex flex-col md:flex-row gap-6 items-start">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center text-3xl font-display font-black shadow-[0_0_40px_rgba(255,42,84,0.4)] shrink-0">
                        {profile.avatar_url ? (
                            <img src={profile.avatar_url} alt={profile.name} className="w-full h-full rounded-full object-cover" />
                        ) : (
                            (profile.name || "?").charAt(0).toUpperCase()
                        )}
                    </div>
                    <div className="flex-1">
                        <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight">{profile.name}</h1>
                        {profile.joined_at && (
                            <p className="text-white/50 mt-2 flex items-center gap-1 text-sm">
                                <Calendar className="w-3.5 h-3.5" /> Membro desde {String(profile.joined_at).slice(0, 10)}
                            </p>
                        )}
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6 max-w-3xl" data-testid="public-stats">
                            {["watching", "want", "paused", "finished", "total"].map((k) => (
                                <div key={k} className={`rounded-xl p-4 border ${k === "total" ? "bg-[#FF2A54]/10 border-[#FF2A54]/30" : "bg-white/5 border-white/10"}`}>
                                    <p className="text-[10px] font-bold uppercase tracking-wider text-white/60">{
                                        { watching: "Assistindo", want: "Quero", paused: "Pausadas", finished: "Finalizadas", total: "Total" }[k]
                                    }</p>
                                    <p className="font-display text-2xl font-black mt-1">{profile.stats[k] || 0}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {profile.recent_reviews?.length > 0 && (
                <section className="px-6 md:px-10 mt-12">
                    <h2 className="font-display text-2xl font-bold mb-4 flex items-center gap-2">
                        <Star className="w-5 h-5 text-[#FF2A54]" /> Avaliações recentes
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {profile.recent_reviews.map((r, i) => (
                            <Link key={i} to={`/series/${r.tmdb_id}`} className="glass rounded-xl p-4 hover:border-white/20 transition-all">
                                <div className="flex items-center gap-1 mb-2">
                                    {[1, 2, 3, 4, 5].map((n) => (
                                        <Star key={n} className={`w-4 h-4 ${n <= r.rating ? "fill-amber-400 text-amber-400" : "text-white/20"}`} />
                                    ))}
                                </div>
                                {r.comment && <p className="text-white/80 text-sm">{r.comment}</p>}
                                <p className="text-white/40 text-xs mt-2">{(r.updated_at || "").slice(0, 10)}</p>
                            </Link>
                        ))}
                    </div>
                </section>
            )}

            <section className="px-6 md:px-10 mt-12 mb-20">
                <h2 className="font-display text-2xl font-bold mb-4 flex items-center gap-2">
                    <UserIcon className="w-5 h-5 text-[#FF2A54]" /> Biblioteca pública
                </h2>
                {library.length === 0 ? (
                    <p className="text-white/50">Este usuário ainda não tem séries na biblioteca.</p>
                ) : (
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                        {library.map((it) => (
                            <PosterCard key={it.tmdb_id} show={{ id: it.tmdb_id, name: it.name, poster_url: it.poster_url }} />
                        ))}
                    </div>
                )}
            </section>
        </AppLayout>
    );
}
