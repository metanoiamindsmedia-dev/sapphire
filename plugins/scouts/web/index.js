// plugins/scouts/web/index.js — Scout roster settings UI
import { registerPluginSettings } from '/static/shared/plugin-registry.js';
import { renderSettingsForm, readSettingsForm } from '/static/shared/plugin-settings-renderer.js';

const BASIC_SCHEMA = [
    { key: 'max_concurrent', type: 'number', label: 'Max Concurrent Scouts', default: 3, help: 'Maximum scouts running simultaneously (1-5)' },
    { key: 'default_toolset', type: 'string', label: 'Default Toolset', default: 'default', help: 'Toolset for scouts when not specified' },
];

let providers = []; // cached from API

function injectStyles() {
    if (document.getElementById('scout-settings-css')) return;
    const style = document.createElement('style');
    style.id = 'scout-settings-css';
    style.textContent = `
        .scout-settings { display: flex; flex-direction: column; gap: 20px; }
        .scout-section-title { font-size: 14px; font-weight: 600; color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 6px; margin-bottom: 4px; }
        .scout-roster { display: flex; flex-direction: column; gap: 8px; }
        .scout-roster-row { display: grid; grid-template-columns: 1fr 1fr 1fr 32px; gap: 8px; align-items: center; }
        .scout-roster-row.header { font-size: 12px; font-weight: 500; color: var(--text-muted); }
        .scout-roster-row input, .scout-roster-row select {
            padding: 6px 10px; font-size: 13px; border: 1px solid var(--border);
            border-radius: 6px; background: var(--bg-tertiary); color: var(--text);
        }
        .scout-roster-row input:focus, .scout-roster-row select:focus { border-color: var(--trim); outline: none; }
        .scout-del { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; }
        .scout-del:hover { color: #d9534f; background: rgba(217,83,79,0.1); }
        .scout-add-btn { align-self: flex-start; padding: 6px 14px; font-size: 13px; background: var(--bg-tertiary); color: var(--text-secondary);
            border: 1px dashed var(--border); border-radius: 6px; cursor: pointer; }
        .scout-add-btn:hover { border-color: var(--trim); color: var(--trim); }
        .scout-hint { font-size: 12px; color: var(--text-muted); line-height: 1.4; }
    `;
    document.head.appendChild(style);
}

function csrfHeaders(extra = {}) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
    return { 'X-CSRF-Token': token, ...extra };
}

async function loadProviders() {
    if (providers.length) return providers;
    try {
        const res = await fetch('/api/scouts/providers', { headers: csrfHeaders() });
        const data = await res.json();
        providers = data.providers || [];
    } catch (e) {
        console.warn('[Scouts] Failed to load providers:', e);
    }
    return providers;
}

function buildProviderSelect(selected) {
    let html = '<option value="">-- Provider --</option>';
    for (const p of providers) {
        const sel = p.key === selected ? ' selected' : '';
        html += `<option value="${p.key}"${sel}>${esc(p.name)}</option>`;
    }
    return html;
}

function buildModelSelect(providerKey, selectedModel) {
    const prov = providers.find(p => p.key === providerKey);
    if (!prov) return '<option value="">-- select provider first --</option>';

    let html = '';
    const models = prov.models || {};
    const keys = Object.keys(models);

    if (keys.length === 0) {
        // Free-form: show current model as only option + allow typing
        html += `<option value="${esc(prov.current_model)}">${esc(prov.current_model)} (current)</option>`;
    } else {
        // Add current model at top if not in the list
        if (prov.current_model && !models[prov.current_model]) {
            const sel = prov.current_model === selectedModel ? ' selected' : '';
            html += `<option value="${esc(prov.current_model)}"${sel}>${esc(prov.current_model)} (current)</option>`;
        }
        for (const [mid, label] of Object.entries(models)) {
            const sel = mid === selectedModel ? ' selected' : '';
            html += `<option value="${esc(mid)}"${sel}>${esc(label)}</option>`;
        }
    }
    return html;
}

function syncRosterFromDom(container, roster) {
    const rows = container.querySelectorAll('.scout-roster-row:not(.header)');
    rows.forEach((row, i) => {
        if (i < roster.length) {
            roster[i].name = row.querySelector('.scout-r-name')?.value?.trim() || '';
            roster[i].provider = row.querySelector('.scout-r-provider')?.value || '';
            roster[i].model = row.querySelector('.scout-r-model')?.value || '';
        }
    });
}

function renderRoster(container, roster) {
    const rosterDiv = container.querySelector('#scout-roster-list');
    rosterDiv.innerHTML = '';

    for (let i = 0; i < roster.length; i++) {
        const entry = roster[i];
        const row = document.createElement('div');
        row.className = 'scout-roster-row';
        row.dataset.idx = i;
        row.innerHTML = `
            <input type="text" class="scout-r-name" value="${esc(entry.name || '')}" placeholder="e.g. Big Brain">
            <select class="scout-r-provider">${buildProviderSelect(entry.provider)}</select>
            <select class="scout-r-model">${buildModelSelect(entry.provider, entry.model)}</select>
            <button class="scout-del" title="Remove">\u00d7</button>
        `;

        // Provider change → rebuild model dropdown
        row.querySelector('.scout-r-provider').addEventListener('change', (e) => {
            const modelSel = row.querySelector('.scout-r-model');
            modelSel.innerHTML = buildModelSelect(e.target.value, '');
        });

        // Delete — sync form state before re-render
        row.querySelector('.scout-del').addEventListener('click', () => {
            syncRosterFromDom(container, roster);
            roster.splice(i, 1);
            renderRoster(container, roster);
        });

        rosterDiv.appendChild(row);
    }
}

function readRoster(container) {
    const rows = container.querySelectorAll('.scout-roster-row:not(.header)');
    const roster = [];
    for (const row of rows) {
        const name = row.querySelector('.scout-r-name')?.value?.trim();
        const provider = row.querySelector('.scout-r-provider')?.value;
        const model = row.querySelector('.scout-r-model')?.value;
        if (name && provider) {
            roster.push({ name, provider, model: model || '' });
        }
    }
    return roster;
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export default {
    name: 'scouts',

    init() {
        injectStyles();

        let roster = []; // mutable reference for add/delete

        registerPluginSettings({
            id: 'scouts',
            name: 'Scouts',
            icon: '\ud83d\udd2d',
            helpText: 'Background AI workers with their own model and tools',

            render: async (container, settings) => {
                await loadProviders();
                roster = settings.roster || [];

                container.innerHTML = `
                    <div class="scout-settings">
                        <div>
                            <div class="scout-section-title">General</div>
                            <div id="scout-basic-settings"></div>
                        </div>
                        <div>
                            <div class="scout-section-title">Model Roster</div>
                            <p class="scout-hint">Define named models Sapphire can use for scouts. She sees the friendly name and knows which provider backs it. If empty, scouts use the current chat model.</p>
                            <div class="scout-roster">
                                <div class="scout-roster-row header">
                                    <span>Friendly Name</span><span>Provider</span><span>Model</span><span></span>
                                </div>
                                <div id="scout-roster-list"></div>
                            </div>
                            <button class="scout-add-btn" id="scout-add-entry">+ Add Model</button>
                        </div>
                    </div>
                `;

                // Render basic manifest settings
                renderSettingsForm(container.querySelector('#scout-basic-settings'), BASIC_SCHEMA, settings);

                // Render roster rows
                renderRoster(container, roster);

                // Add button — sync form state before re-render
                container.querySelector('#scout-add-entry').addEventListener('click', () => {
                    syncRosterFromDom(container, roster);
                    roster.push({ name: '', provider: '', model: '' });
                    renderRoster(container, roster);
                    // Focus the new name input
                    const rows = container.querySelectorAll('.scout-roster-row:not(.header)');
                    const last = rows[rows.length - 1];
                    if (last) last.querySelector('.scout-r-name')?.focus();
                });
            },

            load: async () => {
                try {
                    const res = await fetch('/api/webui/plugins/scouts/settings', { headers: csrfHeaders() });
                    const data = await res.json();
                    return data.settings || data || {};
                } catch { return {}; }
            },

            save: async (settings) => {
                return fetch('/api/webui/plugins/scouts/settings', {
                    method: 'PUT',
                    headers: csrfHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ settings }),
                });
            },

            getSettings: (container) => {
                const basic = readSettingsForm(container.querySelector('#scout-basic-settings'), BASIC_SCHEMA);
                const rosterData = readRoster(container);
                return { ...basic, roster: rosterData };
            },
        });
    },

    destroy() {},
};
