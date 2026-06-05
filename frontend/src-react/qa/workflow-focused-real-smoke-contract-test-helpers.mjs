import path from 'node:path'
import { readFile } from 'node:fs/promises'

import {
  parseFocusedSmokeWorkflowJobs,
  readContractGuardsWorkflowSource,
} from './workflow-focused-real-smoke-helpers.mjs'

const FRONTEND_PACKAGE_FILE = new URL('../../package.json', import.meta.url)
const QA_DIR_URL = new URL('./', import.meta.url)

export async function readFrontendPackageScripts() {
  const packageJson = JSON.parse(await readFile(FRONTEND_PACKAGE_FILE, 'utf8'))
  return packageJson.scripts || {}
}

export async function readFocusedSmokeWorkflowJobs() {
  return parseFocusedSmokeWorkflowJobs(await readContractGuardsWorkflowSource())
}

export function mapFocusedSmokeJobsByComparedTaskId(jobs) {
  const jobsByTask = new Map()

  for (const job of jobs) {
    for (const taskId of job.compareTaskIds) {
      jobsByTask.set(taskId, job)
    }
  }

  return jobsByTask
}

export function resolveWorkflowQaScriptPath(runScript, scripts) {
  const packageScript = scripts[runScript]
  if (!packageScript?.startsWith('node src-react/qa/')) return null

  return packageScript.replace(/^node\s+/, '')
}

export async function readWorkflowQaScriptSource(runScript, scripts) {
  const qaScriptRelativePath = resolveWorkflowQaScriptPath(runScript, scripts)
  if (!qaScriptRelativePath) return null

  const qaScriptUrl = new URL(path.basename(qaScriptRelativePath), QA_DIR_URL)
  return {
    qaScriptRelativePath,
    qaScriptSource: await readFile(qaScriptUrl, 'utf8'),
  }
}

export async function collectFocusedSmokeWorkflowQaScripts() {
  const scripts = await readFrontendPackageScripts()
  const jobs = await readFocusedSmokeWorkflowJobs()
  const qaScripts = []

  for (const job of jobs) {
    if (!job.realSmokeRunScript) continue
    const qaScript = await readWorkflowQaScriptSource(job.realSmokeRunScript, scripts)
    if (!qaScript) continue
    qaScripts.push({
      job,
      ...qaScript,
    })
  }

  return qaScripts
}
