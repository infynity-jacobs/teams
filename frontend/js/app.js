const NAV_ITEMS = [
  { hash: "#/dashboard", label: "Dashboard", icon: "bi-speedometer2", roles: null },
  { hash: "#/profile", label: "My Profile", icon: "bi-person-circle", roles: null },
  { hash: "#/leads", label: "Leads", icon: "bi-people", roles: null },
  { hash: "#/products", label: "Products", icon: "bi-box-seam", roles: null },
  { hash: "#/follow-ups", label: "Follow-ups", icon: "bi-calendar2-week", roles: null },
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

function renderMobileNav() {
  const user = Auth.getUser();
  const items = [
    { hash: "#/dashboard", label: "Home", icon: "bi-house" },
    { hash: "#/leads", label: "Leads", icon: "bi-people" },
    { hash: "#/leads?new=1", label: "New Lead", icon: "bi-plus-lg", primary: true },
    { hash: "#/reports", label: "Reports", icon: "bi-bar-chart" },
    { hash: "#/profile", label: "More", icon: "bi-three-dots" },
  ];
  const nav = qs("#mobile-bottom-nav");
  if (!nav) return;
  nav.innerHTML = items.map(item => {
    const base = item.hash.split("?")[0];
    const active = base === "#/dashboard" ? location.hash.startsWith("#/dashboard") : base === "#/leads" ? location.hash.startsWith("#/leads") : base === "#/reports" ? location.hash.startsWith("#/reports") : base === "#/profile" ? location.hash.startsWith("#/profile") : false;
    return `<a href="${item.hash}" class="mobile-bottom-item ${item.primary ? "mobile-bottom-primary" : ""} ${active ? "active" : ""}"><span class="mobile-bottom-icon"><i class="bi ${item.icon}"></i></span><span>${item.label}</span></a>`;
  }).join("");
}

function setActiveNav() {
  qsa("#nav-links .nav-link").forEach(a => {
    a.classList.toggle("active", location.hash.startsWith(a.getAttribute("href")));
  });
}

async function loadPublicBranding() {
  try {
    const s = await apiFetch("/settings/public");
    document.title = s.site_name || "Lead CRM";
    const brand = qs(".navbar-brand");
    if (brand) brand.innerHTML = s.company_logo_url
      ? `<img src="${escapeHtml(s.company_logo_url)}" style="height:28px;max-width:130px;object-fit:contain" class="me-2">`
      : `<i class="bi bi-graph-up-arrow me-1"></i>${escapeHtml(s.site_name || "Lead CRM")}`;
    const loginTitle = qs("#login-site-name");
    if (loginTitle) loginTitle.textContent = s.site_name || "Lead CRM";
    const loginBranding = qs("#login-branding");
    if (loginBranding) loginBranding.textContent = s.login_branding || "Marketing Lead Management";
    const loginLogo = qs("#login-logo");
    const loginIcon = qs("#login-default-icon");
    if (loginLogo) {
      if (s.company_logo_url) {
        loginLogo.src = s.company_logo_url;
        loginLogo.classList.remove("d-none");
        if (loginIcon) loginIcon.classList.add("d-none");
      } else {
        loginLogo.classList.add("d-none");
        if (loginIcon) loginIcon.classList.remove("d-none");
      }
    }
    if (s.favicon_url) {
      let link = qs("#site-favicon");
      if (!link) { link = document.createElement("link"); link.id = "site-favicon"; link.rel = "icon"; document.head.appendChild(link); }
      link.href = s.favicon_url;
    }
    if (s.primary_color) document.documentElement.style.setProperty("--primary-color", s.primary_color);
    document.documentElement.setAttribute("data-bs-theme", s.theme === "dark" ? "dark" : "light");
  } catch (_) {}
}

async function showForgotPassword() {
  const user = qs("#login-username").value.trim();
  const identifier = prompt("Enter your registered email address or username:", user);
  if (!identifier) return;
  try {
    await apiFetch("/auth/forgot-password", { method: "POST", body: { identifier } });
    showToast("If the account exists, a reset email has been sent.");
  } catch (e) { showToast(e.detail || "Unable to request password reset", "danger"); }
}

async function showResetPassword(token) {
  qs("#login-screen").classList.remove("d-none");
  qs("#app-shell").classList.add("d-none");
  const title = qs("#login-site-name");
  if (title) title.textContent = "Set New Password";
  qs("#login-form").innerHTML = `
    <div class="mb-3"><label class="form-label">New Password</label><input type="password" class="form-control" id="reset-password" minlength="8" required></div>
    <div class="mb-3"><label class="form-label">Confirm Password</label><input type="password" class="form-control" id="reset-password-confirm" minlength="8" required></div>
    <div id="login-error" class="alert alert-danger py-2 d-none"></div>
    <button class="btn btn-primary w-100">Set Password</button>
    <button type="button" class="btn btn-link w-100 mt-2" id="reset-back-login">Back to sign in</button>
  `;
  qs("#reset-back-login")?.addEventListener("click", () => { location.hash = "#/login"; location.reload(); });
  qs("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const p = qs("#reset-password").value, c = qs("#reset-password-confirm").value;
    if (p !== c) { qs("#login-error").textContent = "Passwords do not match"; qs("#login-error").classList.remove("d-none"); return; }
    try {
      await apiFetch("/auth/reset-password", { method: "POST", body: { token, new_password: p } });
      alert("Password changed successfully. You can now sign in.");
      location.hash = "#/login";
      location.reload();
    } catch (err) { qs("#login-error").textContent = err.detail || "Invalid or expired reset link"; qs("#login-error").classList.remove("d-none"); }
  };
}

async function router() {
  const hash = location.hash || "#/dashboard";
  if (hash.startsWith("#/reset-password")) {
    const query = hash.includes("?") ? hash.split("?")[1] : "";
    const token = new URLSearchParams(query).get("token");
    if (!token) {
      qs("#login-screen").classList.remove("d-none");
      qs("#app-shell").classList.add("d-none");
      const err = qs("#login-error");
      err.textContent = "Invalid password reset link.";
      err.classList.remove("d-none");
      return;
    }
    await showResetPassword(token);
    return;
  }

  if (!Auth.isLoggedIn()) {
    qs("#login-screen").classList.remove("d-none");
    qs("#app-shell").classList.add("d-none");
    return;
  }
  qs("#login-screen").classList.add("d-none");
  qs("#app-shell").classList.remove("d-none");
  renderNav();
  renderMobileNav();
  setActiveNav();

  const root = qs("#view-root");
  const hashPath = hash.slice(1).split("?")[0];
  const parts = hashPath.split("/").filter(Boolean);
  const path = parts[0] || "dashboard";
  const param = parts[1];

  try {
    if (path === "dashboard") await Views.dashboard(root);
    else if (path === "profile") await Views.profile(root);
    else if (path === "leads" && !param) await Views.leads(root);
    else if (path === "leads" && param) await Views.leadDetail(root, param);
    else if (path === "products") await Views.products(root);
    else if (path === "follow-ups") await Views.followups(root);
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

document.addEventListener("DOMContentLoaded", async () => {
  await loadPublicBranding();

  // Always route on first load, including unauthenticated reset-password links.
  // Previously an unauthenticated deep link was left on the login screen because
  // router() was only called when a session already existed.
  await router();

  const loginForm = qs("#login-form");
  loginForm?.addEventListener("submit", async (e) => {
    // The reset-password view installs its own submit handler. Do not run the
    // normal login handler for a password-reset URL.
    if (location.hash.startsWith("#/reset-password")) return;

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

  qs("#forgot-password-btn")?.addEventListener("click", showForgotPassword);

  qs("#logout-btn")?.addEventListener("click", () => {
    Auth.clear();
    location.hash = "";
    router();
  });
});
