import { useEffect, useState } from "react";
import AppLayout from "../components/AppLayout";
import { Bell, BellOff, Smartphone, Loader2, Send, Check } from "lucide-react";
import { getPushStatus, subscribePush, unsubscribePush, sendTestPush } from "../lib/push";
import { toast } from "sonner";
import api from "../lib/api";

export default function Settings() {
    const [status, setStatus] = useState(null);
    const [busy, setBusy] = useState(false);

    const refresh = async () => {
        const s = await getPushStatus();
        setStatus(s);
    };

    useEffect(() => { refresh(); }, []);

    const enable = async () => {
        setBusy(true);
        try {
            await subscribePush();
            toast.success("Notificações ativadas!");
            await refresh();
        } catch (e) {
            toast.error(e.message || "Erro ao ativar");
        } finally {
            setBusy(false);
        }
    };

    const disable = async () => {
        setBusy(true);
        try {
            await unsubscribePush();
            toast.success("Notificações desativadas");
            await refresh();
        } catch (e) {
            toast.error(e.message || "Erro");
        } finally {
            setBusy(false);
        }
    };

    const test = async () => {
        try {
            const { data } = await sendTestPush();
            if (data.sent > 0) toast.success(`Enviado em ${data.sent} dispositivo(s)`);
            else toast.error("Não foi possível enviar");
        } catch (e) {
            toast.error("Erro ao testar");
        }
    };

    const triggerToday = async () => {
        try {
            const { data } = await api.post("/push/notify_today");
            toast.success(`${data.created} notificações criadas, ${data.pushed} envios push`);
        } catch {
            toast.error("Erro");
        }
    };

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Configurações</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">Preferências</h1>
            </section>

            <section className="px-6 md:px-10 mt-10 space-y-4 max-w-3xl">
                <div className="glass rounded-2xl p-6 md:p-8">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                            <Bell className="w-5 h-5 text-[#FF2A54]" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <h2 className="font-display text-xl font-bold">Notificações Push</h2>
                            <p className="text-white/60 text-sm mt-1">
                                Receba alertas no navegador (mesmo com a aba fechada) sempre que novos episódios saírem.
                            </p>
                            {status === null ? (
                                <Loader2 className="w-5 h-5 animate-spin text-white/40 mt-4" />
                            ) : !status.supported ? (
                                <p className="text-amber-400 text-sm mt-4">Seu navegador não suporta web push.</p>
                            ) : (
                                <div className="mt-4 flex flex-wrap gap-2">
                                    {status.subscribed ? (
                                        <>
                                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-bold">
                                                <Check className="w-3.5 h-3.5" /> Ativadas neste dispositivo
                                            </span>
                                            <button onClick={test} disabled={busy} data-testid="push-test-btn" className="btn-glass text-sm">
                                                <Send className="w-4 h-4" /> Enviar teste
                                            </button>
                                            <button onClick={disable} disabled={busy} data-testid="push-disable-btn" className="btn-glass text-sm">
                                                <BellOff className="w-4 h-4" /> Desativar
                                            </button>
                                        </>
                                    ) : (
                                        <button onClick={enable} disabled={busy} data-testid="push-enable-btn" className="btn-primary text-sm">
                                            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />}
                                            Ativar notificações
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="glass rounded-2xl p-6 md:p-8">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                            <Smartphone className="w-5 h-5 text-[#FF2A54]" />
                        </div>
                        <div className="flex-1">
                            <h2 className="font-display text-xl font-bold">Instalar como app (PWA)</h2>
                            <p className="text-white/60 text-sm mt-1">
                                Instale o SeriesTrack no seu celular ou desktop direto do navegador. No Chrome/Edge, use o ícone de instalação na barra de endereços. No iOS, use "Adicionar à Tela de Início" no Safari.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="glass rounded-2xl p-6 md:p-8">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center shrink-0">
                            <Send className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                            <h2 className="font-display text-xl font-bold">Verificar episódios de hoje</h2>
                            <p className="text-white/60 text-sm mt-1">
                                Cria notificações in-app e dispara push para episódios da sua biblioteca que estreiam hoje ou amanhã.
                            </p>
                            <button onClick={triggerToday} data-testid="push-notify-today" className="btn-glass mt-4 text-sm">
                                Verificar agora
                            </button>
                        </div>
                    </div>
                </div>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
