function normalizeOptionalValue(value) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeResetOptions(value) {
  if (value === false) {
    return false
  }
  if (value && typeof value === 'object') {
    return { ...value }
  }
  return null
}

export function createSettingsSmokeScenarioRegistry(scenarios) {
  if (!Array.isArray(scenarios)) {
    throw new TypeError('Settings smoke scenario registry must be an array')
  }

  const seenIds = new Set()
  return Object.freeze(scenarios.map((scenario, index) => {
    if (!scenario || typeof scenario !== 'object') {
      throw new TypeError(`Settings smoke scenario at index ${index} must be an object`)
    }

    const id = normalizeOptionalValue(scenario.id)
    if (!id) {
      throw new TypeError(`Settings smoke scenario at index ${index} is missing id`)
    }
    if (seenIds.has(id)) {
      throw new Error(`Duplicate settings smoke scenario id: ${id}`)
    }
    if (typeof scenario.execute !== 'function') {
      throw new TypeError(`Settings smoke scenario "${id}" is missing execute(runtime)`)
    }

    seenIds.add(id)
    return Object.freeze({
      ...scenario,
      id,
      artifact: normalizeOptionalValue(scenario.artifact),
      resetAfter: normalizeResetOptions(scenario.resetAfter),
    })
  }))
}

export async function runSettingsSmokeScenarioRegistry(registry, runtime = {}) {
  if (!Array.isArray(registry)) {
    throw new TypeError('Settings smoke scenario registry must be an array')
  }

  for (const scenario of registry) {
    await scenario.prepare?.(runtime, scenario)
    await scenario.execute(runtime, scenario)

    runtime.completedScenarios?.push?.(scenario.id)
    if (scenario.artifact) {
      runtime.artifacts?.push?.(scenario.artifact)
    }

    await scenario.afterEach?.(runtime, scenario)

    if (scenario.resetAfter) {
      if (typeof runtime.resetScenarioTarget !== 'function') {
        throw new Error(
          `Settings smoke scenario "${scenario.id}" requested resetAfter without resetScenarioTarget()`
        )
      }
      await runtime.resetScenarioTarget(scenario.resetAfter, scenario)
    }
  }
}
