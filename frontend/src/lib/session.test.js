import { tokenExpiresAt, buildSessionReminders, expiringSoon, describeLeft, SESSION_WARN_ID, SESSION_END_ID } from "./session";

const b64url = (o) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const jwt = (payload) => `${b64url({ alg: "HS256" })}.${b64url(payload)}.assinatura`;
const NOW = Date.UTC(2026, 10, 9, 21, 0, 0);
const H = 3600 * 1000;

test("lê o exp do JWT", () => {
    expect(tokenExpiresAt(jwt({ sub: "1", exp: 1800000000 }))).toBe(1800000000 * 1000);
    expect(tokenExpiresAt("lixo")).toBeNull();
    expect(tokenExpiresAt(null)).toBeNull();
    expect(tokenExpiresAt(jwt({ sub: "1" }))).toBeNull();
});

test("agenda aviso 24h antes e no vencimento", () => {
    const exp = NOW + 7 * 24 * H;
    const r = buildSessionReminders(exp, NOW);
    expect(r.map((n) => n.id)).toEqual([SESSION_WARN_ID, SESSION_END_ID]);
    expect(r[0].at.getTime()).toBe(exp - 24 * H);
    expect(r[1].at.getTime()).toBe(exp);
});

test("faltando menos de 24h, só o aviso de vencimento", () => {
    expect(buildSessionReminders(NOW + 5 * H, NOW).map((n) => n.id)).toEqual([SESSION_END_ID]);
});

test("já vencida ou sem data: nada", () => {
    expect(buildSessionReminders(NOW - 1000, NOW)).toEqual([]);
    expect(buildSessionReminders(null, NOW)).toEqual([]);
});

test("expiringSoon e texto do tempo restante", () => {
    expect(expiringSoon(NOW + 5 * H, NOW)).toBe(5 * H);
    expect(expiringSoon(NOW + 30 * H, NOW)).toBeNull();
    expect(expiringSoon(NOW - H, NOW)).toBeNull();
    expect(describeLeft(5 * H)).toBe("5 horas");
    expect(describeLeft(H + 10)).toBe("1 hora");
    expect(describeLeft(20 * 60 * 1000)).toBe("menos de 1 hora");
});
