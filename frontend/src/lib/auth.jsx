import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import api, { setToken, getToken, SESSION_EXPIRED_EVENT } from "./api";
import { cancelSessionReminders } from "./session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null); // null=loading, false=guest, object=user
    const [bootstrapped, setBootstrapped] = useState(false);

    const fetchMe = useCallback(async () => {
        // CRITICAL: If returning from OAuth callback, skip the /auth/me check.
        // AuthCallback will exchange the session_id and call setSession directly.
        if (typeof window !== "undefined" && window.location.hash && window.location.hash.includes("session_id=")) {
            setBootstrapped(true);
            return;
        }
        const tok = getToken();
        if (!tok) {
            setUser(false);
            setBootstrapped(true);
            return;
        }
        try {
            const { data } = await api.get("/auth/me");
            setUser(data);
        } catch (e) {
            // Havia um token salvo, mas o servidor recusou: a sessão venceu.
            if (e?.response?.status === 401) {
                toast.error("Sua sessão expirou. Entre novamente para continuar.");
            }
            setToken(null);
            setUser(false);
        } finally {
            setBootstrapped(true);
        }
    }, []);

    useEffect(() => {
        fetchMe();
    }, [fetchMe]);

    // Token vencido durante o uso (ver interceptor em lib/api.js).
    useEffect(() => {
        let shown = false;
        const onExpired = () => {
            setUser((prev) => {
                if (prev && !shown) {
                    shown = true;
                    toast.error("Sua sessão expirou. Entre novamente para continuar.");
                    setTimeout(() => { shown = false; }, 5000);
                }
                return false;
            });
        };
        window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
        return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
    }, []);

    const setSession = (userObj, token) => {
        if (token) setToken(token);
        setUser(userObj);
        setBootstrapped(true);
    };

    const login = async (email, password) => {
        const { data } = await api.post("/auth/login", { email, password });
        setToken(data.access_token);
        setUser(data.user);
        return data.user;
    };

    const register = async (email, password, name) => {
        const { data } = await api.post("/auth/register", { email, password, name });
        setToken(data.access_token);
        setUser(data.user);
        return data.user;
    };

    const logout = async () => {
        try { await api.post("/auth/logout"); } catch {}
        cancelSessionReminders();
        setToken(null);
        setUser(false);
    };

    return (
        <AuthContext.Provider value={{ user, bootstrapped, login, register, logout, refresh: fetchMe, setSession }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
