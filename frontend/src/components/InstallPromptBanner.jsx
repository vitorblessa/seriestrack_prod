import { useEffect, useState } from "react";
import { Download, Share, X, Smartphone } from "lucide-react";

const DISMISS_KEY = "seriestrack_install_dismissed_at";
const DISMISS_HOURS = 24 * 7; // don't show again for a week after dismissal

/**
 * Native-style install prompt:
 *  - Android/Chrome: catches `beforeinstallprompt` and shows a custom banner with an "Instalar" button.
 *  - iOS Safari: no BIP event exists; we detect iOS + non-standalone and show a "how-to" sheet.
 *  - Already-installed: renders nothing (display-mode: standalone).
 */
export default function InstallPromptBanner() {
    const [deferredPrompt, setDeferredPrompt] = useState(null);
    const [visible, setVisible] = useState(false);
    const [showIosHelp, setShowIosHelp] = useState(false);

    useEffect(() => {
        // Skip if already installed
        const isStandalone =
            window.matchMedia?.("(display-mode: standalone)").matches ||
            window.navigator.standalone === true;
        if (isStandalone) return;

        // Skip if recently dismissed
        const dismissedAt = Number(localStorage.getItem(DISMISS_KEY) || 0);
        if (dismissedAt && Date.now() - dismissedAt < DISMISS_HOURS * 3600 * 1000) return;

        const isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent);
        const isSafari = /^((?!chrome|android|crios|fxios).)*safari/i.test(window.navigator.userAgent);

        // iOS has no BIP — show the "Add to Home Screen" helper
        if (isIos && isSafari) {
            setVisible(true);
            return;
        }

        const handler = (e) => {
            e.preventDefault();
            setDeferredPrompt(e);
            setVisible(true);
        };
        window.addEventListener("beforeinstallprompt", handler);

        const installedHandler = () => {
            setVisible(false);
            setDeferredPrompt(null);
            localStorage.setItem(DISMISS_KEY, String(Date.now()));
        };
        window.addEventListener("appinstalled", installedHandler);

        return () => {
            window.removeEventListener("beforeinstallprompt", handler);
            window.removeEventListener("appinstalled", installedHandler);
        };
    }, []);

    const install = async () => {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            if (outcome === "accepted") {
                setVisible(false);
            }
            setDeferredPrompt(null);
        } else {
            // iOS path
            setShowIosHelp(true);
        }
    };

    const dismiss = () => {
        localStorage.setItem(DISMISS_KEY, String(Date.now()));
        setVisible(false);
    };

    if (!visible) return null;

    return (
        <>
            <div
                data-testid="install-banner"
                className="fixed left-3 right-3 bottom-3 md:left-auto md:right-6 md:bottom-6 md:w-96 z-[60] glass rounded-2xl p-4 shadow-[0_20px_60px_-15px_rgba(255,42,84,0.35)] border border-[#FF2A54]/30 animate-slide-up"
            >
                <div className="flex items-start gap-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center shrink-0">
                        <Smartphone className="w-5 h-5" strokeWidth={2.5} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="font-display font-bold text-sm">Instale o SeriesTrack</p>
                        <p className="text-white/60 text-xs mt-0.5">Um clique. Aparece na tela inicial. Sem loja, sem espera.</p>
                        <div className="mt-3 flex gap-2">
                            <button
                                onClick={install}
                                data-testid="install-accept-btn"
                                className="btn-primary text-xs py-1.5 px-3"
                            >
                                <Download className="w-3.5 h-3.5" /> Instalar
                            </button>
                            <button
                                onClick={dismiss}
                                data-testid="install-dismiss-btn"
                                className="px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 text-xs font-semibold text-white/70"
                            >
                                Depois
                            </button>
                        </div>
                    </div>
                    <button onClick={dismiss} className="text-white/40 hover:text-white shrink-0 p-1" aria-label="Fechar">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {showIosHelp && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[70] flex items-end md:items-center justify-center p-4" onClick={() => setShowIosHelp(false)}>
                    <div className="glass rounded-2xl p-6 max-w-sm w-full" data-testid="ios-install-help" onClick={(e) => e.stopPropagation()}>
                        <div className="flex justify-between items-start mb-4">
                            <h3 className="font-display text-lg font-bold">Instalar no iPhone</h3>
                            <button onClick={() => setShowIosHelp(false)} className="text-white/50 hover:text-white p-1">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <ol className="space-y-3 text-sm text-white/80">
                            <li className="flex items-start gap-3">
                                <span className="w-6 h-6 rounded-full bg-[#FF2A54] flex items-center justify-center text-xs font-black shrink-0">1</span>
                                <span>Toque no ícone <Share className="w-4 h-4 inline mx-1 -mt-0.5" /> <b>Compartilhar</b> na barra do Safari.</span>
                            </li>
                            <li className="flex items-start gap-3">
                                <span className="w-6 h-6 rounded-full bg-[#FF2A54] flex items-center justify-center text-xs font-black shrink-0">2</span>
                                <span>Role e toque em <b>&quot;Adicionar à Tela de Início&quot;</b>.</span>
                            </li>
                            <li className="flex items-start gap-3">
                                <span className="w-6 h-6 rounded-full bg-[#FF2A54] flex items-center justify-center text-xs font-black shrink-0">3</span>
                                <span>Toque em <b>Adicionar</b>. Pronto — o SeriesTrack vira um app na sua tela inicial.</span>
                            </li>
                        </ol>
                        <button onClick={() => { setShowIosHelp(false); dismiss(); }} className="btn-glass w-full mt-6 justify-center">
                            Entendi
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}
