// settings-tabs/dashboard.js - Dashboard with system controls and update checker
import * as ui from '../../ui.js';

let updateStatus = null;

export default {
    id: 'dashboard',
    name: 'Dashboard',
    icon: '\uD83C\uDFE0',
    description: 'System status, updates, and controls',

    render(ctx) {
        const isDocker = ctx.settings?.SAPPHIRE_DOCKER || ctx.docker;
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
    }
};


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

            // Signal nav badge
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
