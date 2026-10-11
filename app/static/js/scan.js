import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";

export function initScanAll() {
  const btnStart = document.getElementById("btn-start-scan-all");
  btnStart?.addEventListener("click", async () => {
    const mode = document.querySelector('input[name="scan-mode"]:checked')?.value || "unscanned";
    const checkedProviders = Array.from(document.querySelectorAll('.provider-check:checked')).map(cb => cb.value);

    if (checkedProviders.length === 0) {
      showToast("Please select at least one mailbox to scan.", "error");
      return;
    }

    btnStart.disabled = true;
    btnStart.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Scanning Mailboxes...`;

    try {
      const res = await apiRequest("/api/scan/all", {
        method: "POST",
        body: { mode, providers: checkedProviders }
      });

      if (res.ok && res.data) {
        renderScanAllSummary(res.data.totals);
        showToast(res.data.message || "Multi-mailbox scan completed", "success");
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnStart.disabled = false;
      btnStart.innerHTML = `<i class="bi bi-play-circle me-2"></i> Start Scanning`;
    }
  });
}

function renderScanAllSummary(totals) {
  const summaryBox = document.getElementById("scan-all-summary-box");
  if (!summaryBox) return;

  summaryBox.classList.remove("d-none");
  document.getElementById("sum-total-scanned").textContent = (totals.total || 0).toLocaleString();
  document.getElementById("sum-safe").textContent = (totals.safe || 0).toLocaleString();
  document.getElementById("sum-suspicious").textContent = (totals.suspicious || 0).toLocaleString();
  document.getElementById("sum-spam").textContent = (totals.spam || 0).toLocaleString();
}

export function initManualScan() {
  const form = document.getElementById("manual-scan-form");
  const resultPanel = document.getElementById("manual-scan-result");
  const placeholder = document.getElementById("manual-scan-placeholder");

  // Sample loaders matching prompt examples
  document.getElementById("btn-sample-phishing")?.addEventListener("click", () => {
    document.getElementById("manual-from-name").value = "PayPal Security";
    document.getElementById("manual-from-address").value = "service@paypa1-security.top";
    document.getElementById("manual-reply-to").value = "collect@free-mail.example";
    document.getElementById("manual-subject").value = "Verify your account immediately";
    document.getElementById("manual-body").value = "Dear customer,\n\nYour account has been temporarily restricted due to suspicious sign-in attempts. Click http://203.0.113.9/login within 24 hours to verify your identity to prevent permanent closure.\n\nThank you,\nPayPal Security";
    document.getElementById("manual-urls").value = "http://203.0.113.9/login";
    document.getElementById("manual-attachments").value = "security_update.pdf.exe";
    document.getElementById("manual-spf").value = "fail";
    document.getElementById("manual-dkim").value = "none";
    document.getElementById("manual-dmarc").value = "fail";
  });

  document.getElementById("btn-sample-borderline")?.addEventListener("click", () => {
    document.getElementById("manual-from-name").value = "Netflix Billing";
    document.getElementById("manual-from-address").value = "billing-alert@sub-renew.xyz";
    document.getElementById("manual-reply-to").value = "";
    document.getElementById("manual-subject").value = "Your payment method has expired";
    document.getElementById("manual-body").value = "Hi there,\n\nWe could not renew your monthly subscription. Update your credit card at https://bit.ly/x1 immediately to avoid interruption.";
    document.getElementById("manual-urls").value = "https://bit.ly/x1";
    document.getElementById("manual-attachments").value = "";
    document.getElementById("manual-spf").value = "pass";
    document.getElementById("manual-dkim").value = "none";
    document.getElementById("manual-dmarc").value = "none";
  });

  document.getElementById("btn-sample-safe")?.addEventListener("click", () => {
    document.getElementById("manual-from-name").value = "Microsoft Security";
    document.getElementById("manual-from-address").value = "account-security@microsoft.com";
    document.getElementById("manual-reply-to").value = "";
    document.getElementById("manual-subject").value = "Your account security information";
    document.getElementById("manual-body").value = "Hello,\n\nThe security info for your Microsoft account was recently accessed from a known device. If this was you, you do not need to do anything.";
    document.getElementById("manual-urls").value = "https://account.microsoft.com";
    document.getElementById("manual-attachments").value = "";
    document.getElementById("manual-spf").value = "pass";
    document.getElementById("manual-dkim").value = "pass";
    document.getElementById("manual-dmarc").value = "pass";
  });

  document.getElementById("btn-clear-manual")?.addEventListener("click", () => {
    form?.reset();
    resultPanel?.classList.add("d-none");
    placeholder?.classList.remove("d-none");
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btnScan = document.getElementById("btn-run-manual-scan");
    btnScan.disabled = true;
    btnScan.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Analyzing Rules...`;

    try {
      const payload = {
        from_name: document.getElementById("manual-from-name")?.value || "",
        from_address: document.getElementById("manual-from-address")?.value || "",
        reply_to: document.getElementById("manual-reply-to")?.value || "",
        subject: document.getElementById("manual-subject")?.value || "",
        body: document.getElementById("manual-body")?.value || "",
        urls: document.getElementById("manual-urls")?.value || "",
        attachments: document.getElementById("manual-attachments")?.value || "",
        auth: {
          spf: document.getElementById("manual-spf")?.value || "none",
          dkim: document.getElementById("manual-dkim")?.value || "none",
          dmarc: document.getElementById("manual-dmarc")?.value || "none"
        },
        save: document.getElementById("manual-save-history")?.checked ?? true
      };

      const res = await apiRequest("/api/scan/manual", {
        method: "POST",
        body: payload
      });

      if (res.ok && res.data) {
        renderManualResult(res.data);
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnScan.disabled = false;
      btnScan.innerHTML = `<i class="bi bi-shield-check me-2"></i> Analyze Email`;
    }
  });
}

function renderManualResult(data) {
  const resultPanel = document.getElementById("manual-scan-result");
  const placeholder = document.getElementById("manual-scan-placeholder");
  if (!resultPanel) return;

  placeholder?.classList.add("d-none");
  resultPanel.classList.remove("d-none");
  resultPanel.scrollIntoView({ behavior: "smooth" });

  const scoreEl = document.getElementById("manual-res-score");
  const labelEl = document.getElementById("manual-res-label");
  const indicatorEl = document.getElementById("manual-meter-indicator");
  const reasonsList = document.getElementById("manual-res-reasons");

  if (scoreEl) scoreEl.textContent = `${data.score} / 100`;
  
  if (indicatorEl) {
    indicatorEl.style.left = `${Math.min(Math.max(data.score, 2), 98)}%`;
  }

  if (labelEl) {
    if (data.label === "safe") {
      labelEl.className = "badge-safe";
      labelEl.innerHTML = `<i class="bi bi-check-circle-fill"></i> SAFE`;
    } else if (data.label === "suspicious") {
      labelEl.className = "badge-suspicious";
      labelEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> SUSPICIOUS`;
    } else if (data.label === "spam") {
      labelEl.className = "badge-spam";
      labelEl.innerHTML = `<i class="bi bi-x-circle-fill"></i> SPAM`;
    }
  }

  if (reasonsList) {
    if (!data.reasons || data.reasons.length === 0) {
      reasonsList.innerHTML = `
        <div class="p-3 rounded bg-light border text-center text-muted small">
          <i class="bi bi-check-circle-fill text-success fs-5 d-block mb-1"></i>
          No threat triggers or risk rules were fired for this email.
        </div>
      `;
    } else {
      reasonsList.innerHTML = data.reasons.map(r => `
        <div class="reason-card">
          <div class="d-flex align-items-center justify-content-between mb-1">
            <span class="badge bg-secondary-subtle text-secondary border font-monospace" style="font-size: 11px;">${r.rule_id}</span>
            <span class="badge bg-danger-subtle text-danger border border-danger-subtle fw-bold">+${r.points} pts</span>
          </div>
          <strong style="color: var(--ms-navy);">${r.title}</strong>
          <p class="small text-muted mb-1 mt-1">${r.explanation}</p>
          ${r.evidence ? `<div class="evidence-box">${r.evidence}</div>` : ''}
        </div>
      `).join("");
    }
  }
}
