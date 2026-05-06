import { useEffect, useRef, useState } from "react";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import PosterCard from "../components/PosterCard";
import { Search as SearchIcon, Loader2 } from "lucide-react";

export default function Search() {
    const [q, setQ] = useState("");
    const [results, setResults] = useState([]);
    const [popular, setPopular] = useState([]);
    const [loading, setLoading] = useState(false);
    const debounceRef = useRef(null);

    useEffect(() => {
        api.get("/series/popular").then((r) => setPopular(r.data)).catch(() => {});
    }, []);

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        if (!q.trim()) {
            setResults([]);
            return;
        }
        debounceRef.current = setTimeout(async () => {
            setLoading(true);
            try {
                const { data } = await api.get("/series/search", { params: { q } });
                setResults(data);
            } finally {
                setLoading(false);
            }
        }, 350);
        return () => debounceRef.current && clearTimeout(debounceRef.current);
    }, [q]);

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Buscar</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2">
                    Encontre sua próxima obsessão
                </h1>

                <div className="mt-8 relative max-w-3xl">
                    <SearchIcon className="w-5 h-5 absolute left-5 top-1/2 -translate-y-1/2 text-white/40" />
                    <input
                        data-testid="search-input"
                        type="text"
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="Busque séries por nome..."
                        className="w-full pl-14 pr-6 py-5 rounded-2xl bg-white/5 border border-white/10 focus:border-[#FF2A54] focus:bg-white/10 outline-none text-lg transition-all"
                        autoFocus
                    />
                    {loading && <Loader2 className="w-5 h-5 absolute right-5 top-1/2 -translate-y-1/2 animate-spin text-white/50" />}
                </div>
            </section>

            <section className="px-6 md:px-10 mt-12" data-testid="search-results">
                {q.trim() ? (
                    results.length === 0 && !loading ? (
                        <p className="text-white/50">Nenhum resultado para "{q}".</p>
                    ) : (
                        <>
                            <h2 className="font-display text-xl font-bold mb-6 text-white/70">
                                {results.length} {results.length === 1 ? "resultado" : "resultados"}
                            </h2>
                            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                                {results.map((s) => <PosterCard key={s.id} show={s} />)}
                            </div>
                        </>
                    )
                ) : (
                    <>
                        <h2 className="font-display text-xl font-bold mb-6 text-white/70">Populares para você descobrir</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-5">
                            {popular.map((s) => <PosterCard key={s.id} show={s} />)}
                        </div>
                    </>
                )}
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
