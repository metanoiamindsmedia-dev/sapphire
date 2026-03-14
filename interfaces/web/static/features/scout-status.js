// features/scout-status.js — Scout pill bar above chat input
import * as eventBus from '../core/event-bus.js';
import { fetchWithTimeout } from '../shared/fetch.js';

let bar = null;
let pollTimer = null;
let initialized = false;
let scouts = new Map(); // id -> {name, status, mission}

const STATUS_COLORS = {
    running: '#f0ad4e',
    pending: '#f0ad4e',
    done: '#5cb85c',
    failed: '#d9534f',
    cancelled: '#888',
};

function ensureBar() {
    if (bar) return bar;
    const form = document.getElementById('chat-form');
    if (!form) return null;

    bar = document.createElement('div');
    bar.id = 'scout-bar';
    form.parentNode.insertBefore(bar, form);
    return bar;
}

function renderPills() {
    if (!bar) return;
    if (scouts.size === 0) {
        bar.style.display = 'none';
        stopPolling();
        return;
    }
    bar.style.display = 'flex';
    startPolling();

    // Build pills
    const existing = new Set();
    for (const [id, scout] of scouts) {
        existing.add(id);
        let pill = bar.querySelector(`[data-scout-id="${id}"]`);
        if (!pill) {
            pill = document.createElement('span');
            pill.className = 'scout-pill';
            pill.dataset.scoutId = id;
            pill.dataset.status = scout.status;
            pill.innerHTML = `<span class="scout-name">${esc(scout.name)}</span><span class="scout-x" title="Dismiss">\u00d7</span>`;
            pill.title = `${scout.name}: ${scout.mission || ''}`;

            // Tooltip on click (mobile) — but not on the X
            pill.addEventListener('click', (e) => {
                if (e.target.classList.contains('scout-x')) return;
                // Toggle tooltip visibility via title (native) — no custom tooltip needed
            });

            // X button
            pill.querySelector('.scout-x').addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    await fetchWithTimeout(`/api/scouts/${id}/dismiss`, { method: 'POST' });
                } catch (err) {
                    console.warn('[Scouts] dismiss failed:', err);
                }
                scouts.delete(id);
                pill.remove();
                renderPills();
            });

            bar.appendChild(pill);
        }

        // Update status
        pill.dataset.status = scout.status;
        pill.style.borderColor = STATUS_COLORS[scout.status] || '#888';
        pill.title = `${scout.name}: ${scout.mission || ''}\nStatus: ${scout.status}`;
    }

    // Remove stale pills
    for (const pill of bar.querySelectorAll('.scout-pill')) {
        if (!existing.has(pill.dataset.scoutId)) {
            pill.remove();
        }
    }
}

async function poll() {
    try {
        const data = await fetchWithTimeout('/api/scouts/status', {}, 5000);
        if (!data?.scouts) return;

        // Sync state
        const remoteIds = new Set();
        for (const s of data.scouts) {
            remoteIds.add(s.id);
            scouts.set(s.id, s);
        }
        // Remove scouts no longer on server
        for (const id of scouts.keys()) {
            if (!remoteIds.has(id)) scouts.delete(id);
        }
        renderPills();
    } catch (err) {
        // Silent — don't spam errors for status polling
    }
}

function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(poll, 3000);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function esc(s) {
    return s.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function initScoutStatus() {
    if (initialized) return;
    initialized = true;

    ensureBar();

    // Listen for scout events via SSE
    eventBus.on('scout_spawned', (data) => {
        scouts.set(data.id, {
            id: data.id,
            name: data.name,
            status: 'running',
            mission: data.mission || '',
        });
        ensureBar();
        renderPills();
    });

    eventBus.on('scout_completed', (data) => {
        const scout = scouts.get(data.id);
        if (scout) {
            scout.status = data.status || 'done';
            renderPills();
        }
    });

    eventBus.on('scout_dismissed', (data) => {
        scouts.delete(data.id);
        renderPills();
    });

    // Initial poll on load
    poll();
}
