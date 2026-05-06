import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { setToken, getToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null); // null=loading, false=guest, object=user
    const [bootstrapped, setBootstrapped] = useState(false);

    const fetchMe = useCallback(async () => {
        const tok = getToken();
        if (!tok) {
            setUser(false);
            setBootstrapped(true);
            return;
        }
        try {
            const { data } = await api.get("/auth/me");
            setUser(data);
        } catch {
            setToken(null);
            setUser(false);
        } finally {
            setBootstrapped(true);
        }
    }, []);

    useEffect(() => {
        fetchMe();
    }, [fetchMe]);

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
        setToken(null);
        setUser(false);
    };

    return (
        <AuthContext.Provider value={{ user, bootstrapped, login, register, logout, refresh: fetchMe }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
