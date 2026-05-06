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

                    <p className="mt-6 text-sm text-center text-white/50">
                        Ainda não tem conta?{" "}
                        <Link to="/register" className="text-[#FF2A54] hover:text-[#FF4D71] font-semibold">Criar agora</Link>
                    </p>

                    <div className="mt-8 px-4 py-3 rounded-lg border border-white/10 bg-white/5 text-xs text-white/50">
                        <span className="font-bold text-white/70">Demo:</span> admin@seriestrack.app / Admin@123
                    </div>
                </form>
            </div>
        </div>
    );
}
