// index.js - Tool Maker settings plugin
// Settings tab in Plugins modal for Tool Maker configuration

import { registerPluginSettings } from '/static/core-ui/plugins-modal/plugin-registry.js';
import pluginsAPI from '/static/core-ui/plugins-modal/plugins-api.js';
import { showDangerConfirm } from '/static/shared/danger-confirm.js';

function csrfHeaders(extra = {}) {
  const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
  return { 'X-CSRF-Token': token, ...extra };
}

function injectStyles() {
  if (document.getElementById('toolmaker-plugin-styles')) return;

  const style = document.createElement('style');
  style.id = 'toolmaker-plugin-styles';
  style.textContent = `
    .tm-form {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .tm-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .tm-group label {
      font-size: 13px;
      font-weight: 500;
      color: var(--text);
    }

    .tm-group select {
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg-primary);
      color: var(--text);
      font-size: 13px;
    }

    .tm-group select:focus {
      outline: none;
      border-color: var(--accent-blue);
    }

    .tm-hint {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }

    .tm-section {
      border-top: 1px solid var(--border);
      padding-top: 16px;
      margin-top: 8px;
    }

    .tm-section-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 12px;
    }

    .tm-tool-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .tm-tool-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--bg-secondary);
      font-size: 13px;
      color: var(--text);
    }

    .tm-tool-name {
      font-weight: 600;
      font-family: monospace;
      font-size: 12px;
    }

    .tm-tool-funcs {
      font-size: 11px;
      color: var(--text-muted);
      flex: 1;
    }

    .tm-empty {
      color: var(--text-muted);
      font-size: 13px;
      padding: 8px;
    }
  `;
  document.head.appendChild(style);
}


let _settings = {};

async function loadCustomTools() {
  try {
    const res = await fetch('/api/webui/plugins/toolmaker/tools');
    if (res.ok) return (await res.json()).tools || [];
  } catch (e) {
    console.warn('Failed to load custom tools:', e);
  }
  return [];
}


function renderForm(container, settings) {
  _settings = settings || {};
  const validation = _settings.validation || 'moderate';

  container.innerHTML = `
    <div class="tm-form">
      <div class="tm-group">
        <label for="tm-validation">Validation Level</label>
        <select id="tm-validation">
          <option value="strict" ${validation === 'strict' ? 'selected' : ''}>Strict — allowlisted imports only</option>
          <option value="moderate" ${validation === 'moderate' ? 'selected' : ''}>Moderate — blocks dangerous ops</option>
          <option value="trust" ${validation === 'trust' ? 'selected' : ''}>Trust — syntax check only</option>
        </select>
        <div class="tm-hint">
          How strictly to validate AI-written tool code before installation.<br>
          <strong>Strict:</strong> Only whitelisted imports (json, re, datetime, math, requests, os, pathlib).<br>
          <strong>Moderate:</strong> Blocks subprocess, socket, ctypes, eval, exec, and dangerous os calls.<br>
          <strong>Trust:</strong> Syntax check only — no import or call restrictions.
        </div>
      </div>

      <div class="tm-section">
        <div class="tm-section-title">Installed Custom Tools</div>
        <div class="tm-tool-list" id="tm-tool-list">
          <div class="tm-empty">Loading...</div>
        </div>
      </div>
    </div>
  `;

  // Trust mode gate — every time
  container.querySelector('#tm-validation').addEventListener('change', async (e) => {
    if (e.target.value === 'trust') {
      const confirmed = await showDangerConfirm({
        title: 'Trust Mode — No Validation',
        warnings: [
          'Trust mode only checks for syntax errors',
          'The AI can use ANY Python import including subprocess, socket, ctypes',
          'This is equivalent to giving the AI unrestricted code execution',
          'Only use this if you fully trust your LLM and prompt setup',
        ],
        buttonLabel: 'Enable Trust Mode',
      });
      if (!confirmed) {
        e.target.value = _settings.validation || 'moderate';
        return;
      }
    }
    autoSave(container);
  });

  // Load custom tools list
  loadCustomTools().then(tools => {
    const listEl = container.querySelector('#tm-tool-list');
    if (!listEl) return;

    if (!tools.length) {
      listEl.innerHTML = '<div class="tm-empty">No custom tools installed. The AI can create tools when Tool Maker is enabled in a toolset.</div>';
      return;
    }

    listEl.innerHTML = tools.map(t => `
      <div class="tm-tool-item">
        <span class="tm-tool-name">${esc(t.module)}</span>
        <span class="tm-tool-funcs">${(t.functions || []).join(', ')}</span>
      </div>
    `).join('');
  });
}


function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}


function getFormSettings(container) {
  const validation = container.querySelector('#tm-validation')?.value || 'moderate';
  return { validation };
}


function autoSave(container) {
  const settings = getFormSettings(container);
  pluginsAPI.saveSettings('toolmaker', settings).catch(e =>
    console.error('Toolmaker auto-save failed:', e)
  );
}


export default {
  name: 'toolmaker',

  init(container) {
    injectStyles();

    registerPluginSettings({
      id: 'toolmaker',
      name: 'Tool Maker',
      icon: '\uD83D\uDEE0\uFE0F',
      helpText: 'Tool Maker lets the AI write, validate, and install Python tools at runtime. Custom tools run inside the Sapphire process. Review installed tools in user/functions/ periodically.',
      render: renderForm,
      load: () => pluginsAPI.getSettings('toolmaker'),
      save: (settings) => pluginsAPI.saveSettings('toolmaker', settings),
      getSettings: getFormSettings
    });

    console.log('\u2714 Tool Maker settings registered');
  },

  destroy() {}
};
