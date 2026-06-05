import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assertT12FieldValues,
  assertT12PutCount,
  assertT12StateCountAtLeast,
  assertT12StoredGraphSettings,
  buildT12PageScenario,
  buildT12ProviderSaveScenario,
  buildT12SaveScenario,
  buildT12StorageSaveScenario,
  createT12ScenarioStepSequence,
  readT12StoredGraphSettings,
  runT12PageActions,
  runT12ScenarioStepSequence,
  waitForT12SettingsReady,
  withT12ScenarioPage,
} from './t12-settings-playwright-helpers.mjs'

test('waitForT12SettingsReady waits for settings page chrome', async () => {
  const calls = []
  const page = {
    waitForURL: async (url, options) => {
      calls.push(`waitForURL:${url}:${options.timeout}`)
    },
    waitForSelector: async (selector, options) => {
      calls.push(`waitForSelector:${selector}:${options.state}:${options.timeout}`)
    },
  }

  await waitForT12SettingsReady(page)

  assert.deepEqual(calls, [
    'waitForURL:**/settings:30000',
    'waitForSelector:.settings-content:visible:30000',
    'waitForSelector:.settings-save-btn:visible:30000',
  ])
})

test('withT12ScenarioPage resets storage, waits for page, and closes page on success', async () => {
  const calls = []
  const page = {
    addInitScript: async (_script, arg) => {
      calls.push(`addInitScript:${typeof arg === 'string' ? arg : JSON.stringify(arg)}`)
    },
    goto: async (url, options) => {
      calls.push(`goto:${url}:${options.waitUntil}`)
    },
    waitForURL: async (url, options) => {
      calls.push(`waitForURL:${url}:${options.timeout}`)
    },
    waitForSelector: async (selector, options) => {
      calls.push(`waitForSelector:${selector}:${options.state}:${options.timeout}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {
      calls.push('context.clearCookies')
    },
    clearPermissions: async () => {
      calls.push('context.clearPermissions')
    },
    newPage: async () => {
      calls.push('context.newPage')
      return page
    },
  }

  const result = await withT12ScenarioPage(
    context,
    'http://127.0.0.1:4173',
    {},
    async (receivedPage) => {
      calls.push(`run:${receivedPage === page}`)
      return 'ok'
    }
  )

  assert.equal(result, 'ok')
  assert.deepEqual(calls, [
    'context.clearCookies',
    'context.clearPermissions',
    'context.newPage',
    'addInitScript:memory_graph_settings',
    'goto:http://127.0.0.1:4173/settings:networkidle',
    'waitForURL:**/settings:30000',
    'waitForSelector:.settings-content:visible:30000',
    'waitForSelector:.settings-save-btn:visible:30000',
    'run:true',
    'page.close',
  ])
})

test('withT12ScenarioPage seeds storage, runs setupPage before goto, and closes page on failure', async () => {
  const calls = []
  const page = {
    addInitScript: async (_script, arg) => {
      calls.push(`addInitScript:${JSON.stringify(arg)}`)
    },
    goto: async (url, options) => {
      calls.push(`goto:${url}:${options.waitUntil}`)
    },
    waitForURL: async () => {},
    waitForSelector: async () => {},
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {
      calls.push('context.clearCookies')
    },
    clearPermissions: async () => {
      calls.push('context.clearPermissions')
    },
    newPage: async () => {
      calls.push('context.newPage')
      return page
    },
  }

  await assert.rejects(
    () => withT12ScenarioPage(
      context,
      'http://127.0.0.1:4173',
      {
        storageStateRaw: '{"graph":{"defaultLayout":"force"}}',
        setupPage: async () => {
          calls.push('setupPage')
        },
      },
      async () => {
        throw new Error('boom')
      }
    ),
    /boom/
  )

  assert.deepEqual(calls, [
    'context.clearCookies',
    'context.clearPermissions',
    'context.newPage',
    'addInitScript:{"storageKey":"memory_graph_settings","raw":"{\\"graph\\":{\\"defaultLayout\\":\\"force\\"}}"}',
    'setupPage',
    'goto:http://127.0.0.1:4173/settings:networkidle',
    'page.close',
  ])
})

test('assertT12FieldValues validates input and checked fields', async () => {
  const page = {
    locator: (selector) => ({
      inputValue: async () => {
        if (selector === '#provider') return 'anthropic'
        if (selector === '#model') return 'claude-sonnet-4-20250514'
        throw new Error(`Unexpected input selector: ${selector}`)
      },
      isChecked: async () => {
        if (selector === '#show-labels') return true
        throw new Error(`Unexpected checked selector: ${selector}`)
      },
    }),
  }

  await assertT12FieldValues(page, [
    {
      selector: '#provider',
      expected: 'anthropic',
      message: (actual) => `Expected provider to be anthropic, got ${actual}`,
    },
    {
      selector: '#model',
      expected: 'claude-sonnet-4-20250514',
      message: (actual) => `Expected model to match backend default, got ${actual}`,
    },
    {
      selector: '#show-labels',
      kind: 'checked',
      expected: true,
      message: (actual) => `Expected showLabels to be true, got ${actual}`,
    },
  ])
})

test('assertT12FieldValues rejects mismatched field values', async () => {
  const page = {
    locator: () => ({
      inputValue: async () => 'openai',
      isChecked: async () => false,
    }),
  }

  await assert.rejects(
    () => assertT12FieldValues(page, [
      {
        selector: '#provider',
        expected: 'anthropic',
        message: (actual) => `Expected provider to be anthropic, got ${actual}`,
      },
    ]),
    /Expected provider to be anthropic, got openai/
  )
})

test('readT12StoredGraphSettings reads graph settings from localStorage', async () => {
  const page = {
    evaluate: async (handler) => {
      globalThis.window = {
        localStorage: {
          getItem: () => '{"graph":{"defaultLayout":"force","nodeSize":8,"showLabels":true}}',
        },
      }
      try {
        return handler()
      } finally {
        delete globalThis.window
      }
    },
  }

  const graph = await readT12StoredGraphSettings(page)
  assert.deepEqual(graph, {
    defaultLayout: 'force',
    nodeSize: 8,
    showLabels: true,
  })
})

test('assertT12StoredGraphSettings validates expected graph fields', () => {
  assert.doesNotThrow(() => {
    assertT12StoredGraphSettings(
      {
        defaultLayout: 'clustered',
        nodeSize: 8,
        showLabels: true,
      },
      {
        defaultLayout: {
          expected: 'clustered',
          message: (actual) => `Expected layout to be clustered, got ${actual}`,
        },
        nodeSize: {
          expected: 8,
          message: (actual) => `Expected node size to be 8, got ${actual}`,
        },
        showLabels: {
          expected: true,
          message: (actual) => `Expected showLabels to be true, got ${actual}`,
        },
      }
    )
  })

  assert.throws(
    () => assertT12StoredGraphSettings(
      { defaultLayout: 'force' },
      {
        defaultLayout: {
          expected: 'clustered',
          message: (actual) => `Expected layout to be clustered, got ${actual}`,
        },
      }
    ),
    /Expected layout to be clustered, got force/
  )
})

test('assertT12PutCount enforces at least one PUT call', () => {
  assert.doesNotThrow(() => {
    assertT12PutCount({ putCount: 1 }, 'Expected at least one PUT')
  })

  assert.throws(
    () => assertT12PutCount({ putCount: 0 }, 'Expected at least one PUT'),
    /Expected at least one PUT/
  )
})

test('assertT12StateCountAtLeast enforces minimum state counts', () => {
  assert.doesNotThrow(() => {
    assertT12StateCountAtLeast({ diagnosticsCalls: 2 }, 'diagnosticsCalls', 2, 'Expected diagnostics count')
  })

  assert.throws(
    () => assertT12StateCountAtLeast({ diagnosticsCalls: 1 }, 'diagnosticsCalls', 2, 'Expected diagnostics count'),
    /Expected diagnostics count/
  )
})

test('runT12PageActions executes supported page actions in order', async () => {
  const calls = []
  const page = {
    waitForSelector: async (selector, options) => {
      calls.push(`waitForSelector:${selector}:${JSON.stringify(options ?? {})}`)
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    locator: (selector) => ({
      fill: async (value) => {
        calls.push(`fill:${selector}:${value}`)
      },
    }),
    selectOption: async (selector, value) => {
      calls.push(`selectOption:${selector}:${value}`)
    },
    uncheck: async (selector) => {
      calls.push(`uncheck:${selector}`)
    },
  }

  await runT12PageActions(page, [
    { type: 'waitForSelector', selector: '.settings-content', options: { timeout: 30000 } },
    { type: 'click', selector: '.settings-save-btn' },
    { type: 'fill', selector: '#settings-openai-model', value: 'glm-4.7' },
    { type: 'selectOption', selector: '#settings-visual-layout', value: 'hierarchical' },
    { type: 'uncheck', selector: '#settings-visual-show-labels' },
  ])

  assert.deepEqual(calls, [
    'waitForSelector:.settings-content:{"timeout":30000}',
    'click:.settings-save-btn',
    'fill:#settings-openai-model:glm-4.7',
    'selectOption:#settings-visual-layout:hierarchical',
    'uncheck:#settings-visual-show-labels',
  ])
})

test('runT12PageActions rejects unsupported action types', async () => {
  await assert.rejects(
    () => runT12PageActions({}, [
      { type: 'hover', selector: '.settings-save-btn' },
    ]),
    /Unsupported T12 page action type: hover/
  )
})

test('buildT12SaveScenario executes declarative save flow with fresh state and screenshot', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async (selector) => {
      if (selector === 'text=配置已保存') {
        calls.push(`waitForSelector:${selector}`)
      }
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12SaveScenario({
    id: 'anthropic_save_path',
    artifact: 'task-12-settings-anthropic-save.png',
    createState: () => ({ putCount: 0 }),
    setupPage: async ({ state }) => {
      state.putCount += 1
      calls.push('setupPage')
    },
    assertInitialState: async ({ state }) => {
      calls.push(`assertInitialState:${state.putCount}`)
    },
    applyChanges: async ({ state }) => {
      state.putCount += 1
      calls.push(`applyChanges:${state.putCount}`)
    },
    assertAfterSave: async ({ state }) => {
      calls.push(`assertAfterSave:${state.putCount}`)
      assert.equal(state.putCount, 2)
    },
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.equal(scenario.artifact, 'task-12-settings-anthropic-save.png')
  assert.deepEqual(calls, [
    'setupPage',
    'assertInitialState:1',
    'applyChanges:2',
    'click:.settings-save-btn',
    'waitForSelector:text=配置已保存',
    'assertAfterSave:2',
    'screenshot:/tmp/evidence/task-12-settings-anthropic-save.png:true',
    'page.close',
  ])
})

test('buildT12SaveScenario supports field/action/stored-graph/put-count config', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async (selector) => {
      if (selector === 'text=配置已保存') {
        calls.push(`waitForSelector:${selector}`)
      }
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    locator: (selector) => ({
      inputValue: async () => {
        if (selector === '#provider') return 'anthropic'
        if (selector === '#model') return 'claude-sonnet-4-20250514'
        throw new Error(`Unexpected input selector: ${selector}`)
      },
      isChecked: async () => {
        if (selector === '#show-labels') return true
        throw new Error(`Unexpected checked selector: ${selector}`)
      },
      fill: async (value) => {
        calls.push(`fill:${selector}:${value}`)
      },
    }),
    selectOption: async (selector, value) => {
      calls.push(`selectOption:${selector}:${value}`)
    },
    uncheck: async (selector) => {
      calls.push(`uncheck:${selector}`)
    },
    evaluate: async () => ({
      defaultLayout: 'clustered',
      nodeSize: 8,
      showLabels: true,
    }),
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12SaveScenario({
    id: 'configured_save',
    artifact: 'configured-save.png',
    createState: () => ({ putCount: 1 }),
    initialFieldValues: [
      {
        selector: '#provider',
        expected: 'anthropic',
        message: (actual) => `Expected provider to be anthropic, got ${actual}`,
      },
      {
        selector: '#model',
        expected: 'claude-sonnet-4-20250514',
        message: (actual) => `Expected model to match backend default, got ${actual}`,
      },
      {
        selector: '#show-labels',
        kind: 'checked',
        expected: true,
        message: (actual) => `Expected showLabels to be true, got ${actual}`,
      },
    ],
    changeActions: [
      { type: 'fill', selector: '#model', value: '   ' },
      { type: 'selectOption', selector: '#layout', value: 'clustered' },
      { type: 'uncheck', selector: '#show-labels' },
    ],
    storedGraphExpectations: {
      defaultLayout: {
        expected: 'clustered',
        message: (actual) => `Expected layout to be clustered, got ${actual}`,
      },
      nodeSize: {
        expected: 8,
        message: (actual) => `Expected node size to be 8, got ${actual}`,
      },
      showLabels: {
        expected: true,
        message: (actual) => `Expected showLabels to be true, got ${actual}`,
      },
    },
    putCountMessage: (actual) => `Expected at least one PUT, got ${actual}`,
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.deepEqual(calls, [
    'fill:#model:   ',
    'selectOption:#layout:clustered',
    'uncheck:#show-labels',
    'click:.settings-save-btn',
    'waitForSelector:text=配置已保存',
    'screenshot:/tmp/evidence/configured-save.png:true',
    'page.close',
  ])
})

test('buildT12ProviderSaveScenario wires registerFixtures and default putCount state', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async (selector) => {
      if (selector === 'text=配置已保存') {
        calls.push(`waitForSelector:${selector}`)
      }
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    locator: (selector) => ({
      inputValue: async () => {
        if (selector === '#provider') return 'anthropic'
        throw new Error(`Unexpected selector: ${selector}`)
      },
      fill: async (value) => {
        calls.push(`fill:${selector}:${value}`)
      },
    }),
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12ProviderSaveScenario({
    id: 'anthropic_save_path',
    artifact: 'task-12-settings-anthropic-save.png',
    registerFixtures: async (_page, state) => {
      state.putCount += 1
      calls.push(`registerFixtures:${state.putCount}`)
    },
    initialFieldValues: [
      {
        selector: '#provider',
        expected: 'anthropic',
        message: (actual) => `Expected provider to be anthropic, got ${actual}`,
      },
    ],
    changeActions: [
      { type: 'fill', selector: '#provider', value: 'anthropic' },
    ],
    putCountMessage: (actual) => `Expected PUT count, got ${actual}`,
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.deepEqual(calls, [
    'registerFixtures:1',
    'fill:#provider:anthropic',
    'click:.settings-save-btn',
    'waitForSelector:text=配置已保存',
    'screenshot:/tmp/evidence/task-12-settings-anthropic-save.png:true',
    'page.close',
  ])
})

test('buildT12StorageSaveScenario wires registerFixtures, storageStateRaw, and stored graph expectations', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async (selector) => {
      if (selector === 'text=配置已保存') {
        calls.push(`waitForSelector:${selector}`)
      }
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    locator: (selector) => ({
      inputValue: async () => {
        if (selector === '#layout') return 'force'
        throw new Error(`Unexpected selector: ${selector}`)
      },
    }),
    selectOption: async (selector, value) => {
      calls.push(`selectOption:${selector}:${value}`)
    },
    evaluate: async () => ({
      defaultLayout: 'clustered',
    }),
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12StorageSaveScenario({
    id: 'corrupted_visualization_storage_path',
    artifact: 'task-12-settings-corrupt-storage.png',
    storageStateRaw: '{broken-json',
    registerFixtures: async (_page, state) => {
      state.putCount += 1
      calls.push(`registerFixtures:${state.putCount}`)
    },
    initialFieldValues: [
      {
        selector: '#layout',
        expected: 'force',
        message: (actual) => `Expected layout to be force, got ${actual}`,
      },
    ],
    changeActions: [
      { type: 'selectOption', selector: '#layout', value: 'clustered' },
    ],
    storedGraphExpectations: {
      defaultLayout: {
        expected: 'clustered',
        message: (actual) => `Expected layout to be clustered, got ${actual}`,
      },
    },
    putCountMessage: (actual) => `Expected PUT count, got ${actual}`,
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.deepEqual(calls, [
    'registerFixtures:1',
    'selectOption:#layout:clustered',
    'click:.settings-save-btn',
    'waitForSelector:text=配置已保存',
    'screenshot:/tmp/evidence/task-12-settings-corrupt-storage.png:true',
    'page.close',
  ])
})

test('buildT12PageScenario executes generic flow with fresh state and screenshot', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async () => {},
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12PageScenario({
    id: 'connection_failure_path',
    artifact: 'task-12-settings-conn-fail.png',
    createState: () => ({ mode: 'failure' }),
    setupPage: async ({ state }) => {
      calls.push(`setupPage:${state.mode}`)
    },
    run: async ({ state }) => {
      calls.push(`run:${state.mode}`)
    },
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.equal(scenario.artifact, 'task-12-settings-conn-fail.png')
  assert.deepEqual(calls, [
    'setupPage:failure',
    'run:failure',
    'screenshot:/tmp/evidence/task-12-settings-conn-fail.png:true',
    'page.close',
  ])
})

test('createT12ScenarioStepSequence validates and freezes named steps', () => {
  const steps = createT12ScenarioStepSequence([
    {
      id: ' prepare ',
      run: async () => {},
    },
  ])

  assert.equal(Object.isFrozen(steps), true)
  assert.equal(steps[0].id, 'prepare')
  assert.equal(Object.isFrozen(steps[0]), true)
})

test('runT12ScenarioStepSequence executes steps in order', async () => {
  const calls = []
  const steps = createT12ScenarioStepSequence([
    {
      id: 'first',
      run: async ({ state }) => {
        state.phase = 'first'
        calls.push('first')
      },
    },
    {
      id: 'second',
      run: async ({ state }) => {
        calls.push(`second:${state.phase}`)
      },
    },
  ])

  await runT12ScenarioStepSequence(steps, {
    state: { phase: 'initial' },
  })

  assert.deepEqual(calls, ['first', 'second:first'])
})

test('runT12ScenarioStepSequence executes action steps and step assertions', async () => {
  const calls = []
  const steps = createT12ScenarioStepSequence([
    {
      id: 'prepare',
      actions: [
        { type: 'click', selector: '.settings-save-btn' },
      ],
      assert: ({ state }) => {
        calls.push(`assert:${state.phase}`)
      },
    },
  ])

  await runT12ScenarioStepSequence(steps, {
    state: { phase: 'prepared' },
    page: {
      click: async (selector) => {
        calls.push(`click:${selector}`)
      },
    },
  })

  assert.deepEqual(calls, [
    'click:.settings-save-btn',
    'assert:prepared',
  ])
})

test('buildT12PageScenario executes declarative steps flow with screenshot', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async () => {},
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12PageScenario({
    id: 'save_happy_path',
    artifact: 'task-12-settings-save.png',
    createState: () => ({ stage: 'initial' }),
    steps: [
      {
        id: 'prepare',
        run: async ({ state }) => {
          state.stage = 'prepared'
          calls.push('prepare')
        },
      },
      {
        id: 'assert',
        run: async ({ state }) => {
          calls.push(`assert:${state.stage}`)
        },
      },
    ],
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.deepEqual(calls, [
    'prepare',
    'assert:prepared',
    'screenshot:/tmp/evidence/task-12-settings-save.png:true',
    'page.close',
  ])
})

test('buildT12PageScenario executes action-only steps flow with screenshot', async () => {
  const calls = []
  const page = {
    addInitScript: async () => {},
    goto: async () => {},
    waitForURL: async () => {},
    waitForSelector: async (selector, options) => {
      calls.push(`waitForSelector:${selector}:${JSON.stringify(options ?? {})}`)
    },
    click: async (selector) => {
      calls.push(`click:${selector}`)
    },
    screenshot: async (options) => {
      calls.push(`screenshot:${options.path}:${options.fullPage}`)
    },
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    clearCookies: async () => {},
    clearPermissions: async () => {},
    newPage: async () => page,
  }

  const scenario = buildT12PageScenario({
    id: 'connection_failure_path',
    artifact: 'task-12-settings-conn-fail.png',
    steps: [
      {
        id: 'trigger',
        actions: [
          { type: 'click', selector: '.settings-test-btn' },
        ],
      },
      {
        id: 'assert_failure',
        actions: [
          { type: 'waitForSelector', selector: 'text=mock connection failure', options: { timeout: 30000 } },
          { type: 'waitForSelector', selector: '.settings-status--failed', options: { timeout: 30000 } },
        ],
      },
    ],
  })

  await scenario.execute({
    context,
    baseUrl: 'http://127.0.0.1:4173',
    evidenceDir: '/tmp/evidence',
  })

  assert.deepEqual(calls, [
    'waitForSelector:.settings-content:{"state":"visible","timeout":30000}',
    'waitForSelector:.settings-save-btn:{"state":"visible","timeout":30000}',
    'click:.settings-test-btn',
    'waitForSelector:text=mock connection failure:{"timeout":30000}',
    'waitForSelector:.settings-status--failed:{"timeout":30000}',
    'screenshot:/tmp/evidence/task-12-settings-conn-fail.png:true',
    'page.close',
  ])
})

test('buildT12SaveScenario rejects missing artifact and execute prerequisites', async () => {
  assert.throws(
    () => buildT12SaveScenario({
      id: 'missing-artifact',
    }),
    /missing artifact/
  )

  const scenario = buildT12SaveScenario({
    id: 'missing-context',
    artifact: 'task-12-settings-save.png',
  })

  await assert.rejects(
    () => scenario.execute({
      baseUrl: 'http://127.0.0.1:4173',
      evidenceDir: '/tmp/evidence',
    }),
    /Missing T12 scenario context/
  )
})

test('buildT12PageScenario rejects missing artifact, missing run, and execute prerequisites', async () => {
  assert.throws(
    () => buildT12PageScenario({
      id: 'missing-artifact',
      run: async () => {},
    }),
    /missing artifact/
  )

  assert.throws(
    () => buildT12PageScenario({
      id: 'missing-run',
      artifact: 'task-12-settings-conn-fail.png',
    }),
    /missing run\(runtime\) or steps/
  )

  const scenario = buildT12PageScenario({
    id: 'missing-base-url',
    artifact: 'task-12-settings-conn-fail.png',
    run: async () => {},
  })

  await assert.rejects(
    () => scenario.execute({
      context: {},
      evidenceDir: '/tmp/evidence',
    }),
    /Missing T12 scenario baseUrl/
  )
})

test('provider and storage save builders reject missing registerFixtures', () => {
  assert.throws(
    () => buildT12ProviderSaveScenario({
      id: 'missing-provider-fixture',
      artifact: 'task-12-settings-anthropic-save.png',
    }),
    /missing registerFixtures/
  )

  assert.throws(
    () => buildT12StorageSaveScenario({
      id: 'missing-storage-fixture',
      artifact: 'task-12-settings-corrupt-storage.png',
    }),
    /missing registerFixtures/
  )
})

test('createT12ScenarioStepSequence rejects duplicates and missing run', () => {
  assert.throws(
    () => createT12ScenarioStepSequence([
      { id: 'dup', run: async () => {} },
      { id: 'dup', run: async () => {} },
    ]),
    /Duplicate T12 scenario step id: dup/
  )

  assert.throws(
    () => createT12ScenarioStepSequence([
      { id: 'missing-run' },
    ]),
    /missing run\(runtime\) or actions/
  )
})
