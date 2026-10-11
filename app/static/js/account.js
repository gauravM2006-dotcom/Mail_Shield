import { apiRequest } from "./api.js";
import { showToast } from "./toast.js";

export async function initAccount() {
  await loadAccountDetails();

  // Profile Form
  document.getElementById("profile-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const display_name = document.getElementById("profile-display-name").value;
    try {
      const res = await apiRequest("/api/account/profile", {
        method: "PATCH",
        body: { display_name }
      });
      if (res.ok) showToast("Profile updated successfully", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Password Form
  document.getElementById("password-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const current = document.getElementById("pwd-current")?.value || "";
    const newPwd = document.getElementById("pwd-new").value;
    const confirmPwd = document.getElementById("pwd-confirm").value;

    try {
      const res = await apiRequest("/api/account/password", {
        method: "POST",
        body: { current, new: newPwd, confirm: confirmPwd }
      });
      if (res.ok) {
        showToast("Password changed successfully", "success");
        document.getElementById("password-form").reset();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Delete Account
  document.getElementById("btn-confirm-delete-account")?.addEventListener("click", async () => {
    const text = document.getElementById("delete-confirm-input").value;
    if (text !== "DELETE") {
      showToast("Please type DELETE to confirm account deletion.", "error");
      return;
    }

    try {
      const res = await apiRequest("/api/account", {
        method: "DELETE",
        body: { confirm: "DELETE" }
      });
      if (res.ok) {
        window.location.href = "/";
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

async function loadAccountDetails() {
  try {
    const res = await apiRequest("/api/account");
    if (res.ok && res.data) {
      const u = res.data;
      document.getElementById("profile-username").textContent = u.username;
      document.getElementById("profile-email").textContent = u.email;
      document.getElementById("profile-display-name").value = u.display_name || "";
      
      const emailStatus = document.getElementById("profile-email-status");
      if (emailStatus) {
        if (u.email_verified) {
          emailStatus.className = "badge bg-success";
          emailStatus.textContent = "Verified";
        } else {
          emailStatus.className = "badge bg-warning text-dark";
          emailStatus.textContent = "Unverified";
        }
      }

      // Render connected mailboxes
      const mbList = document.getElementById("account-mailboxes-list");
      if (mbList && u.mailboxes) {
        mbList.innerHTML = u.mailboxes.map(mb => `
          <div class="list-group-item d-flex align-items-center justify-content-between p-3">
            <div>
              <div class="fw-bold">${mb.provider.toUpperCase()}</div>
              <div class="text-muted small">${mb.address || 'Not connected'}</div>
            </div>
            <div>
              <span class="badge ${mb.status === 'live' ? 'bg-success' : 'bg-secondary'} me-2">${mb.status}</span>
              <span class="badge bg-body-secondary text-body">${mb.cached} cached</span>
            </div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}
