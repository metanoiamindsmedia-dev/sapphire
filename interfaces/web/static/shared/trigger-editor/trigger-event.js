// trigger-editor/trigger-event.js - Event trigger section (daemons + webhooks)
// Response routing is implicit: daemons always reply to source, webhooks always reply via HTTP.
// Chat history + TTS are configured in the existing Chat/Voice accordions (from ai-config).

// Cache sources data so filter hints update on source change
let _sourcesCache = [];

/**
 * Render the event trigger section HTML
 * @param {Object} t - Existing task data (or {})
 * @param {Object} opts - { type: 'daemon' | 'webhook' }
 * @returns {string} HTML string
 */
export function renderEventTrigger(t, opts = {}) {
    const { type } = opts;
    const triggerConfig = t.trigger_config || {};

    if (type === 'webhook') {
        const path = triggerConfig.path || '';
        const method = triggerConfig.method || 'POST';
        return `
            <div class="sched-section-title" style="margin-top:16px">\uD83D\uDD17 Webhook</div>
            <div class="sched-field">
                <label>Path <span class="help-tip" data-tip="The URL path to listen on. Will be available at /api/events/webhook/{path}">?</span></label>
                <div style="display:flex;align-items:center;gap:4px">
                    <span class="text-muted" style="font-size:var(--font-xs)">/api/events/webhook/</span>
                    <input type="text" id="ed-webhook-path" value="${_esc(path)}" placeholder="my-hook" style="flex:1">
                </div>
            </div>
            <div class="sched-field">
                <label>Method</label>
                <select id="ed-webhook-method">
                    <option value="POST" ${method === 'POST' ? 'selected' : ''}>POST</option>
                    <option value="GET" ${method === 'GET' ? 'selected' : ''}>GET</option>
                    <option value="PUT" ${method === 'PUT' ? 'selected' : ''}>PUT</option>
                </select>
            </div>`;
    }

    // Daemon type — event source from plugins
    const eventSource = triggerConfig.source || '';
    const eventFilter = triggerConfig.filter ? JSON.stringify(triggerConfig.filter) : '';
    return `
        <div class="sched-field" style="margin-top:16px">
            <label>Daemon Source <span class="help-tip" data-tip="The event type to listen for. Available sources come from loaded daemon plugins.">?</span></label>
            <select id="ed-event-source" data-current-value="${_esc(eventSource)}">
                <option value="">Select event source...</option>
                <option value="_loading" disabled>Loading plugin events...</option>
            </select>
        </div>
        <details class="sched-accordion" style="margin-top:8px">
            <summary class="sched-acc-header">Filter <span class="sched-preview" id="ed-filter-preview">${eventFilter ? 'active' : ''}</span></summary>
            <div class="sched-acc-body"><div class="sched-acc-inner">
                <div id="ed-filter-hints" class="text-muted" style="font-size:var(--font-xs);margin-bottom:8px">
                    Select a daemon source to see available filter keys.
                </div>
                <div class="sched-field">
                    <label>Filter JSON <span class="help-tip" data-tip="Only events matching these fields will trigger this task. Leave empty to receive all events from this source.">?</span></label>
                    <input type="text" id="ed-event-filter" value="${_esc(eventFilter)}" placeholder='{"channel": "general"}'>
                </div>
            </div></div>
        </details>`;
}

/**
 * Wire event trigger event listeners
 * @param {HTMLElement} modal - The editor modal element
 * @param {Object} opts - { type: 'daemon' | 'webhook' }
 */
export function wireEventTrigger(modal, opts = {}) {
    const { type } = opts;

    if (type === 'daemon') {
        _loadEventSources(modal);

        // Update filter hints when source changes
        modal.querySelector('#ed-event-source')?.addEventListener('change', () => {
            _updateFilterHints(modal);
        });

        // Update filter preview chip
        modal.querySelector('#ed-event-filter')?.addEventListener('input', () => {
            const preview = modal.querySelector('#ed-filter-preview');
            const val = modal.querySelector('#ed-event-filter')?.value?.trim();
            if (preview) preview.textContent = val ? 'active' : '';
        });
    }
}

/**
 * Read event trigger values from the modal
 * @param {HTMLElement} modal - The editor modal element
 * @returns {Object} Event trigger fields for the task data
 */
export function readEventTrigger(modal) {
    const webhookPath = modal.querySelector('#ed-webhook-path');

    if (webhookPath) {
        return {
            trigger_config: {
                path: webhookPath.value.trim(),
                method: modal.querySelector('#ed-webhook-method')?.value || 'POST',
            },
            schedule: '0 0 31 2 *', // never fires via cron (Feb 31)
            chance: 100,
            active_hours_start: null,
            active_hours_end: null,
        };
    }

    // Daemon type
    const filterStr = modal.querySelector('#ed-event-filter')?.value?.trim();
    let filter = null;
    if (filterStr) {
        try { filter = JSON.parse(filterStr); }
        catch { alert('Invalid JSON in filter field'); return null; }
    }

    return {
        trigger_config: {
            source: modal.querySelector('#ed-event-source')?.value || '',
            filter,
        },
        schedule: '0 0 31 2 *', // never fires via cron
        chance: 100,
        active_hours_start: null,
        active_hours_end: null,
    };
}

// ── Private helpers ──

async function _loadEventSources(modal) {
    const select = modal.querySelector('#ed-event-source');
    if (!select) return;

    try {
        const res = await fetch('/api/events/sources');
        if (!res.ok) throw new Error('Failed to fetch event sources');
        const data = await res.json();
        _sourcesCache = data.sources || [];

        select.innerHTML = '<option value="">Select event source...</option>';

        if (_sourcesCache.length === 0) {
            select.innerHTML += '<option value="" disabled>No daemon plugins loaded</option>';
            return;
        }

        // Group by plugin
        const grouped = {};
        for (const s of _sourcesCache) {
            const group = s.plugin || 'core';
            if (!grouped[group]) grouped[group] = [];
            grouped[group].push(s);
        }

        for (const [plugin, events] of Object.entries(grouped)) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = plugin;
            for (const ev of events) {
                const opt = document.createElement('option');
                opt.value = ev.name;
                opt.textContent = ev.label || ev.name;
                optgroup.appendChild(opt);
            }
            select.appendChild(optgroup);
        }

        const current = select.dataset.currentValue;
        if (current) select.value = current;

        // Show hints for pre-selected source
        _updateFilterHints(modal);
    } catch {
        select.innerHTML = '<option value="">Select event source...</option><option value="" disabled>Could not load sources</option>';
    }
}

function _updateFilterHints(modal) {
    const hintsEl = modal.querySelector('#ed-filter-hints');
    if (!hintsEl) return;

    const sourceName = modal.querySelector('#ed-event-source')?.value;
    if (!sourceName) {
        hintsEl.textContent = 'Select a daemon source to see available filter keys.';
        return;
    }

    const source = _sourcesCache.find(s => s.name === sourceName);
    const fields = source?.filter_fields;

    if (!fields || fields.length === 0) {
        hintsEl.textContent = 'This source does not declare filter keys. Check the plugin docs for available fields.';
        return;
    }

    hintsEl.innerHTML = `<strong>Available keys:</strong> ${fields.map(f =>
        `<code>${f.key}</code>${f.label && f.label !== f.key ? ` (${f.label})` : ''}`
    ).join(', ')}`;
}

function _esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
