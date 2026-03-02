// settings-tabs/tts.js - Text-to-speech provider settings
import { renderProviderTab, attachProviderListeners } from '../../shared/provider-selector.js';

const tabConfig = {
    providerKey: 'TTS_PROVIDER',
    disabledMessage: 'Text-to-speech is disabled. Select a provider above to enable voice output.',

    providers: {
        none: {
            label: 'Disabled',
            essentialKeys: [],
            advancedKeys: []
        },
        kokoro: {
            label: 'Local (Kokoro)',
            essentialKeys: [],
            advancedKeys: [
                'TTS_SERVER_HOST', 'TTS_SERVER_PORT',
                'TTS_PRIMARY_SERVER', 'TTS_FALLBACK_SERVER', 'TTS_FALLBACK_TIMEOUT'
            ]
        },
        elevenlabs: {
            label: 'ElevenLabs (Cloud)',
            essentialKeys: ['TTS_ELEVENLABS_API_KEY', 'TTS_ELEVENLABS_MODEL', 'TTS_ELEVENLABS_VOICE_ID'],
            advancedKeys: []
        }
    },

    commonKeys: [],
    commonAdvancedKeys: []
};

export default {
    id: 'tts',
    name: 'TTS',
    icon: '\uD83D\uDD0A',
    description: 'Text-to-speech engine configuration',

    render(ctx) {
        return renderProviderTab(tabConfig, ctx);
    },

    attachListeners(ctx, el) {
        attachProviderListeners(tabConfig, ctx, el);
    }
};
