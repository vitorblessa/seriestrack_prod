import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { Loader2, Play, Heart, Pause, CheckCircle2, Trash2, Library as LibIcon } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { toast } from "sonner";

const STATUSES = [
    { key: "watching", label: "Assistindo", icon: Play },
    { key: "want", label: "Quero assistir", icon: Heart },
    { key: "paused", label: "Pausadas", icon: Pause },
    { key: "finished", label: "Finalizadas", icon: CheckCircle2 },
];

export default function MyLibrary() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState("watching");
    const [stats, setStats] = useState(null);

    const load = async () => {
        setLoading(true);
        try {
            const [{ data: lib }, { data: st }] = await Promise.all([
                api.get("/library"),
                api.get("/stats"),
            ]);
            setItems(lib);
            setStats(st);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const remove = async (tmdb_id) => {
        try {
            await api.delete(`/library/${tmdb_id}`);
            setItems((p) => p.filter((x) => x.tmdb_id !== tmdb_id));
            toast.success("Removida da biblioteca");
            const { data: st } = await api.get("/stats");
            setStats(st);
        } catch {
            toast.error("Erro ao remover");
        }
    };

    const filtered = items.filter((x) => x.status === tab);

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Sua biblioteca</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2 flex items-center gap-3">
                    <LibIcon className="w-9 h-9 text-[#FF2A54]" /> Minha biblioteca
                </h1>

                {/* Stats */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-8" data-testid="library-stats">
                        {STATUSES.map((s) => (
                            <button
                                key={s.key}
                                onClick={() => setTab(s.key)}
                                data-testid={`library-stat-${s.key}`}
                                className={`glass rounded-xl p-4 text-left transition-all ${tab === s.key ? "border-[#FF2A54]/50" : ""}`}
                            >
                                <div className="flex items-center gap-2 text-white/60 text-xs font-bold uppercase tracking-wider">
                                    <s.icon className="w-3.5 h-3.5" /> {s.label}
                                </div>
                                <p className="font-display text-3xl font-black mt-2">{stats[s.key] || 0}</p>
                            </button>
                        ))}
                        <div className="glass rounded-xl p-4">
                            <p className="text-white/60 text-xs font-bold uppercase tracking-wider">Total</p>
                            <p className="font-display text-3xl font-black mt-2 text-[#FF2A54]">{stats.total || 0}</p>
                        </div>
                    </div>
                )}
            </section>

            <section className="px-6 md:px-10 mt-10">
                <Tabs value={tab} onValueChange={setTab}>
                    <TabsList className="bg-white/5 border border-white/10 p-1 flex flex-wrap h-auto">
                        {STATUSES.map((s) => (
                            <TabsTrigger
                                key={s.key}
                                value={s.key}
                                data-testid={`library-tab-${s.key}`}
                                className="data-[state=active]:bg-white data-[state=active]:text-black"
                            >
                                {s.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>

                    <TabsContent value={tab} className="mt-8">
                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
                            </div>
                        ) : filtered.length === 0 ? (
                            <div className="glass rounded-2xl py-20 px-6 text-center">
                                <p className="font-display text-2xl font-bold mb-3">Nenhuma série em "{STATUSES.find((s) => s.key === tab).label}"</p>
                                <p className="text-white/60 mb-6">Comece adicionando algumas séries da busca.</p>
                                <Link to="/search" className="btn-primary inline-flex">Explorar séries</Link>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                                {filtered.map((it) => (
                                    <div key={it.tmdb_id} data-testid={`library-item-${it.tmdb_id}`} className="group relative rounded-xl overflow-hidden border border-white/5 bg-white/5 poster-card">
                                        <Link to={`/series/${it.tmdb_id}`} className="block aspect-[2/3]">
                                            {it.poster_url ? (
                                                <img src={it.poster_url} alt={it.name} className="w-full h-full object-cover" />
                                            ) : (
                                                <div className="w-full h-full bg-surface flex items-center justify-center text-white/30 text-xs">{it.name}</div>
                                            )}
                                        </Link>
                                        <div className="p-3">
                                            <p className="text-sm font-bold line-clamp-1">{it.name}</p>
                                        </div>
                                        <button
                                            onClick={() => remove(it.tmdb_id)}
                                            data-testid={`library-remove-${it.tmdb_id}`}
                                            className="absolute top-2 right-2 p-2 rounded-full bg-black/70 backdrop-blur opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/80"
                                            title="Remover"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
