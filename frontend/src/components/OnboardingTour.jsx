import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent } from "./ui/dialog";
import { Sparkles, Search, CalendarClock, Bell, CalendarDays, UserCog, ChevronRight } from "lucide-react";

export const ONBOARDING_STORAGE_KEY = "seriestrack_onboarding_done";
const STORAGE_KEY = ONBOARDING_STORAGE_KEY;

const STEPS = [
    {
        icon: Sparkles,
        title: "Bem-vindo(a) ao SeriesTrack!",
        body: "Acompanhe tudo que você assiste, descubra novidades e nunca mais perca um episódio.",
    },
    {
        icon: Search,
        title: "Monte sua biblioteca",
        body: "Busque séries e marque como Assistindo, Quero ver, Pausado ou Finalizado. Comece pelas sugestões abaixo — é só clicar no \"+\".",
    },
    {
        icon: CalendarClock,
        title: "Fique por dentro",
        body: "O Dashboard mostra os próximos episódios das séries que você acompanha, direto na tela inicial.",
    },
    {
        icon: Bell,
        title: "Ative as notificações",
        body: "Em Configurações você liga os avisos push do SeriesTrack e recebe um aviso assim que um novo episódio estrear — no navegador, no app instalado (PWA) ou no Android.",
        cta: { label: "Ativar notificações", to: "/settings" },
    },
    {
        icon: CalendarDays,
        title: "Sincronize com o Google Calendar",
        body: "Também em Configurações, conecte sua conta do Google e os próximos episódios entram automaticamente na sua agenda — sem copiar nada manualmente. Prefere Apple Calendar ou Outlook? Dá pra assinar por link também.",
        cta: { label: "Conectar Google Calendar", to: "/settings" },
    },
    {
        icon: UserCog,
        title: "Perfil e Configurações",
        body: "No Perfil você vê suas estatísticas e o status da sua assinatura. Em Configurações ficam o tema (claro/escuro), notificações, sincronização de calendário e importação de outras plataformas — tudo num só lugar.",
    },
];

/** One-time, dismissible tour. Shows only while the user's library is empty
 * and only until they've seen (or skipped) it once — tracked in
 * localStorage, not the backend, since missing it on another device costs
 * nothing (Fase 2 roadmap item: "Onboarding guiado"). Covers the core loop
 * (library → calendar) plus the two most-missed Settings features —
 * push notifications and Google Calendar sync — and points to Perfil/
 * Configurações as the home for everything else. */
export default function OnboardingTour({ show, force = false, onDismiss }) {
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [step, setStep] = useState(0);

    useEffect(() => {
        if (force) {
            setStep(0);
            setOpen(true);
            return;
        }
        if (!show) return;
        try {
            if (localStorage.getItem(STORAGE_KEY) === "1") return;
        } catch {}
        setOpen(true);
    }, [show, force]);

    const dismiss = () => {
        setOpen(false);
        try {
            localStorage.setItem(STORAGE_KEY, "1");
        } catch {}
        onDismiss?.();
    };

    const current = STEPS[step];
    const Icon = current.icon;
    const isLast = step === STEPS.length - 1;

    const goToCta = () => {
        const to = current.cta.to;
        dismiss();
        navigate(to);
    };

    return (
        <Dialog open={open} onOpenChange={(v) => { if (!v) dismiss(); }}>
            <DialogContent
                className="bg-popover border-border text-foreground max-w-md"
                data-testid="onboarding-tour"
            >
                <div className="flex flex-col items-center text-center py-2">
                    <div className="w-14 h-14 rounded-full bg-primary/15 flex items-center justify-center mb-4">
                        <Icon className="w-7 h-7 text-primary" />
                    </div>
                    <h3 className="font-display text-xl font-bold">{current.title}</h3>
                    <p className="text-foreground/60 text-sm mt-2 leading-relaxed">{current.body}</p>
                    {current.cta && (
                        <button
                            onClick={goToCta}
                            data-testid="onboarding-tour-cta"
                            className="text-primary text-sm font-bold mt-3 hover:underline"
                        >
                            {current.cta.label} →
                        </button>
                    )}

                    <div className="flex items-center gap-1.5 mt-6" data-testid="onboarding-tour-dots">
                        {STEPS.map((_, i) => (
                            <span
                                key={i}
                                className={`h-1.5 rounded-full transition-all ${
                                    i === step ? "w-6 bg-primary" : "w-1.5 bg-foreground/20"
                                }`}
                            />
                        ))}
                    </div>

                    <div className="flex items-center justify-between w-full mt-6 gap-3">
                        <button
                            onClick={dismiss}
                            data-testid="onboarding-tour-skip"
                            className="text-foreground/50 text-sm font-medium hover:text-foreground/80 transition-colors"
                        >
                            Pular
                        </button>
                        <button
                            onClick={() => (isLast ? dismiss() : setStep((s) => s + 1))}
                            data-testid="onboarding-tour-next"
                            className="btn-primary px-5 py-2 text-sm"
                        >
                            {isLast ? "Começar" : "Próximo"}
                            {!isLast && <ChevronRight className="w-4 h-4" />}
                        </button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
