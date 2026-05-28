import { Link, NavLink, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth";
import api from "../lib/api";
import { Search, Home, Library, Calendar, Bell, LogOut, User, Tv, Settings as SettingsIcon, Crown, Sparkles, BarChart3, Award } from "lucide-react";

const navItems = [
    { to: "/dashboard", label: "Início", icon: Home, testid: "nav-home-link" },
    { to: "/search", label: "Buscar", icon: Search, testid: "nav-search-link" },
    { to: "/library", label: "Biblioteca", icon: Library, testid: "nav-library-link" },
    { to: "/calendar", label: "Calendário", icon: Calendar, testid: "nav-calendar-link" },
    { to: "/ai-recommendations", label: "IA Recs", icon: Sparkles, testid: "nav-ai-link", proHint: true },
    { to: "/stats", label: "Stats", icon: BarChart3, testid: "nav-stats-link", proHint: true },
    { to: "/wrapped", label: "Wrapped", icon: Award, testid: "nav-wrapped-link" },
];

export default function AppLayout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [unread, setUnread] = useState(0);

    useEffect(() => {
        let mounted = true;
        async function load() {
            try {
                const { data } = await api.get("/notifications/unread_count");
                if (mounted) setUnread(data.count || 0);
            } catch {}
        }
        load();
        const t = setInterval(load, 30000);
        return () => { mounted = false; clearInterval(t); };
    }, []);

    return (
        <div className="min-h-screen bg-obsidian text-white overflow-x-hidden">
            <header className="sticky top-0 z-50 bg-[#0A0A0C]/70 backdrop-blur-2xl backdrop-saturate-150 border-b border-white/5">
                <div className="max-w-[1400px] mx-auto px-3 sm:px-6 md:px-10 py-3 sm:py-4 flex items-center gap-3 md:gap-8">
                    <Link to="/dashboard" className="flex items-center gap-2 group min-w-0" data-testid="brand-logo">
                        <div className="relative shrink-0">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shadow-[0_0_20px_rgba(255,42,84,0.4)]">
                                <Tv className="w-5 h-5 text-white" strokeWidth={2.5} />
                            </div>
                        </div>
                        <span className="font-display font-black text-lg sm:text-xl tracking-tight truncate">SeriesTrack</span>
                    </Link>

                    <nav className="hidden md:flex items-center gap-1 ml-4">
                        {navItems.map((it) => (
                            <NavLink
                                key={it.to}
                                to={it.to}
                                data-testid={it.testid}
                                className={({ isActive }) =>
                                    `flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold transition-all ${
                                        isActive
                                            ? "bg-white text-black"
                                            : "text-white/60 hover:text-white hover:bg-white/5"
                                    }`
                                }
                            >
                                <it.icon className="w-4 h-4" />
                                {it.label}
                            </NavLink>
                        ))}
                    </nav>

                    <div className="ml-auto flex items-center gap-1.5 sm:gap-2 shrink-0">
                        {user?.subscription_tier !== "pro" && (
                            <button
                                onClick={() => navigate("/pricing")}
                                data-testid="nav-upgrade-btn"
                                className="hidden md:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-[#FF2A54] to-[#7c1531] hover:from-[#FF4D71] hover:to-[#7c1531] text-white text-xs font-black uppercase tracking-wider shadow-[0_0_20px_rgba(255,42,84,0.3)]"
                                title="Fazer upgrade para Pro"
                            >
                                <Crown className="w-3.5 h-3.5" /> Upgrade
                            </button>
                        )}
                        {user?.subscription_tier === "pro" && (
                            <span data-testid="nav-pro-badge" className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-amber-500/20 to-[#FF2A54]/20 border border-amber-400/40 text-amber-200 text-xs font-bold uppercase tracking-wider">
                                <Crown className="w-3.5 h-3.5" /> Pro
                            </span>
                        )}
                        <button
                            onClick={() => navigate("/notifications")}
                            data-testid="nav-notifications-btn"
                            className="relative p-2 sm:p-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/5"
                            title="Notificações"
                        >
                            <Bell className="w-4 h-4" />
                            {unread > 0 && (
                                <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-[#FF2A54] text-[10px] font-bold flex items-center justify-center">
                                    {unread > 9 ? "9+" : unread}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => navigate("/profile")}
                            data-testid="nav-profile-btn"
                            className="flex items-center gap-2 p-1 md:pl-1 md:pr-3 md:py-1 rounded-full bg-white/5 hover:bg-white/10 border border-white/5"
                            title="Perfil"
                        >
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center text-xs font-bold">
                                {(user?.name || "?").charAt(0).toUpperCase()}
                            </div>
                            <span className="hidden md:inline text-xs font-semibold text-white/80 max-w-[100px] truncate">
                                {user?.name || "Convidado"}
                            </span>
                        </button>
                        {/* Settings + Logout only on desktop — mobile users use the in-app routes (/settings, /profile→logout) */}
                        <button
                            onClick={() => navigate("/settings")}
                            data-testid="nav-settings-btn"
                            className="hidden md:inline-flex p-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/5 text-white/60 hover:text-white"
                            title="Configurações"
                        >
                            <SettingsIcon className="w-4 h-4" />
                        </button>
                        <button
                            onClick={logout}
                            data-testid="nav-logout-btn"
                            className="hidden md:inline-flex p-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/5 text-white/60 hover:text-white"
                            title="Sair"
                        >
                            <LogOut className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Mobile nav — horizontal scroll keeps it from overflowing the viewport */}
                <div className="md:hidden border-t border-white/5 overflow-x-auto scrollbar-hide">
                    <div className="flex gap-1 px-3 py-2 w-max min-w-full justify-around">
                        {navItems.map((it) => (
                            <NavLink
                                key={it.to}
                                to={it.to}
                                data-testid={`mobile-${it.testid}`}
                                className={({ isActive }) =>
                                    `flex flex-col items-center gap-0.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold shrink-0 whitespace-nowrap ${
                                        isActive ? "text-white" : "text-white/50"
                                    }`
                                }
                            >
                                <it.icon className="w-4 h-4" />
                                {it.label}
                            </NavLink>
                        ))}
                    </div>
                </div>
            </header>

            <main className="max-w-[1400px] mx-auto w-full">{children}</main>

            <footer className="border-t border-white/5 mt-24 py-10 px-6 text-center text-white/40 text-sm">
                <p>SeriesTrack © 2026 — Powered by TMDB. Todas as séries dos seus streamings em um só lugar.</p>
            </footer>
        </div>
    );
}
