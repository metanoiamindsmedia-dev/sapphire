// features/scout-status.js — Scout pill bar above chat input
import * as eventBus from '../core/event-bus.js';
import { fetchWithTimeout } from '../shared/fetch.js';

let bar = null;
let pollTimer = null;
let initialized = false;
let scouts = new Map(); // id -> {name, status, mission, chat_name}
let pendingScoutReport = null; // queued report if Sapphire is mid-stream
let pendingScoutChat = null;   // which chat the report belongs to

const STATUS_COLORS = {
    running: '#f0ad4e',
    pending: '#f0ad4e',
    done: '#5cb85c',
    failed: '#d9534f',
    cancelled: '#888',
};

function getActiveChat() {
    const sel = document.getElementById('chat-select');
    return sel?.value || '';
}

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
    const chat = getActiveChat();

    // Filter to current chat's scouts
    const visible = new Map();
    for (const [id, scout] of scouts) {
        if (scout.chat_name === chat) visible.set(id, scout);
    }

    if (visible.size === 0) {
        bar.style.display = 'none';
        // Keep polling if any scouts are running globally (might switch back)
        const anyRunning = [...scouts.values()].some(s => s.status === 'running');
        if (!anyRunning) stopPolling();
        return;
    }
    bar.style.display = 'flex';
    startPolling();

    // Build pills
    const existing = new Set();
    for (const [id, scout] of visible) {
        existing.add(id);
        let pill = bar.querySelector(`[data-scout-id="${id}"]`);
        if (!pill) {
            pill = document.createElement('span');
            pill.className = 'scout-pill';
            pill.dataset.scoutId = id;
            pill.dataset.status = scout.status;
            pill.innerHTML = `<span class="scout-name">${esc(scout.name)}</span><span class="scout-x" title="Dismiss">\u00d7</span>`;
            pill.title = `${scout.name}: ${scout.mission || ''}`;

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
        const chat = getActiveChat();
        const data = await fetchWithTimeout(`/api/scouts/status?chat=${encodeURIComponent(chat)}`, {}, 5000);
        if (!data?.scouts) return;

        // Sync state — only replace scouts for current chat
        const remoteIds = new Set();
        for (const s of data.scouts) {
            remoteIds.add(s.id);
            scouts.set(s.id, s);
        }
        // Remove scouts that server no longer has (for this chat)
        for (const [id, scout] of scouts) {
            if (scout.chat_name === chat && !remoteIds.has(id)) scouts.delete(id);
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

async function drainScoutReport() {
    if (!pendingScoutReport) return;
    try {
        // Verify we're still on the correct chat
        const activeChat = getActiveChat();
        if (pendingScoutChat && pendingScoutChat !== activeChat) {
            console.log('[Scouts] Wrong chat — report is for', pendingScoutChat, 'but active is', activeChat, '— holding');
            return; // keep queued, CHAT_SWITCHED will retry
        }
        const { getIsProc } = await import('../core/state.js');
        if (getIsProc()) {
            console.log('[Scouts] Still processing, will retry on ai_typing_end');
            return; // keep pendingScoutReport, ai_typing_end will retry
        }
        const report = pendingScoutReport;
        pendingScoutReport = null;
        pendingScoutChat = null;
        console.log('[Scouts] Sending auto-return report to chat');
        const { triggerSendWithText } = await import('../handlers/send-handlers.js');
        await triggerSendWithText(report);
    } catch (err) {
        console.error('[Scouts] Auto-return failed:', err);
        pendingScoutReport = null;
        pendingScoutChat = null;
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
            chat_name: data.chat_name || '',
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

    // Scout batch auto-return — send report as a message when all scouts finish
    eventBus.on('scout_batch_complete', (data) => {
        console.log('[Scouts] Batch complete event received:', data.chat_name, 'scouts:', data.scout_count);
        pendingScoutReport = data.report;
        pendingScoutChat = data.chat_name;
        setTimeout(() => drainScoutReport(), 1500);
    });

    // Drain on ai_typing_end (catches the case where Sapphire was mid-stream)
    eventBus.on('ai_typing_end', () => {
        if (!pendingScoutReport) return;
        console.log('[Scouts] ai_typing_end — draining queued report');
        setTimeout(() => drainScoutReport(), 800);
    });

    // Drain when user switches to the chat the report belongs to
    eventBus.on(eventBus.Events.CHAT_SWITCHED, () => {
        renderPills();
        if (!pendingScoutReport) return;
        console.log('[Scouts] Chat switched — checking if report can drain');
        setTimeout(() => drainScoutReport(), 500);
    });

    // Initial poll on load
    poll();
}
