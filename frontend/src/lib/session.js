/**
 * Aviso de sessão perto de expirar.
 *
 * O login gera um JWT de acesso que vale 7 dias (backend/core/security.py) e
 * fica guardado no aparelho (lib/api.js). Aqui lemos o "exp" desse token — só
 * para saber a data, sem validar nada (quem valida é o backend) — e:
 *   - no app Android, agendamos duas notificações locais: 24h antes de vencer
 *     e na hora em que vence;
 *   - no app e no site, mostramos um aviso dentro da tela quando faltam menos
 *     de 24h, com o botão "Entrar novamente".
 */
import { Capacitor } from "@capacitor/core";

export const SESSION_WARN_ID = 7001; // 24h antes de vencer
export const SESSION_END_ID = 7002; // na hora em que vence
const SESSION_IDS = [SESSION_WARN_ID, SESSION_END_ID];
const DAY_MS = 24 * 60 * 60 * 1000;
const MIN_MS = 60 * 1000;

/** Data de vencimento (ms) lida do JWT, ou null se não der para ler. */
export function tokenExpiresAt(token) {
    if (!token || typeof token !== "string") return null;
    const part = token.split(".")[1];
    if (!part) return null;
    try {
        const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
        const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
        const payload = JSON.parse(atob(padded));
        return typeof payload.exp === "number" ? payload.exp * 1000 : null;
    } catch {
        return null;
    }
}

/** Notificações a agendar; só entram horários que ainda estão no futuro. */
export function buildSessionReminders(expiresAtMs, now = Date.now()) {
    if (!expiresAtMs || Number.isNaN(expiresAtMs)) return [];
    const out = [];
    const warnAt = expiresAtMs - DAY_MS;
    if (warnAt > now + MIN_MS) {
        out.push({
            id: SESSION_WARN_ID,
            at: new Date(warnAt),
            title: "Sua sessão expira amanhã",
            body: "Abra o SeriesTrack e entre novamente para continuar recebendo os avisos dos seus episódios.",
        });
    }
    if (expiresAtMs > now + MIN_MS) {
        out.push({
            id: SESSION_END_ID,
            at: new Date(expiresAtMs),
            title: "Sua sessão expirou",
            body: "Toque para entrar novamente no SeriesTrack.",
        });
    }
    return out;
}

/** Quanto falta (ms) se a sessão vence nas próximas 24h; senão null. */
export function expiringSoon(expiresAtMs, now = Date.now()) {
    if (!expiresAtMs) return null;
    const left = expiresAtMs - now;
    return left > 0 && left <= DAY_MS ? left : null;
}

/** "5 horas", "1 hora", "menos de 1 hora". */
export function describeLeft(ms) {
    const h = Math.floor(ms / (60 * MIN_MS));
    if (h < 1) return "menos de 1 hora";
    return h === 1 ? "1 hora" : `${h} horas`;
}

async function plugin() {
    if (!Capacitor.isNativePlatform()) return null;
    try {
        const { LocalNotifications } = await import("@capacitor/local-notifications");
        return LocalNotifications;
    } catch {
        return null;
    }
}

let queue = Promise.resolve();
const enqueue = (fn) => {
    const r = queue.then(fn, fn);
    queue = r.catch(() => {});
    return r;
};

/** (Re)agenda os avisos de sessão no app Android. No navegador, não faz nada. */
export function syncSessionReminders(token) {
    return enqueue(async () => {
        const LN = await plugin();
        if (!LN) return [];
        await LN.cancel({ notifications: SESSION_IDS.map((id) => ({ id })) });
        const perm = await LN.checkPermissions();
        if (perm.display !== "granted") return [];
        const list = buildSessionReminders(tokenExpiresAt(token));
        if (list.length) {
            await LN.schedule({
                notifications: list.map((n) => ({
                    id: n.id,
                    title: n.title,
                    body: n.body,
                    schedule: { at: n.at, allowWhileIdle: true },
                    extra: { type: "session", expired: n.id === SESSION_END_ID },
                })),
            });
        }
        return list;
    });
}

/** Ao sair da conta de propósito, os avisos deixam de fazer sentido. */
export function cancelSessionReminders() {
    return enqueue(async () => {
        const LN = await plugin();
        if (!LN) return;
        await LN.cancel({ notifications: SESSION_IDS.map((id) => ({ id })) }).catch(() => {});
    });
}

/** Chama cb() quando o usuário toca num aviso de sessão. Devolve o "desligar". */
export function onSessionNotificationTap(cb) {
    let handle = null;
    let off = false;
    plugin().then((LN) => {
        if (!LN || off) return;
        LN.addListener("localNotificationActionPerformed", (a) => {
            if (a?.notification?.extra?.type === "session") cb(a.notification.extra);
        }).then((h) => { if (off) h.remove(); else handle = h; }).catch(() => {});
    });
    return () => { off = true; handle?.remove(); };
}
