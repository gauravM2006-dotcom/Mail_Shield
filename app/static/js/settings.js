import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";
import { applyTheme, applyAccent, applyDensity, applyFontSize } from "./theme.js";

export async function initSettings() {
  await loadSettings();

  // Theme selector
  document.querySelectorAll('input[name="setting-theme"]').forEach(r => {
    r.addEventListener("change", (e) => {
      applyTheme(e.target.value);
      saveSettingsPartial({ appearance: { theme: e.target.value } });
    });
  });

  // Accent selector
  document.querySelectorAll("[data-accent-choice]").forEach(btn => {
    btn.addEventListener("click", () => {
      const accent = btn.getAttribute("data-accent-choice");
      applyAccent(accent);
      saveSettingsPartial({ appearance: { accent } });
    });
  });

  // Density & Font size
  document.getElementById("setting-density")?.addEventListener("change", (e) => {
    applyDensity(e.target.value);
    saveSettingsPartial({ appearance: { density: e.target.value } });
  });

  document.getElementById("setting-font-size")?.addEventListener("change", (e) => {
    applyFontSize(e.target.value);
    saveSettingsPartial({ appearance: { font_size: e.target.value } });
  });

  // Sync settings
  document.getElementById("setting-sync-depth")?.addEventListener("change", (e) => {
    saveSettingsPartial({ sync: { depth_days: parseInt(e.target.value) } });
  });

  document.getElementById("setting-auto-scan-all")?.addEventListener("change", (e) => {
    saveSettingsPartial({ sync: { auto_scan_all: e.target.checked } });
  });
}

async function loadSettings() {
  try {
    const res = await apiRequest("/api/settings");
    if (res.ok && res.data) {
      const s = res.data;
      if (s.appearance) {
        const themeRadio = document.querySelector(`input[name="setting-theme"][value="${s.appearance.theme || 'follow_system'}"]`);
        if (themeRadio) themeRadio.checked = true;
        if (s.appearance.density) document.getElementById("setting-density").value = s.appearance.density;
        if (s.appearance.font_size) document.getElementById("setting-font-size").value = s.appearance.font_size;
      }
      if (s.sync) {
        if (s.sync.depth_days) document.getElementById("setting-sync-depth").value = s.sync.depth_days;
        if (document.getElementById("setting-auto-scan-all")) {
          document.getElementById("setting-auto-scan-all").checked = Boolean(s.sync.auto_scan_all);
        }
      }
    }
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

async function saveSettingsPartial(payload) {
  try {
    await apiRequest("/api/settings", {
      method: "PATCH",
      body: payload
    });
    showToast("Preferences saved", "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}
