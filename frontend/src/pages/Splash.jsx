import { Link } from "react-router-dom";
import { useEffect, useRef, useState, useCallback } from "react";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { Tv, Bell, Calendar, Sparkles, ArrowRight, Play, ChevronLeft, ChevronRight } from "lucide-react";
import PosterCard from "../components/PosterCard";

const HERO_BG = "https://images.unsplash.com/photo-1755963969538-00dfa22a7c0b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHwxfHxjaW5lbWF0aWMlMjBkYXJrJTIwZnV0dXJpc3RpYyUyMGNpdHl8ZW58MHx8fHwxNzc4MDk3ODUyfDA&ixlib=rb-4.1.0&q=85";

export default function Splash() {
    const { user } = useAuth();
    const [trending, setTrending] = useState([]);
    const scrollerRef = useRef(null);
    const [canLeft, setCanLeft] = useState(false);
    const [canRight, setCanRight] = useState(false);
    const [hovering, setHovering] = useState(false);

    useEffect(() => {
        api.get("/series/trending").then((r) => setTrending(r.data.slice(0, 10))).catch(() => {});
    }, []);

    const updateEdges = useCallback(() => {
        const el = scrollerRef.current;
        if (!el) return;
        const max = el.scrollWidth - el.clientWidth;
        setCanLeft(el.scrollLeft > 4);
        setCanRight(el.scrollLeft < max - 4);
    }, []);

    useEffect(() => {
        const el = scrollerRef.current;
        if (!el) return;
        updateEdges();
        el.addEventListener("scroll", updateEdges, { passive: true });
        const ro = new ResizeObserver(updateEdges);
        ro.observe(el);
        return () => {
            el.removeEventListener("scroll", updateEdges);
            ro.disconnect();
        };
    }, [trending, updateEdges]);

    const scrollBy = (dir) => {
        const el = scrollerRef.current;
        if (!el) return;
        el.scrollBy({ left: Math.round(el.clientWidth * 0.85) * dir, behavior: "smooth" });
    };

    return (
        <div className="min-h-screen bg-obsidian text-white overflow-hidden">
            {/* Top nav */}
            <nav className="fixed top-0 inset-x-0 z-50 bg-[#0A0A0C]/60 backdrop-blur-xl border-b border-white/5">
                <div className="max-w-[1400px] mx-auto px-6 md:px-10 py-4 flex items-center">
                    <div className="flex items-center gap-2">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shadow-[0_0_20px_rgba(255,42,84,0.4)]">
                            <Tv className="w-5 h-5" strokeWidth={2.5} />
                        </div>
                        <span className="font-display font-black text-xl tracking-tight">SeriesTrack</span>
                    </div>
                    <div className="ml-auto flex items-center gap-3">
                        {user ? (
                            <Link to="/dashboard" className="btn-primary text-sm" data-testid="splash-dashboard-button">
                                Ir para o app <ArrowRight className="w-4 h-4" />
                            </Link>
                        ) : (
                            <>
                                <Link to="/login" data-testid="splash-login-button" className="text-sm font-semibold text-white/70 hover:text-white px-4 py-2">
                                    Entrar
                                </Link>
                                <Link to="/register" data-testid="splash-register-button" className="btn-primary text-sm">
                                    Criar conta grátis <ArrowRight className="w-4 h-4" />
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            {/* Hero */}
            <section className="relative min-h-[88vh] flex items-end pt-20">
                <div className="absolute inset-0 z-0">
                    <img src={HERO_BG} alt="" className="w-full h-full object-cover opacity-60" />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/80 to-[#0A0A0C]/30" />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#0A0A0C] via-[#0A0A0C]/60 to-transparent" />
                </div>

                <div className="relative z-10 max-w-[1400px] mx-auto px-6 md:px-10 py-20 md:py-32 w-full">
                    <div className="max-w-3xl animate-fade-up">
                        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass text-xs font-bold uppercase tracking-[0.2em] text-white/80 mb-6">
                            <Sparkles className="w-3 h-3 text-[#FF2A54]" />
                            Lançamento ao vivo via TMDB
                        </span>
                        <h1 className="font-display text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.95] text-balance">
                            Suas séries.<br/>
                            <span className="text-white/60">Todos os streamings.</span><br/>
                            <span className="bg-gradient-to-r from-[#FF2A54] to-[#FF8a6a] bg-clip-text text-transparent">Um só lugar.</span>
                        </h1>
                        <p className="mt-8 text-lg md:text-xl text-white/70 leading-relaxed max-w-2xl">
                            Acompanhe automaticamente o lançamento de episódios em <span className="text-white font-semibold">Netflix, Prime Video, Disney+, Max, Apple TV+, Paramount+, Crunchyroll</span> e mais. Receba alertas, monte calendários e nunca perca uma estreia.
                        </p>
                        <div className="mt-10 flex flex-wrap items-center gap-4">
                            <Link to={user ? "/dashboard" : "/register"} className="btn-primary text-base" data-testid="splash-cta-primary">
                                <Play className="w-4 h-4 fill-white" />
                                Começar gratuitamente
                            </Link>
                            <Link to={user ? "/search" : "/login"} className="btn-glass text-base" data-testid="splash-cta-secondary">
                                Explorar séries
                            </Link>
                        </div>

                        <div className="mt-16 flex flex-wrap gap-8 text-sm">
                            <div>
                                <p className="font-display text-3xl font-black">120k+</p>
                                <p className="text-white/50">séries indexadas</p>
                            </div>
                            <div>
                                <p className="font-display text-3xl font-black">12</p>
                                <p className="text-white/50">streamings monitorados</p>
                            </div>
                            <div>
                                <p className="font-display text-3xl font-black">24/7</p>
                                <p className="text-white/50">tracking automático</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* What is SeriesTrack */}
            <section className="px-6 md:px-10 max-w-[1400px] mx-auto pt-4">
                <div className="max-w-3xl">
                    <h2 className="font-display text-2xl md:text-3xl font-bold">O que é o SeriesTrack?</h2>
                    <p className="mt-4 text-white/70 leading-relaxed">
                        SeriesTrack é um aplicativo web gratuito para quem acompanha séries de TV.
                        Você cria uma conta, monta sua biblioteca pessoal com as séries que assiste
                        (Netflix, Prime Video, Disney+, Max, Apple TV+, Paramount+, Crunchyroll e outros),
                        e o app avisa automaticamente quando um novo episódio ou temporada estreia —
                        por notificação push e, opcionalmente, sincronizando as datas de lançamento
                        direto num calendário separado ("SeriesTrack") na sua conta do Google Calendar.
                        Também oferece recomendações de séries geradas por IA com base no seu histórico.
                    </p>
                </div>
            </section>

            {/* Features */}
            <section className="py-24 px-6 md:px-10 max-w-[1400px] mx-auto">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {[
                        { icon: Tv, title: "Biblioteca pessoal", desc: "Organize séries em Assistindo, Pausadas, Finalizadas e Quero assistir." },
                        { icon: Calendar, title: "Calendário de estreias", desc: "Veja episódios do dia, semana e mês com filtros por streaming, e sincronize automaticamente com seu Google Calendar." },
                        { icon: Bell, title: "Alertas inteligentes", desc: "Notificações quando novos episódios saírem ou novas temporadas estrearem." },
                    ].map((f) => (
                        <div key={f.title} className="glass rounded-2xl p-8 hover:border-white/20 transition-all">
                            <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center mb-5">
                                <f.icon className="w-5 h-5 text-[#FF2A54]" />
                            </div>
                            <h3 className="font-display text-xl font-bold mb-2">{f.title}</h3>
                            <p className="text-white/60 leading-relaxed text-sm">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Trending preview */}
            {trending.length > 0 && (
                <section
                    className="py-16 px-6 md:px-10 max-w-[1400px] mx-auto"
                    onMouseEnter={() => setHovering(true)}
                    onMouseLeave={() => setHovering(false)}
                >
                    <div className="flex items-end justify-between mb-6">
                        <div>
                            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Em alta agora</p>
                            <h2 className="font-display text-3xl md:text-4xl font-bold mt-2">Trending da semana</h2>
                        </div>
                    </div>
                    <div className="relative">
                        <div
                            ref={scrollerRef}
                            data-testid="splash-trending-rail"
                            className="flex overflow-x-auto gap-5 pb-4 snap-x scrollbar-thin -mx-6 md:-mx-10 px-6 md:px-10"
                        >
                            {trending.map((s) => <PosterCard key={s.id} show={s} />)}
                        </div>

                        {/* Desktop nav arrows */}
                        <button
                            type="button"
                            aria-label="Anterior"
                            data-testid="splash-trending-prev"
                            onClick={() => scrollBy(-1)}
                            className={`hidden md:flex absolute top-1/2 -translate-y-1/2 left-1 z-10 w-11 h-11 items-center justify-center rounded-full bg-black/70 backdrop-blur border border-white/10 text-white/90 hover:bg-black hover:scale-105 transition-all duration-200 ${
                                hovering && canLeft ? "opacity-100" : "opacity-0 pointer-events-none"
                            }`}
                            style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.5)" }}
                        >
                            <ChevronLeft className="w-5 h-5" />
                        </button>
                        <button
                            type="button"
                            aria-label="Próximo"
                            data-testid="splash-trending-next"
                            onClick={() => scrollBy(1)}
                            className={`hidden md:flex absolute top-1/2 -translate-y-1/2 right-1 z-10 w-11 h-11 items-center justify-center rounded-full bg-black/70 backdrop-blur border border-white/10 text-white/90 hover:bg-black hover:scale-105 transition-all duration-200 ${
                                hovering && canRight ? "opacity-100" : "opacity-0 pointer-events-none"
                            }`}
                            style={{ boxShadow: "0 8px 24px rgba(0,0,0,0.5)" }}
                        >
                            <ChevronRight className="w-5 h-5" />
                        </button>

                        {/* Edge fades */}
                        <div
                            className={`hidden md:block pointer-events-none absolute inset-y-0 left-0 w-12 -ml-6 md:-ml-10 bg-gradient-to-r from-[#0A0A0C] to-transparent transition-opacity duration-200 ${
                                canLeft ? "opacity-100" : "opacity-0"
                            }`}
                        />
                        <div
                            className={`hidden md:block pointer-events-none absolute inset-y-0 right-0 w-12 -mr-6 md:-mr-10 bg-gradient-to-l from-[#0A0A0C] to-transparent transition-opacity duration-200 ${
                                canRight ? "opacity-100" : "opacity-0"
                            }`}
                        />
                    </div>
                </section>
            )}

            {/* CTA */}
            <section className="py-24 px-6 md:px-10 max-w-[1400px] mx-auto">
                <div className="glass rounded-3xl p-12 md:p-16 text-center relative overflow-hidden">
                    <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-[#FF2A54]/20 blur-3xl" />
                    <div className="relative">
                        <h2 className="font-display text-4xl md:text-5xl font-black tracking-tight">
                            Pronto para nunca mais perder um episódio?
                        </h2>
                        <p className="mt-6 text-white/60 max-w-2xl mx-auto text-lg">
                            Comece grátis. Sem cartão de crédito. Cancele quando quiser.
                        </p>
                        <Link to="/register" className="btn-primary mt-10 text-base inline-flex" data-testid="splash-cta-bottom">
                            Criar minha conta <ArrowRight className="w-4 h-4" />
                        </Link>
                    </div>
                </div>
            </section>

            <footer className="border-t border-white/5 py-10 px-6 text-center text-white/40 text-sm">
                <p>SeriesTrack © 2026 — Powered by TMDB. Feito para fãs de série.</p>
                <div className="flex justify-center gap-6 mt-3 text-xs">
                    <Link to="/privacy" className="hover:text-white/80">Privacidade</Link>
                    <Link to="/terms" className="hover:text-white/80">Termos</Link>
                    <Link to="/delete-account" className="hover:text-white/80">Excluir conta</Link>
                </div>
            </footer>
        </div>
    );
}
