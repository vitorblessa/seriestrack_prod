import { useEffect, useRef, useState } from "react";
import AppLayout from "../components/AppLayout";
import { Bell, BellOff, Smartphone, Loader2, Send, Check, Upload, CalendarDays, Copy, ExternalLink } from "lucide-react";
import { getPushStatus, subscribePush, unsubscribePush, sendTestPush } from "../lib/push";
import { toast } from "sonner";
import api from "../lib/api";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Settings() {
    const { user } = useAuth();
    const [status, setStatus] = useState(null);
    const [busy, setBusy] = useState(false);
    const [importing, setImporting] = useState(false);
    const [importResult, setImportResult] = useState(null);
    const fileRef = useRef(null);
    const isPro = user?.subscription_tier === "pro";

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

    const handleImport = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        if (file.size > 5 * 1024 * 1024) {
            toast.error("Arquivo muito grande (max 5MB)");
            return;
        }
        setImporting(true);
        setImportResult(null);
        try {
            const fd = new FormData();
            fd.append("file", file);
            const { data } = await api.post("/import/trakt", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setImportResult(data);
            toast.success(`Importadas ${data.added} séries (de ${data.total})`);
        } catch (err) {
            const msg = err?.response?.data?.detail || "Erro ao importar";
            toast.error(typeof msg === "string" ? msg : "Erro ao importar");
        } finally {
            setImporting(false);
            if (fileRef.current) fileRef.current.value = "";
        }
    };

    const downloadICS = async () => {
        try {
            const res = await api.get("/calendar/ical", { responseType: "blob" });
            const blob = new Blob([res.data], { type: "text/calendar" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "seriestrack.ics";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            toast.success("Calendário baixado!");
        } catch {
            toast.error("Erro ao gerar calendário");
        }
    };

    const [feedUrl, setFeedUrl] = useState("");
    const [feedBusy, setFeedBusy] = useState(false);

    const generateFeedUrl = async () => {
        setFeedBusy(true);
        try {
            const { data } = await api.post("/calendar/ical/feed");
            setFeedUrl(data.feed_url);
            await navigator.clipboard.writeText(data.feed_url).catch(() => {});
            toast.success("URL gerada e copiada — qualquer URL anterior foi revogada");
        } catch {
            toast.error("Erro ao gerar URL");
        } finally {
            setFeedBusy(false);
        }
    };

    const revokeFeedUrl = async () => {
        try {
            await api.delete("/calendar/ical/feed");
            setFeedUrl("");
            toast.success("URL revogada — quem tinha o link perdeu acesso");
        } catch {
            toast.error("Erro ao revogar");
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

                <div className="glass rounded-2xl p-6 md:p-8" data-testid="import-trakt-card">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                            <Upload className="w-5 h-5 text-[#FF2A54]" />
                        </div>
                        <div className="flex-1">
                            <h2 className="font-display text-xl font-bold">Importar do Trakt</h2>
                            <p className="text-white/60 text-sm mt-1">
                                Faça upload do seu export do Trakt (JSON ou CSV). Buscamos cada série no TMDB e adicionamos à sua biblioteca como "Quero assistir".
                            </p>
                            {!isPro && (
                                <p className="text-amber-300/80 text-xs mt-2">
                                    Plano Free: máximo de 50 séries no total. Itens além do limite ficam de fora — <Link to="/pricing" className="underline">faça upgrade</Link> para importar tudo.
                                </p>
                            )}
                            <div className="mt-4 flex flex-wrap items-center gap-3">
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept=".json,.csv,application/json,text/csv"
                                    onChange={handleImport}
                                    disabled={importing}
                                    className="hidden"
                                    data-testid="trakt-file-input"
                                    id="trakt-file"
                                />
                                <label
                                    htmlFor="trakt-file"
                                    data-testid="trakt-import-btn"
                                    className={`btn-primary text-sm cursor-pointer ${importing ? "opacity-50 pointer-events-none" : ""}`}
                                >
                                    {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                                    {importing ? "Importando..." : "Escolher arquivo"}
                                </label>
                                <a
                                    href="https://trakt.tv/settings/data"
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-xs text-white/50 hover:text-white inline-flex items-center gap-1"
                                >
                                    Onde baixo meu export? <ExternalLink className="w-3 h-3" />
                                </a>
                            </div>
                            {importResult && (
                                <div className="mt-5 p-4 rounded-xl bg-white/[0.04] border border-white/10 text-sm" data-testid="trakt-import-result">
                                    <p className="font-bold text-emerald-300">
                                        ✓ {importResult.added} séries adicionadas <span className="text-white/50 font-normal">de {importResult.total}</span>
                                    </p>
                                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-white/60">
                                        <div><span className="text-white/40">Duplicadas:</span> {importResult.duplicates}</div>
                                        <div><span className="text-white/40">Não encontradas:</span> {importResult.not_found_count}</div>
                                        <div><span className="text-white/40">Bloqueadas (limite):</span> {importResult.skipped_cap}</div>
                                    </div>
                                    {importResult.skipped_cap > 0 && (
                                        <Link to="/pricing" className="mt-3 inline-block text-xs font-bold text-[#FF2A54] hover:underline">
                                            🔓 Desbloquear ilimitado no Pro →
                                        </Link>
                                    )}
                                    {importResult.not_found?.length > 0 && (
                                        <details className="mt-3">
                                            <summary className="text-xs text-white/50 cursor-pointer">Ver não encontradas ({importResult.not_found.length})</summary>
                                            <ul className="mt-2 text-xs text-white/60 max-h-32 overflow-auto list-disc pl-5">
                                                {importResult.not_found.map((t, i) => <li key={i}>{t}</li>)}
                                            </ul>
                                        </details>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="glass rounded-2xl p-6 md:p-8" data-testid="export-ical-card">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-[#FF2A54]/15 border border-[#FF2A54]/30 flex items-center justify-center shrink-0">
                            <CalendarDays className="w-5 h-5 text-[#FF2A54]" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <h2 className="font-display text-xl font-bold">Calendário (iCal)</h2>
                            <p className="text-white/60 text-sm mt-1">
                                Sincronize os próximos episódios da sua biblioteca direto no Google Calendar, Apple Calendar ou Outlook.
                            </p>

                            <div className="mt-4 flex flex-wrap gap-2">
                                <button onClick={downloadICS} className="btn-primary text-sm" data-testid="ical-download-btn">
                                    <CalendarDays className="w-4 h-4" /> Baixar .ics
                                </button>
                                <button onClick={generateFeedUrl} disabled={feedBusy} className="btn-glass text-sm" data-testid="ical-copy-url-btn">
                                    {feedBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Copy className="w-4 h-4" />}
                                    {feedUrl ? "Gerar nova URL" : "Gerar URL de assinatura"}
                                </button>
                                {feedUrl && (
                                    <button onClick={revokeFeedUrl} className="btn-glass text-sm" data-testid="ical-revoke-btn">
                                        Revogar
                                    </button>
                                )}
                            </div>
                            {feedUrl && (
                                <div className="mt-3 p-3 rounded-xl bg-white/[0.04] border border-white/10 text-xs break-all font-mono text-white/70" data-testid="ical-feed-url">
                                    {feedUrl}
                                </div>
                            )}

                            <details className="mt-4 text-xs text-white/60">
                                <summary className="cursor-pointer text-white/70 font-semibold">Como assinar no Google Calendar / Apple</summary>
                                <ol className="mt-2 list-decimal pl-5 space-y-1">
                                    <li>Clique em "Gerar URL de assinatura" acima — copiamos automaticamente.</li>
                                    <li><b>Google Calendar:</b> Outros calendários → De URL → Cole o link.</li>
                                    <li><b>Apple Calendar:</b> Arquivo → Nova Assinatura de Calendário → Cole o link.</li>
                                </ol>
                                <p className="mt-2 text-emerald-300/80">🔒 URL com token isolado (só lê o calendário, não dá acesso à conta). Pode revogar quando quiser.</p>
                            </details>
                        </div>
                    </div>
                </div>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
