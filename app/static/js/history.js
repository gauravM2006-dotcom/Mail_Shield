import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";

export async function initHistory() {
  // Tabs: Scans vs Batches
  document.getElementById("btn-view-scans")?.addEventListener("click", () => {
    document.getElementById("view-scans-panel").classList.remove("d-none");
    document.getElementById("view-batches-panel").classList.add("d-none");
    document.getElementById("btn-view-scans").className = "btn btn-primary";
    document.getElementById("btn-view-batches").className = "btn btn-outline-secondary";
    loadScans();
  });

  document.getElementById("btn-view-batches")?.addEventListener("click", () => {
    document.getElementById("view-scans-panel").classList.add("d-none");
    document.getElementById("view-batches-panel").classList.remove("d-none");
    document.getElementById("btn-view-batches").className = "btn btn-primary";
    document.getElementById("btn-view-scans").className = "btn btn-outline-secondary";
    loadBatches();
  });

  document.getElementById("history-search")?.addEventListener("input", () => loadScans());
  document.getElementById("history-label-filter")?.addEventListener("change", () => loadScans());
  document.getElementById("btn-clear-history")?.addEventListener("click", () => clearAllHistory());

  await loadScans();
}

async function loadScans() {
  const tbody = document.getElementById("scans-table-body");
  if (!tbody) return;

  const label = document.getElementById("history-label-filter")?.value || "";
  const q = document.getElementById("history-search")?.value || "";

  let url = "/api/history/scans?limit=50";
  if (label) url += `&label=${label}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;

  try {
    const res = await apiRequest(url);
    if (res.ok && res.data) {
      const items = res.data.items || [];
      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="text-center py-5">
              <div class="ms-empty-icon mx-auto"><i class="bi bi-clock-history"></i></div>
              <h6 class="fw-bold mb-1" style="color: var(--ms-navy);">No scan history found</h6>
              <p class="text-muted small mb-0">Analyzed emails and manual scans will appear here.</p>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = items.map(s => {
        const fromStr = (s.email_summary?.from?.name || s.email_summary?.from?.address) || "Unknown";
        const dateStr = s.created_at ? new Date(s.created_at).toLocaleString() : "";
        
        let badge = `<span class="badge-safe"><i class="bi bi-check-circle-fill"></i> Safe ${s.score}</span>`;
        if (s.label === "suspicious") {
          badge = `<span class="badge-suspicious"><i class="bi bi-exclamation-triangle-fill"></i> Suspicious ${s.score}</span>`;
        } else if (s.label === "spam") {
          badge = `<span class="badge-spam"><i class="bi bi-x-circle-fill"></i> Spam ${s.score}</span>`;
        }

        return `
          <tr>
            <td class="small text-muted">${dateStr}</td>
            <td><span class="badge bg-light text-dark border">${s.provider.toUpperCase()}</span></td>
            <td class="text-truncate fw-medium" style="max-width:180px; color: var(--ms-navy);">${fromStr}</td>
            <td class="text-truncate" style="max-width:300px;">${s.email_summary?.subject || "(No Subject)"}</td>
            <td>${badge}</td>
            <td><span class="badge bg-secondary-subtle text-secondary border font-monospace">${s.reasons_count} rules</span></td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-danger p-1 px-2 btn-delete-scan" data-id="${s.id}" title="Delete record">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join("");

      tbody.querySelectorAll(".btn-delete-scan").forEach(btn => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-id");
          await apiRequest(`/api/history/scans/${id}`, { method: "DELETE" });
          showToast("Scan record deleted", "info");
          loadScans();
        });
      });
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-4 small">${err.message}</td></tr>`;
  }
}

async function loadBatches() {
  const tbody = document.getElementById("batches-table-body");
  if (!tbody) return;

  try {
    const res = await apiRequest("/api/history/batches");
    if (res.ok && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center py-5">
              <div class="ms-empty-icon mx-auto"><i class="bi bi-layers"></i></div>
              <h6 class="fw-bold mb-1" style="color: var(--ms-navy);">No batch scan jobs</h6>
              <p class="text-muted small mb-0">Multi-mailbox scan jobs will be logged here.</p>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = res.data.map(b => {
        const dateStr = b.started_at ? new Date(b.started_at).toLocaleString() : "";
        return `
          <tr>
            <td class="small text-muted">${dateStr}</td>
            <td><span class="badge bg-light text-dark border text-uppercase">${b.mode}</span></td>
            <td>${(b.providers || []).map(p => `<span class="badge bg-secondary-subtle text-secondary me-1">${p.toUpperCase()}</span>`).join("")}</td>
            <td class="fw-bold">${(b.total_mails || 0).toLocaleString()}</td>
            <td class="small">
              <span class="text-success fw-semibold">${b.totals?.safe || 0} Safe</span> ·
              <span class="text-warning fw-semibold">${b.totals?.suspicious || 0} Suspicious</span> ·
              <span class="text-danger fw-semibold">${b.totals?.spam || 0} Spam</span>
            </td>
            <td class="text-end">
              <span class="badge bg-success-subtle text-success border border-success-subtle">Completed</span>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger text-center py-4 small">${err.message}</td></tr>`;
  }
}

async function clearAllHistory() {
  if (!confirm("Are you sure you want to permanently clear all scan logs?")) return;
  try {
    const res = await apiRequest("/api/history/clear", { method: "DELETE" });
    if (res.ok) {
      showToast("Scan history cleared", "info");
      loadScans();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}
