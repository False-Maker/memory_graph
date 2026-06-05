import { createSettingsSmokeScenarioRegistry } from './settings-playwright-scenarios.mjs'
import {
  registerT12AnthropicSaveFixtures,
  registerT12ConnectionFailureFixtures,
  registerT12DefaultConfigSaveFixtures,
  registerT12OllamaSaveFixtures,
  registerT12SecretStorageUnavailableFixtures,
  registerT12SaveHappyPathFixtures,
} from './t12-settings-playwright-fixtures.mjs'
import {
  assertT12PutCount,
  assertT12StateCountAtLeast,
  buildT12PageScenario,
  buildT12ProviderSaveScenario,
  buildT12StorageSaveScenario,
  createT12ScenarioStepSequence,
} from './t12-settings-playwright-helpers.mjs'
import { SETTINGS_SMOKE_TEST_IDS } from '../pages/SettingsPage.smoke-helpers.js'

const T12_ANTHROPIC_INITIAL_FIELDS = Object.freeze([
  {
    selector: '#settings-llm-provider',
    expected: 'anthropic',
    message: (actual) => `Expected initial provider to be anthropic, got ${actual}`,
  },
  {
    selector: '#settings-anthropic-base-url',
    expected: 'https://api.anthropic.com',
    message: (actual) => `Expected Anthropic base URL input to show backend default, got ${actual}`,
  },
  {
    selector: '#settings-anthropic-model',
    expected: 'claude-sonnet-4-20250514',
    message: (actual) => `Expected Anthropic model input to show backend default, got ${actual}`,
  },
])

const T12_OLLAMA_INITIAL_FIELDS = Object.freeze([
  {
    selector: '#settings-llm-provider',
    expected: 'ollama',
    message: (actual) => `Expected initial provider to be ollama, got ${actual}`,
  },
  {
    selector: '#settings-ollama-url',
    expected: 'http://localhost:11434',
    message: (actual) => `Expected Ollama URL input to show backend value, got ${actual}`,
  },
  {
    selector: '#settings-ollama-model',
    expected: 'qwen2.5:14b',
    message: (actual) => `Expected Ollama model input to show backend value, got ${actual}`,
  },
])

const T12_CORRUPTED_STORAGE_INITIAL_FIELDS = Object.freeze([
  {
    selector: '#settings-visual-layout',
    expected: 'force',
    message: (actual) => `Expected corrupted storage to fall back to default layout, got ${actual}`,
  },
])

const T12_INVALID_VISUALIZATION_INITIAL_FIELDS = Object.freeze([
  {
    selector: '#settings-visual-layout',
    expected: 'force',
    message: (actual) => `Expected invalid layout to fall back to force, got ${actual}`,
  },
  {
    selector: '#settings-visual-node-size',
    expected: '8',
    message: (actual) => `Expected invalid node size to fall back to 8, got ${actual}`,
  },
  {
    selector: '#settings-visual-show-labels',
    kind: 'checked',
    expected: true,
    message: (actual) => `Expected invalid showLabels to fall back to true, got ${actual}`,
  },
])

const T12_CORRUPTED_STORAGE_EXPECTATIONS = Object.freeze({
  defaultLayout: {
    expected: 'clustered',
    message: (actual) => `Expected repaired localStorage layout to be clustered, got ${actual}`,
  },
})

const T12_INVALID_VISUALIZATION_EXPECTATIONS = Object.freeze({
  defaultLayout: {
    expected: 'force',
    message: (actual) => `Expected sanitized layout to be force, got ${actual}`,
  },
  nodeSize: {
    expected: 8,
    message: (actual) => `Expected sanitized node size to be 8, got ${actual}`,
  },
  showLabels: {
    expected: true,
    message: (actual) => `Expected sanitized showLabels to be true, got ${actual}`,
  },
})

const T12_SAVE_HAPPY_PATH_STEPS = createT12ScenarioStepSequence([
  {
    id: 'wait_for_diagnostics_blocks',
    actions: [
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.diagnosticsSection}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.diagnosticsSummary}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.taskChainBlock}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.recentFailuresBlock}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=核心运行依赖未通过诊断', options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=mock provider timeout', options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=workspace-main', options: { timeout: 30000 } },
    ],
  },
  {
    id: 'refresh_diagnostics',
    actions: [
      { type: 'click', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.diagnosticsRefreshButton}"]` },
    ],
    assert: ({ state }) => {
      assertT12StateCountAtLeast(
        state,
        'diagnosticsCalls',
        2,
        `Expected at least two diagnostics loads, got ${state.diagnosticsCalls}`
      )
    },
  },
  {
    id: 'edit_form_before_save',
    actions: [
      { type: 'fill', selector: '#settings-openai-base-url', value: 'https://open.bigmodel.cn/api/coding/paas/v4' },
      { type: 'fill', selector: '#settings-openai-model', value: 'glm-4.7' },
      { type: 'selectOption', selector: '#settings-visual-layout', value: 'hierarchical' },
      { type: 'fill', selector: '#settings-visual-node-size', value: '14' },
      { type: 'uncheck', selector: '#settings-visual-show-labels' },
    ],
  },
  {
    id: 'save_configuration',
    actions: [
      { type: 'click', selector: '.settings-save-btn' },
      { type: 'waitForSelector', selector: 'text=配置已保存，但运行诊断仍未通过', options: { timeout: 30000 } },
    ],
  },
  {
    id: 'override_unsaved_values_for_test_connection',
    actions: [
      { type: 'fill', selector: '#settings-openai-base-url', value: 'https://mock-override.example/v1' },
      { type: 'fill', selector: '#settings-openai-model', value: 'glm-4.7-preview' },
    ],
  },
  {
    id: 'run_connection_test_and_assert_status',
    actions: [
      { type: 'click', selector: '.settings-test-btn' },
      { type: 'waitForSelector', selector: 'text=连接测试成功！', options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=degraded', options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=disabled', options: { timeout: 30000 } },
    ],
    assert: ({ state }) => {
      assertT12PutCount(state, `Expected at least one PUT /config call, got ${state.putCount}`)
      assertT12StateCountAtLeast(
        state,
        'testConnectionCount',
        1,
        `Expected at least one POST /config/test-connection call, got ${state.testConnectionCount}`
      )
    },
  },
])

const T12_CONNECTION_FAILURE_PATH_STEPS = createT12ScenarioStepSequence([
  {
    id: 'trigger_connection_test',
    actions: [
      { type: 'click', selector: '.settings-test-btn' },
    ],
  },
  {
    id: 'assert_failure_status',
    actions: [
      { type: 'waitForSelector', selector: 'text=mock connection failure', options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: '.settings-status--failed', options: { timeout: 30000 } },
    ],
  },
])

const T12_SECRET_STORAGE_UNAVAILABLE_STEPS = createT12ScenarioStepSequence([
  {
    id: 'assert_unavailable_secret_storage_banner',
    actions: [
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.secretStorageStatus}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=设置页不能保存新的 API Key', options: { timeout: 30000 } },
    ],
  },
  {
    id: 'attempt_blocked_secret_save',
    actions: [
      { type: 'fill', selector: 'input[type="password"]', value: 'sk-blocked' },
      { type: 'click', selector: '.settings-save-btn' },
      { type: 'waitForSelector', selector: `[data-testid="${SETTINGS_SMOKE_TEST_IDS.globalErrorAlert}"]`, options: { timeout: 30000 } },
      { type: 'waitForSelector', selector: 'text=请清空 API Key 输入框后仅保存其他字段', options: { timeout: 30000 } },
    ],
    assert: ({ state }) => {
      if (state.putCount !== 0) {
        throw new Error(`Expected blocked secret save to avoid PUT /config, got ${state.putCount}`)
      }
    },
  },
  {
    id: 'save_non_secret_fields_after_clearing_secret',
    actions: [
      { type: 'fill', selector: 'input[type="password"]', value: '' },
      { type: 'fill', selector: '#settings-openai-base-url', value: 'https://open.bigmodel.cn/api/coding/paas/v4' },
      { type: 'fill', selector: '#settings-openai-model', value: 'glm-4.7' },
      { type: 'click', selector: '.settings-save-btn' },
      { type: 'waitForSelector', selector: 'text=配置已保存，运行诊断已刷新', options: { timeout: 30000 } },
    ],
    assert: ({ state }) => {
      if (state.putCount !== 1) {
        throw new Error(`Expected one non-secret PUT /config after clearing API key, got ${state.putCount}`)
      }
    },
  },
])

export const T12_SCENARIOS = createSettingsSmokeScenarioRegistry([
  buildT12PageScenario({
    id: 'save_happy_path',
    artifact: 'task-12-settings-save.png',
    createState: () => ({
      putCount: 0,
      testConnectionCount: 0,
      diagnosticsCalls: 0,
    }),
    setupPage: async ({ page, state }) => {
      await registerT12SaveHappyPathFixtures(page, state)
    },
    steps: T12_SAVE_HAPPY_PATH_STEPS,
  }),
  buildT12PageScenario({
    id: 'connection_failure_path',
    artifact: 'task-12-settings-conn-fail.png',
    setupPage: async ({ page }) => {
      await registerT12ConnectionFailureFixtures(page)
    },
    steps: T12_CONNECTION_FAILURE_PATH_STEPS,
  }),
  buildT12PageScenario({
    id: 'secret_storage_unavailable_path',
    artifact: 'task-12-settings-secret-storage-unavailable.png',
    createState: () => ({ putCount: 0 }),
    setupPage: async ({ page, state }) => {
      await registerT12SecretStorageUnavailableFixtures(page, state)
    },
    steps: T12_SECRET_STORAGE_UNAVAILABLE_STEPS,
  }),
  buildT12ProviderSaveScenario({
    id: 'anthropic_save_path',
    artifact: 'task-12-settings-anthropic-save.png',
    registerFixtures: registerT12AnthropicSaveFixtures,
    initialFieldValues: T12_ANTHROPIC_INITIAL_FIELDS,
    changeActions: [
      { type: 'fill', selector: '#settings-anthropic-model', value: '   ' },
    ],
    putCountMessage: (actual) => `Expected PUT /config for Anthropic save, got ${actual}`,
  }),
  buildT12ProviderSaveScenario({
    id: 'ollama_save_path',
    artifact: 'task-12-settings-ollama-save.png',
    registerFixtures: registerT12OllamaSaveFixtures,
    initialFieldValues: T12_OLLAMA_INITIAL_FIELDS,
    changeActions: [
      { type: 'fill', selector: '#settings-ollama-url', value: '  http://127.0.0.1:11434  ' },
      { type: 'fill', selector: '#settings-ollama-model', value: '  qwen2.5:32b  ' },
    ],
    putCountMessage: (actual) => `Expected PUT /config for Ollama save, got ${actual}`,
  }),
  buildT12StorageSaveScenario({
    id: 'corrupted_visualization_storage_path',
    artifact: 'task-12-settings-corrupt-storage.png',
    storageStateRaw: '{broken-json',
    registerFixtures: registerT12DefaultConfigSaveFixtures,
    initialFieldValues: T12_CORRUPTED_STORAGE_INITIAL_FIELDS,
    changeActions: [
      { type: 'selectOption', selector: '#settings-visual-layout', value: 'clustered' },
    ],
    storedGraphExpectations: T12_CORRUPTED_STORAGE_EXPECTATIONS,
    putCountMessage: (actual) => `Expected PUT /config to succeed after corrupted storage recovery, got ${actual}`,
  }),
  buildT12StorageSaveScenario({
    id: 'invalid_visualization_values_path',
    artifact: 'task-12-settings-invalid-storage.png',
    storageStateRaw: JSON.stringify({
      graph: {
        defaultLayout: 'unknown-layout',
        nodeSize: 'not-a-number',
        showLabels: 'yes'
      }
    }),
    registerFixtures: registerT12DefaultConfigSaveFixtures,
    initialFieldValues: T12_INVALID_VISUALIZATION_INITIAL_FIELDS,
    storedGraphExpectations: T12_INVALID_VISUALIZATION_EXPECTATIONS,
    putCountMessage: (actual) => `Expected PUT /config to succeed after invalid value recovery, got ${actual}`,
  }),
])
