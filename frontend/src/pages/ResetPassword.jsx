import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Tv, Lock, Loader2, CheckCircle2 } from "lucide-react";

export default function ResetPassword() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const token = searchParams.get("token") || "";
    const [password, setPassword] = useState("");
    const [confirm, setConfirm] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [done, setDone] = useState(false);

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        if (password !== confirm) {
            setError("As senhas não coincidem");
            return;
        }
        setLoading(true);
        try {
            await api.post("/auth/reset_password", { token, password });
            setDone(true);
            setTimeout(() => navigate("/login"), 2500);
        } catch (err) {
            setError(formatApiError(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <div className="w-full max-w-md animate-fade-up">
                <Link to="/login" className="flex items-center gap-2 mb-10">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center">
                        <Tv className="w-5 h-5" strokeWidth={2.5} />
                    </div>
                    <span className="font-display font-black text-xl">SeriesTrack</span>
                </Link>

                {!token ? (
                    <div className="text-center">
                        <h1 className="font-display text-3xl font-black">Link inválido</h1>
                        <p className="text-foreground/50 mt-3">Esse link de redefinição está incompleto ou expirou.</p>
                        <Link to="/forgot-password" className="inline-block mt-8 text-[#FF2A54] hover:text-[#FF4D71] font-semibold">
                            Solicitar novo link
                        </Link>
                    </div>
                ) : done ? (
                    <div className="text-center" data-testid="reset-password-done">
                        <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-6">
                            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                        </div>
                        <h1 className="font-display text-3xl font-black">Senha redefinida!</h1>
                        <p className="text-foreground/50 mt-3">Redirecionando para o login...</p>
                    </div>
                ) : (
                    <form onSubmit={onSubmit}>
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Recuperar acesso</p>
                        <h1 className="font-display text-4xl font-black mt-2">Nova senha</h1>
                        <p className="text-foreground/50 mt-3">Escolha uma nova senha para sua conta.</p>

                        {error && (
                            <div data-testid="auth-error" className="mt-6 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                                {error}
                            </div>
                        )}

                        <div className="mt-8 space-y-4">
                            <label className="block">
                                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60">Nova senha</span>
                                <div className="mt-2 relative">
                                    <Lock className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-foreground/40" />
                                    <input
                                        data-testid="reset-password-input"
                                        type="password"
                                        required
                                        minLength={6}
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="••••••••"
                                        className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-white/5 border border-border focus:border-[#FF2A54] focus:bg-white/10 outline-none transition-all"
                                    />
                                </div>
                            </label>
                            <label className="block">
                                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60">Confirmar senha</span>
                                <div className="mt-2 relative">
                                    <Lock className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-foreground/40" />
                                    <input
                                        data-testid="reset-password-confirm-input"
                                        type="password"
                                        required
                                        minLength={6}
                                        value={confirm}
                                        onChange={(e) => setConfirm(e.target.value)}
                                        placeholder="••••••••"
                                        className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-white/5 border border-border focus:border-[#FF2A54] focus:bg-white/10 outline-none transition-all"
                                    />
                                </div>
                            </label>
                        </div>

                        <button
                            type="submit"
                            data-testid="reset-submit-button"
                            disabled={loading}
                            className="btn-primary w-full mt-8 disabled:opacity-60"
                        >
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                            Redefinir senha
                        </button>
                    </form>
                )}
            </div>
        </div>
    );
}
