const NAV_ITEMS = [
  { hash: "#/dashboard", label: "Dashboard", icon: "bi-speedometer2", roles: null },
  { hash: "#/leads", label: "Leads", icon: "bi-people", roles: null },
  { hash: "#/import", label: "Import", icon: "bi-upload", roles: ["super_admin", "site_admin", "marketing_manager", "team_leader"] },
  { hash: "#/reports", label: "Reports", icon: "bi-bar-chart", roles: null },
  { hash: "#/teams", label: "Teams", icon: "bi-diagram-3", roles: null },
  { hash: "#/users", label: "Users", icon: "bi-person-badge", roles: ["super_admin", "site_admin", "marketing_manager", "team_leader"] },
  { hash: "#/settings", label: "Settings", icon: "bi-gear", roles: ["super_admin", "site_admin"] },
  { hash: "#/audit", label: "Audit Log", icon: "bi-journal-text", roles: ["super_admin", "site_admin"] },
];

function renderNav() {
  const user = Auth.getUser();
  const navLinks = qs("#nav-links");
  navLinks.innerHTML = NAV_ITEMS
    .filter(item => !item.roles || item.roles.includes(user.role))
    .map(item => `<li class="nav-item"><a class="nav-link" href="${item.hash}"><i class="bi ${item.icon} me-1"></i>${item.label}</a></li>`)
    .join("");
  qs("#nav-user").textContent = `${user.full_name} (${roleLabel(user.role)})`;
}

function setActiveNav() {
  qsa("#nav-links .nav-link").forEach(a => {
    a.classList.toggle("active", location.hash.startsWith(a.getAttribute("href")));
  });
}

async function router() {
  if (!Auth.isLoggedIn()) {
    qs("#login-screen").classList.remove("d-none");
    qs("#app-shell").classList.add("d-none");
    return;
  }
  qs("#login-screen").classList.add("d-none");
  qs("#app-shell").classList.remove("d-none");
  renderNav();
  setActiveNav();

  const root = qs("#view-root");
  const hash = location.hash || "#/dashboard";
  const [, path, param] = hash.split("/");

  try {
    if (!path || path === "dashboard") await Views.dashboard(root);
    else if (path === "leads" && !param) await Views.leads(root);
    else if (path === "leads" && param) await Views.leadDetail(root, param);
    else if (path === "import") await Views.import(root);
    else if (path === "teams") await Views.teams(root);
    else if (path === "users") await Views.users(root);
    else if (path === "settings") await Views.settings(root);
    else if (path === "reports") await Views.reports(root);
    else if (path === "audit") await Views.audit(root);
    else root.innerHTML = `<div class="alert alert-warning">Page not found.</div>`;
  } catch (e) {
    root.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.detail || e.message || "Something went wrong loading this page.")}</div>`;
  }
}

window.addEventListener("hashchange", router);

document.addEventListener("DOMContentLoaded", () => {
  if (Auth.isLoggedIn()) {
    router();
  } else {
    qs("#login-screen").classList.remove("d-none");
  }

  qs("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = qs("#login-username").value;
    const password = qs("#login-password").value;
    const errBox = qs("#login-error");
    errBox.classList.add("d-none");
    try {
      const data = await apiLogin(username, password);
      Auth.setSession(data.access_token, {
        user_id: data.user_id, full_name: data.full_name, role: data.role,
      });
      location.hash = "#/dashboard";
      router();
    } catch (err) {
      errBox.textContent = err.detail || "Login failed";
      errBox.classList.remove("d-none");
    }
  });

  qs("#logout-btn").addEventListener("click", () => {
    Auth.clear();
    location.hash = "";
    router();
  });
});
