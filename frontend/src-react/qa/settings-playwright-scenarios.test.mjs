import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createSettingsSmokeScenarioRegistry,
  runSettingsSmokeScenarioRegistry,
} from './settings-playwright-scenarios.mjs'

test('createSettingsSmokeScenarioRegistry freezes stable scenario metadata', () => {
  const registry = createSettingsSmokeScenarioRegistry([
    {
      id: ' happy_path ',
      artifact: ' screenshot.png ',
      resetAfter: { clearRoutes: false },
      execute: async () => {},
    },
  ])

  assert.equal(Object.isFrozen(registry), true)
  assert.equal(registry[0].id, 'happy_path')
  assert.equal(registry[0].artifact, 'screenshot.png')
  assert.deepEqual(registry[0].resetAfter, { clearRoutes: false })
  assert.equal(Object.isFrozen(registry[0]), true)
})

test('createSettingsSmokeScenarioRegistry rejects duplicate ids and missing execute handler', () => {
  assert.throws(
    () => createSettingsSmokeScenarioRegistry([
      { id: 'dup', execute: async () => {} },
      { id: 'dup', execute: async () => {} },
    ]),
    /Duplicate settings smoke scenario id: dup/
  )

  assert.throws(
    () => createSettingsSmokeScenarioRegistry([
      { id: 'missing-execute' },
    ]),
    /missing execute/
  )
})

test('runSettingsSmokeScenarioRegistry executes in order and records evidence metadata', async () => {
  const calls = []
  const registry = createSettingsSmokeScenarioRegistry([
    {
      id: 'first',
      artifact: 'first.png',
      resetAfter: { clearRoutes: false },
      prepare: ({ state }) => {
        state.phase = 'first'
        calls.push('prepare:first')
      },
      execute: ({ state }) => {
        calls.push(`execute:${state.phase}`)
      },
      afterEach: () => {
        calls.push('after:first')
      },
    },
    {
      id: 'second',
      artifact: 'second.png',
      execute: ({ state }) => {
        calls.push(`execute:${state.phase}`)
      },
    },
  ])

  const completedScenarios = []
  const artifacts = []
  const state = { phase: 'initial' }

  await runSettingsSmokeScenarioRegistry(registry, {
    state,
    completedScenarios,
    artifacts,
    resetScenarioTarget: async (options, scenario) => {
      calls.push(`reset:${scenario.id}:${options.clearRoutes}`)
      state.phase = 'second'
    },
  })

  assert.deepEqual(calls, [
    'prepare:first',
    'execute:first',
    'after:first',
    'reset:first:false',
    'execute:second',
  ])
  assert.deepEqual(completedScenarios, ['first', 'second'])
  assert.deepEqual(artifacts, ['first.png', 'second.png'])
})

test('runSettingsSmokeScenarioRegistry rejects resetAfter without reset helper', async () => {
  const registry = createSettingsSmokeScenarioRegistry([
    {
      id: 'needs-reset',
      resetAfter: { clearRoutes: false },
      execute: async () => {},
    },
  ])

  await assert.rejects(
    () => runSettingsSmokeScenarioRegistry(registry, {}),
    /requested resetAfter without resetScenarioTarget/
  )
})
