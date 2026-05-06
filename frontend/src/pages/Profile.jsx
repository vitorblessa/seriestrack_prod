import { useEffect, useState } from "react";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { useAuth } from "../lib/auth";
import { User, Mail, Calendar, LogOut, Trophy } from "lucide-react";

export default function Profile() {
    const { user, logout } = useAuth();
    const [stats, setStats] = useState(null);

    useEffect(() => {
        api.get("/stats").then((r) => setStats(r.data)).catch(() => {});
    }, []);

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Perfil</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">Sua conta</h1>
            </section>

            <section className="px-6 md:px-10 mt-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="glass rounded-2xl p-8 text-center">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center mx-auto text-3xl font-display font-black shadow-[0_0_40px_rgba(255,42,84,0.4)]">
                        {(user?.name || "?").charAt(0).toUpperCase()}
                    </div>
                    <h2 className="font-display text-2xl font-bold mt-5">{user?.name}</h2>
                    <p className="text-white/50 text-sm mt-1 flex items-center justify-center gap-1">
                        <Mail className="w-3.5 h-3.5" /> {user?.email}
                    </p>
                    {user?.created_at && (
                        <p className="text-white/40 text-xs mt-3 flex items-center justify-center gap-1">
                            <Calendar className="w-3 h-3" /> Membro desde {String(user.created_at).slice(0, 10)}
                        </p>
                    )}
                    <button onClick={logout} data-testid="profile-logout" className="btn-glass mt-6 text-sm w-full">
                        <LogOut className="w-4 h-4" /> Sair da conta
                    </button>
                </div>

                <div className="lg:col-span-2 glass rounded-2xl p-8">
                    <div className="flex items-center gap-2 mb-6">
                        <Trophy className="w-5 h-5 text-[#FF2A54]" />
                        <h2 className="font-display text-2xl font-bold">Suas estatísticas</h2>
                    </div>
                    {stats ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4" data-testid="profile-stats">
                            <Stat label="Total" value={stats.total} accent />
                            <Stat label="Assistindo" value={stats.watching} />
                            <Stat label="Quero assistir" value={stats.want} />
                            <Stat label="Pausadas" value={stats.paused} />
                            <Stat label="Finalizadas" value={stats.finished} />
                        </div>
                    ) : (
                        <p className="text-white/50">Carregando...</p>
                    )}
                </div>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}

function Stat({ label, value, accent }) {
    return (
        <div className={`rounded-xl p-5 border ${accent ? "bg-[#FF2A54]/10 border-[#FF2A54]/30" : "bg-white/5 border-white/10"}`}>
            <p className="text-xs font-bold uppercase tracking-wider text-white/60">{label}</p>
            <p className="font-display text-4xl font-black mt-2">{value || 0}</p>
        </div>
    );
}
