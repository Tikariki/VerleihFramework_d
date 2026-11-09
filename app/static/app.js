/* Dashboard-Logik. Spricht ausschließlich mit der JSON-API unter /api. */

const state = {
  meta: null,
  items: [],
  customers: [],
  rentals: [],
  dashboard: null,
  view: "dashboard",
  rentalFilter: "",
  itemFilter: "",
};

const el = (id) => document.getElementById(id);

/* ------------------------------------------------------------- Hilfsmittel */
const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

const money = (value) => {
  const number = Number(value ?? 0);
  return number.toLocaleString("de-AT", { style: "currency", currency: "EUR" });
};

const formatDate = (iso) => {
  if (!iso) return "–";
  const [y, m, d] = String(iso).slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
};

const todayIso = () => new Date().toLocaleDateString("sv-SE");

let toastTimer = null;
function toast(message, isError = false) {
  const box = el("toast");
  box.textContent = message;
  box.className = `toast${isError ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), 3800);
}

async function apiGet(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

async function apiSend(url, method, body) {
  const options = { method, headers: {} };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

async function readError(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail.length) {
      return data.detail.map((d) => d.msg).join(", ");
    }
    return data.message || "Unbekannter Fehler";
  } catch {
    return `Fehler ${response.status}`;
  }
}

/* ------------------------------------------------------------------ Laden */
async function loadMeta() {
  state.meta = await apiGet("/api/meta");
  const types = state.meta.item_types || [];
  const pluginCount = (state.meta.plugins || []).length;
  el("plugin-badge").textContent =
    `${pluginCount} Plugins · ${types.length} Verleiharten`;

  const filter = el("item-filter");
  filter.innerHTML =
    `<button class="active" data-type="">Alle Typen</button>` +
    types.map((t) => `<button data-type="${escapeHtml(t.type_key)}">${escapeHtml(t.label)}</button>`).join("");
}

async function loadData() {
  const [items, customers, rentals, dashboard] = await Promise.all([
    apiGet("/api/items?include_inactive=true"),
    apiGet("/api/customers"),
    apiGet(`/api/rentals${state.rentalFilter ? `?status=${state.rentalFilter}` : ""}`),
    apiGet("/api/dashboard"),
  ]);
  state.items = items.items;
  state.customers = customers.customers;
  state.rentals = rentals.rentals;
  state.dashboard = dashboard;
}

async function refresh() {
  await loadData();
  render();
}

/* -------------------------------------------------------------- Rendering */
function render() {
  renderDashboard();
  renderRentals();
  renderItems();
  renderCustomers();
  renderPricing();
}

function renderDashboard() {
  const data = state.dashboard;
  if (!data) return;

  el("today").textContent = new Date().toLocaleDateString("de-AT", {
    weekday: "long", day: "2-digit", month: "long", year: "numeric",
  });

  el("kpis").innerHTML = `
    <div class="kpi" style="--accent:#2563eb">
      <div class="kpi-label">Verliehen</div>
      <div class="kpi-value">${data.items.rented}</div>
      <div class="kpi-hint">von ${data.items.active} aktiven Gegenständen</div>
    </div>
    <div class="kpi" style="--accent:#059669">
      <div class="kpi-label">Verfügbar</div>
      <div class="kpi-value">${data.items.available}</div>
      <div class="kpi-hint">${data.items.inactive} deaktiviert</div>
    </div>
    <div class="kpi" style="--accent:#7c3aed">
      <div class="kpi-label">Aktive Vorgänge</div>
      <div class="kpi-value">${data.rentals.active}</div>
      <div class="kpi-hint">${data.rentals.overdue} überfällig · ${data.rentals.due_today} heute fällig</div>
    </div>
    <div class="kpi" style="--accent:#0d9488">
      <div class="kpi-label">Einnahmen (Monat)</div>
      <div class="kpi-value">${money(data.revenue.month)}</div>
      <div class="kpi-hint">gesamt ${money(data.revenue.total)}</div>
    </div>`;

  const due = data.due_soon || [];
  el("due-list").innerHTML = due.length
    ? due.map((rental) => {
        const days = rental.days_until_due;
        let badge = `<span class="badge ok">in ${days} ${days === 1 ? "Tag" : "Tagen"}</span>`;
        if (days < 0) badge = `<span class="badge late">${Math.abs(days)} Tage überfällig</span>`;
        else if (days === 0) badge = `<span class="badge warn">heute fällig</span>`;
        return `<div class="list-row">
          <div>
            <strong>${escapeHtml(rental.item_name)}</strong>
            <div class="meta">${escapeHtml(rental.customer_name)} · bis ${formatDate(rental.due_date)}</div>
          </div>
          ${badge}
        </div>`;
      }).join("")
    : `<div class="empty">Keine Rückgaben in den nächsten 7 Tagen.</div>`;

  const types = (data.items.by_type || []).filter((t) => t.total > 0);
  const max = Math.max(...types.map((t) => t.total), 1);
  el("type-breakdown").innerHTML = types.length
    ? types.map((type) => `
        <div class="bar-row">
          <span>${escapeHtml(type.label)}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${(type.total / max) * 100}%"><span class="bar-fill-inner" style="width:${(type.rented / Math.max(type.total, 1)) * 100}%"></span></span></span>
          <span class="bar-value">${type.rented}/${type.total}</span>
        </div>`).join("")
    : `<div class="empty">Noch keine Gegenstände angelegt.</div>`;

  const rows = (data.recent_rentals || []).slice(0, 6);
  el("recent-table").innerHTML = `
    <thead><tr>
      <th>Gegenstand</th><th>Kunde</th><th>Zeitraum</th><th>Status</th><th class="num">Betrag</th>
    </tr></thead>
    <tbody>${rows.length ? rows.map((rental) => `
      <tr>
        <td>${escapeHtml(rental.item_name)}</td>
        <td>${escapeHtml(rental.customer_name)}</td>
        <td>${formatDate(rental.start_date)} – ${formatDate(rental.due_date)}</td>
        <td>${statusBadge(rental.status)}</td>
        <td class="num">${money(rental.total)}</td>
      </tr>`).join("") : `<tr><td colspan="5" class="empty">Noch keine Verleihvorgänge.</td></tr>`}
    </tbody>`;
}

function statusBadge(status) {
  const map = {
    active: `<span class="badge rented">verliehen</span>`,
    returned: `<span class="badge ok">zurückgegeben</span>`,
    overdue: `<span class="badge late">überfällig</span>`,
    available: `<span class="badge ok">verfügbar</span>`,
    rented: `<span class="badge rented">verliehen</span>`,
    inactive: `<span class="badge off">deaktiviert</span>`,
  };
  return map[status] || `<span class="badge off">${escapeHtml(status)}</span>`;
}

function renderRentals() {
  const rentals = state.rentals;
  el("rental-table").innerHTML = `
    <thead><tr>
      <th>Gegenstand</th><th>Kunde</th><th>Von</th><th>Bis</th>
      <th class="num">Tage</th><th class="num">Betrag</th><th>Status</th><th></th>
    </tr></thead>
    <tbody>${rentals.length ? rentals.map((rental) => `
      <tr>
        <td><strong>${escapeHtml(rental.item_name)}</strong><div class="meta small muted">${escapeHtml(rental.item_type)}</div></td>
        <td>${escapeHtml(rental.customer_name)}</td>
        <td>${formatDate(rental.start_date)}</td>
        <td>${formatDate(rental.due_date)}</td>
        <td class="num">${rental.days}</td>
        <td class="num">${money(rental.total)}</td>
        <td>${statusBadge(rental.status)}</td>
        <td>
          <div class="row-actions">
            ${rental.status === "returned" ? "" :
              `<button class="btn btn-ghost small" data-return="${rental.id}">Rückgabe</button>`}
            <button class="btn btn-ghost small" data-details="${rental.id}">Details</button>
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="8" class="empty">Keine Verleihvorgänge gefunden.</td></tr>`}
    </tbody>`;
}

function renderItems() {
  const items = state.items.filter(
    (item) => !state.itemFilter || item.type_key === state.itemFilter
  );
  el("item-table").innerHTML = `
    <thead><tr>
      <th>Gegenstand</th><th>Typ</th><th>Kategorie</th>
      <th class="num">Tagespreis</th><th>Status</th><th></th>
    </tr></thead>
    <tbody>${items.length ? items.map((item) => `
      <tr>
        <td>
          <strong>${escapeHtml(item.name)}</strong>
          <div class="cell-sub meta small muted" title="${escapeHtml(item.description || "")}">${escapeHtml(item.description || "–")}</div>
        </td>
        <td>${escapeHtml(item.type_label)}</td>
        <td>${escapeHtml(item.category)}</td>
        <td class="num">${money(item.daily_rate)}</td>
        <td>${statusBadge(item.status)}</td>
        <td>
          <div class="row-actions">
            <button class="btn btn-ghost small" data-edit-item="${item.id}">Bearbeiten</button>
            <button class="btn btn-danger small" data-delete-item="${item.id}">Löschen</button>
          </div>
        </td>
      </tr>`).join("") : `<tr><td colspan="6" class="empty">Keine Gegenstände vorhanden.</td></tr>`}
    </tbody>`;
}

function renderCustomers() {
  const customers = state.customers;
  const docLabels = Object.fromEntries(
    (state.meta?.id_document_types || []).map((doc) => [doc.key, doc.label])
  );
  el("customer-table").innerHTML = `
    <thead><tr>
      <th>Name</th><th>Kontakt</th><th>Ausweis</th><th>Status</th><th></th>
    </tr></thead>
    <tbody>${customers.length ? customers.map((customer) => {
      const doc = customer.id_document;
      return `<tr>
        <td><strong>${escapeHtml(customer.full_name)}</strong></td>
        <td class="small muted">${escapeHtml(customer.email || customer.phone || "–")}</td>
        <td class="small">${doc
          ? `${escapeHtml(docLabels[doc.type_key] || doc.type_key)} · ${escapeHtml(doc.number)}
             ${doc.file_name ? `<span class="badge ok">Datei</span>` : ""}`
          : `<span class="badge late">fehlt</span>`}</td>
        <td>${customer.has_active_rental
          ? `<span class="badge rented">hat Ausrüstung</span>`
          : `<span class="badge off">inaktiv</span>`}</td>
        <td>
          <div class="row-actions">
            <button class="btn btn-ghost small" data-edit-customer="${customer.id}">Bearbeiten</button>
            <button class="btn btn-ghost small" data-doc-customer="${customer.id}">Ausweis</button>
            <button class="btn btn-danger small" data-delete-customer="${customer.id}">Löschen</button>
          </div>
        </td>
      </tr>`;
    }).join("") : `<tr><td colspan="5" class="empty">Keine Kunden vorhanden.</td></tr>`}
    </tbody>`;
}

function renderPricing() {
  const rules = (state.meta?.pricing_rules || []).slice().sort((a, b) => a.priority - b.priority);
  el("rule-list").innerHTML = rules.length
    ? rules.map((rule) => {
        let detail = "";
        if (rule.tiers) {
          const tiers = rule.tiers
            .filter((tier) => Number(tier.discount_percent) !== 0)
            .sort((a, b) => b.min_days - a.min_days)
            .map((tier) => `ab ${tier.min_days} ${Number(tier.min_days) === 1 ? "Tag" : "Tagen"} −${tier.discount_percent} %`);
          detail = tiers.length ? "Staffel: " + tiers.join(", ") : "kein Mengenrabatt";
        } else if (rule.categories) {
          detail = Object.entries(rule.categories)
            .map(([cat, percent]) => `${cat}: ${percent > 0 ? "+" : ""}${percent} %`)
            .join(", ");
        } else if (rule.percent) {
          detail = `Aufschlag ${rule.percent} %`;
        } else if (rule.fee) {
          detail = `Pauschale ${money(rule.fee)}`;
        }
        return `<div class="rule">
          <div>
            <strong>${escapeHtml(rule.label)}</strong>
            <div class="rule-key">${escapeHtml(rule.key)} · Priorität ${rule.priority}</div>
            ${detail ? `<div class="small muted">${escapeHtml(detail)}</div>` : ""}
          </div>
          <span class="rule-src">${escapeHtml(rule.source)}</span>
        </div>`;
      }).join("")
    : `<div class="empty">Keine Preisregeln registriert.</div>`;
}

/* -------------------------------------------------------------- Navigation */
const titles = {
  dashboard: ["Dashboard", "Überblick über Verleih, Rückgaben und Einnahmen"],
  rentals: ["Verleihvorgänge", "Ausgabe, Rückgabe und Historie"],
  items: ["Gegenstände", "Bestand aller Verleiharten"],
  customers: ["Kunden", "Identifikation per Ausweis"],
  pricing: ["Preise", "Regelwerk der Preisberechnung"],
};

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((button) =>
    button.classList.toggle("active", button.dataset.view === view));
  document.querySelectorAll(".view").forEach((section) =>
    section.classList.toggle("hidden", section.id !== `view-${view}`));
  const [title, subtitle] = titles[view];
  el("page-title").textContent = title;
  el("page-subtitle").textContent = subtitle;
}

/* ------------------------------------------------------------------ Modal */
function openModal({ title, body, submitLabel = "Speichern", onSubmit, onSubmitLabel }) {
  el("modal-title").textContent = title;
  el("modal-submit").textContent = submitLabel;
  el("modal-submit").style.display = onSubmit ? "" : "none";
  const form = el("modal-form");
  form.innerHTML = body;
  form.onsubmit = async (event) => {
    event.preventDefault();
    try {
      await onSubmit(form);
      closeModal();
      await refresh();
    } catch (error) {
      toast(error.message, true);
    }
  };
  el("modal").classList.remove("hidden");
  setTimeout(() => form.querySelector("input, select")?.focus(), 60);
}

function closeModal() {
  el("modal").classList.add("hidden");
  el("modal-form").innerHTML = "";
}

/* ------------------------------------------------------------- Formulare  */
function itemTypeOptions(selected) {
  return (state.meta?.item_types || []).map((type) =>
    `<option value="${escapeHtml(type.type_key)}" ${type.type_key === selected ? "selected" : ""}>
      ${escapeHtml(type.label)}
    </option>`).join("");
}

function attributeFields(typeKey, values = {}) {
  const type = (state.meta?.item_types || []).find((t) => t.type_key === typeKey);
  if (!type) return "";
  return type.attributes.map((field) => {
    const value = values[field.name] ?? "";
    const label = `<label>${escapeHtml(field.label)}${field.required ? " *" : ""}</label>`;
    if (field.kind === "select") {
      const options = [`<option value="">– bitte wählen –</option>`]
        .concat(field.options.map((option) =>
          `<option value="${escapeHtml(option)}" ${String(value) === option ? "selected" : ""}>${escapeHtml(option)}</option>`));
      return `<div class="field">${label}<select name="attr_${field.name}" ${field.required ? "required" : ""}>${options.join("")}</select></div>`;
    }
    if (field.kind === "bool") {
      return `<div class="field"><label class="checkbox">
        <input type="checkbox" name="attr_${field.name}" ${value ? "checked" : ""} />
        ${escapeHtml(field.label)}</label></div>`;
    }
    const type2 = field.kind === "number" ? "number" : "text";
    const step = field.kind === "number" ? `step="any" min="1"` : "";
    return `<div class="field">${label}
      <input type="${type2}" ${step} name="attr_${field.name}" value="${escapeHtml(value)}"
             ${field.required ? "required" : ""} placeholder="${escapeHtml(field.unit || "")}" />
    </div>`;
  }).join("");
}

function collectAttributes(form, typeKey) {
  const type = (state.meta?.item_types || []).find((t) => t.type_key === typeKey);
  const attributes = {};
  (type?.attributes || []).forEach((field) => {
    const input = form.querySelector(`[name="attr_${field.name}"]`);
    if (!input) return;
    if (field.kind === "bool") attributes[field.name] = input.checked;
    else if (input.value !== "") attributes[field.name] = input.value;
  });
  return attributes;
}

function openItemModal(item) {
  const typeKey = item?.type_key || (state.meta?.item_types?.[0]?.type_key ?? "");
  openModal({
    title: item ? `Gegenstand bearbeiten: ${item.name}` : "Neuen Gegenstand anlegen",
    submitLabel: item ? "Speichern" : "Anlegen",
    body: `
      <div class="row-2">
        <div class="field"><label>Verleihtyp</label>
          <select name="type_key" id="item-type" ${item ? "disabled" : ""}>
            ${itemTypeOptions(typeKey)}
          </select>
          ${item ? `<span class="hint">Typ ist nach dem Anlegen unveränderlich.</span>` : ""}
        </div>
        <div class="field"><label>Kategorie</label>
          <input name="category" value="${escapeHtml(item?.category || "Standard")}" required />
          <span class="hint">z. B. Premium, Standard, Kinder</span>
        </div>
      </div>
      <div class="row-2">
        <div class="field"><label>Name</label>
          <input name="name" value="${escapeHtml(item?.name || "")}" required placeholder="z. B. Atomic Redster 170" />
        </div>
        <div class="field"><label>Tagespreis (€)</label>
          <input name="daily_rate" type="number" step="0.01" min="0.01" value="${item?.daily_rate ?? ""}" required />
        </div>
      </div>
      <div id="attr-fields" class="grid" style="display:grid; gap:14px">
        ${attributeFields(typeKey, item?.attributes || {})}
      </div>`,
    onSubmit: async (form) => {
      const type = form.querySelector('[name="type_key"]').value || typeKey;
      const payload = {
        type_key: type,
        name: form.querySelector('[name="name"]').value,
        category: form.querySelector('[name="category"]').value,
        daily_rate: form.querySelector('[name="daily_rate"]').value,
        attributes: collectAttributes(form, type),
      };
      if (item) {
        delete payload.type_key;
        await apiSend(`/api/items/${item.id}`, "PUT", payload);
        toast("Gegenstand aktualisiert.");
      } else {
        await apiSend("/api/items", "POST", payload);
        toast("Gegenstand angelegt.");
      }
    },
  });

  const typeSelect = el("item-type");
  if (typeSelect && !item) {
    typeSelect.addEventListener("change", () => {
      el("attr-fields").innerHTML = attributeFields(typeSelect.value, {});
    });
  }
}

function openRentalModal() {
  const items = state.items.filter((item) => item.active && item.status === "available");
  const allItems = state.items.filter((item) => item.active);
  const customers = state.customers;

  openModal({
    title: "Verleihvorgang anlegen",
    submitLabel: "Verleih starten",
    body: `
      <div class="field"><label>Gegenstand</label>
        <select name="item_id" required>
          <option value="">– bitte wählen –</option>
          ${allItems.map((item) => `<option value="${item.id}" ${item.status !== "available" ? "disabled" : ""}>
            ${escapeHtml(item.name)} · ${escapeHtml(item.type_label)} · ${money(item.daily_rate)}/Tag
            ${item.status !== "available" ? " (verliehen)" : ""}
          </option>`).join("")}
        </select>
        <span class="hint">${items.length} von ${allItems.length} Gegenständen aktuell frei.</span>
      </div>
      <div class="field"><label>Kunde</label>
        <select name="customer_id" required>
          <option value="">– bitte wählen –</option>
          ${customers.map((customer) => `<option value="${customer.id}">
            ${escapeHtml(customer.full_name)}${customer.has_id_document ? "" : " (kein Ausweis)"}
          </option>`).join("")}
        </select>
        <span class="hint">Ohne hinterlegten Ausweis lehnt das System den Verleih ab.</span>
      </div>
      <div class="row-2">
        <div class="field"><label>Verleihbeginn</label>
          <input type="date" name="start_date" value="${todayIso()}" required />
        </div>
        <div class="field"><label>Dauer (Tage)</label>
          <input type="number" name="days" min="1" max="365" value="1" required />
        </div>
      </div>
      <div class="price-preview" id="price-preview">
        <span class="muted small">Preis wird berechnet, sobald Gegenstand und Dauer feststehen.</span>
      </div>`,
    onSubmit: async (form) => {
      await apiSend("/api/rentals", "POST", {
        item_id: Number(form.querySelector('[name="item_id"]').value),
        customer_id: Number(form.querySelector('[name="customer_id"]').value),
        start_date: form.querySelector('[name="start_date"]').value,
        days: Number(form.querySelector('[name="days"]').value),
      });
      toast("Verleihvorgang angelegt.");
    },
  });

  const form = el("modal-form");
  const updatePreview = async () => {
    const itemId = form.querySelector('[name="item_id"]').value;
    const days = form.querySelector('[name="days"]').value;
    const start = form.querySelector('[name="start_date"]').value;
    const box = el("price-preview");
    if (!itemId || !days) return;
    try {
      const quote = await apiSend("/api/rentals/quote", "POST", {
        item_id: Number(itemId),
        customer_id: Number(form.querySelector('[name="customer_id"]').value) || 0,
        days: Number(days),
        start_date: start,
      });
      box.innerHTML = quote.lines.map((line) => `
          <div class="price-line"><span>${escapeHtml(line.label)}</span>
          <span>${money(line.amount)}</span></div>`).join("") +
        `<div class="price-total"><span>Gesamt</span><span>${money(quote.total)}</span></div>`;
    } catch (error) {
      box.innerHTML = `<span class="small" style="color:#b91c1c">${escapeHtml(error.message)}</span>`;
    }
  };
  ["item_id", "days", "start_date", "customer_id"].forEach((name) => {
    form.querySelector(`[name="${name}"]`)?.addEventListener("change", updatePreview);
    form.querySelector(`[name="${name}"]`)?.addEventListener("input", updatePreview);
  });
}

function openCustomerModal(customer) {
  const docTypes = state.meta?.id_document_types || [];
  const doc = customer?.id_document;
  openModal({
    title: customer ? `Kunde bearbeiten: ${customer.full_name}` : "Neuen Kunden anlegen",
    submitLabel: customer ? "Speichern" : "Anlegen",
    body: `
      <div class="row-2">
        <div class="field"><label>Vorname</label>
          <input name="first_name" value="${escapeHtml(customer?.first_name || "")}" required />
        </div>
        <div class="field"><label>Nachname</label>
          <input name="last_name" value="${escapeHtml(customer?.last_name || "")}" required />
        </div>
      </div>
      <div class="row-2">
        <div class="field"><label>E-Mail</label>
          <input name="email" type="email" value="${escapeHtml(customer?.email || "")}" />
        </div>
        <div class="field"><label>Telefon</label>
          <input name="phone" value="${escapeHtml(customer?.phone || "")}" />
        </div>
      </div>
      <div class="row-2">
        <div class="field"><label>Ausweistyp</label>
          <select name="id_type">
            <option value="">– kein Ausweis –</option>
            ${docTypes.map((type) => `<option value="${escapeHtml(type.key)}"
              ${doc?.type_key === type.key ? "selected" : ""}>${escapeHtml(type.label)}</option>`).join("")}
          </select>
        </div>
        <div class="field"><label>Ausweisnummer</label>
          <input name="id_number" value="${escapeHtml(doc?.number || "")}" />
        </div>
      </div>`,
    onSubmit: async (form) => {
      const payload = {
        first_name: form.querySelector('[name="first_name"]').value,
        last_name: form.querySelector('[name="last_name"]').value,
        email: form.querySelector('[name="email"]').value,
        phone: form.querySelector('[name="phone"]').value,
      };
      const idType = form.querySelector('[name="id_type"]').value;
      const idNumber = form.querySelector('[name="id_number"]').value;
      if (idType) {
        payload.id_type = idType;
        payload.id_number = idNumber;
      }
      if (customer) {
        await apiSend(`/api/customers/${customer.id}`, "PUT", payload);
        toast("Kunde aktualisiert.");
      } else {
        await apiSend("/api/customers", "POST", payload);
        toast("Kunde angelegt.");
      }
    },
  });
}

function openDocumentModal(customer) {
  const docTypes = state.meta?.id_document_types || [];
  openModal({
    title: `Ausweis hinterlegen: ${customer.full_name}`,
    submitLabel: "Hochladen",
    body: `
      <div class="field"><label>Ausweistyp</label>
        <select name="type_key" required>
          ${docTypes.map((type) => `<option value="${escapeHtml(type.key)}"
            ${customer.id_document?.type_key === type.key ? "selected" : ""}>
            ${escapeHtml(type.label)}</option>`).join("")}
        </select>
      </div>
      <div class="field"><label>Ausweisnummer</label>
        <input name="number" value="${escapeHtml(customer.id_document?.number || "")}" required />
      </div>
      <div class="field"><label>Scan (JPG, PNG oder PDF, max. 5 MB)</label>
        <input type="file" name="file" accept=".jpg,.jpeg,.png,.pdf" />
        <span class="hint">Optional: Foto oder Scan des Ausweises.</span>
      </div>`,
    onSubmit: async (form) => {
      const data = new FormData();
      data.append("type_key", form.querySelector('[name="type_key"]').value);
      data.append("number", form.querySelector('[name="number"]').value);
      const file = form.querySelector('[name="file"]').files[0];
      if (file) data.append("file", file);
      await apiSend(`/api/customers/${customer.id}/document`, "POST", data);
      toast("Ausweis gespeichert.");
    },
  });
}

function openRentalDetails(rental) {
  const lines = (rental.price_lines || []).map((line) => `
    <div class="price-line"><span>${escapeHtml(line.label)}</span><span>${money(line.amount)}</span></div>`).join("");
  openModal({
    title: `Verleihvorgang #${rental.id}`,
    body: `
      <div class="list">
        <div class="list-row"><span>Gegenstand</span><strong>${escapeHtml(rental.item_name)}</strong></div>
        <div class="list-row"><span>Kunde</span><strong>${escapeHtml(rental.customer_name)}</strong></div>
        <div class="list-row"><span>Zeitraum</span><strong>${formatDate(rental.start_date)} – ${formatDate(rental.due_date)}</strong></div>
        <div class="list-row"><span>Tagespreis</span><strong>${money(rental.daily_rate)}</strong></div>
        <div class="list-row"><span>Status</span>${statusBadge(rental.status)}</div>
      </div>
      <div class="price-preview">
        ${lines}
        <div class="price-total"><span>Gesamt</span><span>${money(rental.total)}</span></div>
      </div>`,
  });
}

/* ----------------------------------------------------------------- Events */
document.addEventListener("click", async (event) => {
  const target = event.target;

  if (target.matches(".nav-item")) switchView(target.dataset.view);

  if (target.matches("[data-goto]")) switchView(target.dataset.goto);

  if (target.matches("[data-close]")) closeModal();

  if (target.matches('[data-action="new-rental"]') || target.id === "primary-action") {
    switchView("rentals");
    openRentalModal();
  }
  if (target.matches('[data-action="new-item"]')) openItemModal(null);
  if (target.matches('[data-action="new-customer"]')) openCustomerModal(null);

  if (target.matches("[data-edit-item]")) {
    const item = state.items.find((i) => String(i.id) === target.dataset.editItem);
    openItemModal(item);
  }

  if (target.matches("[data-delete-item]")) {
    const item = state.items.find((i) => String(i.id) === target.dataset.deleteItem);
    if (!confirm(`"${item.name}" löschen?`)) return;
    try {
      const result = await apiSend(`/api/items/${item.id}`, "DELETE");
      toast(result.message);
      await refresh();
    } catch (error) {
      toast(error.message, true);
    }
  }

  if (target.matches("[data-edit-customer]")) {
    const customer = state.customers.find((c) => String(c.id) === target.dataset.editCustomer);
    openCustomerModal(customer);
  }

  if (target.matches("[data-doc-customer]")) {
    const customer = state.customers.find((c) => String(c.id) === target.dataset.docCustomer);
    openDocumentModal(customer);
  }

  if (target.matches("[data-delete-customer]")) {
    const customer = state.customers.find((c) => String(c.id) === target.dataset.deleteCustomer);
    if (!confirm(`${customer.full_name} löschen?`)) return;
    try {
      await apiSend(`/api/customers/${customer.id}`, "DELETE");
      toast("Kunde gelöscht.");
      await refresh();
    } catch (error) {
      toast(error.message, true);
    }
  }

  if (target.matches("[data-return]")) {
    if (!confirm("Gegenstand als zurückgegeben markieren?")) return;
    try {
      await apiSend(`/api/rentals/${target.dataset.return}/return`, "POST");
      toast("Rückgabe verbucht.");
      await refresh();
    } catch (error) {
      toast(error.message, true);
    }
  }

  if (target.matches("[data-details]")) {
    const rental = state.rentals.find((r) => String(r.id) === target.dataset.details);
    openRentalDetails(rental);
  }

  if (target.matches("#rental-filter button")) {
    document.querySelectorAll("#rental-filter button").forEach((b) => b.classList.remove("active"));
    target.classList.add("active");
    state.rentalFilter = target.dataset.status;
    await refresh();
  }

  if (target.matches("#item-filter button")) {
    document.querySelectorAll("#item-filter button").forEach((b) => b.classList.remove("active"));
    target.classList.add("active");
    state.itemFilter = target.dataset.type;
    renderItems();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});

/* ------------------------------------------------------------------- Start */
(async function init() {
  try {
    await loadMeta();
    await refresh();
    switchView("dashboard");
  } catch (error) {
    toast(`Startfehler: ${error.message}`, true);
  }
})();
