import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";

let rulesConfig = null;
let activeCatIndex = 0;

export async function initRules() {
  await loadRulesConfig();

  // Save changes button
  document.getElementById("btn-save-rules")?.addEventListener("click", () => saveRulesConfig());
  document.getElementById("btn-reset-rules")?.addEventListener("click", () => resetRulesConfig());

  // Threshold sliders and range inputs
  const suspInput = document.getElementById("th-suspicious");
  const suspRange = document.getElementById("th-suspicious-range");
  const spamInput = document.getElementById("th-spam");
  const spamRange = document.getElementById("th-spam-range");

  suspInput?.addEventListener("input", (e) => {
    if (suspRange) suspRange.value = e.target.value;
    updateThresholdDisplay();
  });
  suspRange?.addEventListener("input", (e) => {
    if (suspInput) suspInput.value = e.target.value;
    updateThresholdDisplay();
  });

  spamInput?.addEventListener("input", (e) => {
    if (spamRange) spamRange.value = e.target.value;
    updateThresholdDisplay();
  });
  spamRange?.addEventListener("input", (e) => {
    if (spamInput) spamInput.value = e.target.value;
    updateThresholdDisplay();
  });

  // Add Keyword
  document.getElementById("btn-add-keyword")?.addEventListener("click", () => {
    const inp = document.getElementById("input-add-keyword");
    const val = (inp?.value || "").trim().toLowerCase();
    if (!val || !rulesConfig?.keyword_categories?.[activeCatIndex]) return;
    if (!rulesConfig.keyword_categories[activeCatIndex].keywords.includes(val)) {
      rulesConfig.keyword_categories[activeCatIndex].keywords.push(val);
      renderSelectedCategoryKeywords(activeCatIndex);
      inp.value = "";
    }
  });

  // Add Senders
  document.getElementById("btn-add-allow")?.addEventListener("click", () => {
    const inp = document.getElementById("input-add-allow");
    const val = (inp?.value || "").trim().toLowerCase();
    if (!val || !rulesConfig?.lists) return;
    if (!rulesConfig.lists.allow_senders) rulesConfig.lists.allow_senders = [];
    if (!rulesConfig.lists.allow_senders.includes(val)) {
      rulesConfig.lists.allow_senders.push(val);
      renderListChips("allow_senders", "allow-senders-chips");
      inp.value = "";
    }
  });

  document.getElementById("btn-add-block")?.addEventListener("click", () => {
    const inp = document.getElementById("input-add-block");
    const val = (inp?.value || "").trim().toLowerCase();
    if (!val || !rulesConfig?.lists) return;
    if (!rulesConfig.lists.block_senders) rulesConfig.lists.block_senders = [];
    if (!rulesConfig.lists.block_senders.includes(val)) {
      rulesConfig.lists.block_senders.push(val);
      renderListChips("block_senders", "block-senders-chips");
      inp.value = "";
    }
  });

  // Sandbox runner
  document.getElementById("btn-run-sandbox")?.addEventListener("click", () => runSandboxTest());
}

async function loadRulesConfig() {
  try {
    const res = await apiRequest("/api/rules");
    if (res.ok && res.data) {
      rulesConfig = res.data;
      renderRulesUI();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderRulesUI() {
  if (!rulesConfig) return;

  // 1. Thresholds
  const th = rulesConfig.thresholds || { suspicious: 30, spam: 60 };
  const suspInput = document.getElementById("th-suspicious");
  const suspRange = document.getElementById("th-suspicious-range");
  const spamInput = document.getElementById("th-spam");
  const spamRange = document.getElementById("th-spam-range");

  if (suspInput) suspInput.value = th.suspicious;
  if (suspRange) suspRange.value = th.suspicious;
  if (spamInput) spamInput.value = th.spam;
  if (spamRange) spamRange.value = th.spam;
  updateThresholdDisplay();

  // 2. Keyword Categories
  const catList = document.getElementById("kw-categories-list");
  if (catList && rulesConfig.keyword_categories) {
    catList.innerHTML = rulesConfig.keyword_categories.map((cat, idx) => `
      <div class="list-group-item list-group-item-action d-flex align-items-center justify-content-between ${idx === activeCatIndex ? 'active' : ''}" data-cat-idx="${idx}" style="cursor: pointer; border-radius: 8px; margin-bottom: 4px;">
        <div>
          <h6 class="mb-0 fw-semibold">${cat.label}</h6>
          <small class="${idx === activeCatIndex ? 'text-white-50' : 'text-muted'}">${cat.keywords.length} keywords · +${cat.weight} pts</small>
        </div>
        <div class="form-check form-switch" onclick="event.stopPropagation();">
          <input class="form-check-input" type="checkbox" ${cat.enabled ? 'checked' : ''} data-cat-toggle="${idx}">
        </div>
      </div>
    `).join("");

    // Toggle switch listeners
    catList.querySelectorAll("[data-cat-toggle]").forEach(toggle => {
      toggle.addEventListener("change", (e) => {
        const cIdx = parseInt(toggle.getAttribute("data-cat-toggle"));
        if (rulesConfig.keyword_categories[cIdx]) {
          rulesConfig.keyword_categories[cIdx].enabled = e.target.checked;
        }
      });
    });

    // Category click listeners
    catList.querySelectorAll("[data-cat-idx]").forEach(item => {
      item.addEventListener("click", () => {
        catList.querySelectorAll("[data-cat-idx]").forEach(i => i.classList.remove("active"));
        item.classList.add("active");
        activeCatIndex = parseInt(item.getAttribute("data-cat-idx"));
        renderSelectedCategoryKeywords(activeCatIndex);
      });
    });

    renderSelectedCategoryKeywords(activeCatIndex);
  }

  // 3. Lists
  renderListChips("allow_senders", "allow-senders-chips");
  renderListChips("block_senders", "block-senders-chips");
}

function renderSelectedCategoryKeywords(idx) {
  const container = document.getElementById("kw-chips-container");
  if (!container || !rulesConfig.keyword_categories[idx]) return;

  const cat = rulesConfig.keyword_categories[idx];
  document.getElementById("selected-cat-title").textContent = cat.label;
  const weightBadge = document.getElementById("selected-cat-weight");
  if (weightBadge) weightBadge.textContent = `+${cat.weight} pts per match`;

  container.innerHTML = cat.keywords.map((kw, kIdx) => `
    <span class="badge bg-light text-dark border p-2 d-inline-flex align-items-center gap-2 shadow-xs" style="font-size: 13px;">
      ${kw}
      <button type="button" class="btn-close btn-close-xs ms-1" style="font-size: 8px;" data-rm-kw="${idx}-${kIdx}"></button>
    </span>
  `).join("");

  // Remove keyword listener
  container.querySelectorAll("[data-rm-kw]").forEach(btn => {
    btn.addEventListener("click", () => {
      const [cI, kI] = btn.getAttribute("data-rm-kw").split("-").map(Number);
      rulesConfig.keyword_categories[cI].keywords.splice(kI, 1);
      renderSelectedCategoryKeywords(cI);
    });
  });
}

function renderListChips(listKey, containerId) {
  const container = document.getElementById(containerId);
  if (!container || !rulesConfig.lists) return;

  const items = rulesConfig.lists[listKey] || [];
  container.innerHTML = items.map((val, idx) => `
    <span class="badge bg-light text-dark border p-2 d-inline-flex align-items-center gap-2 shadow-xs" style="font-size: 13px;">
      ${val}
      <button type="button" class="btn-close btn-close-xs ms-1" style="font-size: 8px;" data-rm-list="${listKey}-${idx}"></button>
    </span>
  `).join("");

  container.querySelectorAll("[data-rm-list]").forEach(btn => {
    btn.addEventListener("click", () => {
      const [k, i] = btn.getAttribute("data-rm-list").split("-");
      rulesConfig.lists[k].splice(Number(i), 1);
      renderListChips(k, containerId);
    });
  });
}

function updateThresholdDisplay() {
  const suspVal = parseInt(document.getElementById("th-suspicious")?.value || 30);
  const spamVal = parseInt(document.getElementById("th-spam")?.value || 60);

  const display = document.getElementById("threshold-zone-display");
  if (display) {
    display.textContent = `Safe: 0–${suspVal - 1} · Suspicious: ${suspVal}–${spamVal - 1} · Spam: ${spamVal}–100`;
  }

  const markSusp = document.getElementById("scale-mark-susp");
  const markSpam = document.getElementById("scale-mark-spam");
  if (markSusp) markSusp.textContent = suspVal;
  if (markSpam) markSpam.textContent = spamVal;
}

async function saveRulesConfig() {
  if (!rulesConfig) return;

  rulesConfig.thresholds.suspicious = parseInt(document.getElementById("th-suspicious").value);
  rulesConfig.thresholds.spam = parseInt(document.getElementById("th-spam").value);

  try {
    const res = await apiRequest("/api/rules", {
      method: "PUT",
      body: rulesConfig
    });
    if (res.ok) {
      showToast("Rules updated successfully", "success");
      loadRulesConfig();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function resetRulesConfig() {
  if (!confirm("Are you sure you want to reset all rules and thresholds to system defaults?")) return;
  try {
    const res = await apiRequest("/api/rules/reset", { method: "POST" });
    if (res.ok) {
      showToast("Rules reset to system defaults", "info");
      loadRulesConfig();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function runSandboxTest() {
  const subject = document.getElementById("sandbox-subject")?.value || "";
  const body = document.getElementById("sandbox-body")?.value || "";
  const out = document.getElementById("sandbox-output");

  try {
    const res = await apiRequest("/api/rules/test", {
      method: "POST",
      body: { mail: { subject, body_text: body }, config: rulesConfig }
    });

    if (res.ok && res.data) {
      const d = res.data;
      out.classList.remove("d-none");
      
      let badge = `<span class="badge-safe"><i class="bi bi-check-circle-fill"></i> SAFE</span>`;
      if (d.label === "suspicious") badge = `<span class="badge-suspicious"><i class="bi bi-exclamation-triangle-fill"></i> SUSPICIOUS</span>`;
      if (d.label === "spam") badge = `<span class="badge-spam"><i class="bi bi-x-circle-fill"></i> SPAM</span>`;

      out.innerHTML = `
        <div class="d-flex align-items-center justify-content-between mb-3 pb-2 border-bottom">
          <strong class="fs-5" style="color: var(--ms-navy);">${d.score} / 100</strong>
          ${badge}
        </div>
        <div class="small d-flex flex-column gap-2">
          ${d.reasons.length ? d.reasons.map(r => `
            <div class="p-2 border rounded bg-light">
              <div class="d-flex justify-content-between mb-1">
                <strong>${r.title}</strong>
                <span class="badge bg-danger-subtle text-danger">+${r.points} pts</span>
              </div>
              <div class="text-muted font-monospace" style="font-size: 11px;">${r.evidence}</div>
            </div>
          `).join("") : '<div class="text-success"><i class="bi bi-check-circle-fill me-1"></i> No rule triggers fired.</div>'}
        </div>
      `;
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}
