// Theme and styling preference manager
export function initTheme() {
  const savedTheme = localStorage.getItem("ms_theme") || "follow_system";
  const savedAccent = localStorage.getItem("ms_accent") || "blue";
  const savedDensity = localStorage.getItem("ms_density") || "comfortable";
  const savedFontSize = localStorage.getItem("ms_font_size") || "medium";

  applyTheme(savedTheme);
  applyAccent(savedAccent);
  applyDensity(savedDensity);
  applyFontSize(savedFontSize);
}

export function applyTheme(theme) {
  localStorage.setItem("ms_theme", theme);
  const html = document.documentElement;

  if (theme === "dark") {
    html.setAttribute("data-bs-theme", "dark");
  } else if (theme === "light") {
    html.setAttribute("data-bs-theme", "light");
  } else {
    // follow system
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    html.setAttribute("data-bs-theme", isDark ? "dark" : "light");
  }
}

export function applyAccent(accent) {
  localStorage.setItem("ms_accent", accent);
  document.documentElement.setAttribute("data-accent", accent);
}

export function applyDensity(density) {
  localStorage.setItem("ms_density", density);
  document.documentElement.setAttribute("data-density", density);
}

export function applyFontSize(size) {
  localStorage.setItem("ms_font_size", size);
  document.documentElement.setAttribute("data-font-size", size);
}

// Auto-run on script load
initTheme();
