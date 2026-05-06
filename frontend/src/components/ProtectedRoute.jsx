import { Navigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Loader2 } from "lucide-react";

export default function ProtectedRoute({ children }) {
    const { user, bootstrapped } = useAuth();
    if (!bootstrapped) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-obsidian">
                <Loader2 className="w-8 h-8 animate-spin text-[#FF2A54]" />
            </div>
        );
    }
    if (!user) return <Navigate to="/login" replace />;
    return children;
}
