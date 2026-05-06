/* ═══════════════════════════════════════════════
   ModdyDashboard — main.js
   ═══════════════════════════════════════════════ */

// ── Toast system ────────────────────────────────
const Toast = {
  container: null,
  init() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },
  show(message, type = 'info', duration = 3500) {
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><span>${message}</span>`;
    this.container.appendChild(t);
    setTimeout(() => {
      t.style.opacity = '0';
      t.style.transform = 'translateX(100%)';
      setTimeout(() => t.remove(), 300);
    }, duration);
  },
  success(m) { this.show(m, 'success'); },
  error(m)   { this.show(m, 'error'); },
  info(m)    { this.show(m, 'info'); },
};

// ── API helper ───────────────────────────────────
const API = {
  async request(method, url, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.message || 'Error desconocido');
    return data;
  },
  get(url)          { return this.request('GET',    url); },
  post(url, body)   { return this.request('POST',   url, body); },
  put(url, body)    { return this.request('PUT',    url, body); },
  delete(url)       { return this.request('DELETE', url); },
};

// ── Modal system ─────────────────────────────────
const Modal = {
  open(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.add('open'); document.body.style.overflow = 'hidden'; }
  },
  close(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('open'); document.body.style.overflow = ''; }
  },
  closeAll() {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
    });
    document.body.style.overflow = '';
  },
};

// ── Toggle switch ────────────────────────────────
function initToggles() {
  document.querySelectorAll('.toggle input').forEach(input => {
    input.addEventListener('change', () => {
      const key = input.dataset.key;
      if (!key) return;
      // Debounce auto-save
      clearTimeout(input._debounce);
      input._debounce = setTimeout(() => autoSaveField(key, input.checked), 600);
    });
  });
}

// ── Auto-save individual field ────────────────────
async function autoSaveField(key, value) {
  const guildId = document.body.dataset.guildId;
  if (!guildId) return;
  try {
    await API.post(`/api/${guildId}/settings/general`, { [key]: value });
    Toast.success('Guardado automáticamente');
  } catch (e) {
    Toast.error(e.message);
  }
}

// ── Tabs ─────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tabs').forEach(tabGroup => {
    tabGroup.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(c => {
          c.style.display = c.id === target ? '' : 'none';
        });
      });
    });
  });
}

// ── Chips (multi-select roles) ────────────────────
function initChips() {
  document.querySelectorAll('[data-chips]').forEach(wrapper => {
    const input    = wrapper.querySelector('input[type="hidden"]');
    const display  = wrapper.querySelector('.chips-container');
    const select   = wrapper.querySelector('select.chips-select');
    if (!display || !select) return;

    const getValue = () => input ? input.value.split(',').filter(Boolean) : [];
    const setValue = (arr) => { if (input) input.value = arr.join(','); };

    function renderChips(arr) {
      display.querySelectorAll('.chip').forEach(c => c.remove());
      arr.forEach(id => {
        const opt  = select.querySelector(`option[value="${id}"]`);
        const label = opt ? opt.text : id;
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.innerHTML = `${label}<span class="chip-remove" data-id="${id}">×</span>`;
        chip.querySelector('.chip-remove').addEventListener('click', e => {
          e.stopPropagation();
          const current = getValue().filter(v => v !== id);
          setValue(current);
          renderChips(current);
        });
        display.appendChild(chip);
      });
    }

    select.addEventListener('change', () => {
      const id = select.value;
      if (!id) return;
      const current = getValue();
      if (!current.includes(id)) {
        current.push(id);
        setValue(current);
        renderChips(current);
      }
      select.value = '';
    });

    renderChips(getValue());
  });
}

// ── Color picker sync ─────────────────────────────
function initColorPickers() {
  document.querySelectorAll('.color-row').forEach(row => {
    const picker = row.querySelector('input[type="color"]');
    const text   = row.querySelector('input[type="text"]');
    const swatch = row.querySelector('.color-swatch');
    if (!picker || !text) return;

    const sync = (hex) => {
      if (swatch) swatch.style.background = '#' + hex.replace('#', '');
      if (picker) picker.value = '#' + hex.replace('#', '');
      if (text)   text.value  = hex.replace('#', '');
      // Update panel preview if present
      updatePanelPreview();
    };

    picker.addEventListener('input', () => sync(picker.value));
    text.addEventListener('input',   () => {
      if (/^[0-9a-fA-F]{6}$/.test(text.value)) sync('#' + text.value);
    });
    sync(text.value || 'ffffff');
  });
}

// ── Panel live preview ────────────────────────────
function updatePanelPreview() {
  const preview = document.getElementById('panel-preview');
  if (!preview) return;

  const title  = document.getElementById('panel-title')?.value || 'Panel de Tickets';
  const desc   = document.getElementById('panel-desc')?.value  || 'Selecciona una categoría.';
  const color  = document.getElementById('panel-color-text')?.value || '5865F2';
  const tipo   = document.getElementById('panel-tipo')?.value  || 'buttons';

  preview.querySelector('.panel-preview-embed').style.borderLeftColor = '#' + color;
  preview.querySelector('.panel-preview-title').textContent = title;
  preview.querySelector('.panel-preview-desc').textContent  = desc;

  const btnsContainer = preview.querySelector('.panel-preview-btns');
  if (btnsContainer) {
    const activeCats = document.querySelectorAll('[data-cat-item]');
    btnsContainer.innerHTML = '';
    if (tipo === 'select' || activeCats.length === 0) {
      btnsContainer.innerHTML = tipo === 'select'
        ? '<div style="background:#2f3136;color:#dcddde;padding:8px 12px;border-radius:4px;font-size:14px;border:1px solid #4f545c;width:100%">📋 Selecciona una categoría...</div>'
        : '<span style="color:#72767d;font-size:12px">Sin categorías aún</span>';
    } else {
      activeCats.forEach(cat => {
        const lbl   = cat.querySelector('[data-label]')?.textContent || 'Botón';
        const emoji = cat.querySelector('[data-emoji]')?.textContent || '';
        const color = cat.dataset.color || 'blurple';
        const btn = document.createElement('button');
        btn.className = `preview-btn ${color}`;
        btn.textContent = (emoji ? emoji + ' ' : '') + lbl;
        btnsContainer.appendChild(btn);
      });
    }
  }
}

// ── Search/filter table ───────────────────────────
function initTableSearch() {
  document.querySelectorAll('[data-search]').forEach(input => {
    const target = input.dataset.search;
    const table  = document.querySelector(target);
    if (!table) return;
    input.addEventListener('input', () => {
      const q = input.value.toLowerCase();
      table.querySelectorAll('tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  });
}

// ── Confirm delete dialogs ────────────────────────
function confirmDelete(message, callback) {
  if (window.confirm(message)) callback();
}

// ── Close modal on overlay click ─────────────────
function initModalClose() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) Modal.closeAll();
    });
  });
  document.querySelectorAll('[data-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => Modal.closeAll());
  });
}

// ── Sidebar mobile toggle ─────────────────────────
function initMobileSidebar() {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  }
}

// ── Init all ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
  initToggles();
  initTabs();
  initChips();
  initColorPickers();
  initTableSearch();
  initModalClose();
  initMobileSidebar();

  // Live preview listeners
  ['panel-title','panel-desc','panel-tipo'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', updatePanelPreview);
  });

  // Global keyboard: Escape closes modals
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') Modal.closeAll();
  });
});
