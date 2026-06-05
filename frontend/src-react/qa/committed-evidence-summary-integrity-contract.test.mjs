import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = new URL('../../../', import.meta.url)
const EVIDENCE_DIR_URL = new URL('../../../.sisyphus/evidence/', import.meta.url)
const FRONTEND_PACKAGE_FILE = new URL('../../package.json', import.meta.url)

function isValidIsoDateString(value) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function walkValues(value, visit, key = '') {
  if (Array.isArray(value)) {
    value.forEach((item) => walkValues(item, visit, key))
    return
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([nextKey, nextValue]) => walkValues(nextValue, visit, nextKey))
    return
  }
  visit(value, key)
}

function assertStatusValue(status, label) {
  assert.ok(['passed', 'blocked', 'failed'].includes(status), `${label} has unsupported status: ${status}`)
}

test('committed task summary evidence samples keep stable integrity across the whole evidence directory', async () => {
  const repoRootPath = fileURLToPath(REPO_ROOT)
  const evidenceDirPath = fileURLToPath(EVIDENCE_DIR_URL)
  const frontendPackage = JSON.parse(await readFile(FRONTEND_PACKAGE_FILE, 'utf8'))
  const frontendScripts = frontendPackage.scripts || {}
  const summaryFiles = (await readdir(evidenceDirPath))
    .filter((name) => name.endsWith('-summary.json'))
    .sort()

  assert.ok(summaryFiles.length > 0, 'expected committed summary evidence samples to exist')

  for (const fileName of summaryFiles) {
    const filePath = path.join(evidenceDirPath, fileName)
    const data = JSON.parse(await readFile(filePath, 'utf8'))
    const label = `.sisyphus/evidence/${fileName}`

    assert.ok(isValidIsoDateString(data.generated_at), `${label} is missing a valid generated_at`)

    if (typeof data.status === 'string') {
      assertStatusValue(data.status, label)
    } else {
      const hasMatrixLikeAggregate = Array.isArray(data.tasks) || Array.isArray(data.providers)
      assert.equal(hasMatrixLikeAggregate, true, `${label} is missing status without matrix aggregate structure`)
    }

    if (typeof data.command === 'string') {
      const npmMatch = data.command.match(/^npm --prefix frontend run ([A-Za-z0-9:_-]+)/)
      if (npmMatch) {
        assert.equal(
          npmMatch[1] in frontendScripts,
          true,
          `${label} references missing frontend script ${npmMatch[1]}`
        )
      }

      const nodeQaMatch = data.command.match(/^node (src-react\/qa\/[A-Za-z0-9._/-]+\.mjs)$/)
      if (nodeQaMatch) {
        assert.equal(
          existsSync(path.join(repoRootPath, 'frontend', nodeQaMatch[1])),
          true,
          `${label} references missing qa script ${nodeQaMatch[1]}`
        )
      }
    }

    if (typeof data.exit_code === 'number' && typeof data.status === 'string') {
      if (data.status === 'passed') {
        assert.equal(data.exit_code, 0, `${label} should have exit_code=0 when status=passed`)
      } else {
        assert.notEqual(data.exit_code, 0, `${label} should have non-zero exit_code when status=${data.status}`)
      }
    }

    for (const collectionKey of ['tasks', 'providers']) {
      if (!Array.isArray(data[collectionKey]) || !data.counts) continue

      const computedCounts = { passed: 0, blocked: 0, failed: 0 }
      for (const item of data[collectionKey]) {
        assertStatusValue(item.status, `${label}:${collectionKey}`)
        computedCounts[item.status] += 1

        if (typeof item.exitCode === 'number') {
          if (item.status === 'passed') {
            assert.equal(item.exitCode, 0, `${label}:${collectionKey} has passed item with non-zero exitCode`)
          } else {
            assert.notEqual(item.exitCode, 0, `${label}:${collectionKey} has ${item.status} item with zero exitCode`)
          }
        }
      }

      for (const statusKey of Object.keys(computedCounts)) {
        assert.equal(
          data.counts[statusKey] ?? 0,
          computedCounts[statusKey],
          `${label}:${collectionKey} count mismatch for ${statusKey}`
        )
      }
    }

    const missingReferences = []
    walkValues(data, (value, key) => {
      if (typeof value !== 'string') return

      if (value.startsWith('.sisyphus/evidence/')) {
        if (!existsSync(path.join(repoRootPath, value))) {
          missingReferences.push(`${key}:${value}`)
        }
        return
      }

      if ((key === 'artifact' || key === 'artifacts') && /^task-/.test(value)) {
        if (!existsSync(path.join(evidenceDirPath, value))) {
          missingReferences.push(`${key}:${value}`)
        }
      }
    })
    assert.deepEqual(missingReferences, [], `${label} references missing evidence files: ${missingReferences.join(', ')}`)
  }
})
