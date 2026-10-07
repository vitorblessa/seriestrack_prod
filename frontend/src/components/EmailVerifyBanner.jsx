import { useState } from "react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import api from "../lib/api";
import { Mail, X, Loader2 } from "lucide-react";

export default function EmailVerifyBanner() {
    const { user } = useAuth();
    const [sending, setSending] = useState(false);
    const [dismissed, setDismissed] = useState(false);

    if (!user || user.email_verified || dismissed) return null;

    const resend = async () => {
        setSending(true);
        try {
            await api.post("/auth/resend_verification");
            toast.success("E-mail de confirmação reenviado — confira a caixa de entrada (e o spam).");
        } catch {
            toast.error("Não deu pra reenviar agora. Tenta de novo em instantes.");
        } finally {
            setSending(false);
        }
    };

    return (
        <div data-testid="email-verify-banner" className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2.5 flex items-center justify-center gap-3 text-sm text-amber-200 text-center">
            <Mail className="w-4 h-4 shrink-0" />
            <span>Confirme seu e-mail para garantir o acesso à sua conta.</span>
            <button
                onClick={resend}
                disabled={sending}
                className="font-semibold underline underline-offset-2 hover:text-amber-100 disabled:opacity-60 inline-flex items-center gap-1.5 shrink-0"
            >
                {sending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Reenviar e-mail
            </button>
            <button onClick={() => setDismissed(true)} className="ml-1 text-amber-200/50 hover:text-amber-200 shrink-0" aria-label="Dispensar">
                <X className="w-4 h-4" />
            </button>
        </div>
    );
}
