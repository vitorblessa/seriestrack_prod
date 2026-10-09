import { useEffect, useState } from "react";
import { Dialog, DialogContent } from "./ui/dialog";
import { Sparkles, Search, CalendarClock, ChevronRight } from "lucide-react";

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
        body: "Veja os próximos episódios no calendário e receba avisos quando um novo episódio sair.",
    },
];

/** One-time, dismissible 3-step tour. Shows only while the user's library is
 * empty and only until they've seen (or skipped) it once — tracked in
 * localStorage, not the backend, since missing it on another device costs
 * nothing (Fase 2 roadmap item: "Onboarding guiado"). */
export default function OnboardingTour({ show, force = false, onDismiss }) {
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

    return (
        <Dialog open={open} onOpenChange={(v) => { if (!v) dismiss(); }}>
            <DialogContent
                className="bg-[#0F0F12] border-white/10 text-white max-w-md"
                data-testid="onboarding-tour"
            >
                <div className="flex flex-col items-center text-center py-2">
                    <div className="w-14 h-14 rounded-full bg-[#FF2A54]/15 flex items-center justify-center mb-4">
                        <Icon className="w-7 h-7 text-[#FF2A54]" />
                    </div>
                    <h3 className="font-display text-xl font-bold">{current.title}</h3>
                    <p className="text-white/60 text-sm mt-2 leading-relaxed">{current.body}</p>

                    <div className="flex items-center gap-1.5 mt-6" data-testid="onboarding-tour-dots">
                        {STEPS.map((_, i) => (
                            <span
                                key={i}
                                className={`h-1.5 rounded-full transition-all ${
                                    i === step ? "w-6 bg-[#FF2A54]" : "w-1.5 bg-white/20"
                                }`}
                            />
                        ))}
                    </div>

                    <div className="flex items-center justify-between w-full mt-6 gap-3">
                        <button
                            onClick={dismiss}
                            data-testid="onboarding-tour-skip"
                            className="text-white/50 text-sm font-medium hover:text-white/80 transition-colors"
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
