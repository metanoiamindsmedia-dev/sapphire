// settings-tabs/dashboard.js - Dashboard with system controls, update checker, and token metrics
import * as ui from '../../ui.js';

let updateStatus = null;

export default {
    id: 'dashboard',
    name: 'Dashboard',
    icon: '\uD83C\uDFE0',
    description: 'System status, updates, and controls',

    render(ctx) {
        return `
            <div class="dashboard-grid">
                <div class="dash-card">
                    <h4>System</h4>
                    <div class="dash-version" id="dash-version">v${window.__appVersion || '?'}</div>
                    <div class="dash-controls">
                        <button class="btn-primary btn-sm" id="dash-restart">Restart</button>
                        <button class="btn-sm danger" id="dash-shutdown">Shutdown</button>
                    </div>
                </div>
                <div class="dash-card">
                    <h4>Updates</h4>
                    <div class="dash-update-status" id="dash-update-status">
                        <span class="text-muted">Checking...</span>
                    </div>
                    <div class="dash-update-actions" id="dash-update-actions"></div>
                </div>
                <div class="dash-card dash-card-wide">
                    <h4>Token Usage <span class="text-muted" style="font-size:var(--font-xs);font-weight:normal">(30 days)</span></h4>
                    <div id="dash-metrics-summary" class="dash-metrics">
                        <span class="text-muted">Loading...</span>
                    </div>
                </div>
                <div class="dash-card dash-card-wide">
                    <h4>Usage by Model</h4>
                    <div id="dash-metrics-breakdown" class="dash-metrics">
                        <span class="text-muted">Loading...</span>
                    </div>
                </div>
            </div>
        `;
    },

    attachListeners(ctx, el) {
        // Restart
        el.querySelector('#dash-restart')?.addEventListener('click', async () => {
            if (!confirm('Restart Sapphire?')) return;
            try {
                await fetch('/api/system/restart', { method: 'POST' });
                ui.showToast('Restarting...', 'success');
                setTimeout(() => pollForRestart(), 2000);
            } catch { ui.showToast('Restart failed', 'error'); }
        });

        // Shutdown
        el.querySelector('#dash-shutdown')?.addEventListener('click', async () => {
            if (!confirm('Shut down Sapphire? You will need to restart it manually.')) return;
            try {
                await fetch('/api/system/shutdown', { method: 'POST' });
                ui.showToast('Shutting down...', 'success');
            } catch { ui.showToast('Shutdown failed', 'error'); }
        });

        // Check for updates
        checkForUpdate(el);

        // Load metrics
        loadMetrics(el);
    }
};


// =============================================================================
// UPDATE CHECKER
// =============================================================================

async function checkForUpdate(el) {
    const statusEl = el.querySelector('#dash-update-status');
    const actionsEl = el.querySelector('#dash-update-actions');
    if (!statusEl || !actionsEl) return;

    try {
        const res = await fetch('/api/system/update-check');
        if (!res.ok) throw new Error('Check failed');
        updateStatus = await res.json();

        if (updateStatus.available) {
            statusEl.innerHTML = `
                <span class="dash-update-badge">v${updateStatus.latest} available</span>
                <span class="text-muted" style="font-size:var(--font-xs)">Current: v${updateStatus.current}</span>
            `;

            if (updateStatus.docker || updateStatus.managed) {
                actionsEl.innerHTML = `<p class="text-muted" style="font-size:var(--font-xs);margin:0">Update via: <code>docker compose pull && docker compose up -d</code></p>`;
            } else if (updateStatus.has_git) {
                actionsEl.innerHTML = `<button class="btn-primary btn-sm" id="dash-do-update">Update Now</button>`;
                actionsEl.querySelector('#dash-do-update')?.addEventListener('click', () => doUpdate(el));
            } else {
                actionsEl.innerHTML = `<p class="text-muted" style="font-size:var(--font-xs);margin:0">Download the latest release from <a href="https://github.com/ddxfish/sapphire/releases" target="_blank">GitHub</a></p>`;
            }

            window.dispatchEvent(new CustomEvent('update-available', { detail: updateStatus }));
        } else {
            statusEl.innerHTML = `<span class="text-muted">\u2713 Up to date (v${updateStatus.current})</span>`;
            actionsEl.innerHTML = `<button class="btn-sm" id="dash-recheck" style="margin-top:6px">Check Again</button>`;
            actionsEl.querySelector('#dash-recheck')?.addEventListener('click', () => {
                statusEl.innerHTML = '<span class="text-muted">Checking...</span>';
                actionsEl.innerHTML = '';
                checkForUpdate(el);
            });
        }
    } catch (e) {
        statusEl.innerHTML = `<span class="text-muted">Could not check for updates</span>`;
    }
}

async function doUpdate(el) {
    const actionsEl = el.querySelector('#dash-update-actions');
    if (!actionsEl) return;

    const btn = actionsEl.querySelector('#dash-do-update');
    if (btn) { btn.disabled = true; btn.textContent = 'Updating...'; }

    try {
        const res = await fetch('/api/system/update', { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Update failed');
        }
        const result = await res.json();
        ui.showToast('Updated! Restarting...', 'success');

        const statusEl = el.querySelector('#dash-update-status');
        if (statusEl) statusEl.innerHTML = '<span class="text-muted">Restarting with new version...</span>';
        actionsEl.innerHTML = '';

        setTimeout(() => pollForRestart(), 2000);
    } catch (e) {
        ui.showToast(e.message, 'error');
        if (btn) { btn.disabled = false; btn.textContent = 'Update Now'; }
    }
}

function pollForRestart() {
    let attempts = 0;
    const poll = async () => {
        attempts++;
        try {
            const res = await fetch('/api/health');
            if (res.ok) { window.location.reload(); return; }
        } catch {}
        if (attempts < 30) setTimeout(poll, 1000);
    };
    poll();
}


// =============================================================================
// TOKEN METRICS
// =============================================================================

const fmt = n => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
};

async function loadMetrics(el) {
    const summaryEl = el.querySelector('#dash-metrics-summary');
    const breakdownEl = el.querySelector('#dash-metrics-breakdown');

    try {
        const [sumRes, brkRes] = await Promise.all([
            fetch('/api/metrics/summary?days=30'),
            fetch('/api/metrics/breakdown?days=30')
        ]);

        if (!sumRes.ok || !brkRes.ok) throw new Error('Metrics fetch failed');

        const summary = await sumRes.json();
        const breakdown = await brkRes.json();

        renderSummary(summaryEl, summary);
        renderBreakdown(breakdownEl, breakdown.models || []);
    } catch (e) {
        if (summaryEl) summaryEl.innerHTML = '<span class="text-muted">No metrics data yet</span>';
        if (breakdownEl) breakdownEl.innerHTML = '<span class="text-muted">Send some messages to start collecting metrics</span>';
    }
}

function renderSummary(el, s) {
    if (!el || !s.total_calls) {
        if (el) el.innerHTML = '<span class="text-muted">No data yet — metrics start recording from this version</span>';
        return;
    }

    const cacheRate = s.total_prompt > 0 && s.total_cache_read > 0
        ? Math.round((s.total_cache_read / s.total_prompt) * 100) : null;

    el.innerHTML = `
        <div class="metrics-grid">
            <div class="metric-item">
                <div class="metric-value">${fmt(s.total_calls)}</div>
                <div class="metric-label">LLM Calls</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${fmt(s.total_tokens)}</div>
                <div class="metric-label">Total Tokens</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${fmt(s.total_prompt)}</div>
                <div class="metric-label">Input</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">${fmt(s.total_completion)}</div>
                <div class="metric-label">Output</div>
            </div>
            ${s.total_thinking > 0 ? `
            <div class="metric-item">
                <div class="metric-value">${fmt(s.total_thinking)}</div>
                <div class="metric-label">Thinking</div>
            </div>` : ''}
            ${cacheRate !== null ? `
            <div class="metric-item">
                <div class="metric-value">${cacheRate}%</div>
                <div class="metric-label">Cache Hit</div>
            </div>` : ''}
        </div>
    `;
}

function renderBreakdown(el, models) {
    if (!el || !models.length) {
        if (el) el.innerHTML = '<span class="text-muted">No model data yet</span>';
        return;
    }

    const rows = models.slice(0, 8).map(m => {
        const cacheInfo = m.cache_read > 0
            ? `<span class="text-muted" style="font-size:var(--font-xs)">cache ${Math.round((m.cache_read / (m.prompt || 1)) * 100)}%</span>`
            : '';
        return `
            <tr>
                <td>${m.model}</td>
                <td class="text-right">${fmt(m.calls)}</td>
                <td class="text-right">${fmt(m.total)}</td>
                <td class="text-right">${m.duration > 0 ? `${m.duration.toFixed(0)}s` : '-'}</td>
                <td class="text-right">${cacheInfo}</td>
            </tr>
        `;
    }).join('');

    el.innerHTML = `
        <table class="metrics-table">
            <thead>
                <tr>
                    <th>Model</th>
                    <th class="text-right">Calls</th>
                    <th class="text-right">Tokens</th>
                    <th class="text-right">Time</th>
                    <th class="text-right">Cache</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}
