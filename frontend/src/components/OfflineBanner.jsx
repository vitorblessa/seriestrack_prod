import { useEffect, useState } from "react";
import { WifiOff, RefreshCw } from "lucide-react";
import { subscribeQueue, isOnline, flushQueue } from "../lib/offlineQueue";

/**
 * Small top banner, visible only when it has something to say:
 *  - offline right now, or
 *  - online again but there are still queued actions (add/remove from
 *    library, episode progress) made while offline, syncing in the background.
 * Silent/invisible the rest of the time — most users will never see this.
 */
export default function OfflineBanner() {
    const [online, setOnline] = useState(true);
    const [pending, setPending] = useState(0);

    useEffect(() => {
        let mounted = true;
        isOnline().then((v) => mounted && setOnline(v));

        const unsub = subscribeQueue((q) => setPending(q.length));

        const onOnline = () => setOnline(true);
        const onOffline = () => setOnline(false);
        window.addEventListener("online", onOnline);
        window.addEventListener("offline", onOffline);

        // Native connectivity changes come through watchNetwork()'s own
        // listener (which also triggers flushQueue); poll lightly here just
        // to keep this banner's "online" flag in sync on native too.
        const interval = setInterval(() => {
            isOnline().then((v) => mounted && setOnline(v));
        }, 5000);

        return () => {
            mounted = false;
            unsub();
            window.removeEventListener("online", onOnline);
            window.removeEventListener("offline", onOffline);
            clearInterval(interval);
        };
    }, []);

    if (online && pending === 0) return null;

    return (
        <div
            data-testid="offline-banner"
            className="fixed top-0 left-0 right-0 z-[70] flex items-center justify-center gap-2 py-1.5 text-xs font-semibold text-white"
            style={{
                paddingTop: "env(safe-area-inset-top)",
                background: online ? "hsl(var(--primary))" : "#3a3a40",
            }}
        >
            {online ? (
                <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Sincronizando {pending} {pending === 1 ? "alteração" : "alterações"}…
                </>
            ) : (
                <>
                    <WifiOff className="w-3.5 h-3.5" />
                    Sem conexão — mostrando dados salvos{pending > 0 ? ` (${pending} pendente${pending === 1 ? "" : "s"})` : ""}
                </>
            )}
        </div>
    );
}
