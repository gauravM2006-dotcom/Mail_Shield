import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";
import { initSocket, onEvent } from "./socket.js";

let currentProvider = "gmail";
let selectedEmailIds = new Set();

export async function initDashboard(defaultTab = "gmail") {
  currentProvider = defaultTab;
  initSocket();

  // Setup provider tabs and cards listeners
  document.querySelectorAll("[data-provider-tab]").forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      const target = tabBtn.getAttribute("data-provider-tab");
      switchTab(target);
    });
  });

  document.querySelectorAll("[data-provider-card]").forEach((card) => {
    card.addEventListener("click", () => {
      const target = card.getAttribute("data-provider-card");
      switchTab(target);
    });
  });

  // Action buttons
  document.getElementById("btn-refresh-tab")?.addEventListener("click", () => syncCurrentTab());
  document.getElementById("btn-scan-selected")?.addEventListener("click", () => scanSelectedEmails());
  document.getElementById("btn-scan-unscanned")?.addEventListener("click", () => scanTab("unscanned"));
  document.getElementById("btn-rescan-all")?.addEventListener("click", () => scanTab("all"));
  document.getElementById("btn-disconnect-tab")?.addEventListener("click", () => disconnectCurrentTab());

  // Search input with debounce
  let debounceTimer;
  document.getElementById("mail-search-input")?.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      loadEmailsForTab(currentProvider);
    }, 250);
  });

  // Filter chips
  document.querySelectorAll("[data-filter-label]").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("[data-filter-label]").forEach(c => c.classList.remove("active", "btn-primary"));
      chip.classList.add("active", "btn-primary");
      loadEmailsForTab(currentProvider);
    });
  });

  // Select all checkbox
  document.getElementById("select-all-checkbox")?.addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    document.querySelectorAll(".mail-select-check").forEach((cb) => {
      cb.checked = isChecked;
      const id = cb.getAttribute("data-id");
      if (isChecked) selectedEmailIds.add(id);
      else selectedEmailIds.delete(id);
    });
    updateSelectedCount();
  });

  // Realtime events
  onEvent("mail:new", (data) => {
    if (data.provider === currentProvider) {
      prependEmailRow(data.email);
    }
    updateSummaryCards();
  });

  onEvent("scan:result", (data) => {
    updateRowScanBadge(data.email_id, data.score, data.label);
    updateSummaryCards();
  });

  // Modal cache compact listener
  document.getElementById("btn-modal-clear-cache")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-modal-clear-cache");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Compacting...`;
    try {
      const res = await apiRequest("/api/mail/cache/clear", { method: "POST" });
      if (res.ok) {
        showToast(res.data.message || "Cache optimized successfully", "success");
        await updateSummaryCards();
      }
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<i class="bi bi-trash3 me-1"></i> Compact`;
    }
  });

  // Initial load
  await updateSummaryCards();
  await loadAccountsStatus();
  await loadEmailsForTab(currentProvider);
}

export function switchTab(providerKey) {
  currentProvider = providerKey;
  selectedEmailIds.clear();
  updateSelectedCount();

  // Update URL without reload
  const url = new URL(window.location);
  url.searchParams.set("tab", providerKey);
  window.history.pushState({}, "", url);

  // Update Tab pills active state
  document.querySelectorAll("[data-provider-tab]").forEach((btn) => {
    if (btn.getAttribute("data-provider-tab") === providerKey) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Update Mailbox Cards active state
  document.querySelectorAll("[data-provider-card]").forEach((card) => {
    if (card.getAttribute("data-provider-card") === providerKey) {
      card.classList.add("active-tab");
    } else {
      card.classList.remove("active-tab");
    }
  });

  loadAccountsStatus();
  loadEmailsForTab(providerKey);
}

export async function loadAccountsStatus() {
  try {
    const res = await apiRequest("/api/mail/accounts");
    if (res.ok && res.data) {
      res.data.forEach((acc) => {
        // Tab badge
        const badge = document.getElementById(`tab-badge-${acc.provider}`);
        if (badge) {
          if (acc.unread_new > 0) {
            badge.textContent = acc.unread_new;
            badge.classList.remove("d-none");
          } else {
            badge.classList.add("d-none");
          }
        }

        // Overview Card Elements
        const cardStatus = document.getElementById(`card-status-${acc.provider}`);
        const cardAddr = document.getElementById(`card-address-${acc.provider}`);
        const cardCached = document.getElementById(`card-cached-${acc.provider}`);

        if (cardStatus) {
          if (acc.connected) {
            cardStatus.className = "badge bg-success-subtle text-success border border-success-subtle small d-flex align-items-center gap-1";
            cardStatus.innerHTML = `<span class="status-dot live"></span> Connected`;
          } else {
            cardStatus.className = "badge bg-secondary-subtle text-secondary border small d-flex align-items-center gap-1";
            cardStatus.innerHTML = `<span class="status-dot disconnected"></span> Not Connected`;
          }
        }

        if (cardAddr && acc.address) {
          cardAddr.textContent = acc.address;
        }

        if (cardCached) {
          cardCached.textContent = `${(acc.cached || 0).toLocaleString()} emails`;
        }

        if (acc.provider === currentProvider) {
          renderTabHeader(acc);
        }
      });
    }
  } catch (err) {
    console.error("Error loading account statuses:", err);
  }
}

function renderTabHeader(acc) {
  const notConnectedCard = document.getElementById("tab-connect-card");
  const connectedView = document.getElementById("tab-connected-view");

  if (acc.connected) {
    notConnectedCard?.classList.add("d-none");
    connectedView?.classList.remove("d-none");
  } else {
    notConnectedCard?.classList.remove("d-none");
    connectedView?.classList.add("d-none");
    const titleEl = document.getElementById("connect-card-provider-title");
    if (titleEl) titleEl.textContent = `Connect your ${acc.provider.toUpperCase()} Mailbox`;
  }
}

export async function loadEmailsForTab(provider) {
  const tbody = document.getElementById("email-table-body");
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="7" class="text-center py-5">
        <div class="spinner-border spinner-border-sm text-primary me-2"></div>
        <span class="text-muted small">Loading messages from ${provider.toUpperCase()}...</span>
      </td>
    </tr>
  `;

  try {
    const activeFilter = document.querySelector("[data-filter-label].active")?.getAttribute("data-filter-label") || "";
    const searchQ = document.getElementById("mail-search-input")?.value || "";

    let queryUrl = `/api/mail/${provider}?limit=50`;
    if (activeFilter) queryUrl += `&label=${activeFilter}`;
    if (searchQ) queryUrl += `&q=${encodeURIComponent(searchQ)}`;

    const res = await apiRequest(queryUrl);
    if (res.ok && res.data) {
      const items = res.data.items || [];
      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="text-center py-5">
              <div class="ms-empty-icon mx-auto"><i class="bi bi-inbox"></i></div>
              <h6 class="fw-bold mb-1" style="color: var(--ms-navy);">No emails to review</h6>
              <p class="text-muted small mb-0">No matching emails found in this folder or search filter.</p>
            </td>
          </tr>
        `;
        return;
      }
      tbody.innerHTML = "";
      items.forEach((item) => {
        tbody.appendChild(createEmailRow(item));
      });
    }
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-4 text-danger small">
          <i class="bi bi-exclamation-triangle me-2"></i> Error loading emails: ${err.message}
        </td>
      </tr>
    `;
  }
}

function createEmailRow(mail) {
  const tr = document.createElement("tr");
  tr.className = `mail-row ${mail.is_read ? "" : "unread"}`;
  tr.id = `email-row-${mail.id}`;

  const fromName = (mail.from && (mail.from.name || mail.from.address)) || "Unknown";
  const fromAddr = (mail.from && mail.from.address) || "";
  
  let dateStr = "";
  if (mail.received_at) {
    const d = new Date(mail.received_at);
    dateStr = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // Double indication: icon + text + score
  let badgeHtml = `<span class="badge-unscanned" id="badge-${mail.id}"><i class="bi bi-dash-circle"></i> Unscanned</span>`;
  if (mail.current_scan) {
    const score = mail.current_scan.score;
    const label = mail.current_scan.label;
    if (label === "safe") {
      badgeHtml = `<span class="badge-safe" id="badge-${mail.id}"><i class="bi bi-check-circle-fill"></i> Safe ${score}</span>`;
    } else if (label === "suspicious") {
      badgeHtml = `<span class="badge-suspicious" id="badge-${mail.id}"><i class="bi bi-exclamation-triangle-fill"></i> Suspicious ${score}</span>`;
    } else if (label === "spam") {
      badgeHtml = `<span class="badge-spam" id="badge-${mail.id}"><i class="bi bi-x-circle-fill"></i> Spam ${score}</span>`;
    }
  }

  tr.innerHTML = `
    <td style="width: 42px;" onclick="event.stopPropagation();">
      <input type="checkbox" class="form-check-input mail-select-check" data-id="${mail.id}" aria-label="Select email">
    </td>
    <td style="width: 200px;">
      <div class="fw-semibold text-truncate" title="${fromName}" style="color: var(--ms-navy);">${fromName}</div>
      <div class="text-muted text-truncate" style="font-size: 11px;">${fromAddr}</div>
    </td>
    <td>
      <div class="d-flex align-items-center gap-2">
        <span class="text-truncate fw-medium" style="max-width: 420px; color: var(--ms-text);">${mail.subject || "(No Subject)"}</span>
        <span class="text-muted text-truncate d-none d-md-inline" style="max-width: 260px; font-size: 12px;"> - ${mail.snippet || ""}</span>
      </div>
    </td>
    <td style="width: 40px;" class="text-center">
      ${mail.has_attachments ? '<i class="bi bi-paperclip text-muted fs-6" title="Has attachment"></i>' : ''}
    </td>
    <td style="width: 110px;" class="text-muted small">${dateStr}</td>
    <td style="width: 160px;">${badgeHtml}</td>
    <td style="width: 70px;" class="text-end" onclick="event.stopPropagation();">
      <button class="btn btn-sm btn-outline-secondary btn-row-scan p-1 px-2" data-id="${mail.id}" title="Scan this email now">
        <i class="bi bi-shield-play"></i>
      </button>
    </td>
  `;

  // Row click opens the Drawer
  tr.addEventListener("click", () => openEmailDrawer(mail.id));

  // Checkbox listener
  const check = tr.querySelector(".mail-select-check");
  check?.addEventListener("change", (e) => {
    if (e.target.checked) selectedEmailIds.add(mail.id);
    else selectedEmailIds.delete(mail.id);
    updateSelectedCount();
  });

  // Single scan button listener
  const scanBtn = tr.querySelector(".btn-row-scan");
  scanBtn?.addEventListener("click", async () => {
    scanBtn.disabled = true;
    scanBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;
    try {
      const res = await apiRequest("/api/scan/single", {
        method: "POST",
        body: { email_id: mail.id }
      });
      if (res.ok && res.data) {
        updateRowScanBadge(mail.id, res.data.score, res.data.label);
        showToast(`Scan complete: Score ${res.data.score} (${res.data.label.toUpperCase()})`, "success");
        updateSummaryCards();
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      scanBtn.disabled = false;
      scanBtn.innerHTML = `<i class="bi bi-shield-play"></i>`;
    }
  });

  return tr;
}

function updateRowScanBadge(emailId, score, label) {
  const badge = document.getElementById(`badge-${emailId}`);
  if (!badge) return;
  if (label === "safe") {
    badge.className = "badge-safe";
    badge.innerHTML = `<i class="bi bi-check-circle-fill"></i> Safe ${score}`;
  } else if (label === "suspicious") {
    badge.className = "badge-suspicious";
    badge.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> Suspicious ${score}`;
  } else if (label === "spam") {
    badge.className = "badge-spam";
    badge.innerHTML = `<i class="bi bi-x-circle-fill"></i> Spam ${score}`;
  }
}

function updateSelectedCount() {
  const count = selectedEmailIds.size;
  const btn = document.getElementById("btn-scan-selected");
  if (btn) {
    btn.disabled = count === 0;
    btn.innerHTML = `<i class="bi bi-check2-square me-1"></i> Scan Selected (${count})`;
  }
}

/* =====================================================================
   EMAIL DETAIL DRAWER & REASONS AUDIT
   ===================================================================== */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export async function openEmailDrawer(emailId) {
  const drawer = document.getElementById("email-detail-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (!drawer) return;

  drawer.classList.add("open");
  backdrop?.classList.add("open");

  // Show loading placeholders in existing drawer elements
  const subjectEl = document.getElementById("drawer-email-subject");
  const fromNameEl = document.getElementById("drawer-from-name");
  const fromAddrEl = document.getElementById("drawer-from-addr");
  const reasonsEl = document.getElementById("drawer-rule-reasons");
  const bodyEl = document.getElementById("drawer-email-body");
  const alertContainer = document.getElementById("drawer-alert-container");

  if (subjectEl) subjectEl.textContent = "Loading email details...";
  if (fromNameEl) fromNameEl.textContent = "...";
  if (fromAddrEl) fromAddrEl.textContent = "";
  if (alertContainer) alertContainer.innerHTML = "";
  if (reasonsEl) {
    reasonsEl.innerHTML = `
      <div class="p-4 text-center text-muted small">
        <div class="spinner-border spinner-border-sm text-primary mb-2"></div>
        <div>Loading deterministic security audit...</div>
      </div>
    `;
  }
  if (bodyEl) {
    bodyEl.innerHTML = `<span class="text-muted">Loading sanitized content...</span>`;
  }

  try {
    const res = await apiRequest(`/api/mail/${currentProvider}/${emailId}`);
    if (res.ok && res.data) {
      renderDrawerContent(res.data);
    }
  } catch (err) {
    if (reasonsEl) {
      reasonsEl.innerHTML = `<div class="alert alert-danger small mb-0"><i class="bi bi-exclamation-triangle me-1"></i> Failed to load email audit: ${escapeHtml(err.message)}</div>`;
    }
    if (subjectEl) subjectEl.textContent = "Error loading email";
  }
}

function renderDrawerContent(mail) {
  const score = mail.current_scan ? mail.current_scan.score : null;
  const label = mail.current_scan ? mail.current_scan.label : "unscanned";

  // Provider badge and date
  const provBadge = document.getElementById("drawer-provider-badge");
  if (provBadge) {
    provBadge.textContent = (mail.provider || currentProvider || "INBOX").toUpperCase();
  }

  const dateEl = document.getElementById("drawer-date");
  if (dateEl) {
    dateEl.textContent = mail.received_at
      ? new Date(mail.received_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })
      : "-";
  }

  // Email subject and sender
  const subjectEl = document.getElementById("drawer-email-subject");
  if (subjectEl) {
    subjectEl.textContent = mail.subject || "(No Subject)";
    subjectEl.title = mail.subject || "";
  }

  const avatarEl = document.getElementById("drawer-sender-avatar");
  const senderName = (mail.from && (mail.from.name || mail.from.address)) || "Unknown";
  const senderAddr = (mail.from && mail.from.address) || "";
  if (avatarEl) {
    avatarEl.textContent = (senderName.trim().charAt(0) || "S").toUpperCase();
  }

  const fromNameEl = document.getElementById("drawer-from-name");
  if (fromNameEl) fromNameEl.textContent = senderName;

  const fromAddrEl = document.getElementById("drawer-from-addr");
  if (fromAddrEl) fromAddrEl.textContent = senderAddr ? `<${senderAddr}>` : "";

  // Alert banner
  const alertContainer = document.getElementById("drawer-alert-container");
  if (alertContainer) {
    if (label === "suspicious") {
      alertContainer.innerHTML = `
        <div class="ms-drawer-alert-banner" style="background:#FEF7EA; border-color:#FDE68A; color:#92400E;">
          <i class="bi bi-exclamation-triangle-fill fs-5 text-warning flex-shrink-0"></i>
          <div>
            <strong>Caution — Suspicious Email Detected</strong><br>
            <span style="font-size:0.82rem;">This message triggered deterministic risk rules. Verify the sender before clicking links or downloading files.</span>
          </div>
        </div>
      `;
    } else if (label === "spam") {
      alertContainer.innerHTML = `
        <div class="ms-drawer-alert-banner" style="background:#FEEEEE; border-color:#FECACA; color:#DC2626;">
          <i class="bi bi-x-octagon-fill fs-5 text-danger flex-shrink-0"></i>
          <div>
            <strong>High Risk — Phishing / Spam Detected</strong><br>
            <span style="font-size:0.82rem;">This message exceeded dangerous threat thresholds. Do not open attachments or click links.</span>
          </div>
        </div>
      `;
    } else {
      alertContainer.innerHTML = "";
    }
  }

  // Score Badge
  const scoreBadgeEl = document.getElementById("drawer-score-badge");
  if (scoreBadgeEl) {
    if (label === "safe") {
      scoreBadgeEl.innerHTML = `<span class="badge-safe"><i class="bi bi-check-circle-fill"></i> Safe ${score ?? 0}</span>`;
    } else if (label === "suspicious") {
      scoreBadgeEl.innerHTML = `<span class="badge-suspicious"><i class="bi bi-exclamation-triangle-fill"></i> Suspicious ${score ?? 0}</span>`;
    } else if (label === "spam") {
      scoreBadgeEl.innerHTML = `<span class="badge-spam"><i class="bi bi-x-circle-fill"></i> Spam ${score ?? 0}</span>`;
    } else {
      scoreBadgeEl.innerHTML = `<span class="badge-unscanned"><i class="bi bi-dash-circle"></i> Unscanned</span>`;
    }
  }

  // Authentication Status
  const authEl = document.getElementById("drawer-auth-status");
  if (authEl) {
    const auth = mail.auth_results || {};
    const spf = (auth.spf || "none").toLowerCase();
    const dkim = (auth.dkim || "none").toLowerCase();
    if (spf === "pass" && dkim === "pass") {
      authEl.innerHTML = `<i class="bi bi-patch-check-fill text-success"></i> SPF/DKIM Passed`;
    } else if (spf === "pass" || dkim === "pass") {
      authEl.innerHTML = `<i class="bi bi-patch-exclamation-fill text-warning"></i> SPF: ${auth.spf || 'none'} · DKIM: ${auth.dkim || 'none'}`;
    } else if (spf === "fail" || dkim === "fail") {
      authEl.innerHTML = `<i class="bi bi-patch-minus-fill text-danger"></i> Auth Failed (SPF: ${auth.spf || 'fail'}, DKIM: ${auth.dkim || 'fail'})`;
    } else {
      authEl.innerHTML = `<i class="bi bi-patch-question text-muted"></i> Auth: Unverified / Neutral`;
    }
  }

  // Banner text
  const bannerTextEl = document.getElementById("drawer-banner-text");
  if (bannerTextEl) {
    if (label === "unscanned") {
      bannerTextEl.textContent = "Unscanned — Click Re-scan below to calculate threat score";
    } else if (label === "safe") {
      bannerTextEl.textContent = "Deterministic rule breakdown below — Zero risk rules fired";
    } else {
      bannerTextEl.textContent = `${mail.reasons?.length || 0} deterministic detection rules contributed points to score`;
    }
  }

  // Circular Score Gauge
  const circleContainer = document.getElementById("drawer-score-circle-container");
  if (circleContainer) {
    let circleClass = "ms-score-circle-safe";
    if (label === "suspicious") circleClass = "ms-score-circle-suspicious";
    else if (label === "spam") circleClass = "ms-score-circle-spam";
    else if (label === "unscanned") circleClass = "";

    circleContainer.innerHTML = `
      <div class="ms-score-circle ${circleClass}">
        <div class="ms-score-circle-value">${score !== null && score !== undefined ? score : "—"}</div>
        <div class="ms-score-circle-label">${label.toUpperCase()}</div>
      </div>
    `;
  }

  // Triggered Detection Rules Breakdown
  const reasonsEl = document.getElementById("drawer-rule-reasons");
  if (reasonsEl) {
    if (label === "unscanned") {
      reasonsEl.innerHTML = `
        <div class="p-3 rounded bg-light border text-center small">
          <i class="bi bi-shield-slash text-muted fs-4 d-block mb-1"></i>
          <strong>This email has not been scanned yet</strong>
          <p class="text-muted small mb-2" style="font-size: 11px;">Run deterministic security rules to detect phishing, spoofing, and malware.</p>
          <button class="btn btn-sm btn-primary" id="btn-drawer-quick-scan">
            <i class="bi bi-shield-play me-1"></i> Scan Now
          </button>
        </div>
      `;
      document.getElementById("btn-drawer-quick-scan")?.addEventListener("click", () => rescanDrawerEmail(mail.id));
    } else if (!mail.reasons || mail.reasons.length === 0) {
      reasonsEl.innerHTML = `
        <div class="p-3 rounded bg-success-subtle border border-success-subtle text-center small text-success">
          <i class="bi bi-shield-check fs-4 d-block mb-1"></i>
          <strong>Clean Email — Passed All Security Rules</strong>
          <div class="text-muted small mt-1" style="font-size: 11px;">No suspicious keywords, domain spoofing, suspicious links, or threat indicators were detected (Score: 0 / 100).</div>
        </div>
      `;
    } else {
      let badgeClass = label === "spam" ? "bg-danger-subtle text-danger border border-danger-subtle" : "bg-warning-subtle text-warning-emphasis border border-warning-subtle";
      let iconColor = label === "spam" ? "text-danger" : "text-warning";
      let iconName = label === "spam" ? "x-circle-fill" : "exclamation-triangle-fill";

      const rows = mail.reasons.map((r) => `
        <div class="ms-drawer-reason-item">
          <div class="d-flex align-items-start gap-2" style="min-width: 0;">
            <i class="bi bi-${iconName} ${iconColor} mt-1 flex-shrink-0" style="font-size: 0.95rem;"></i>
            <div style="min-width: 0;">
              <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="fw-bold small" style="color: var(--ms-navy);">${escapeHtml(r.title)}</span>
                <span class="badge bg-light text-secondary border font-monospace" style="font-size: 10px;">${escapeHtml(r.rule_id || r.group || 'RULE')}</span>
              </div>
              ${r.explanation ? `<div class="text-muted small mt-1" style="font-size: 11.5px; line-height: 1.4;">${escapeHtml(r.explanation)}</div>` : ''}
              ${r.evidence ? `<div class="small mt-1 font-monospace p-1 px-2 rounded bg-white border text-danger" style="font-size: 11px; word-break: break-all;"><strong>Evidence:</strong> ${escapeHtml(r.evidence)}</div>` : ''}
            </div>
          </div>
          <div class="ms-auto ps-2 text-end flex-shrink-0">
            <span class="badge ${badgeClass} fw-bold" style="font-size: 11px;">+${r.points} pts</span>
          </div>
        </div>
      `).join("");

      reasonsEl.innerHTML = `
        <div class="d-flex flex-column gap-2">${rows}</div>
        <div class="p-2 px-3 mt-2 rounded border d-flex align-items-center justify-content-between" style="background: var(--ms-surface-alt);">
          <span class="small fw-bold text-muted">Total Calculated Risk Score:</span>
          <span class="fw-bold ${label === 'spam' ? 'text-danger' : 'text-warning'}" style="font-size: 0.95rem;">${score ?? 0} / 100</span>
        </div>
      `;
    }
  }

  // Body content
  const bodyEl = document.getElementById("drawer-email-body");
  if (bodyEl) {
    bodyEl.textContent = mail.body_text || mail.snippet || "No body text available.";
  }

  // Raw Headers & URLs
  const rawHeadersEl = document.getElementById("drawer-email-raw-body");
  if (rawHeadersEl) {
    let headerText = `Subject: ${mail.subject || ''}\n`;
    headerText += `From: ${mail.from?.name || ''} <${mail.from?.address || ''}>\n`;
    headerText += `To: ${(mail.to || []).map(t => `${t.name || ''} <${t.address || ''}>`).join(", ")}\n`;
    if (mail.reply_to?.address) headerText += `Reply-To: ${mail.reply_to.address}\n`;
    headerText += `Received: ${mail.received_at || ''}\n`;
    headerText += `SPF: ${mail.auth_results?.spf || 'none'} | DKIM: ${mail.auth_results?.dkim || 'none'} | DMARC: ${mail.auth_results?.dmarc || 'none'}\n\n`;

    if (mail.urls && mail.urls.length > 0) {
      headerText += `--- DETECTED URLS (${mail.urls.length}) ---\n`;
      mail.urls.forEach((u, i) => {
        headerText += `[${i+1}] Destination: ${u.href}\n    Visible Text: ${u.text || u.href}\n    Host: ${u.host || ''} (Registrable: ${u.registrable || ''})\n\n`;
      });
    } else {
      headerText += `--- DETECTED URLS ---\nNo URLs found in email body.`;
    }
    rawHeadersEl.textContent = headerText;
  }

  // Attachments Section
  const attWrapper = document.getElementById("drawer-attachments-wrapper");
  const attList = document.getElementById("drawer-attachments-list");
  if (attWrapper && attList) {
    if (mail.attachments && mail.attachments.length > 0) {
      attWrapper.classList.remove("d-none");
      attList.innerHTML = mail.attachments.map((a) => {
        const ext = (a.ext || "").toLowerCase();
        const isDangerous = ["exe", "scr", "bat", "vbs", "cmd", "js"].includes(ext);
        return `
          <div class="p-2 px-3 border rounded bg-white d-flex align-items-center justify-content-between gap-3 shadow-xs" style="min-width: 200px;">
            <div class="d-flex align-items-center gap-2">
              <i class="bi bi-paperclip text-primary fs-5"></i>
              <div>
                <div class="fw-bold small text-truncate" style="max-width: 140px; color: var(--ms-navy);">${escapeHtml(a.name || "Attachment")}</div>
                <div class="text-muted" style="font-size: 10.5px;">${ext.toUpperCase()} · ${a.size ? Math.round(a.size/1024) + ' KB' : 'File'}</div>
              </div>
            </div>
            ${isDangerous ? '<span class="badge-spam small"><i class="bi bi-x-circle-fill"></i> Executable</span>' : '<span class="badge bg-light text-muted border small">Safe Ext</span>'}
          </div>
        `;
      }).join("");
    } else {
      attWrapper.classList.add("d-none");
      attList.innerHTML = "";
    }
  }

  // Re-bind Action Buttons
  const btnWhitelist = document.getElementById("btn-drawer-whitelist");
  if (btnWhitelist) {
    btnWhitelist.onclick = async () => {
      if (!senderAddr) return;
      btnWhitelist.disabled = true;
      try {
        await apiRequest("/api/rules/lists", { method: "POST", body: { list: "allow_senders", value: senderAddr } });
        showToast(`Sender ${senderAddr} added to Trusted Allow-list`, "success");
        await rescanDrawerEmail(mail.id);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        btnWhitelist.disabled = false;
      }
    };
  }

  const btnBlacklist = document.getElementById("btn-drawer-blacklist");
  if (btnBlacklist) {
    btnBlacklist.onclick = async () => {
      if (!senderAddr) return;
      btnBlacklist.disabled = true;
      try {
        await apiRequest("/api/rules/lists", { method: "POST", body: { list: "block_senders", value: senderAddr } });
        showToast(`Sender ${senderAddr} added to Blocked list`, "success");
        await rescanDrawerEmail(mail.id);
      } catch (err) {
        showToast(err.message, "error");
      } finally {
        btnBlacklist.disabled = false;
      }
    };
  }

  const btnRescan = document.getElementById("btn-drawer-rescan");
  if (btnRescan) {
    btnRescan.onclick = () => rescanDrawerEmail(mail.id);
  }
}

async function rescanDrawerEmail(emailId) {
  const btnRescan = document.getElementById("btn-drawer-rescan");
  if (btnRescan) {
    btnRescan.disabled = true;
    btnRescan.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Scanning...`;
  }

  try {
    const res = await apiRequest("/api/scan/single", {
      method: "POST",
      body: { email_id: emailId }
    });
    if (res.ok && res.data) {
      showToast(`Scan complete: Score ${res.data.score} (${res.data.label.toUpperCase()})`, "success");
      updateRowScanBadge(emailId, res.data.score, res.data.label);
      updateSummaryCards();
      // Re-fetch email details to re-render drawer
      const detailRes = await apiRequest(`/api/mail/${currentProvider}/${emailId}`);
      if (detailRes.ok && detailRes.data) {
        renderDrawerContent(detailRes.data);
      }
    }
  } catch (err) {
    showToast(`Scan error: ${err.message}`, "error");
  } finally {
    if (btnRescan) {
      btnRescan.disabled = false;
      btnRescan.innerHTML = `<i class="bi bi-arrow-clockwise"></i> Re-scan`;
    }
  }
}

export function closeEmailDrawer() {
  document.getElementById("email-detail-drawer")?.classList.remove("open");
  document.getElementById("drawer-backdrop")?.classList.remove("open");
}

export function updateCacheStorageUI(storage) {
  if (!storage) return;
  const percentEl = document.getElementById("cache-quota-percent");
  const textEl = document.getElementById("cache-quota-text");
  const fillEl = document.getElementById("cache-quota-fill");

  const modalPercent = document.getElementById("modal-cache-percent");
  const modalFill = document.getElementById("modal-cache-fill");
  const modalUsed = document.getElementById("modal-cache-used");

  const pct = storage.percent || 0;
  const pctStr = `${pct}%`;
  const usedHtml = `${storage.used_formatted || '0 MB'} <span class="text-muted fw-normal" style="font-size: 11px;">/ ${storage.max_formatted || '5 GB max'}</span>`;

  if (percentEl) percentEl.textContent = pctStr;
  if (textEl) textEl.innerHTML = usedHtml;
  if (fillEl) fillEl.style.width = `${Math.min(100, Math.max(1, pct))}%`;

  if (modalPercent) modalPercent.textContent = pctStr;
  if (modalFill) modalFill.style.width = `${Math.min(100, Math.max(1, pct))}%`;
  if (modalUsed) modalUsed.textContent = `${storage.used_formatted || '0 MB'} stored (${(storage.total_cached || 0).toLocaleString()} cached messages)`;
}

export async function updateSummaryCards() {
  try {
    const res = await apiRequest("/api/dashboard/summary");
    if (res.ok && res.data) {
      const elTotal = document.getElementById("stat-total-mails");
      const elScanned = document.getElementById("stat-scanned-mails");
      const elSusp = document.getElementById("stat-suspicious-mails");
      const elSpam = document.getElementById("stat-spam-mails");

      if (elTotal) elTotal.textContent = (res.data.mails || 0).toLocaleString();
      if (elScanned) elScanned.textContent = (res.data.scanned || 0).toLocaleString();
      if (elSusp) elSusp.textContent = (res.data.suspicious || 0).toLocaleString();
      if (elSpam) elSpam.textContent = (res.data.spam || 0).toLocaleString();

      if (res.data.storage) {
        updateCacheStorageUI(res.data.storage);
      }
    }
  } catch (err) {
    console.error("Error updating summary stats:", err);
  }
}

async function scanSelectedEmails() {
  if (selectedEmailIds.size === 0) return;
  try {
    const res = await apiRequest("/api/scan/selected", {
      method: "POST",
      body: { provider: currentProvider, email_ids: Array.from(selectedEmailIds) }
    });
    if (res.ok) {
      showToast(res.data.message || "Batch scan completed", "success");
      selectedEmailIds.clear();
      updateSelectedCount();
      loadEmailsForTab(currentProvider);
      updateSummaryCards();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function scanTab(mode = "unscanned") {
  try {
    const res = await apiRequest("/api/scan/tab", {
      method: "POST",
      body: { provider: currentProvider, mode }
    });
    if (res.ok) {
      showToast(res.data.message || "Tab scan completed", "success");
      loadEmailsForTab(currentProvider);
      updateSummaryCards();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function syncCurrentTab() {
  try {
    const res = await apiRequest(`/api/mail/${currentProvider}/sync`, { method: "POST" });
    if (res.ok) {
      showToast(res.data.message || "Mailbox synced", "success");
      loadEmailsForTab(currentProvider);
      loadAccountsStatus();
      updateSummaryCards();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function disconnectCurrentTab() {
  if (!confirm(`Are you sure you want to disconnect your ${currentProvider.toUpperCase()} mailbox and delete cached data?`)) return;
  try {
    const res = await apiRequest(`/api/mail/${currentProvider}`, { method: "DELETE" });
    if (res.ok) {
      showToast(`Disconnected ${currentProvider}`, "info");
      loadAccountsStatus();
      loadEmailsForTab(currentProvider);
      updateSummaryCards();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}
