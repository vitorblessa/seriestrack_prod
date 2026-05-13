import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "./api";

const THEME_LS_KEY = "seriestrack_theme";
const DEFAULT_THEME = "default";

export const FREE_THEMES = ["default"];
export const PRO_THEMES = [
    "oled", "netflix", "disney_plus", "hbo_max",
    "prime_video", "apple_tv", "paramount_plus", "globoplay",
];

export const THEME_LABELS = {
    default: "SeriesTrack (padrão)",
    oled: "OLED puro",
    netflix: "Netflix",
    disney_plus: "Disney+",
    hbo_max: "HBO Max",
    prime_video: "Prime Video",
    apple_tv: "Apple TV+",
    paramount_plus: "Paramount+",
    globoplay: "Globoplay",
};

export const THEME_SWATCHES = {
    default: { bg: "#0A0A0C", accent: "#FF2A54" },
    oled: { bg: "#000000", accent: "#FFFFFF" },
    netflix: { bg: "#0a0000", accent: "#E50914" },
    disney_plus: { bg: "#001A33", accent: "#146EF5" },
    hbo_max: { bg: "#0C0028", accent: "#8C4EFF" },
    prime_video: { bg: "#001F2E", accent: "#00A8E1" },
    apple_tv: { bg: "#000000", accent: "#FFFFFF" },
    paramount_plus: { bg: "#001028", accent: "#0064FF" },
    globoplay: { bg: "#1A0008", accent: "#FF4F00" },
};

function applyThemeToDom(theme) {
    if (typeof document === "undefined") return;
    document.body.setAttribute("data-theme", theme || DEFAULT_THEME);
}

const ThemeCtx = createContext({
    theme: DEFAULT_THEME,
    setTheme: () => {},
    isPro: false,
});

export function ThemeProvider({ children }) {
    const [theme, setThemeState] = useState(() => {
        if (typeof window === "undefined") return DEFAULT_THEME;
        return localStorage.getItem(THEME_LS_KEY) || DEFAULT_THEME;
    });

    // Apply initial theme
    useEffect(() => { applyThemeToDom(theme); }, [theme]);

    // Re-sync from backend on mount (overrides localStorage if user has saved pref)
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { data } = await api.get("/me/preferences");
                const remote = data?.preferences?.ui_theme;
                if (!cancelled && remote && remote !== theme) {
                    setThemeState(remote);
                    localStorage.setItem(THEME_LS_KEY, remote);
                }
            } catch {
                /* not logged in or backend unreachable — keep local */
            }
        })();
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const setTheme = useCallback(async (next) => {
        // Optimistic local switch
        setThemeState(next);
        localStorage.setItem(THEME_LS_KEY, next);
        applyThemeToDom(next);
        // Persist to backend (will 402 for non-Pro users — caller handles)
        try {
            await api.patch("/me/preferences", { ui_theme: next });
        } catch (e) {
            throw e;
        }
    }, []);

    return (
        <ThemeCtx.Provider value={{ theme, setTheme }}>
            {children}
        </ThemeCtx.Provider>
    );
}

export function useTheme() {
    return useContext(ThemeCtx);
}
