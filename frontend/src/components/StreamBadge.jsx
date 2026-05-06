import { brandFor } from "../lib/providers";

export default function StreamBadge({ name, logoUrl }) {
    const { color, text } = brandFor(name);
    return (
        <span
            className="stream-badge"
            style={{ backgroundColor: color, color: text, border: text === "#fff" ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)" }}
            title={name}
        >
            {logoUrl ? (
                <img src={logoUrl} alt={name} className="w-3.5 h-3.5 rounded-sm object-cover" />
            ) : null}
            {name}
        </span>
    );
}
