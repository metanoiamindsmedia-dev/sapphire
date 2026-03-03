// settings-tabs/embedding.js - Embedding provider settings
import { renderProviderTab, attachProviderListeners } from '../../shared/provider-selector.js';

const tabConfig = {
    providerKey: 'EMBEDDING_PROVIDER',
    disabledMessage: 'Embeddings disabled. Memory and knowledge search will use text matching only.',

    providers: {
        none: {
            label: 'Disabled',
            essentialKeys: [],
            advancedKeys: []
        },
        local: {
            label: 'Local (Nomic ONNX)',
            essentialKeys: [],
            advancedKeys: []
        },
        api: {
            label: 'Remote (Nomic API)',
            essentialKeys: ['EMBEDDING_API_URL'],
            advancedKeys: ['EMBEDDING_API_KEY']
        }
    },

    commonKeys: [],
    commonAdvancedKeys: []
};

export default {
    id: 'embedding',
    name: 'Embedding',
    icon: '\uD83E\uDDF2',
    description: 'Vector embedding engine for memory and knowledge search',

    render(ctx) {
        return renderProviderTab(tabConfig, ctx);
    },

    attachListeners(ctx, el) {
        attachProviderListeners(tabConfig, ctx, el);
    }
};
