import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import AppLayout from "../components/AppLayout";
import { Loader2, Calendar as CalIcon, ChevronLeft, ChevronRight } from "lucide-react";
import { brandFor } from "../lib/providers";

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
const MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

function ymd(d) {
    return d.toISOString().slice(0, 10);
}

export default function CalendarPage() {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [cursor, setCursor] = useState(() => {
        const d = new Date();
        return new Date(d.getFullYear(), d.getMonth(), 1);
    });
    const [filter, setFilter] = useState("all");

    useEffect(() => {
        let c = false;
        async function load() {
            setLoading(true);
            try {
                const { data } = await api.get("/calendar/upcoming");
                if (!c) setEvents(data);
            } finally {
                if (!c) setLoading(false);
            }
        }
        load();
        return () => { c = true; };
    }, []);

    const allProviders = useMemo(() => {
        const set = new Set();
        events.forEach((e) => (e.providers || []).forEach((p) => set.add(p)));
        return Array.from(set);
    }, [events]);

    const filteredEvents = useMemo(() => {
        if (filter === "all") return events;
        return events.filter((e) => (e.providers || []).includes(filter));
    }, [events, filter]);

    const calendarDays = useMemo(() => {
        const year = cursor.getFullYear();
        const month = cursor.getMonth();
        const first = new Date(year, month, 1);
        const startWeekday = first.getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const cells = [];
        for (let i = 0; i < startWeekday; i++) cells.push(null);
        for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
        while (cells.length % 7 !== 0) cells.push(null);
        return cells;
    }, [cursor]);

    const eventsByDate = useMemo(() => {
        const map = {};
        for (const e of filteredEvents) {
            if (!e.air_date) continue;
            map[e.air_date] = map[e.air_date] || [];
            map[e.air_date].push(e);
        }
        return map;
    }, [filteredEvents]);

    const todayStr = ymd(new Date());

    return (
        <AppLayout>
            <section className="px-6 md:px-10 pt-10">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#FF2A54]">Calendário</p>
                <h1 className="font-display text-4xl md:text-5xl font-black tracking-tight mt-2 flex items-center gap-3">
                    <CalIcon className="w-9 h-9 text-[#FF2A54]" /> Próximas estreias
                </h1>
                <p className="text-white/50 mt-2 max-w-2xl">Episódios das séries da sua biblioteca, organizados por data e por streaming.</p>

                {/* Filters */}
                <div
                    className="mt-6 flex md:flex-wrap items-center gap-2 overflow-x-auto scrollbar-hide -mx-6 px-6 md:mx-0 md:px-0 md:overflow-visible"
                    data-testid="calendar-filters"
                >
                    <button
                        onClick={() => setFilter("all")}
                        data-testid="calendar-filter-all"
                        className={`shrink-0 px-2.5 py-1 md:px-4 md:py-2 rounded-full text-[11px] md:text-xs font-bold uppercase tracking-wider transition-all whitespace-nowrap ${
                            filter === "all" ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"
                        }`}
                    >
                        Todos
                    </button>
                    {allProviders.map((p) => {
                        const b = brandFor(p);
                        const active = filter === p;
                        return (
                            <button
                                key={p}
                                onClick={() => setFilter(p)}
                                data-testid={`calendar-filter-${p.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                                className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 md:px-4 md:py-2 rounded-full text-[11px] md:text-xs font-bold uppercase tracking-wider transition-all border whitespace-nowrap ${
                                    active ? "ring-2 ring-white/30" : ""
                                }`}
                                style={{ background: active ? b.color : "rgba(255,255,255,0.05)", color: active ? b.text : "rgba(255,255,255,0.7)", borderColor: active ? b.color : "rgba(255,255,255,0.1)" }}
                            >
                                {!active && (
                                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: b.color }} />
                                )}
                                {p}
                            </button>
                        );
                    })}
                </div>

                {/* Month nav */}
                <div className="mt-10 flex items-center justify-between">
                    <h2 className="font-display text-2xl md:text-3xl font-bold">
                        {MONTHS[cursor.getMonth()]} <span className="text-white/40">{cursor.getFullYear()}</span>
                    </h2>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
                            data-testid="calendar-prev-month"
                            className="p-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setCursor(new Date())}
                            className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold uppercase tracking-wider"
                        >
                            Hoje
                        </button>
                        <button
                            onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
                            data-testid="calendar-next-month"
                            className="p-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Calendar grid */}
                <div className="mt-6 grid grid-cols-7 gap-px bg-white/5 rounded-2xl overflow-hidden border border-white/10" data-testid="calendar-grid">
                    {WEEKDAYS.map((d) => (
                        <div key={d} className="bg-[#0A0A0C] py-3 text-center text-xs font-bold uppercase tracking-[0.15em] text-white/50">
                            {d}
                        </div>
                    ))}
                    {calendarDays.map((d, i) => {
                        const dateStr = d ? ymd(d) : null;
                        const dayEvents = dateStr ? eventsByDate[dateStr] || [] : [];
                        const isToday = dateStr === todayStr;
                        return (
                            <div key={i} className={`bg-[#0A0A0C] min-h-[100px] md:min-h-[120px] p-2 ${isToday ? "ring-1 ring-[#FF2A54]/50 ring-inset" : ""}`}>
                                {d && (
                                    <>
                                        <div className={`text-xs font-bold ${isToday ? "text-[#FF2A54]" : "text-white/60"}`}>{d.getDate()}</div>
                                        <div className="mt-1 space-y-1">
                                            {dayEvents.slice(0, 3).map((e, j) => (
                                                <Link
                                                    key={j}
                                                    to={`/series/${e.tmdb_id}`}
                                                    className="block text-[10px] px-2 py-1 rounded bg-white/5 hover:bg-white/10 border-l-2 truncate"
                                                    style={{ borderLeftColor: brandFor((e.providers || [])[0]).color }}
                                                    title={`${e.series_name} T${e.season_number}E${e.episode_number}`}
                                                >
                                                    <span className="font-bold">T{e.season_number}E{e.episode_number}</span> {e.series_name}
                                                </Link>
                                            ))}
                                            {dayEvents.length > 3 && (
                                                <p className="text-[10px] text-white/40">+{dayEvents.length - 3} mais</p>
                                            )}
                                        </div>
                                    </>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Upcoming list */}
                <div className="mt-12">
                    <h2 className="font-display text-2xl md:text-3xl font-bold mb-6">Lista completa de próximos eps</h2>
                    {loading ? (
                        <Loader2 className="w-6 h-6 animate-spin text-[#FF2A54]" />
                    ) : filteredEvents.length === 0 ? (
                        <div className="glass rounded-2xl py-16 px-6 text-center">
                            <p className="font-display text-xl font-bold">Nenhum episódio próximo encontrado.</p>
                            <p className="text-white/60 mt-2">Adicione séries à sua biblioteca para ver lançamentos aqui.</p>
                            <Link to="/search" className="btn-primary inline-flex mt-6">Explorar séries</Link>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {filteredEvents.map((e, i) => (
                                <Link
                                    key={i}
                                    to={`/series/${e.tmdb_id}`}
                                    data-testid={`calendar-event-${i}`}
                                    className="glass rounded-xl p-4 flex gap-4 hover:border-white/20 transition-all"
                                >
                                    <div className="w-20 aspect-[2/3] shrink-0 bg-surface rounded-md overflow-hidden">
                                        {e.poster_url && <img src={e.poster_url} alt="" className="w-full h-full object-cover" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#FF2A54]">{e.air_date}</p>
                                        <p className="font-display font-bold text-lg mt-1">{e.series_name}</p>
                                        <p className="text-white/70 text-sm">T{e.season_number}·E{e.episode_number} — {e.episode_name}</p>
                                        {e.providers?.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5 mt-2">
                                                {e.providers.map((p) => {
                                                    const b = brandFor(p);
                                                    return (
                                                        <span key={p} className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded" style={{ background: b.color, color: b.text }}>
                                                            {p}
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </section>
            <div className="h-20" />
        </AppLayout>
    );
}
