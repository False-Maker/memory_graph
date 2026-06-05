import test from 'node:test'
import assert from 'node:assert/strict'

import { T12_SCENARIOS } from './t12-settings-playwright-scenarios.mjs'

test('t12 scenario definitions keep stable scenario and artifact order', () => {
  assert.deepEqual(
    T12_SCENARIOS.map((scenario) => scenario.id),
    [
      'save_happy_path',
      'connection_failure_path',
      'secret_storage_unavailable_path',
      'anthropic_save_path',
      'ollama_save_path',
      'corrupted_visualization_storage_path',
      'invalid_visualization_values_path',
    ]
  )

  assert.deepEqual(
    T12_SCENARIOS.map((scenario) => scenario.artifact),
    [
      'task-12-settings-save.png',
      'task-12-settings-conn-fail.png',
      'task-12-settings-secret-storage-unavailable.png',
      'task-12-settings-anthropic-save.png',
      'task-12-settings-ollama-save.png',
      'task-12-settings-corrupt-storage.png',
      'task-12-settings-invalid-storage.png',
    ]
  )
})
