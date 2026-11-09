import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "seriestrack_token";

const client = axios.create({ baseURL: API });

client.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Sessão vencida (ou token recusado) durante o uso: limpa o token e avisa o
// AuthProvider (lib/auth.jsx), que mostra "Sua sessão expirou" e leva ao login.
// Pedidos de login/cadastro ficam de fora — ali o 401 é senha errada.
export const SESSION_EXPIRED_EVENT = "seriestrack:session-expired";
client.interceptors.response.use(
    (res) => res,
    (error) => {
        const status = error?.response?.status;
        const url = error?.config?.url || "";
        const sentToken = Boolean(error?.config?.headers?.Authorization);
        if (status === 401 && sentToken && !/\/auth\/(login|register|google)/.test(url)) {
            localStorage.removeItem(TOKEN_KEY);
            window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
        }
        return Promise.reject(error);
    },
);

export default client;

export function setToken(t) {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
}

export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function formatApiError(err) {
    const detail = err?.response?.data?.detail;
    if (!detail) return err?.message || "Algo deu errado.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
    }
    if (detail && typeof detail.msg === "string") return detail.msg;
    return String(detail);
}
