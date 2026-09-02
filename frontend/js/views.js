const Views = {};

// ---------------- Dashboard ----------------
Views.dashboard = async function (root) {
  root.innerHTML = `<div class="d-flex justify-content-center py-5"><div class="spinner-border text-primary"></div></div>`;
  const [stats, myLeads] = await Promise.all([
    apiFetch("/reports/conversion-stats"),
    apiFetch("/leads?page=1&page_size=5"),
  ]);

  const cards = [
    { label: "Total Leads", value: stats.total_leads, icon: "bi-people", color: "primary" },
    { label: "New", value: stats.by_status.new || 0, icon: "bi-star", color: "secondary" },
    { label: "In Follow-up", value: stats.by_status.follow_up || 0, icon: "bi-telephone-outbound", color: "warning" },
    { label: "Converted", value: stats.by_status.converted || 0, icon: "bi-check-circle", color: "success" },
    { label: "Lost", value: stats.by_status.lost || 0, icon: "bi-x-circle", color: "danger" },
    { label: "Conversion Rate", value: stats.conversion_rate + "%", icon: "bi-graph-up", color: "info" },
  ];

  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h4 class="mb-0">Dashboard</h4>
      <a href="#/leads" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> New Lead</a>
    </div>
    <div class="row g-3 mb-4">
      ${cards.map(c => `
        <div class="col-6 col-md-4 col-lg-2">
          <div class="card stat-card p-3 h-100">
            <i class="bi ${c.icon} text-${c.color} fs-4"></i>
            <div class="stat-value mt-2">${c.value}</div>
            <div class="text-muted small">${c.label}</div>
          </div>
        </div>`).join("")}
    </div>
    <div class="card">
      <div class="card-header bg-white d-flex justify-content-between align-items-center">
        <strong>Recent Leads</strong>
        <a href="#/leads" class="small">View all &rarr;</a>
      </div>
      <div class="table-responsive">
        <table class="table table-hover mb-0">
          <thead class="table-light"><tr><th>Name</th><th>Company</th><th>Source</th><th>Status</th><th>Assigned To</th><th>Created</th></tr></thead>
          <tbody>
            ${myLeads.items.map(l => `
              <tr class="clickable-row" onclick="location.hash='#/leads/${l.id}'">
                <td>${escapeHtml(l.first_name)} ${escapeHtml(l.last_name || "")}</td>
                <td>${escapeHtml(l.company || "-")}</td>
                <td>${escapeHtml(l.source || "-")}</td>
                <td>${statusBadge(l.status)}</td>
                <td>${escapeHtml(l.assigned_to_name || "Unassigned")}</td>
                <td>${fmtDate(l.created_at)}</td>
              </tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted py-4">No leads yet</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
};

// ---------------- Leads List ----------------
Views.leadsState = { page: 1, filters: {} };

Views.leads = async function (root) {
  const user = Auth.getUser();
  const [teams] = await Promise.all([apiFetch("/teams")]);
  let staffList = [];
  if (["super_admin", "site_admin", "marketing_manager", "team_leader"].includes(user.role)) {
    staffList = await apiFetch("/users");
  }

  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
      <h4 class="mb-0">Leads</h4>
      <button class="btn btn-primary btn-sm" id="new-lead-btn"><i class="bi bi-plus-lg"></i> New Lead</button>
    </div>
    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-2">
          <div class="col-md-3"><input class="form-control form-control-sm" id="f-search" placeholder="Search name, email, phone..."></div>
          <div class="col-md-2">
            <select class="form-select form-select-sm" id="f-status"><option value="">Any Status</option>${STATUS_OPTIONS.map(s => `<option value="${s}">${s.replace("_", " ")}</option>`).join("")}</select>
          </div>
          <div class="col-md-2">
            <select class="form-select form-select-sm" id="f-team"><option value="">Any Team</option>${buildOptions(teams, "id", "name")}</select>
          </div>
          <div class="col-md-2">
            <select class="form-select form-select-sm" id="f-staff"><option value="">Any Staff</option>${buildOptions(staffList, "id", "full_name")}</select>
          </div>
          <div class="col-md-2"><input type="date" class="form-control form-control-sm" id="f-from"></div>
          <div class="col-md-1"><input type="date" class="form-control form-control-sm" id="f-to"></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="table-responsive">
        <table class="table table-hover mb-0">
          <thead class="table-light"><tr><th>Name</th><th>Email / Phone</th><th>Company</th><th>Source</th><th>Status</th><th>Assigned To</th><th>Team</th><th>Created</th></tr></thead>
          <tbody id="leads-tbody"><tr><td colspan="8" class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></td></tr></tbody>
        </table>
      </div>
      <div class="card-footer bg-white d-flex justify-content-between align-items-center">
        <span class="text-muted small" id="leads-count"></span>
        <div id="leads-pagination"></div>
      </div>
    </div>
  `;

  const reload = () => Views._loadLeadsTable(1);
  ["f-search", "f-status", "f-team", "f-staff", "f-from", "f-to"].forEach(id => {
    qs("#" + id).addEventListener("change", reload);
  });
  qs("#f-search").addEventListener("keyup", (e) => { if (e.key === "Enter") reload(); });
  qs("#new-lead-btn").addEventListener("click", () => Views._leadFormModal(null, teams, staffList));

  Views._teams = teams;
  Views._staffList = staffList;
  Views._loadLeadsTable(1);
};

Views._loadLeadsTable = async function (page) {
  const params = new URLSearchParams();
  const search = qs("#f-search")?.value;
  const status = qs("#f-status")?.value;
  const team = qs("#f-team")?.value;
  const staff = qs("#f-staff")?.value;
  const from = qs("#f-from")?.value;
  const to = qs("#f-to")?.value;
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (team) params.set("team_id", team);
  if (staff) params.set("assigned_to_id", staff);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  params.set("page", page);
  params.set("page_size", 20);

  const data = await apiFetch(`/leads?${params.toString()}`);
  const tbody = qs("#leads-tbody");
  tbody.innerHTML = data.items.map(l => `
    <tr class="clickable-row" onclick="location.hash='#/leads/${l.id}'">
      <td>${escapeHtml(l.first_name)} ${escapeHtml(l.last_name || "")}</td>
      <td><div class="small">${escapeHtml(l.email || "-")}</div><div class="small text-muted">${escapeHtml(l.phone || "")}</div></td>
      <td>${escapeHtml(l.company || "-")}</td>
      <td>${escapeHtml(l.source || "-")}</td>
      <td>${statusBadge(l.status)}</td>
      <td>${escapeHtml(l.assigned_to_name || "Unassigned")}</td>
      <td>${escapeHtml(l.team_name || "-")}</td>
      <td>${fmtDate(l.created_at)}</td>
    </tr>`).join("") || `<tr><td colspan="8" class="text-center text-muted py-4">No leads found</td></tr>`;

  qs("#leads-count").textContent = `${data.total} lead(s) found`;
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(data.total / pageSize));
  const pag = qs("#leads-pagination");
  pag.innerHTML = "";
  if (totalPages > 1) {
    pag.innerHTML = `
      <div class="btn-group btn-group-sm">
        <button class="btn btn-outline-secondary" ${page <= 1 ? "disabled" : ""} id="prev-page">Prev</button>
        <button class="btn btn-outline-secondary disabled">${page} / ${totalPages}</button>
        <button class="btn btn-outline-secondary" ${page >= totalPages ? "disabled" : ""} id="next-page">Next</button>
      </div>`;
    qs("#prev-page")?.addEventListener("click", () => Views._loadLeadsTable(page - 1));
    qs("#next-page")?.addEventListener("click", () => Views._loadLeadsTable(page + 1));
  }
};

// ---------------- Lead Detail ----------------
Views.leadDetail = async function (root, leadId) {
  root.innerHTML = `<div class="d-flex justify-content-center py-5"><div class="spinner-border text-primary"></div></div>`;
  const user = Auth.getUser();
  const canAssign = ["super_admin", "site_admin", "marketing_manager", "team_leader"].includes(user.role);

  let lead;
  try {
    lead = await apiFetch(`/leads/${leadId}`);
  } catch (e) {
    root.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.detail || "Lead not found")}</div>`;
    return;
  }

  let staffList = [];
  if (canAssign) {
    staffList = await apiFetch("/users?role=marketing_staff" + (lead.team_id ? `&team_id=${lead.team_id}` : ""));
  }

  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <div>
        <a href="#/leads" class="text-decoration-none small"><i class="bi bi-arrow-left"></i> Back to Leads</a>
        <h4 class="mb-0 mt-1">${escapeHtml(lead.first_name)} ${escapeHtml(lead.last_name || "")} ${statusBadge(lead.status)}</h4>
      </div>
      <button class="btn btn-outline-secondary btn-sm" id="edit-lead-btn"><i class="bi bi-pencil"></i> Edit</button>
    </div>
    <div class="row g-3">
      <div class="col-lg-4">
        <div class="card mb-3">
          <div class="card-header bg-white"><strong>Contact Info</strong></div>
          <div class="card-body small">
            <p class="mb-1"><i class="bi bi-envelope me-1 text-muted"></i>${escapeHtml(lead.email || "-")}</p>
            <p class="mb-1"><i class="bi bi-telephone me-1 text-muted"></i>${escapeHtml(lead.phone || "-")}</p>
            <p class="mb-1"><i class="bi bi-building me-1 text-muted"></i>${escapeHtml(lead.company || "-")}</p>
            <p class="mb-1"><i class="bi bi-signpost me-1 text-muted"></i>Source: ${escapeHtml(lead.source || "-")}</p>
            <p class="mb-1"><i class="bi bi-geo-alt me-1 text-muted"></i>Place/Area: ${escapeHtml(lead.place_area || "-")}</p>
            <p class="mb-1"><i class="bi bi-person-hearts me-1 text-muted"></i>Referred By: ${escapeHtml(lead.referred_by || "-")}</p>
            <p class="mb-1"><i class="bi bi-people me-1 text-muted"></i>Team: ${escapeHtml(lead.team_name || "-")}</p>
            <p class="mb-1"><i class="bi bi-person-check me-1 text-muted"></i>Assigned: ${escapeHtml(lead.assigned_to_name || "Unassigned")}</p>
            <p class="mb-1"><i class="bi bi-calendar-plus me-1 text-muted"></i>Created: ${fmtDate(lead.created_at)}</p>
            ${lead.converted_at ? `<p class="mb-1"><i class="bi bi-check-circle me-1 text-success"></i>Converted: ${fmtDate(lead.converted_at)}</p>` : ""}
            ${lead.lost_reason ? `<p class="mb-1"><i class="bi bi-x-circle me-1 text-danger"></i>Lost reason: ${escapeHtml(lead.lost_reason)}</p>` : ""}
            ${lead.notes ? `<hr><p class="mb-0"><strong>Notes:</strong><br>${escapeHtml(lead.notes)}</p>` : ""}
          </div>
        </div>

        <div class="card mb-3">
          <div class="card-header bg-white"><strong>Update Status</strong></div>
          <div class="card-body">
            <select class="form-select form-select-sm mb-2" id="status-select">
              ${STATUS_OPTIONS.map(s => `<option value="${s}" ${s === lead.status ? "selected" : ""}>${s.replace("_", " ")}</option>`).join("")}
            </select>
            <textarea class="form-control form-control-sm mb-2" id="status-note" placeholder="Note (optional)" rows="2"></textarea>
            <input class="form-control form-control-sm mb-2 d-none" id="lost-reason" placeholder="Reason for loss">
            <button class="btn btn-primary btn-sm w-100" id="status-save-btn">Update Status</button>
          </div>
        </div>

        ${canAssign ? `
        <div class="card mb-3">
          <div class="card-header bg-white"><strong>Assign Lead</strong></div>
          <div class="card-body">
            <select class="form-select form-select-sm mb-2" id="assign-select">
              <option value="">Select staff...</option>
              ${buildOptions(staffList, "id", "full_name", lead.assigned_to_id)}
            </select>
            <button class="btn btn-outline-primary btn-sm w-100" id="assign-save-btn">Assign</button>
          </div>
        </div>` : ""}
      </div>

      <div class="col-lg-8">
        <div class="card mb-3">
          <div class="card-header bg-white d-flex justify-content-between align-items-center">
            <strong>Follow-ups</strong>
            <button class="btn btn-sm btn-outline-primary" id="add-followup-btn"><i class="bi bi-plus-lg"></i> Log Follow-up</button>
          </div>
          <div class="card-body">
            ${lead.follow_ups.length ? lead.follow_ups.map(f => `
              <div class="timeline-item">
                <div class="d-flex justify-content-between">
                  <strong class="text-capitalize">${escapeHtml(f.follow_up_type)}</strong>
                  <span class="text-muted small">${fmtDateTime(f.created_at)}</span>
                </div>
                ${f.outcome ? `<div class="small text-muted">Outcome: ${escapeHtml(f.outcome)}</div>` : ""}
                ${f.notes ? `<div class="small">${escapeHtml(f.notes)}</div>` : ""}
              </div>`).join("") : `<p class="text-muted mb-0">No follow-ups logged yet.</p>`}
          </div>
        </div>

        <div class="card">
          <div class="card-header bg-white"><strong>Status History</strong></div>
          <div class="card-body">
            ${lead.history.length ? lead.history.map(h => `
              <div class="timeline-item">
                <div class="d-flex justify-content-between">
                  <span>${h.old_status ? `${statusBadge(h.old_status)} &rarr; ${statusBadge(h.new_status)}` : statusBadge(h.new_status)}</span>
                  <span class="text-muted small">${fmtDateTime(h.changed_at)}</span>
                </div>
                ${h.note ? `<div class="small text-muted mt-1">${escapeHtml(h.note)}</div>` : ""}
              </div>`).join("") : `<p class="text-muted mb-0">No history yet.</p>`}
          </div>
        </div>
      </div>
    </div>
  `;

  qs("#status-select").addEventListener("change", (e) => {
    qs("#lost-reason").classList.toggle("d-none", e.target.value !== "lost");
  });

  qs("#status-save-btn").addEventListener("click", async () => {
    try {
      await apiFetch(`/leads/${leadId}/status`, {
        method: "POST",
        body: {
          status: qs("#status-select").value,
          note: qs("#status-note").value || null,
          lost_reason: qs("#lost-reason").value || null,
        },
      });
      showToast("Status updated");
      router();
    } catch (e) { showToast(e.detail || "Failed to update status", "danger"); }
  });

  qs("#assign-save-btn")?.addEventListener("click", async () => {
    const val = qs("#assign-select").value;
    if (!val) return showToast("Select a staff member", "warning");
    try {
      await apiFetch(`/leads/${leadId}/assign`, { method: "POST", body: { assigned_to_id: parseInt(val) } });
      showToast("Lead assigned");
      router();
    } catch (e) { showToast(e.detail || "Failed to assign lead", "danger"); }
  });

  qs("#edit-lead-btn").addEventListener("click", async () => {
    const teams = await apiFetch("/teams");
    Views._leadFormModal(lead, teams, staffList);
  });

  qs("#add-followup-btn").addEventListener("click", () => {
    const { modal, el } = openModal(`
      <div class="modal-header"><h5 class="modal-title">Log Follow-up</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <form id="followup-form">
          <div class="mb-2">
            <label class="form-label small">Type</label>
            <select class="form-select" name="follow_up_type">
              <option value="call">Call</option><option value="email">Email</option>
              <option value="meeting">Meeting</option><option value="other">Other</option>
            </select>
          </div>
          <div class="mb-2"><label class="form-label small">Outcome</label><input class="form-control" name="outcome" placeholder="e.g. Interested, No answer"></div>
          <div class="mb-2"><label class="form-label small">Notes</label><textarea class="form-control" name="notes" rows="3"></textarea></div>
        </form>
      </div>
      <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="followup-save-btn">Save</button></div>
    `);
    qs("#followup-save-btn", el).addEventListener("click", async () => {
      const fd = new FormData(qs("#followup-form", el));
      const payload = Object.fromEntries(fd.entries());
      try {
        await apiFetch(`/leads/${leadId}/follow-ups`, { method: "POST", body: payload });
        showToast("Follow-up logged");
        modal.hide();
        router();
      } catch (e) { showToast(e.detail || "Failed to log follow-up", "danger"); }
    });
  });
};

Views._leadFormModal = async function (lead, teams, staffList) {
  const isEdit = !!lead;
  let referralOptions = [];
  try { referralOptions = await apiFetch("/settings/options?category=referred_by"); } catch (e) { /* non-fatal - dropdown just stays empty */ }

  const { modal, el } = openModal(`
    <div class="modal-header"><h5 class="modal-title">${isEdit ? "Edit Lead" : "New Lead"}</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">
      <form id="lead-form">
        <div class="row g-2">
          <div class="col-6"><label class="form-label small">First Name *</label><input class="form-control" name="first_name" required value="${escapeHtml(lead?.first_name || "")}"></div>
          <div class="col-6"><label class="form-label small">Last Name</label><input class="form-control" name="last_name" value="${escapeHtml(lead?.last_name || "")}"></div>
          <div class="col-6"><label class="form-label small">Email</label><input type="email" class="form-control" name="email" value="${escapeHtml(lead?.email || "")}"></div>
          <div class="col-6"><label class="form-label small">Phone</label><input class="form-control" name="phone" value="${escapeHtml(lead?.phone || "")}"></div>
          <div class="col-6"><label class="form-label small">Company</label><input class="form-control" name="company" value="${escapeHtml(lead?.company || "")}"></div>
          <div class="col-6"><label class="form-label small">Source</label><input class="form-control" name="source" value="${escapeHtml(lead?.source || "")}" placeholder="e.g. Website, Referral"></div>
          <div class="col-6"><label class="form-label small">Place / Area</label><input class="form-control" name="place_area" value="${escapeHtml(lead?.place_area || "")}" placeholder="e.g. city, neighborhood, territory"></div>
          <div class="col-6">
            <label class="form-label small">Referred By</label>
            <select class="form-select" name="referred_by">
              <option value="">-- None --</option>
              ${buildOptions(referralOptions, "value", "value", lead?.referred_by)}
              ${lead?.referred_by && !referralOptions.some(o => o.value === lead.referred_by) ? `<option value="${escapeHtml(lead.referred_by)}" selected>${escapeHtml(lead.referred_by)} (inactive)</option>` : ""}
            </select>
          </div>
          <div class="col-12"><label class="form-label small">Notes</label><textarea class="form-control" name="notes" rows="2">${escapeHtml(lead?.notes || "")}</textarea></div>
        </div>
        <div id="lead-form-error" class="alert alert-danger py-2 mt-2 d-none"></div>
      </form>
    </div>
    <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="lead-save-btn">Save</button></div>
  `);

  qs("#lead-save-btn", el).addEventListener("click", async () => {
    const form = qs("#lead-form", el);
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    Object.keys(payload).forEach(k => { if (payload[k] === "") delete payload[k]; });
    try {
      if (isEdit) {
        await apiFetch(`/leads/${lead.id}`, { method: "PUT", body: payload });
        showToast("Lead updated");
      } else {
        await apiFetch("/leads", { method: "POST", body: payload });
        showToast("Lead created");
      }
      modal.hide();
      router();
    } catch (e) {
      const box = qs("#lead-form-error", el);
      box.textContent = e.detail || "Failed to save lead";
      box.classList.remove("d-none");
    }
  });
};

// ---------------- Import ----------------
Views.import = async function (root) {
  root.innerHTML = `
    <h4 class="mb-3">Import Leads from Excel</h4>
    <div class="card mb-3">
      <div class="card-body">
        <p class="text-muted small">Upload an .xlsx file, then map its columns to lead fields. Rows missing a first name will be rejected; rows matching an existing lead's email/phone are skipped as duplicates.</p>
        <input type="file" class="form-control" id="import-file" accept=".xlsx,.xlsm">
        <button class="btn btn-primary btn-sm mt-2" id="preview-btn"><i class="bi bi-eye"></i> Preview & Map Columns</button>
      </div>
    </div>
    <div id="mapping-area"></div>
    <div id="import-result"></div>
    <div class="card mt-3">
      <div class="card-header bg-white"><strong>Recent Import Batches</strong></div>
      <div class="table-responsive">
        <table class="table mb-0">
          <thead class="table-light"><tr><th>File</th><th>Total</th><th>Imported</th><th>Duplicates</th><th>Errors</th><th>By</th><th>Date</th></tr></thead>
          <tbody id="batches-tbody"><tr><td colspan="7" class="text-center py-3"><div class="spinner-border spinner-border-sm"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  `;

  const loadBatches = async () => {
    const batches = await apiFetch("/import/batches");
    qs("#batches-tbody").innerHTML = batches.map(b => `
      <tr>
        <td>${escapeHtml(b.filename)}</td>
        <td>${b.total_rows}</td>
        <td class="text-success">${b.success_count}</td>
        <td class="text-warning">${b.duplicate_count}</td>
        <td class="text-danger">${b.error_count}</td>
        <td>${escapeHtml(b.imported_by || "-")}</td>
        <td>${fmtDateTime(b.created_at)}</td>
      </tr>`).join("") || `<tr><td colspan="7" class="text-center text-muted py-3">No imports yet</td></tr>`;
  };
  loadBatches();

  qs("#preview-btn").addEventListener("click", async () => {
    const fileInput = qs("#import-file");
    if (!fileInput.files.length) return showToast("Choose a file first", "warning");
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    let preview;
    try {
      preview = await apiFetch("/import/preview", { method: "POST", body: fd, isForm: true });
    } catch (e) { return showToast(e.detail || "Preview failed", "danger"); }

    const appFields = preview.application_fields;
    const required = preview.required_fields;
    const teams = await apiFetch("/teams");
    let staffList = [];
    try { staffList = await apiFetch("/users?role=marketing_staff"); } catch (e) {}

    qs("#mapping-area").innerHTML = `
      <div class="card mb-3">
        <div class="card-header bg-white"><strong>Column Mapping</strong> <span class="text-muted small">(${preview.row_count} data rows detected)</span></div>
        <div class="card-body">
          <div class="row g-2 mb-3">
            ${appFields.map(f => `
              <div class="col-md-4">
                <label class="form-label small text-capitalize">${f.replace("_", " ")} ${required.includes(f) ? "*" : ""}</label>
                <select class="form-select form-select-sm map-field" data-field="${f}">
                  <option value="">-- Not mapped --</option>
                  ${preview.headers.map(h => `<option value="${escapeHtml(h)}" ${h.toLowerCase().includes(f.replace("_", "")) || h.toLowerCase().replace(/\s/g,'').includes(f.replace('_','')) ? 'selected' : ''}>${escapeHtml(h)}</option>`).join("")}
                </select>
              </div>`).join("")}
          </div>
          <div class="row g-2 mb-3">
            <div class="col-md-4">
              <label class="form-label small">Default Team (optional)</label>
              <select class="form-select form-select-sm" id="default-team"><option value="">None</option>${buildOptions(teams, "id", "name")}</select>
            </div>
            <div class="col-md-4">
              <label class="form-label small">Default Assignee (optional)</label>
              <select class="form-select form-select-sm" id="default-assignee"><option value="">None</option>${buildOptions(staffList, "id", "full_name")}</select>
            </div>
            <div class="col-md-4">
              <label class="form-label small">Default Source (optional)</label>
              <input class="form-control form-control-sm" id="default-source" placeholder="e.g. Trade Show 2026">
            </div>
          </div>
          <div class="table-responsive mb-3">
            <table class="table table-sm table-bordered">
              <thead><tr>${preview.headers.map(h => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
              <tbody>${preview.sample_rows.map(r => `<tr>${r.map(c => `<td>${escapeHtml(c ?? "")}</td>`).join("")}</tr>`).join("")}</tbody>
            </table>
          </div>
          <button class="btn btn-success btn-sm" id="commit-btn"><i class="bi bi-upload"></i> Import Now</button>
        </div>
      </div>
    `;

    qs("#commit-btn").addEventListener("click", async () => {
      const mapping = {};
      qsa(".map-field").forEach(sel => { if (sel.value) mapping[sel.dataset.field] = sel.value; });
      if (!mapping.first_name) return showToast("You must map 'first_name'", "warning");

      const fd2 = new FormData();
      fd2.append("file", fileInput.files[0]);
      fd2.append("mapping", JSON.stringify(mapping));
      const dTeam = qs("#default-team").value;
      const dAssignee = qs("#default-assignee").value;
      const dSource = qs("#default-source").value;
      if (dTeam) fd2.append("default_team_id", dTeam);
      if (dAssignee) fd2.append("default_assigned_to_id", dAssignee);
      if (dSource) fd2.append("default_source", dSource);

      try {
        const result = await apiFetch("/import/commit", { method: "POST", body: fd2, isForm: true });
        qs("#import-result").innerHTML = `
          <div class="alert alert-success">
            Imported <strong>${result.success_count}</strong> lead(s). Skipped <strong>${result.duplicate_count}</strong> duplicate(s).
            ${result.error_count ? `<strong>${result.error_count}</strong> row(s) had errors.` : ""}
          </div>
          ${result.errors.length ? `<div class="card"><div class="card-header bg-white">Errors</div><ul class="list-group list-group-flush">${result.errors.map(e => `<li class="list-group-item small">Row ${e.row}: ${escapeHtml(e.error)}</li>`).join("")}</ul></div>` : ""}
        `;
        showToast("Import complete");
        loadBatches();
      } catch (e) { showToast(e.detail || "Import failed", "danger"); }
    });
  });
};

// ---------------- Teams ----------------
Views.teams = async function (root) {
  const user = Auth.getUser();
  const canManage = ["super_admin", "site_admin", "marketing_manager"].includes(user.role);
  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Teams</h4>
      ${canManage ? `<button class="btn btn-primary btn-sm" id="new-team-btn"><i class="bi bi-plus-lg"></i> New Team</button>` : ""}
    </div>
    <div class="card">
      <div class="table-responsive">
        <table class="table table-hover mb-0">
          <thead class="table-light"><tr><th>Name</th><th>Description</th><th>Members</th><th>Status</th>${canManage ? "<th></th>" : ""}</tr></thead>
          <tbody id="teams-tbody"><tr><td colspan="5" class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  `;

  const load = async () => {
    const teams = await apiFetch("/teams");
    qs("#teams-tbody").innerHTML = teams.map(t => `
      <tr>
        <td>${escapeHtml(t.name)}</td>
        <td class="text-muted small">${escapeHtml(t.description || "-")}</td>
        <td>${t.member_count}</td>
        <td>${t.is_active ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Inactive</span>'}</td>
        ${canManage ? `<td class="text-end"><button class="btn btn-sm btn-outline-secondary edit-team" data-id="${t.id}"><i class="bi bi-pencil"></i></button></td>` : ""}
      </tr>`).join("") || `<tr><td colspan="5" class="text-center text-muted py-4">No teams yet</td></tr>`;

    qsa(".edit-team").forEach(btn => btn.addEventListener("click", () => {
      const team = teams.find(t => t.id == btn.dataset.id);
      Views._teamFormModal(team);
    }));
  };
  load();
  Views._reloadTeams = load;

  qs("#new-team-btn")?.addEventListener("click", () => Views._teamFormModal(null));
};

Views._teamFormModal = function (team) {
  const isEdit = !!team;
  const { modal, el } = openModal(`
    <div class="modal-header"><h5 class="modal-title">${isEdit ? "Edit Team" : "New Team"}</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">
      <form id="team-form">
        <div class="mb-2"><label class="form-label small">Name *</label><input class="form-control" name="name" required value="${escapeHtml(team?.name || "")}"></div>
        <div class="mb-2"><label class="form-label small">Description</label><textarea class="form-control" name="description" rows="2">${escapeHtml(team?.description || "")}</textarea></div>
        ${isEdit ? `<div class="form-check"><input type="checkbox" class="form-check-input" name="is_active" id="team-active" ${team.is_active ? "checked" : ""}><label class="form-check-label" for="team-active">Active</label></div>` : ""}
        <div id="team-form-error" class="alert alert-danger py-2 mt-2 d-none"></div>
      </form>
    </div>
    <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="team-save-btn">Save</button></div>
  `);

  qs("#team-save-btn", el).addEventListener("click", async () => {
    const form = qs("#team-form", el);
    const payload = { name: form.name.value, description: form.description.value || null };
    if (isEdit) payload.is_active = form.is_active.checked;
    try {
      if (isEdit) await apiFetch(`/teams/${team.id}`, { method: "PUT", body: payload });
      else await apiFetch("/teams", { method: "POST", body: payload });
      showToast("Team saved");
      modal.hide();
      Views._reloadTeams();
    } catch (e) {
      const box = qs("#team-form-error", el);
      box.textContent = e.detail || "Failed to save team";
      box.classList.remove("d-none");
    }
  });
};

// ---------------- Users ----------------
Views.users = async function (root) {
  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Staff & Users</h4>
      <button class="btn btn-primary btn-sm" id="new-user-btn"><i class="bi bi-plus-lg"></i> New User</button>
    </div>
    <div class="card">
      <div class="table-responsive">
        <table class="table table-hover mb-0">
          <thead class="table-light"><tr><th>Name</th><th>Username</th><th>Email</th><th>Role</th><th>Team</th><th>Status</th><th></th></tr></thead>
          <tbody id="users-tbody"><tr><td colspan="7" class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  `;

  const teams = await apiFetch("/teams");
  const teamName = (id) => teams.find(t => t.id === id)?.name || "-";

  const load = async () => {
    const users = await apiFetch("/users");
    qs("#users-tbody").innerHTML = users.map(u => `
      <tr>
        <td>${escapeHtml(u.full_name)}</td>
        <td>${escapeHtml(u.username)}</td>
        <td class="small">${escapeHtml(u.email)}</td>
        <td><span class="badge bg-primary-subtle text-primary-emphasis">${roleLabel(u.role)}</span></td>
        <td>${escapeHtml(teamName(u.team_id))}</td>
        <td>${u.is_active ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Disabled</span>'}</td>
        <td class="text-end">
  <button class="btn btn-sm btn-outline-secondary edit-user" data-id="${u.id}"><i class="bi bi-pencil"></i></button>
  <button class="btn btn-sm btn-outline-warning reset-user" data-id="${u.id}" title="Send password reset email"><i class="bi bi-key"></i></button>
</td>
      </tr>`).join("") || `<tr><td colspan="7" class="text-center text-muted py-4">No users yet</td></tr>`;

    qsa(".edit-user").forEach(btn => btn.addEventListener("click", () => {
      const u = users.find(x => x.id == btn.dataset.id);
      Views._userFormModal(u, teams);
    }));
    qsa(".reset-user").forEach(btn => btn.addEventListener("click", async () => {
      if (!confirm("Send a password reset email to this user?")) return;
      try {
        await apiFetch(`/auth/admin-reset-password?user_id=${btn.dataset.id}`, { method: "POST" });
        showToast("Password reset email sent");
      } catch (e) { showToast(e.detail || "Failed to send reset email", "danger"); }
    }));
  };
  load();
  Views._reloadUsers = load;

  qs("#new-user-btn").addEventListener("click", () => Views._userFormModal(null, teams));
};

Views._userFormModal = function (user, teams) {
  const isEdit = !!user;
  const { modal, el } = openModal(`
    <div class="modal-header"><h5 class="modal-title">${isEdit ? "Edit User" : "New User"}</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">
      <form id="user-form">
        <div class="row g-2">
          <div class="col-6"><label class="form-label small">Full Name *</label><input class="form-control" name="full_name" required value="${escapeHtml(user?.full_name || "")}"></div>
          <div class="col-6"><label class="form-label small">Username *</label><input class="form-control" name="username" required ${isEdit ? "readonly" : ""} value="${escapeHtml(user?.username || "")}"></div>
          <div class="col-6"><label class="form-label small">Email *</label><input type="email" class="form-control" name="email" required value="${escapeHtml(user?.email || "")}"></div>
          <div class="col-6"><label class="form-label small">Role *</label>
            <select class="form-select" name="role">${ROLE_OPTIONS.map(r => `<option value="${r}" ${user?.role === r ? "selected" : ""}>${roleLabel(r)}</option>`).join("")}</select>
          </div>
          <div class="col-6"><label class="form-label small">Team</label>
            <select class="form-select" name="team_id"><option value="">None</option>${buildOptions(teams, "id", "name", user?.team_id)}</select>
          </div>
          <div class="col-6"><label class="form-label small">${isEdit ? "New Password (optional)" : "Password *"}</label>
            <input type="password" class="form-control" name="password" ${isEdit ? "" : "required"}>
          </div>
          ${isEdit ? `<div class="col-12 form-check mt-2"><input type="checkbox" class="form-check-input" name="is_active" id="user-active" ${user.is_active ? "checked" : ""}><label class="form-check-label" for="user-active">Active</label></div>` : ""}
        </div>
        <div id="user-form-error" class="alert alert-danger py-2 mt-2 d-none"></div>
      </form>
    </div>
    <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="user-save-btn">Save</button></div>
  `);

  qs("#user-save-btn", el).addEventListener("click", async () => {
    const form = qs("#user-form", el);
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    payload.team_id = payload.team_id ? parseInt(payload.team_id) : null;
    if (isEdit) payload.is_active = form.is_active.checked;
    if (!payload.password) delete payload.password;
    try {
      if (isEdit) await apiFetch(`/users/${user.id}`, { method: "PUT", body: payload });
      else await apiFetch("/users", { method: "POST", body: payload });
      showToast("User saved");
      modal.hide();
      Views._reloadUsers();
    } catch (e) {
      const box = qs("#user-form-error", el);
      box.textContent = e.detail || "Failed to save user";
      box.classList.remove("d-none");
    }
  });
};

// ---------------- Reports ----------------
const REPORT_TYPES = [
  { key: "new", label: "New Leads", endpoint: "/reports/leads", params: { stage: "new" } },
  { key: "follow_up", label: "Follow-up Leads", endpoint: "/reports/leads", params: { stage: "follow_up" } },
  { key: "pending", label: "Pending Leads", endpoint: "/reports/leads", params: { stage: "pending" } },
  { key: "converted", label: "Converted Leads", endpoint: "/reports/leads", params: { stage: "converted" } },
  { key: "lost", label: "Lost / Closed Leads", endpoint: "/reports/leads", params: { stage: "lost" } },
  { key: "all", label: "All Leads", endpoint: "/reports/leads", params: { stage: "all" } },
  { key: "staff", label: "Staff-wise Performance", endpoint: "/reports/staff-performance", params: {} },
  { key: "team", label: "Team-wise Performance", endpoint: "/reports/team-performance", params: {} },
];

Views.reports = async function (root) {
  const teams = await apiFetch("/teams");
  let staffList = [];
  try { staffList = await apiFetch("/users"); } catch (e) {}

  root.innerHTML = `
    <h4 class="mb-3 no-print">Reports</h4>
    <div class="card mb-3 no-print">
      <div class="card-body">
        <div class="row g-2">
          <div class="col-md-3">
            <label class="form-label small">Report</label>
            <select class="form-select form-select-sm" id="rpt-type">${REPORT_TYPES.map(r => `<option value="${r.key}">${r.label}</option>`).join("")}</select>
          </div>
          <div class="col-md-2"><label class="form-label small">From</label><input type="date" class="form-control form-control-sm" id="rpt-from"></div>
          <div class="col-md-2"><label class="form-label small">To</label><input type="date" class="form-control form-control-sm" id="rpt-to"></div>
          <div class="col-md-2">
            <label class="form-label small">Team</label>
            <select class="form-select form-select-sm" id="rpt-team"><option value="">Any</option>${buildOptions(teams, "id", "name")}</select>
          </div>
          <div class="col-md-3">
            <label class="form-label small">Staff</label>
            <select class="form-select form-select-sm" id="rpt-staff"><option value="">Any</option>${buildOptions(staffList, "id", "full_name")}</select>
          </div>
          <div class="col-md-2"><label class="form-label small">Source</label><input class="form-control form-control-sm" id="rpt-source" placeholder="Any source"></div>
        </div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-primary btn-sm" id="run-report-btn"><i class="bi bi-search"></i> Run Report</button>
          <button class="btn btn-outline-secondary btn-sm" id="export-xlsx-btn"><i class="bi bi-file-earmark-excel"></i> Export XLSX</button>
          <button class="btn btn-outline-secondary btn-sm" id="export-pdf-btn"><i class="bi bi-file-earmark-pdf"></i> Export PDF</button>
          <button class="btn btn-outline-secondary btn-sm" id="print-btn"><i class="bi bi-printer"></i> Print</button>\n          <button class="btn btn-outline-primary btn-sm" id="email-report-btn"><i class="bi bi-envelope"></i> Email Report</button>
        </div>
      </div>
    </div>
    <div class="card"><div class="card-body table-responsive" id="report-output"><p class="text-muted mb-0">Choose a report and click "Run Report".</p></div></div>
  `;

  const buildParams = () => {
    const type = REPORT_TYPES.find(r => r.key === qs("#rpt-type").value);
    const params = new URLSearchParams(type.params);
    const from = qs("#rpt-from").value, to = qs("#rpt-to").value;
    const team = qs("#rpt-team").value, staff = qs("#rpt-staff").value, source = qs("#rpt-source").value.trim();
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    if (team) params.set("team_id", team);
    if (staff) params.set("staff_id", staff);
    if (source) params.set("source", source);
    return { type, params };
  };

  qs("#run-report-btn").addEventListener("click", async () => {
    const { type, params } = buildParams();
    const out = qs("#report-output");
    out.innerHTML = `<div class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></div>`;
    try {
      const data = await apiFetch(`${type.endpoint}?${params.toString()}`);
      out.innerHTML = `
        <h5>${type.label}</h5>
        <table class="table table-sm table-bordered report-table">
          <thead class="table-light"><tr>${data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>
          <tbody>${data.rows.map(r => `<tr>${r.map(c => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${data.headers.length}" class="text-center text-muted">No data</td></tr>`}</tbody>
        </table>`;
    } catch (e) { out.innerHTML = `<div class="alert alert-danger">${escapeHtml(e.detail || "Failed to load report")}</div>`; }
  });

  qs("#export-xlsx-btn").addEventListener("click", async () => {
    const { type, params } = buildParams();
    params.set("export", "xlsx");
    try { await apiDownload(`${type.endpoint}?${params.toString()}`, `${type.key}_report.xlsx`); }
    catch (e) { showToast(e.detail || "Export failed", "danger"); }
  });

  qs("#export-pdf-btn").addEventListener("click", async () => {
    const { type, params } = buildParams();
    params.set("export", "pdf");
    try { await apiDownload(`${type.endpoint}?${params.toString()}`, `${type.key}_report.pdf`); }
    catch (e) { showToast(e.detail || "Export failed", "danger"); }
  });

  qs("#print-btn").addEventListener("click", () => window.print());

  qs("#email-report-btn").addEventListener("click", () => {
    const { type } = buildParams();
    const { modal, el } = openModal(`
      <div class="modal-header"><h5 class="modal-title">Email ${escapeHtml(type.label)}</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <label class="form-label small">Recipients (comma separated)</label>
        <input class="form-control mb-2" id="email-recipients" type="text" placeholder="person@example.com, manager@example.com">
        <label class="form-label small">Subject</label><input class="form-control mb-2" id="email-subject" value="${escapeHtml(type.label)}">
        <label class="form-label small">Message</label><textarea class="form-control mb-2" id="email-message" rows="4">Please find the requested report attached.</textarea>
        <label class="form-label small">Attachments</label>
        <div><label class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="attach-pdf" checked> PDF</label>
        <label class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="attach-xlsx" checked> XLSX</label></div>
        <div id="email-report-error" class="alert alert-danger py-2 mt-2 d-none"></div>
      </div>
      <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="send-report-email">Send</button></div>`);
    qs("#send-report-email", el).addEventListener("click", async () => {
      const recipients = qs("#email-recipients", el).value.split(",").map(x=>x.trim()).filter(Boolean);
      const attachments=[]; if(qs("#attach-pdf",el).checked) attachments.push("pdf"); if(qs("#attach-xlsx",el).checked) attachments.push("xlsx");
      const err=qs("#email-report-error",el);
      if(!recipients.length || !attachments.length){err.textContent="Enter at least one recipient and select an attachment.";err.classList.remove("d-none");return;}
      const {params}=buildParams();
      const body={report_type:type.key,recipients,date_from:params.get("date_from")||null,date_to:params.get("date_to")||null,
        team_id:params.get("team_id")?parseInt(params.get("team_id")):null,staff_id:params.get("staff_id")?parseInt(params.get("staff_id")):null,
        source:params.get("source")||null, subject:qs("#email-subject",el).value,message:qs("#email-message",el).value,attachments};
      try{await apiFetch("/reports/email",{method:"POST",body});showToast("Report emailed successfully");modal.hide();}
      catch(e){err.textContent=e.detail||"Failed to email report";err.classList.remove("d-none");}
    });
  });
};

// ---------------- Audit Log ----------------
Views.audit = async function (root) {
  root.innerHTML = `
    <h4 class="mb-3">Audit Log</h4>
    <div class="card">
      <div class="table-responsive">
        <table class="table table-sm mb-0">
          <thead class="table-light"><tr><th>Time</th><th>User</th><th>Action</th><th>Entity</th><th>Details</th><th>IP</th></tr></thead>
          <tbody id="audit-tbody"><tr><td colspan="6" class="text-center py-4"><div class="spinner-border spinner-border-sm"></div></td></tr></tbody>
        </table>
      </div>
    </div>
  `;
  const logs = await apiFetch("/audit?page_size=100");
  qs("#audit-tbody").innerHTML = logs.map(l => `
    <tr>
      <td class="small">${fmtDateTime(l.created_at)}</td>
      <td class="small">${l.user_id ?? "-"}</td>
      <td class="small">${escapeHtml(l.action)}</td>
      <td class="small">${escapeHtml(l.entity_type || "-")} ${l.entity_id ?? ""}</td>
      <td class="small text-muted">${l.details ? escapeHtml(JSON.stringify(l.details)) : "-"}</td>
      <td class="small">${escapeHtml(l.ip_address || "-")}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted py-4">No audit entries</td></tr>`;
};

// ---------------- Settings ----------------
Views.settings = async function (root) {
  const current = await apiFetch("/settings/system");
  root.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Settings</h4>
      <button class="btn btn-primary btn-sm" id="settings-save"><i class="bi bi-check-lg"></i> Save Changes</button>
    </div>
    <ul class="nav nav-tabs mb-3" role="tablist">
      <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#site-tab">Site Customization</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#smtp-tab">SMTP / Email</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#users-tab">User & Role</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#teams-tab">Teams</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#workflow-tab">Lead Workflow</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#reports-tab">Report Settings</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#security-tab">Security</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#audit-tab">Audit Logs</button></li>
    </ul>
    <div class="tab-content">
      <div class="tab-pane fade show active" id="site-tab">
        <div class="card"><div class="card-body">
          <div class="row g-3">
            <div class="col-md-6"><label class="form-label">Site/Application Name</label><input class="form-control" data-setting="site_name" value="${escapeHtml(current.site_name)}"></div>
            <div class="col-md-6"><label class="form-label">Company Name</label><input class="form-control" data-setting="company_name" value="${escapeHtml(current.company_name)}"></div>
            <div class="col-md-6"><label class="form-label">Contact Email</label><input type="email" class="form-control" data-setting="contact_email" value="${escapeHtml(current.contact_email)}"></div>
            <div class="col-md-6"><label class="form-label">Contact Phone</label><input class="form-control" data-setting="contact_phone" value="${escapeHtml(current.contact_phone)}"></div>
            <div class="col-12"><label class="form-label">Company Address</label><textarea class="form-control" rows="2" data-setting="company_address">${escapeHtml(current.company_address)}</textarea></div>
            <div class="col-md-4"><label class="form-label">Primary Color</label><input type="color" class="form-control form-control-color" data-setting="primary_color" value="${escapeHtml(current.primary_color || "#0d6efd")}"></div>
            <div class="col-md-4"><label class="form-label">Theme</label><select class="form-select" data-setting="theme"><option value="light" ${current.theme==="light"?"selected":""}>Light</option><option value="dark" ${current.theme==="dark"?"selected":""}>Dark</option></select></div>
            <div class="col-md-4"><label class="form-label">Locale</label><input class="form-control" data-setting="locale" value="${escapeHtml(current.locale)}"></div>
            <div class="col-md-6"><label class="form-label">Timezone</label><input class="form-control" data-setting="timezone" value="${escapeHtml(current.timezone)}"></div>
            <div class="col-md-6"><label class="form-label">Date Format</label><input class="form-control" data-setting="date_format" value="${escapeHtml(current.date_format)}"></div>
            <div class="col-12"><label class="form-label">Login Page Branding Text</label><input class="form-control" data-setting="login_branding" value="${escapeHtml(current.login_branding)}"></div>
          </div>
          <hr><div class="row g-3">
            <div class="col-md-6"><label class="form-label">Logo</label><input type="file" class="form-control" id="logo-upload" accept=".png,.jpg,.jpeg,.webp,.svg"></div>
            <div class="col-md-6"><label class="form-label">Favicon</label><input type="file" class="form-control" id="favicon-upload" accept=".png,.jpg,.jpeg,.ico,.svg"></div>
          </div>
        </div></div>
      </div>
      <div class="tab-pane fade" id="smtp-tab"><div class="card"><div class="card-body">
        <div class="row g-3">
          <div class="col-md-6"><label class="form-label">SMTP Server / Host</label><input class="form-control" data-setting="smtp_host" value="${escapeHtml(current.smtp_host)}"></div>
          <div class="col-md-2"><label class="form-label">Port</label><input type="number" class="form-control" data-setting="smtp_port" value="${escapeHtml(current.smtp_port)}"></div>
          <div class="col-md-4"><label class="form-label">Security</label><select class="form-select" data-setting="smtp_security"><option value="starttls" ${current.smtp_security==="starttls"?"selected":""}>STARTTLS</option><option value="ssl" ${current.smtp_security==="ssl"?"selected":""}>SSL/TLS</option><option value="none" ${current.smtp_security==="none"?"selected":""}>None</option></select></div>
          <div class="col-md-6"><label class="form-label">SMTP Username</label><input class="form-control" data-setting="smtp_username" value="${escapeHtml(current.smtp_username)}"></div>
          <div class="col-md-6"><label class="form-label">SMTP Password</label><input type="password" class="form-control" data-setting="smtp_password" placeholder="${current.smtp_password==="********"?"Saved — leave blank to keep it":"Enter password"}"></div>
          <div class="col-md-6"><label class="form-label">Sender Email</label><input type="email" class="form-control" data-setting="smtp_sender_email" value="${escapeHtml(current.smtp_sender_email)}"></div>
          <div class="col-md-6"><label class="form-label">Sender / Display Name</label><input class="form-control" data-setting="smtp_sender_name" value="${escapeHtml(current.smtp_sender_name)}"></div>
          <div class="col-md-8"><label class="form-label">Frontend URL (used in password reset links)</label><input class="form-control" data-setting="frontend_url" value="${escapeHtml(current.frontend_url)}" placeholder="https://crm.example.com"></div>
          <div class="col-md-4 d-flex align-items-end"><button class="btn btn-outline-primary w-100" id="smtp-test">Send Test Email</button></div>
        </div>
        <div class="alert alert-info mt-3 mb-0 small">SMTP passwords are encrypted at rest and are never returned to the browser.</div>
      </div></div></div>
      <div class="tab-pane fade" id="users-tab"><div class="card"><div class="card-body">
        <h6>User & Role Settings</h6><p class="text-muted">Manage Super Admin, Site Admin, Marketing Manager, Team Leader and Marketing Staff accounts and permissions.</p>
        <a href="#/users" class="btn btn-outline-primary">Open User Management</a>
      </div></div></div>
      <div class="tab-pane fade" id="teams-tab"><div class="card"><div class="card-body">
        <h6>Team Settings</h6><p class="text-muted">Create teams, assign team leaders and manage team membership.</p>
        <a href="#/teams" class="btn btn-outline-primary">Open Team Management</a>
      </div></div></div>
      <div class="tab-pane fade" id="workflow-tab"><div class="card"><div class="card-body">
        <h6>Lead Status / Workflow Settings</h6><p class="text-muted">The standard workflow is New → Contacted → Follow-up → Pending → Converted/Lost → Closed. The active status list below controls which statuses are offered in lead forms.</p>
        <div id="workflow-options" class="row g-2"></div>
      </div></div></div>
      <div class="tab-pane fade" id="reports-tab"><div class="card"><div class="card-body">
        <h6>Report Settings</h6><div class="row g-3">
          <div class="col-md-6"><label class="form-label">Default report format</label><select class="form-select" data-setting="default_report_format"><option value="pdf">PDF</option><option value="xlsx">XLSX</option><option value="both">PDF + XLSX</option></select></div>
          <div class="col-md-6"><label class="form-label">Email report footer</label><input class="form-control" data-setting="report_email_footer" value="${escapeHtml(current.report_email_footer || "")}"></div>
        </div>
      </div></div></div>
      <div class="tab-pane fade" id="security-tab"><div class="card"><div class="card-body">
        <h6>Security Settings</h6><div class="row g-3">
          <div class="col-md-6"><label class="form-label">Session timeout (minutes)</label><input type="number" min="15" class="form-control" data-setting="session_timeout_minutes" value="${escapeHtml(current.session_timeout_minutes)}"></div>
          <div class="col-md-6"><label class="form-label">Password reset token lifetime (minutes)</label><input type="number" min="5" class="form-control" data-setting="password_reset_expire_minutes" value="${escapeHtml(current.password_reset_expire_minutes)}"></div>
        </div>
        <hr><button class="btn btn-outline-secondary" id="change-own-password">Change My Password</button>
      </div></div></div>
      <div class="tab-pane fade" id="audit-tab"><div class="card"><div class="card-body">
        <h6>Audit Logs</h6><p class="text-muted">Review administrative changes, authentication events, password resets, SMTP tests and emailed reports.</p>
        <a href="#/audit" class="btn btn-outline-primary">Open Audit Log</a>
      </div></div></div>
    </div>`;

  const collect = () => {
    const values = {};
    qsa("[data-setting]", root).forEach(el => values[el.dataset.setting] = el.value);
    return values;
  };
  qs("#settings-save").addEventListener("click", async () => {
    try {
      await apiFetch("/settings/system", {method:"PUT", body:{values:collect()}});
      for (const [kind,id] of [["logo","logo-upload"],["favicon","favicon-upload"]]) {
        const file = qs("#"+id).files[0];
        if (file) { const fd=new FormData(); fd.append("file",file); await apiFetch("/settings/upload?kind="+kind,{method:"POST",body:fd,isForm:true}); }
      }
      showToast("Settings saved");
      await loadPublicBranding();
    } catch(e) { showToast(e.detail || "Failed to save settings", "danger"); }
  });

  qs("#smtp-test").addEventListener("click", async () => {
    const recipient = prompt("Send test email to:", current.contact_email || "");
    if (!recipient) return;
    try { await apiFetch("/settings/test-email",{method:"POST",body:{recipient}}); showToast("Test email sent"); }
    catch(e){ showToast(e.detail || "SMTP test failed","danger"); }
  });

  qs("#change-own-password").addEventListener("click", () => {
    const {modal,el}=openModal(`<div class="modal-header"><h5 class="modal-title">Change Password</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body"><input type="password" class="form-control mb-2" id="cp-current" placeholder="Current password"><input type="password" class="form-control" id="cp-new" placeholder="New password (minimum 8 characters)"><div id="cp-error" class="alert alert-danger mt-2 d-none"></div></div>
      <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" id="cp-save">Change</button></div>`);
    qs("#cp-save",el).addEventListener("click",async()=>{
      try { await apiFetch("/auth/change-password",{method:"POST",body:{current_password:qs("#cp-current",el).value,new_password:qs("#cp-new",el).value}}); showToast("Password changed"); modal.hide(); }
      catch(e){qs("#cp-error",el).textContent=e.detail||"Failed";qs("#cp-error",el).classList.remove("d-none");}
    });
  });

  const workflow = await apiFetch("/settings/options?category=lead_status&include_inactive=true");
  qs("#workflow-options").innerHTML = STATUS_OPTIONS.map(st => {
    const o=workflow.find(x=>x.value===st);
    return `<div class="col-md-4"><div class="form-check form-switch"><input class="form-check-input workflow-status" type="checkbox" value="${st}" ${!o || o.is_active ? "checked":""}><label class="form-check-label">${st.replace("_"," ")}</label></div></div>`;
  }).join("");
  // Seed/update workflow options from this screen.
  qsa(".workflow-status").forEach(cb=>cb.addEventListener("change",async()=>{
    try {
      if(cb.checked) await apiFetch("/settings/options",{method:"POST",body:{category:"lead_status",value:cb.value}});
      else { const o=workflow.find(x=>x.value===cb.value); if(o) await apiFetch(`/settings/options/${o.id}`,{method:"DELETE"}); }
      showToast("Workflow updated");
    } catch(e){ showToast(e.detail||"Workflow update failed","danger"); cb.checked=!cb.checked; }
  }));
};
