import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// The Emergent badge in index.html uses inline `display: inline-flex !important`,
// which beats any external stylesheet override. Detect PWA mode here and yank
// the element from the DOM entirely so it doesn't peek through in the installed app.
function hideBadgeIfPwa() {
    const isStandalone =
        (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
        (window.matchMedia && window.matchMedia("(display-mode: fullscreen)").matches) ||
        (window.matchMedia && window.matchMedia("(display-mode: minimal-ui)").matches) ||
        (window.matchMedia && window.matchMedia("(display-mode: window-controls-overlay)").matches) ||
        (window.navigator && window.navigator.standalone === true);
    if (!isStandalone) return;
    document.documentElement.classList.add("pwa-standalone");
    const kill = () => {
        const el = document.getElementById("emergent-badge");
        if (el && el.parentNode) el.parentNode.removeChild(el);
    };
    kill();
    // The badge script might re-inject after load — retry a couple of times.
    setTimeout(kill, 500);
    setTimeout(kill, 2000);
}
hideBadgeIfPwa();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
