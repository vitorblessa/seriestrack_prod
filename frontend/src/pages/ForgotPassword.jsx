import { useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Tv, Mail, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [sent, setSent] = useState(false);

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await api.post("/auth/forgot_password", { email });
            setSent(true);
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

                {sent ? (
                    <div className="text-center" data-testid="forgot-password-sent">
                        <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-6">
                            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                        </div>
                        <h1 className="font-display text-3xl font-black">Verifique seu e-mail</h1>
                        <p className="text-foreground/50 mt-3">
                            Se existir uma conta com o e-mail{" "}
                            <span className="text-foreground/80 font-semibold">{email}</span>, enviamos um link para
                            redefinir a senha. Ele expira em 1 hora.
                        </p>

                        <div className="mt-6 flex gap-3 px-4 py-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-left">
                            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                            <p className="text-amber-200/90 text-sm leading-relaxed">
                                Não encontrou na caixa de entrada? Confira a pasta de{" "}
                                <span className="font-semibold">spam / lixo eletrônico</span>. Se estiver lá,
                                marque o e-mail como <span className="font-semibold">"não é spam"</span> ou
                                adicione <span className="font-semibold">noreply@series-track.com</span> aos
                                remetentes confiáveis — assim os próximos avisos do SeriesTrack chegam direto
                                na sua caixa de entrada.
                            </p>
                        </div>

                        <Link to="/login" className="inline-block mt-8 text-[#FF2A54] hover:text-[#FF4D71] font-semibold">
                            Voltar para o login
                        </Link>
                    </div>
                ) : (
                    <form onSubmit={onSubmit}>
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Recuperar acesso</p>
                        <h1 className="font-display text-4xl font-black mt-2">Esqueceu a senha?</h1>
                        <p className="text-foreground/50 mt-3">
                            Informe seu e-mail e enviaremos um link para redefinir sua senha.
                        </p>

                        {error && (
                            <div data-testid="auth-error" className="mt-6 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                                {error}
                            </div>
                        )}

                        <label className="block mt-8">
                            <span className="text-xs font-bold uppercase tracking-wider text-foreground/60">Email</span>
                            <div className="mt-2 relative">
                                <Mail className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-foreground/40" />
                                <input
                                    data-testid="forgot-email-input"
                                    type="email"
                                    required
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="voce@email.com"
                                    className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-white/5 border border-border focus:border-[#FF2A54] focus:bg-white/10 outline-none transition-all"
                                />
                            </div>
                        </label>

                        <button
                            type="submit"
                            data-testid="forgot-submit-button"
                            disabled={loading}
                            className="btn-primary w-full mt-8 disabled:opacity-60"
                        >
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                            Enviar link de redefinição
                        </button>

                        <p className="mt-6 text-sm text-center text-foreground/50">
                            Lembrou a senha?{" "}
                            <Link to="/login" className="text-[#FF2A54] hover:text-[#FF4D71] font-semibold">Entrar</Link>
                        </p>
                    </form>
                )}
            </div>
        </div>
    );
}
