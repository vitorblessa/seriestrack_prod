import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Tv, Loader2, CheckCircle2, XCircle } from "lucide-react";

export default function VerifyEmail() {
    const [searchParams] = useSearchParams();
    const { user, refresh } = useAuth();
    const token = searchParams.get("token") || "";
    const [status, setStatus] = useState(token ? "loading" : "missing"); // loading | ok | error | missing
    const [error, setError] = useState("");

    useEffect(() => {
        if (!token) return;
        let active = true;
        (async () => {
            try {
                await api.post("/auth/verify_email", { token });
                if (!active) return;
                setStatus("ok");
                if (user) refresh();
            } catch (err) {
                if (!active) return;
                setError(formatApiError(err));
                setStatus("error");
            }
        })();
        return () => { active = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <div className="w-full max-w-md animate-fade-up text-center">
                <Link to="/login" className="flex items-center justify-center gap-2 mb-10">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#FF2A54] to-[#7c1531] flex items-center justify-center">
                        <Tv className="w-5 h-5" strokeWidth={2.5} />
                    </div>
                    <span className="font-display font-black text-xl">SeriesTrack</span>
                </Link>

                {status === "loading" && (
                    <div data-testid="verify-email-loading">
                        <Loader2 className="w-8 h-8 mx-auto animate-spin text-white/40" />
                        <p className="text-white/50 mt-6">Confirmando seu e-mail...</p>
                    </div>
                )}

                {status === "ok" && (
                    <div data-testid="verify-email-success">
                        <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-6">
                            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
                        </div>
                        <h1 className="font-display text-3xl font-black">E-mail confirmado!</h1>
                        <p className="text-white/50 mt-3">Sua conta está verificada. Pode continuar aproveitando o SeriesTrack.</p>
                        <Link to={user ? "/dashboard" : "/login"} className="inline-block mt-8 text-[#FF2A54] hover:text-[#FF4D71] font-semibold">
                            {user ? "Ir para o início" : "Ir para o login"}
                        </Link>
                    </div>
                )}

                {(status === "error" || status === "missing") && (
                    <div data-testid="verify-email-error">
                        <div className="w-14 h-14 mx-auto rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mb-6">
                            <XCircle className="w-7 h-7 text-red-400" />
                        </div>
                        <h1 className="font-display text-3xl font-black">Link inválido</h1>
                        <p className="text-white/50 mt-3">
                            {status === "missing"
                                ? "Esse link de confirmação está incompleto."
                                : (error || "Esse link expirou ou já foi usado.")}
                            {" "}Entre na sua conta para reenviar o e-mail de confirmação.
                        </p>
                        <Link to="/login" className="inline-block mt-8 text-[#FF2A54] hover:text-[#FF4D71] font-semibold">
                            Ir para o login
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}
