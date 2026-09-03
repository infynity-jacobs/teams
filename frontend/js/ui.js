function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const id = "t" + Date.now();
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.id = id;
  el.innerHTML = `<div class="d-flex">
      <div class="toast-body">${escapeHtml(message)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: 4000 });
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function statusBadge(status) {
  const label = (status || "").replace("_", " ");
  return `<span class="badge badge-status status-${status}">${escapeHtml(label)}</span>`;
}

function fmtDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function fmtDateTime(iso, opts = {}) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", ...(opts.seconds ? {second: "2-digit"} : {}) });
}

function roleLabel(role) {
  const map = {
    super_admin: "Super Admin",
    site_admin: "Site Admin",
    marketing_manager: "Marketing Manager",
    team_leader: "Team Leader",
    marketing_staff: "Marketing Staff",
  };
  return map[role] || role;
}

const STATUS_OPTIONS = ["new", "contacted", "follow_up", "pending", "converted", "lost", "closed"];
const ROLE_OPTIONS = ["super_admin", "site_admin", "marketing_manager", "team_leader", "marketing_staff"];

function openModal(html, { size = "" } = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "modal fade";
  wrapper.tabIndex = -1;
  wrapper.innerHTML = `<div class="modal-dialog ${size}"><div class="modal-content">${html}</div></div>`;
  document.body.appendChild(wrapper);
  const modal = new bootstrap.Modal(wrapper);
  wrapper.addEventListener("hidden.bs.modal", () => wrapper.remove());
  modal.show();
  return { el: wrapper, modal };
}

function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function buildOptions(items, valueKey, labelKey, selected) {
  return items.map(i => {
    const v = typeof i === "object" ? i[valueKey] : i;
    const l = typeof i === "object" ? i[labelKey] : i;
    const sel = String(v) === String(selected) ? "selected" : "";
    return `<option value="${escapeHtml(v)}" ${sel}>${escapeHtml(l)}</option>`;
  }).join("");
}
