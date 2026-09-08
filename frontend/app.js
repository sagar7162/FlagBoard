const API_BASE = window.FLAGBOARD_API_BASE || "http://localhost:8000";
const state = { token: localStorage.getItem("flagboard_token"), email: localStorage.getItem("flagboard_email") || "", organizations: [], projects: [], flags: [], audits: [], selectedOrg: null, selectedProject: null, selectedFlag: null, socket: null };

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const shortId = (value) => value ? `${value.slice(0, 8)}…` : "—";
const formatTime = (value) => value ? new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value)) : "—";

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}), ...(options.headers || {}) } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.status === 204 ? null : response.json();
}

function showDashboard() { $("#login-view").classList.add("is-hidden"); $("#dashboard-view").classList.remove("is-hidden"); $("#user-email").textContent = state.email; $("#sidebar-email").textContent = state.email; }
function showLogin() { $("#dashboard-view").classList.add("is-hidden"); $("#login-view").classList.remove("is-hidden"); }
function toast(message) { const element = $("#toast"); element.textContent = message; element.classList.add("show"); window.clearTimeout(toast.timeout); toast.timeout = window.setTimeout(() => element.classList.remove("show"), 2800); }
function setConnection(connected, label = connected ? "Live connection" : "Not connected") { $("#connection-dot").style.background = connected ? "var(--green)" : "#a6afaa"; $("#connection-label").textContent = label; }

async function login(event) {
  event.preventDefault(); const error = $("#login-error"); error.textContent = "";
  try { const data = await api("/auth/login", { method: "POST", body: JSON.stringify({ email: $("#email").value, password: $("#password").value }) }); state.token = data.access_token; state.email = $("#email").value; localStorage.setItem("flagboard_token", state.token); localStorage.setItem("flagboard_email", state.email); showDashboard(); await loadOrganizations(); }
  catch (err) { error.textContent = err.message; }
}

async function loadOrganizations() {
  state.organizations = await api("/orgs"); $("#org-list").innerHTML = state.organizations.map((org) => `<button class="org-button ${state.selectedOrg?.id === org.id ? "active" : ""}" data-org="${org.id}">${escapeHtml(org.name)}</button>`).join("");
  document.querySelectorAll("[data-org]").forEach((button) => button.addEventListener("click", () => selectOrganization(button.dataset.org)));
  if (state.organizations.length) await selectOrganization(state.selectedOrg?.id || state.organizations[0].id); else { $("#org-name").textContent = "No organizations"; $("#project-list").innerHTML = ""; renderEmpty("Create an organization to start managing flags."); }
}

async function selectOrganization(id) {
  state.selectedOrg = state.organizations.find((org) => org.id === id); $("#org-name").textContent = state.selectedOrg?.name || "Workspace"; document.querySelectorAll("[data-org]").forEach((button) => button.classList.toggle("active", button.dataset.org === id));
  state.projects = await api(`/orgs/${id}/projects`); $("#project-list").innerHTML = state.projects.map((project) => `<button class="project-button ${state.selectedProject?.id === project.id ? "active" : ""}" data-project="${project.id}">${escapeHtml(project.name)}</button>`).join(""); document.querySelectorAll("[data-project]").forEach((button) => button.addEventListener("click", () => selectProject(button.dataset.project)));
  if (state.projects.length) await selectProject(state.selectedProject?.organization_id === id ? state.selectedProject.id : state.projects[0].id); else { $("#project-context").textContent = "No projects in this organization."; renderEmpty("Create a project to start managing flags."); }
  connectSocket(id);
}

async function selectProject(id) { state.selectedProject = state.projects.find((project) => project.id === id); document.querySelectorAll("[data-project]").forEach((button) => button.classList.toggle("active", button.dataset.project === id)); $("#project-context").textContent = state.selectedProject ? `${state.selectedProject.key} · ${state.selectedProject.name}` : ""; await loadFlags(); }

async function loadFlags() { state.flags = await api(`/projects/${state.selectedProject.id}/flags`); renderFlags(); if (state.flags[0]) await selectFlag(state.selectedFlag?.id && state.flags.some((flag) => flag.id === state.selectedFlag.id) ? state.selectedFlag.id : state.flags[0].id); else renderAudit([]); }
function currentEnvironment(flag) { return flag.environments.find((item) => item.environment === $("#environment").value) || flag.environments[0]; }
function renderFlags() { $("#flag-count").textContent = `${state.flags.length} ${state.flags.length === 1 ? "flag" : "flags"}`; $("#flag-list").innerHTML = state.flags.length ? state.flags.map((flag) => { const config = currentEnvironment(flag); return `<div class="flag-row"><div class="flag-main"><strong>${escapeHtml(flag.name)}</strong><span class="flag-key">${escapeHtml(flag.key)}</span></div><div class="flag-status ${config?.enabled ? "on" : "off"}"><span class="status-dot"></span>${config?.enabled ? "Enabled" : "Disabled"}</div><div class="rollout">${config?.rollout_percentage == null ? "100% rollout" : `${config.rollout_percentage}% rollout`}</div><button class="switch" type="button" role="switch" aria-checked="${Boolean(config?.enabled)}" aria-label="Toggle ${escapeHtml(flag.name)}" data-flag="${flag.id}"></button></div>`; }).join("") : `<div class="empty-state">No flags in this project.</div>`; document.querySelectorAll("[data-flag]").forEach((button) => button.addEventListener("click", () => toggleFlag(button.dataset.flag, button))); }

async function toggleFlag(id, button) { const flag = state.flags.find((item) => item.id === id); const config = currentEnvironment(flag); button.disabled = true; try { const updated = await api(`/flags/${id}/environments/${$("#environment").value}/toggle`, { method: "PATCH", body: JSON.stringify({ enabled: !config.enabled }) }); const index = state.flags.findIndex((item) => item.id === id); state.flags[index] = updated; renderFlags(); await selectFlag(id); toast(`${flag.name} ${!config.enabled ? "enabled" : "disabled"}`); } catch (err) { toast(err.message); button.disabled = false; } }

async function selectFlag(id) { state.selectedFlag = state.flags.find((flag) => flag.id === id); if (!state.selectedFlag) return; try { state.audits = await api(`/flags/${id}/audit-log`); renderAudit(state.audits); } catch (err) { renderAudit([]); toast(err.message); } }
function renderAudit(audits) { $("#audit-list").innerHTML = audits.length ? audits.slice(0, 12).map((entry) => `<tr><td>${escapeHtml(entry.action.replaceAll("_", " "))}</td><td class="mono">${escapeHtml(state.selectedFlag?.key || shortId(entry.flag_id))}</td><td class="mono">${shortId(entry.actor_user_id)}</td><td class="mono">${formatTime(entry.created_at)}</td><td class="mono">${escapeHtml(summary(entry))}</td></tr>`).join("") : `<tr><td colspan="5" class="table-empty">No audit entries for this flag yet.</td></tr>`; }
function summary(entry) { const before = entry.before?.enabled; const after = entry.after?.enabled; if (typeof after === "boolean" && before !== after) return `${before ? "on" : "off"} → ${after ? "on" : "off"}`; return entry.after?.environment ? `${entry.after.environment}` : "Configuration updated"; }

function connectSocket(orgId) { if (state.socket) state.socket.close(); const protocol = API_BASE.startsWith("https") ? "wss" : "ws"; const host = API_BASE.replace(/^https?:\/\//, ""); state.socket = new WebSocket(`${protocol}://${host}/ws/orgs/${orgId}?token=${encodeURIComponent(state.token)}`); state.socket.addEventListener("open", () => setConnection(true)); state.socket.addEventListener("close", () => setConnection(false)); state.socket.addEventListener("error", () => setConnection(false, "Connection unavailable")); state.socket.addEventListener("message", async () => { await loadFlags(); toast("Flag updated live"); }); }
function renderEmpty(message) { $("#flag-count").textContent = "—"; $("#flag-list").innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`; renderAudit([]); }

$("#login-form").addEventListener("submit", login);
$("#logout-button").addEventListener("click", () => { if (state.socket) state.socket.close(); localStorage.removeItem("flagboard_token"); localStorage.removeItem("flagboard_email"); state.token = null; showLogin(); });
$("#environment").addEventListener("change", () => { renderFlags(); if (state.selectedFlag) selectFlag(state.selectedFlag.id); });

if (state.token) { showDashboard(); loadOrganizations().catch(() => { localStorage.removeItem("flagboard_token"); localStorage.removeItem("flagboard_email"); state.token = null; showLogin(); }); }
