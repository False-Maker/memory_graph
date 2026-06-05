import path from 'node:path'

const T12_SETTINGS_STORAGE_KEY = 'memory_graph_settings'
const T12_SETTINGS_READY_TIMEOUT_MS = 30000
const T12_SETTINGS_SAVE_SUCCESS_SELECTOR = 'text=配置已保存'

function normalizeOptionalValue(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function resolveAssertionMessage(message, actual) {
  return typeof message === 'function' ? message(actual) : message
}

function normalizeT12PageAction(action, index) {
  if (!action || typeof action !== 'object') {
    throw new TypeError(`T12 page action at index ${index} must be an object`)
  }
  if (typeof action.type !== 'string' || !action.type.trim()) {
    throw new TypeError(`T12 page action at index ${index} is missing type`)
  }
  return {
    ...action,
    type: action.type.trim(),
  }
}

async function readT12FieldValue(page, field) {
  const locator = page.locator(field.selector)
  if (field.kind === 'checked') {
    return await locator.isChecked()
  }
  return await locator.inputValue()
}

export async function waitForT12SettingsReady(page) {
  await page.waitForURL('**/settings', { timeout: T12_SETTINGS_READY_TIMEOUT_MS })
  await page.waitForSelector('.settings-content', {
    state: 'visible',
    timeout: T12_SETTINGS_READY_TIMEOUT_MS,
  })
  await page.waitForSelector('.settings-save-btn', {
    state: 'visible',
    timeout: T12_SETTINGS_READY_TIMEOUT_MS,
  })
}

export async function withT12ScenarioPage(context, baseUrl, options = {}, run) {
  await context.clearCookies()
  await context.clearPermissions()

  const page = await context.newPage()
  const storageStateRaw = Object.prototype.hasOwnProperty.call(options, 'storageStateRaw')
    ? options.storageStateRaw
    : null

  if (storageStateRaw === null) {
    await page.addInitScript((storageKey) => {
      window.localStorage.removeItem(storageKey)
    }, T12_SETTINGS_STORAGE_KEY)
  } else {
    await page.addInitScript(({ storageKey, raw }) => {
      window.localStorage.setItem(storageKey, raw)
    }, {
      storageKey: T12_SETTINGS_STORAGE_KEY,
      raw: storageStateRaw,
    })
  }

  if (typeof options.setupPage === 'function') {
    await options.setupPage(page)
  }

  try {
    await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' })
    await waitForT12SettingsReady(page)
    return await run(page)
  } finally {
    await page.close()
  }
}

export async function assertT12FieldValues(page, fields) {
  for (const field of fields) {
    const actual = await readT12FieldValue(page, field)
    if (actual !== field.expected) {
      throw new Error(resolveAssertionMessage(field.message, actual))
    }
  }
}

export async function readT12StoredGraphSettings(page) {
  return await page.evaluate(() => {
    return JSON.parse(window.localStorage.getItem('memory_graph_settings') || '{}').graph
  })
}

export function assertT12StoredGraphSettings(storedGraph, expectations) {
  for (const [field, config] of Object.entries(expectations)) {
    if (!config) continue
    if (storedGraph?.[field] !== config.expected) {
      throw new Error(resolveAssertionMessage(config.message, storedGraph?.[field]))
    }
  }
}

export function assertT12PutCount(state, message) {
  if (state.putCount < 1) {
    throw new Error(message)
  }
}

export function assertT12StateCountAtLeast(state, key, minimum, message) {
  if (!state || typeof state !== 'object') {
    throw new Error(message)
  }
  if ((state[key] ?? 0) < minimum) {
    throw new Error(message)
  }
}

export async function runT12PageActions(page, actions) {
  if (!Array.isArray(actions)) {
    throw new TypeError('T12 page actions must be an array')
  }

  for (let index = 0; index < actions.length; index += 1) {
    const action = normalizeT12PageAction(actions[index], index)
    const selector = action.selector

    switch (action.type) {
      case 'waitForSelector':
        await page.waitForSelector(selector, action.options ?? {})
        break
      case 'click':
        await page.click(selector)
        break
      case 'fill':
        await page.locator(selector).fill(action.value)
        break
      case 'selectOption':
        await page.selectOption(selector, action.value)
        break
      case 'uncheck':
        await page.uncheck(selector)
        break
      default:
        throw new TypeError(`Unsupported T12 page action type: ${action.type}`)
    }
  }
}

function ensureT12ScenarioRuntime(runtime) {
  const { baseUrl, context, evidenceDir } = runtime
  if (!context) {
    throw new Error('Missing T12 scenario context')
  }
  if (!baseUrl) {
    throw new Error('Missing T12 scenario baseUrl')
  }
  if (!evidenceDir) {
    throw new Error('Missing T12 scenario evidenceDir')
  }
}

export function createT12ScenarioStepSequence(steps) {
  if (!Array.isArray(steps)) {
    throw new TypeError('T12 scenario step sequence must be an array')
  }

  const seenIds = new Set()
  return Object.freeze(steps.map((step, index) => {
    if (!step || typeof step !== 'object') {
      throw new TypeError(`T12 scenario step at index ${index} must be an object`)
    }

    const id = normalizeOptionalValue(step.id)
    if (!id) {
      throw new TypeError(`T12 scenario step at index ${index} is missing id`)
    }
    if (seenIds.has(id)) {
      throw new Error(`Duplicate T12 scenario step id: ${id}`)
    }
    const actions = Array.isArray(step.actions)
      ? Object.freeze(step.actions.map((action, actionIndex) => normalizeT12PageAction(action, actionIndex)))
      : null
    if (!actions && typeof step.run !== 'function') {
      throw new TypeError(`T12 scenario step "${id}" is missing run(runtime) or actions`)
    }

    seenIds.add(id)
    return Object.freeze({
      ...step,
      id,
      actions,
    })
  }))
}

export async function runT12ScenarioStepSequence(steps, runtime) {
  if (!Array.isArray(steps)) {
    throw new TypeError('T12 scenario step sequence must be an array')
  }

  for (const step of steps) {
    if (step.actions) {
      await runT12PageActions(runtime.page, step.actions)
      await step.assert?.(runtime, step)
      continue
    }
    await step.run(runtime, step)
  }
}

export function buildT12PageScenario(definition) {
  if (!definition || typeof definition !== 'object') {
    throw new TypeError('T12 page scenario definition must be an object')
  }

  const artifact = normalizeOptionalValue(definition.artifact)
  if (!artifact) {
    throw new TypeError('T12 page scenario definition is missing artifact')
  }
  const steps = Array.isArray(definition.steps)
    ? createT12ScenarioStepSequence(definition.steps)
    : null
  if (!steps && typeof definition.run !== 'function') {
    throw new TypeError('T12 page scenario definition is missing run(runtime) or steps')
  }

  return {
    ...definition,
    artifact,
    steps,
    async execute(runtime) {
      ensureT12ScenarioRuntime(runtime)
      const { baseUrl, context, evidenceDir } = runtime

      const state = typeof definition.createState === 'function'
        ? definition.createState()
        : {}

      await withT12ScenarioPage(
        context,
        baseUrl,
        {
          storageStateRaw: Object.prototype.hasOwnProperty.call(definition, 'storageStateRaw')
            ? definition.storageStateRaw
            : null,
          setupPage: async (page) => {
            await definition.setupPage?.({
              ...runtime,
              page,
              state,
            })
          },
        },
        async (page) => {
          const scenarioRuntime = {
            ...runtime,
            page,
            state,
          }
          if (steps) {
            await runT12ScenarioStepSequence(steps, scenarioRuntime)
          } else {
            await definition.run(scenarioRuntime)
          }
          await page.screenshot({
            path: path.join(evidenceDir, artifact),
            fullPage: true,
          })
        }
      )
    },
  }
}

export function buildT12SaveScenario(definition) {
  if (!definition || typeof definition !== 'object') {
    throw new TypeError('T12 save scenario definition must be an object')
  }

  const saveSuccessSelector = normalizeOptionalValue(definition.saveSuccessSelector)
    || T12_SETTINGS_SAVE_SUCCESS_SELECTOR

  return buildT12PageScenario({
    ...definition,
    async run(runtime) {
      if (Array.isArray(definition.initialFieldValues)) {
        await assertT12FieldValues(runtime.page, definition.initialFieldValues)
      }
      await definition.assertInitialState?.(runtime)
      if (Array.isArray(definition.changeActions)) {
        await runT12PageActions(runtime.page, definition.changeActions)
      }
      await definition.applyChanges?.(runtime)
      await runtime.page.click('.settings-save-btn')
      await runtime.page.waitForSelector(saveSuccessSelector, {
        timeout: T12_SETTINGS_READY_TIMEOUT_MS,
      })
      if (definition.storedGraphExpectations && typeof definition.storedGraphExpectations === 'object') {
        const storedGraph = await readT12StoredGraphSettings(runtime.page)
        assertT12StoredGraphSettings(storedGraph, definition.storedGraphExpectations)
      }
      if (Object.prototype.hasOwnProperty.call(definition, 'putCountMessage')) {
        assertT12PutCount(
          runtime.state,
          resolveAssertionMessage(definition.putCountMessage, runtime.state?.putCount)
        )
      }
      await definition.assertAfterSave?.(runtime)
    },
  })
}

function buildT12FixtureBackedSaveScenario(kind, definition) {
  if (!definition || typeof definition !== 'object') {
    throw new TypeError(`T12 ${kind} save scenario definition must be an object`)
  }
  if (typeof definition.registerFixtures !== 'function') {
    throw new TypeError(`T12 ${kind} save scenario definition is missing registerFixtures(page, state)`)
  }

  return buildT12SaveScenario({
    ...definition,
    createState: definition.createState ?? (() => ({ putCount: 0 })),
    setupPage: async ({ page, state }) => {
      await definition.registerFixtures(page, state)
    },
  })
}

export function buildT12ProviderSaveScenario(definition) {
  return buildT12FixtureBackedSaveScenario('provider', definition)
}

export function buildT12StorageSaveScenario(definition) {
  return buildT12FixtureBackedSaveScenario('storage', definition)
}
