// Brand colors / icons for streaming providers (TMDB returns provider_name)
export const PROVIDER_BRANDS = {
    "Netflix": { color: "#E50914", text: "#fff" },
    "Amazon Prime Video": { color: "#00A8E1", text: "#fff" },
    "Prime Video": { color: "#00A8E1", text: "#fff" },
    "Disney Plus": { color: "#113CCF", text: "#fff" },
    "Disney+": { color: "#113CCF", text: "#fff" },
    "Max": { color: "#002BE7", text: "#fff" },
    "HBO Max": { color: "#002BE7", text: "#fff" },
    "Apple TV Plus": { color: "#000000", text: "#fff" },
    "Apple TV+": { color: "#000000", text: "#fff" },
    "Paramount Plus": { color: "#0064FF", text: "#fff" },
    "Paramount+": { color: "#0064FF", text: "#fff" },
    "Crunchyroll": { color: "#F47521", text: "#fff" },
    "Hulu": { color: "#1CE783", text: "#000" },
    "Peacock": { color: "#000000", text: "#fff" },
    "Globoplay": { color: "#FF433D", text: "#fff" },
    "Star Plus": { color: "#1A1AE6", text: "#fff" },
    "Claro tv+": { color: "#E60000", text: "#fff" },
};

export function brandFor(name) {
    if (!name) return { color: "#212126", text: "#fff" };
    return PROVIDER_BRANDS[name] || { color: "#212126", text: "#fff" };
}
