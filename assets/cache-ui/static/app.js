(() => {
  const POLL_MS = 5000;

  const els = {
    healthBadge: document.getElementById("health-badge"),
    metaHost: document.getElementById("meta-host"),
    metaVersion: document.getElementById("meta-version"),
    metaDbsize: document.getElementById("meta-dbsize"),
    metaError: document.getElementById("meta-error"),
    sessionList: document.getElementById("session-list"),
    patternSelect: document.getElementById("pattern-select"),
    keyTbody: document.getElementById("key-tbody"),
    keyTable: document.getElementById("key-table"),
    keyCount: document.getElementById("key-count"),
    emptyState: document.getElementById("empty-state"),
    detailKey: document.getElementById("detail-key"),
    detailBody: document.getElementById("detail-body"),
    autoPoll: document.getElementById("auto-poll"),
    btnRefresh: document.getElementById("btn-refresh"),
    toast: document.getElementById("toast"),
  };

  const state = {
    selectedSessionId: null, // null = all keys for pattern
    selectedKey: null,
    pollTimer: null,
    sessions: [],
    keys: [],
  };

  function toast(msg, kind = "ok") {
    els.toast.textContent = msg;
    els.toast.className = `toast ${kind}`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      els.toast.classList.add("hidden");
    }, 3200);
  }

  async function api(path, options) {
    const res = await fetch(path, {
      headers: { Accept: "application/json" },
      ...options,
    });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const detail = data.detail || res.statusText || "Request failed";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function formatTtl(ttl) {
    if (ttl === -1) return "∞";
    if (ttl === -2) return "—";
    if (ttl < 60) return `${ttl}s`;
    if (ttl < 3600) return `${Math.floor(ttl / 60)}m`;
    return `${Math.floor(ttl / 3600)}h`;
  }

  async function loadHealth() {
    try {
      const h = await api("/api/health");
      if (h.ok) {
        els.healthBadge.textContent = "PONG";
        els.healthBadge.className = "badge badge-ok";
        els.metaError.classList.add("hidden");
      } else {
        els.healthBadge.textContent = "DOWN";
        els.healthBadge.className = "badge badge-bad";
        els.metaError.textContent = h.error || "Redis unreachable";
        els.metaError.classList.remove("hidden");
      }
      els.metaHost.textContent = h.redis_url_host || "—";
      els.metaVersion.textContent = h.redis_version
        ? `redis ${h.redis_version}`
        : "—";
      els.metaDbsize.textContent =
        typeof h.dbsize === "number" ? `dbsize ${h.dbsize}` : "—";
    } catch (err) {
      els.healthBadge.textContent = "ERROR";
      els.healthBadge.className = "badge badge-bad";
      els.metaError.textContent = err.message;
      els.metaError.classList.remove("hidden");
    }
  }

  function renderSessions() {
    const frag = document.createDocumentFragment();

    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className =
      "session-card" + (state.selectedSessionId === null ? " selected" : "");
    allBtn.innerHTML = `<div class="sid">All keys (pattern)</div>
      <div class="tags"><span class="tag dim">${els.patternSelect.value}</span></div>`;
    allBtn.addEventListener("click", () => {
      state.selectedSessionId = null;
      state.selectedKey = null;
      renderSessions();
      loadKeys();
    });
    frag.appendChild(allBtn);

    for (const s of state.sessions) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "session-card" +
        (state.selectedSessionId === s.session_id ? " selected" : "");
      const tags = [];
      if (s.has_context) tags.push('<span class="tag">context</span>');
      if (s.has_state) tags.push('<span class="tag">state</span>');
      if (s.has_decisions) tags.push('<span class="tag">decisions</span>');
      for (const g of s.gates || []) {
        tags.push(`<span class="tag">gate ${g}</span>`);
      }
      tags.push(`<span class="tag dim">${s.key_count} keys</span>`);
      btn.innerHTML = `<div class="sid">${escapeHtml(s.session_id)}</div>
        <div class="tags">${tags.join("")}</div>`;
      btn.addEventListener("click", () => {
        state.selectedSessionId = s.session_id;
        state.selectedKey = null;
        renderSessions();
        renderKeysFromSession(s);
      });
      frag.appendChild(btn);
    }

    els.sessionList.innerHTML = "";
    els.sessionList.appendChild(frag);
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderKeys(keys) {
    state.keys = keys;
    els.keyCount.textContent = `${keys.length} key(s)`;
    els.keyTbody.innerHTML = "";

    if (!keys.length) {
      els.emptyState.classList.remove("hidden");
      els.keyTable.classList.add("hidden");
      els.detailKey.textContent = "";
      els.detailBody.textContent = "Select a key to inspect.";
      return;
    }

    els.emptyState.classList.add("hidden");
    els.keyTable.classList.remove("hidden");

    for (const k of keys) {
      const tr = document.createElement("tr");
      if (state.selectedKey === k.key) tr.classList.add("selected");
      tr.innerHTML = `
        <td class="key-cell">${escapeHtml(k.key)}</td>
        <td>${escapeHtml(k.type)}</td>
        <td>${formatTtl(k.ttl)}</td>`;
      tr.addEventListener("click", () => selectKey(k.key));
      els.keyTbody.appendChild(tr);
    }

    if (state.selectedKey && !keys.some((k) => k.key === state.selectedKey)) {
      state.selectedKey = null;
      els.detailKey.textContent = "";
      els.detailBody.textContent = "Select a key to inspect.";
    }
  }

  function renderKeysFromSession(session) {
    renderKeys(session.keys || []);
  }

  async function loadSessions() {
    try {
      const data = await api("/api/sessions");
      state.sessions = data.sessions || [];
      renderSessions();
      if (state.selectedSessionId) {
        const s = state.sessions.find(
          (x) => x.session_id === state.selectedSessionId
        );
        if (s) {
          renderKeysFromSession(s);
          return;
        }
        state.selectedSessionId = null;
      }
      await loadKeys();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function loadKeys() {
    if (state.selectedSessionId) {
      const s = state.sessions.find(
        (x) => x.session_id === state.selectedSessionId
      );
      if (s) {
        renderKeysFromSession(s);
        return;
      }
    }
    const pattern = els.patternSelect.value;
    try {
      const data = await api(
        `/api/keys?pattern=${encodeURIComponent(pattern)}`
      );
      renderKeys(data.keys || []);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function selectKey(key) {
    state.selectedKey = key;
    for (const tr of els.keyTbody.querySelectorAll("tr")) {
      tr.classList.toggle(
        "selected",
        tr.querySelector(".key-cell")?.textContent === key
      );
    }
    els.detailKey.textContent = key;
    els.detailBody.textContent = "Loading…";
    try {
      const detail = await api(`/api/keys/${encodeURIComponent(key)}`);
      const pretty = JSON.stringify(
        {
          type: detail.type,
          ttl: detail.ttl,
          encoding: detail.encoding,
          value: detail.value,
          preview_base64: detail.preview_base64 || undefined,
        },
        null,
        2
      );
      els.detailBody.textContent = pretty;
    } catch (err) {
      els.detailBody.textContent = err.message;
    }
  }

  async function refreshAll() {
    await loadHealth();
    await loadSessions();
    if (state.selectedKey) {
      await selectKey(state.selectedKey);
    }
  }

  function setupPoll() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
    if (els.autoPoll.checked) {
      state.pollTimer = setInterval(refreshAll, POLL_MS);
    }
  }

  els.btnRefresh.addEventListener("click", () => refreshAll());
  els.autoPoll.addEventListener("change", setupPoll);
  els.patternSelect.addEventListener("change", () => {
    state.selectedSessionId = null;
    state.selectedKey = null;
    renderSessions();
    loadKeys();
  });

  refreshAll();
  setupPoll();
})();
