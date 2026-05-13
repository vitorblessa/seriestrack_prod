import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { formatApiError } from "../lib/api";
import { Tv, Mail, Lock, Loader2 } from "lucide-react";

const AUTH_BG = "https://images.unsplash.com/photo-1763895971784-f7e00791cae3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHw0fHxjaW5lbWF0aWMlMjBkYXJrJTIwZnV0dXJpc3RpYyUyMGNpdHl8ZW58MHx8fHwxNzc4MDk3ODUyfDA&ixlib=rb-4.1.0&q=85";

export default function Login() {
    const { user, login } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    if (user) return <Navigate to="/dashboard" replace />;

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(email, password);
            navigate("/dashboard");
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex">
            {/* Side image */}
            <div className="hidden lg:block lg:w-1/2 relative">
                <img src={AUTH_BG} alt="" className="absolute inset-0 w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-tr from-[#0A0A0C] via-[#0A0A0C]/40 to-transparent" />
                <div className="absolute bottom-12 left-12 right-12">
                    <div className="flex items-center gap-2 mb-6">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center">
                            <Tv className="w-5 h-5" strokeWidth={2.5} />
                        </div>
                        <span className="font-display font-black text-2xl">SeriesTrack</span>
                    </div>
                    <h2 className="font-display text-4xl font-black leading-tight max-w-md">
                        Suas séries favoritas.<br/>
                        <span className="text-white/60">Sempre em dia.</span>
                    </h2>
                </div>
            </div>

            {/* Form */}
            <div className="w-full lg:w-1/2 flex items-center justify-center p-6 md:p-12">
                <form onSubmit={onSubmit} className="w-full max-w-md animate-fade-up">
                    <Link to="/" className="lg:hidden flex items-center gap-2 mb-10">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center">
                            <Tv className="w-5 h-5" strokeWidth={2.5} />
                        </div>
                        <span className="font-display font-black text-xl">SeriesTrack</span>
                    </Link>

                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Bem-vindo de volta</p>
                    <h1 className="font-display text-4xl md:text-5xl font-black mt-2">Entrar</h1>
                    <p className="text-white/50 mt-3">Continue acompanhando suas séries onde parou.</p>

                    {error && (
                        <div data-testid="auth-error" className="mt-6 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                            {error}
                        </div>
                    )}

                    <div className="mt-8 space-y-4">
                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-white/60">Email</span>
                            <div className="mt-2 relative">
                                <Mail className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-white/40" />
                                <input
                                    data-testid="auth-email-input"
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="voce@email.com"
                                    className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#FF2A54] focus:bg-white/10 outline-none transition-all"
                                />
                            </div>
                        </label>

                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-white/60">Senha</span>
                            <div className="mt-2 relative">
                                <Lock className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-white/40" />
                                <input
                                    data-testid="auth-password-input"
                                    type="password"
                                    required
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#FF2A54] focus:bg-white/10 outline-none transition-all"
                                />
                            </div>
                        </label>
                    </div>

                    <button
                        type="submit"
                        data-testid="auth-submit-button"
                        disabled={loading}
                        className="btn-primary w-full mt-8 disabled:opacity-60"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                        Entrar na minha conta
                    </button>

                    <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-white/40 font-bold">
                        <div className="flex-1 h-px bg-white/10" />
                        ou
                        <div className="flex-1 h-px bg-white/10" />
                    </div>

                    <button
                        type="button"
                        data-testid="google-login-button"
                        onClick={() => {
                            // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
                            const redirectUrl = window.location.origin + "/auth/callback";
                            window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
                        }}
                        className="w-full inline-flex items-center justify-center gap-3 rounded-full bg-white text-black px-8 py-3.5 font-bold tracking-wide hover:bg-white/90 transition-all"
                    >
                        <svg viewBox="0 0 24 24" className="w-5 h-5">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                        Continuar com Google
                    </button>

                    <p className="mt-6 text-sm text-center text-white/50">
                        Ainda não tem conta?{" "}
                        <Link to="/register" className="text-[#FF2A54] hover:text-[#FF4D71] font-semibold">Criar agora</Link>
                    </p>
                </form>
            </div>
        </div>
    );
}
