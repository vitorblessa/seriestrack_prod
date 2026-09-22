import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import api from "../lib/api";
import { toast } from "sonner";
import { AlertTriangle, Loader2 } from "lucide-react";

/**
 * Public route, but requires auth to actually delete. If unauthenticated,
 * we show the info + a CTA to log in. Google Play requires this URL to
 * respond 200 without login.
 */
export default function DeleteAccount() {
    const { user, logout } = useAuth();
    const nav = useNavigate();
    const [confirm, setConfirm] = useState("");
    const [busy, setBusy] = useState(false);

    const doDelete = async () => {
        if (confirm !== "EXCLUIR") {
            toast.error("Digite EXCLUIR para confirmar");
            return;
        }
        if (!window.confirm("Última confirmação. Tem certeza que deseja excluir permanentemente sua conta e todos os dados?")) return;
        setBusy(true);
        try {
            await api.delete("/auth/me");
            toast.success("Conta excluída. Sentiremos sua falta.");
            try { await logout(); } catch (_) {}
            setTimeout(() => nav("/", { replace: true }), 900);
        } catch (e) {
            toast.error(e?.response?.data?.detail || "Erro ao excluir. Tente novamente.");
            setBusy(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0A0C] text-white/90 py-14 px-6" data-testid="delete-account-page">
            <div className="max-w-2xl mx-auto space-y-6">
                <div className="flex items-center justify-between mb-4">
                    <Link to="/" className="text-[#FF2A54] font-bold text-lg">SeriesTrack</Link>
                    <Link to="/" className="text-sm text-white/60 hover:text-white">← Início</Link>
                </div>

                <div className="glass rounded-3xl p-8 border border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-12 h-12 rounded-full bg-red-500/10 grid place-items-center">
                            <AlertTriangle className="w-6 h-6 text-red-400" />
                        </div>
                        <h1 className="font-display text-3xl font-bold">Excluir minha conta</h1>
                    </div>

                    <p className="text-white/70 mb-4">Esta ação é <strong className="text-red-400">permanente e irreversível</strong>. Ao confirmar, removeremos em até 7 dias:</p>
                    <ul className="list-disc pl-6 space-y-1 text-white/70 mb-6 text-sm">
                        <li>Perfil, e-mail, senha e conexão com Google</li>
                        <li>Biblioteca completa e progresso de episódios</li>
                        <li>Todas as avaliações e comentários públicos</li>
                        <li>Notificações e inscrições push</li>
                        <li>Preferências, temas e listas privadas</li>
                        <li>Cache de recomendações de IA</li>
                    </ul>

                    <p className="text-white/50 text-xs mb-6">Retenção obrigatória: os registros de pagamento são anonimizados imediatamente e mantidos por 5 anos, conforme legislação fiscal brasileira. Sua assinatura Stripe será cancelada automaticamente.</p>

                    {user ? (
                        <>
                            <label className="block text-sm text-white/80 mb-2">
                                Digite <code className="bg-white/10 px-2 py-0.5 rounded">EXCLUIR</code> para confirmar:
                            </label>
                            <input
                                data-testid="delete-account-confirm-input"
                                type="text"
                                value={confirm}
                                onChange={(e) => setConfirm(e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-red-500"
                                placeholder="EXCLUIR"
                                autoCapitalize="characters"
                            />
                            <button
                                data-testid="delete-account-confirm-btn"
                                disabled={busy || confirm !== "EXCLUIR"}
                                onClick={doDelete}
                                className="mt-4 w-full bg-red-500 hover:bg-red-600 disabled:bg-red-500/40 disabled:cursor-not-allowed text-white font-bold rounded-xl py-3 flex items-center justify-center gap-2 transition"
                            >
                                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Excluir permanentemente"}
                            </button>
                            <button
                                onClick={() => nav(-1)}
                                className="mt-2 w-full text-white/60 hover:text-white py-3 text-sm"
                            >
                                Cancelar
                            </button>
                        </>
                    ) : (
                        <div className="text-center py-6">
                            <p className="text-white/70 mb-4">Faça login com sua conta para excluí-la.</p>
                            <Link to="/login" className="btn-primary inline-flex">Entrar</Link>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
