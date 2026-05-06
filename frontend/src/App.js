import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/App.css";
import { AuthProvider } from "./lib/auth";
import { Toaster } from "sonner";
import ProtectedRoute from "./components/ProtectedRoute";
import { registerSW } from "./lib/push";
import Splash from "./pages/Splash";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Search from "./pages/Search";
import SeriesDetail from "./pages/SeriesDetail";
import MyLibrary from "./pages/MyLibrary";
import CalendarPage from "./pages/CalendarPage";
import Notifications from "./pages/Notifications";
import Profile from "./pages/Profile";
import AuthCallback from "./pages/AuthCallback";
import PublicProfile from "./pages/PublicProfile";
import Settings from "./pages/Settings";

registerSW();

export default function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <AuthProvider>
                    <Toaster
                        theme="dark"
                        position="bottom-right"
                        toastOptions={{
                            style: {
                                background: "rgba(22,22,26,0.9)",
                                border: "1px solid rgba(255,255,255,0.08)",
                                color: "#fff",
                                backdropFilter: "blur(12px)",
                            },
                        }}
                    />
                    <Routes>
                        <Route path="/" element={<Splash />} />
                        <Route path="/login" element={<Login />} />
                        <Route path="/register" element={<Register />} />
                        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                        <Route path="/search" element={<ProtectedRoute><Search /></ProtectedRoute>} />
                        <Route path="/series/:id" element={<ProtectedRoute><SeriesDetail /></ProtectedRoute>} />
                        <Route path="/library" element={<ProtectedRoute><MyLibrary /></ProtectedRoute>} />
                        <Route path="/calendar" element={<ProtectedRoute><CalendarPage /></ProtectedRoute>} />
                        <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
                        <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
                        <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                        <Route path="/auth/callback" element={<AuthCallback />} />
                        <Route path="/u/:id" element={<ProtectedRoute><PublicProfile /></ProtectedRoute>} />
                    </Routes>
                </AuthProvider>
            </BrowserRouter>
        </div>
    );
}
