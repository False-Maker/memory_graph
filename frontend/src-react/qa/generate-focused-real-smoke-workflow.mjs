import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'

import { WORKFLOW_FILE } from './workflow-focused-real-smoke-helpers.mjs'
import { replaceFocusedRealSmokeWorkflowBlock } from './focused-real-smoke-workflow-manifest.mjs'

const args = new Set(process.argv.slice(2))
const checkOnly = args.has('--check')

const currentWorkflowSource = await readFile(WORKFLOW_FILE, 'utf8')
const nextWorkflowSource = replaceFocusedRealSmokeWorkflowBlock(currentWorkflowSource)

if (checkOnly) {
  assert.equal(
    currentWorkflowSource,
    nextWorkflowSource,
    'contract-guards.yml focused real smoke block drifted from the generated manifest'
  )
  process.stdout.write('Focused real smoke workflow block is in sync.\n')
  process.exit(0)
}

if (currentWorkflowSource !== nextWorkflowSource) {
  await writeFile(WORKFLOW_FILE, nextWorkflowSource)
}

process.stdout.write('Focused real smoke workflow block synced.\n')
