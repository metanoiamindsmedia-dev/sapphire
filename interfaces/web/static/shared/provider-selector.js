/**
 * Reusable provider selector for service tabs (STT, TTS, Embeddings).
 *
 * Each service tab declares:
 *   providerKey   – setting key (e.g. 'STT_PROVIDER')
 *   providers     – { value: { label, essentialKeys, advancedKeys } }
 *   commonKeys    – fields shown for every non-disabled provider
 *   commonAdvancedKeys – advanced fields for every non-disabled provider
 *   disabledMessage – text when provider is 'none'
 */

export function renderProviderTab(tabConfig, ctx) {
    const current = _currentProvider(tabConfig, ctx);
    const providerDef = tabConfig.providers[current] || tabConfig.providers.none;

    let html = _renderDropdown(tabConfig, current, ctx);

    if (current === 'none') {
        html += `<p class="setting-help" style="padding:12px 0;opacity:0.7">
            ${tabConfig.disabledMessage || 'Disabled. Select a provider above to enable.'}
        </p>`;
        return html;
    }

    // Provider-specific essential fields
    if (providerDef.essentialKeys?.length) {
        html += ctx.renderFields(providerDef.essentialKeys);
    }

    // Common fields (shared across all active providers)
    if (tabConfig.commonKeys?.length) {
        html += ctx.renderFields(tabConfig.commonKeys);
    }

    // Advanced: provider-specific + common
    const advKeys = [
        ...(providerDef.advancedKeys || []),
        ...(tabConfig.commonAdvancedKeys || [])
    ];
    if (advKeys.length) {
        html += ctx.renderAccordion(`${tabConfig.providerKey}-adv`, advKeys);
    }

    return html;
}

export function attachProviderListeners(tabConfig, ctx, el, tabModule) {
    const dropdown = el.querySelector(`#setting-${tabConfig.providerKey}`);
    if (!dropdown) return;

    dropdown.addEventListener('change', () => {
        ctx.markChanged(tabConfig.providerKey, dropdown.value);
        // Re-render to show/hide provider-specific fields
        // pendingChanges persists across re-renders
        const content = el.closest('.settings-main')?.querySelector('#settings-content');
        if (content) {
            const body = content.querySelector('.settings-tab-body');
            if (body) {
                // Use tab's full render if available (preserves test buttons etc.)
                body.innerHTML = tabModule?.render ? tabModule.render(ctx) : renderProviderTab(tabConfig, ctx);
                // Re-attach all listeners (provider dropdown + tab-specific like test buttons)
                if (tabModule?.attachListeners) {
                    tabModule.attachListeners(ctx, content);
                } else {
                    attachProviderListeners(tabConfig, ctx, content);
                }
                // Re-attach generic listeners (accordion, input tracking, etc.)
                if (ctx.attachAccordionListeners) ctx.attachAccordionListeners(content);
            }
        }
    });
}

// ── Internal ──

function _currentProvider(tabConfig, ctx) {
    // Pending change takes priority over saved setting
    if (tabConfig.providerKey in ctx.pendingChanges) {
        return ctx.pendingChanges[tabConfig.providerKey];
    }
    return ctx.settings[tabConfig.providerKey] || 'none';
}

function _renderDropdown(tabConfig, current, ctx) {
    const key = tabConfig.providerKey;
    const h = ctx.help[key];
    const isOverridden = ctx.overrides.includes(key);

    const options = Object.entries(tabConfig.providers)
        .map(([value, def]) =>
            `<option value="${value}" ${value === current ? 'selected' : ''}>${def.label}</option>`
        ).join('');

    return `
        <div class="settings-grid">
            <div class="setting-row full-width${isOverridden ? ' overridden' : ''}" data-key="${key}">
                <div class="setting-label">
                    <div class="setting-label-row">
                        <label>${ctx.formatLabel(key)}</label>
                        ${h ? `<span class="help-icon" data-help-key="${key}" title="Details">?</span>` : ''}
                        ${isOverridden ? '<span class="override-badge">Custom</span>' : ''}
                    </div>
                    ${h?.short ? `<div class="setting-help">${h.short}</div>` : ''}
                </div>
                <div class="setting-input">
                    <select id="setting-${key}" data-key="${key}">${options}</select>
                </div>
                <div class="setting-actions">
                    ${isOverridden ? `<button class="btn-icon reset-btn" data-reset-key="${key}" title="Reset to default">\u21BA</button>` : ''}
                </div>
            </div>
        </div>
    `;
}
