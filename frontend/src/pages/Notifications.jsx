import { useEffect, useState } from "react";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { Bell, BellRing, Loader2, CheckCheck } from "lucide-react";
import { Link } from "react-router-dom";

export default function Notifications() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        setLoading(true);
        try {
            const { data } = await api.get("/notifications");
            setItems(data);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const markAll = async () => {
        await api.post("/notifications/read_all");
        await load();
    };

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <div className="flex items-end justify-between flex-wrap gap-4">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Atualizações</p>
                        <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2 flex items-center gap-3">
                            <BellRing className="w-9 h-9 text-[#FF2A54]" /> Notificações
                        </h1>
                    </div>
                    {items.some((i) => !i.read) && (
                        <button onClick={markAll} data-testid="notifications-mark-all" className="btn-glass text-sm">
                            <CheckCheck className="w-4 h-4" /> Marcar todas como lidas
                        </button>
                    )}
                </div>
            </section>

            <section className="px-6 md:px-10 mt-8" data-testid="notifications-list">
                {loading ? (
                    <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />
                ) : items.length === 0 ? (
                    <div className="glass rounded-2xl py-20 px-6 text-center">
                        <Bell className="w-10 h-10 mx-auto text-white/30" />
                        <p className="font-display text-xl font-bold mt-4">Nenhuma notificação ainda</p>
                        <p className="text-white/60 mt-2">Adicione séries à sua biblioteca para receber atualizações.</p>
                    </div>
                ) : (
                    <div className="space-y-3 max-w-3xl">
                        {items.map((n, i) => (
                            <Link
                                key={i}
                                to={n.tmdb_id ? `/series/${n.tmdb_id}` : "/notifications"}
                                className={`glass rounded-xl p-4 flex gap-4 hover:border-white/20 transition-all ${!n.read ? "border-[#FF2A54]/40" : ""}`}
                            >
                                <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                                    <Bell className="w-5 h-5 text-[#FF2A54]" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-baseline gap-2">
                                        <p className="font-display font-bold">{n.title}</p>
                                        {!n.read && <span className="w-2 h-2 rounded-full bg-[#FF2A54]" />}
                                    </div>
                                    <p className="text-white/60 text-sm mt-1">{n.message}</p>
                                    <p className="text-white/40 text-xs mt-2">{n.created_at?.slice(0, 16).replace("T", " ")}</p>
                                </div>
                                {n.poster_url && <img src={n.poster_url} alt="" className="w-12 aspect-[2/3] object-cover rounded" />}
                            </Link>
                        ))}
                    </div>
                )}
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
