import { existsSync } from 'node:fs'
import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const REPO_ROOT = new URL('../../../', import.meta.url)
export const FRONTEND_PACKAGE_FILE = new URL('../../package.json', import.meta.url)
export const SIDECAR_PACKAGE_FILE = new URL('../../api/package.json', import.meta.url)
export const README_FILE = new URL('../../../README.md', import.meta.url)
export const DEVELOPMENT_FILE = new URL('../../../docs/DEVELOPMENT.md', import.meta.url)
export const ARCHITECTURE_FILE = new URL('../../../docs/ARCHITECTURE.md', import.meta.url)
export const ROADMAP_FILE = new URL('../../../docs/ROADMAP.md', import.meta.url)
export const BASELINE_FILE = new URL('../../../docs/Product_Engineering_Baseline.md', import.meta.url)
export const FOLLOWUP_FILE = new URL('../../../docs/claude-review-followup.md', import.meta.url)
export const WORKFLOW_FILE = new URL('../../../.github/workflows/contract-guards.yml', import.meta.url)
export const FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE = new URL(
  '../../../.github/workflows/focused-real-smoke-reusable.yml',
  import.meta.url
)

function maybeIncludeDoc(label, fileUrl) {
  return existsSync(fileURLToPath(fileUrl)) ? [[label, fileUrl]] : []
}

export const CORE_PRODUCT_DOCS = Object.freeze([
  ...maybeIncludeDoc('README.md', README_FILE),
  ...maybeIncludeDoc('docs/DEVELOPMENT.md', DEVELOPMENT_FILE),
  ...maybeIncludeDoc('docs/ARCHITECTURE.md', ARCHITECTURE_FILE),
  ...maybeIncludeDoc('docs/ROADMAP.md', ROADMAP_FILE),
  ...maybeIncludeDoc('docs/Product_Engineering_Baseline.md', BASELINE_FILE),
])

export const CORE_PRODUCT_DOCS_WITH_FOLLOWUP = Object.freeze([
  ...CORE_PRODUCT_DOCS,
  ...maybeIncludeDoc('docs/claude-review-followup.md', FOLLOWUP_FILE),
])

export const NPM_RUN_COMMAND_PATTERN = /npm --prefix (frontend(?:\/api)?) run ([A-Za-z0-9:_-]+)/g
export const LOCAL_PYTHON_SCRIPT_PATTERN = /python3?\s+((?:scripts|tests)\/[^\s`]+?\.py)(?=\s|`|$)/g
export const LOCAL_BASH_SCRIPT_PATTERN = /bash\s+((?:scripts|tests)\/[^\s`]+?)(?=\s|`|$)/g
export const PYTEST_INVOCATION_PATTERN = /python3?\s+-m\s+pytest\s+([^\n`]+)/g
export const LOCAL_MARKDOWN_LINK_PATTERN = /\[[^\]]+\]\((\/home\/elucid\/projects\/web\/Memory_graph\/[^)#:\s]+)(?::\d+(?::\d+)?)?(?:#L?\d+(?:C\d+)?)?\)/g

export function extractDocumentCommandsFromSource(source) {
  return [...source.matchAll(NPM_RUN_COMMAND_PATTERN)].map((match) => ({
    prefix: match[1],
    script: match[2],
  }))
}

export function collectMatches(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1])
}

export function collectPytestTargetsFromSource(source) {
  const matches = [...source.matchAll(PYTEST_INVOCATION_PATTERN)]
  const targets = []

  for (const match of matches) {
    for (const token of match[1].split(/\s+/)) {
      if (/^tests\/.+\.py$/.test(token)) {
        targets.push(token)
      }
    }
  }

  return targets
}

export function globPatternToRegExp(pattern) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`^${escaped.replace(/\*/g, '.*')}$`)
}

export async function readUtf8(fileUrl) {
  return readFile(fileUrl, 'utf8')
}

export async function loadPackageScripts() {
  const frontendPackage = JSON.parse(await readUtf8(FRONTEND_PACKAGE_FILE))
  const sidecarPackage = JSON.parse(await readUtf8(SIDECAR_PACKAGE_FILE))

  return {
    frontend: frontendPackage.scripts || {},
    'frontend/api': sidecarPackage.scripts || {},
  }
}

export async function collectDocumentCommands(fileUrl) {
  return extractDocumentCommandsFromSource(await readUtf8(fileUrl))
}

export function findMissingCommands(commands, packageScriptsByPrefix) {
  return commands.filter(({ prefix, script }) => !(script in packageScriptsByPrefix[prefix]))
}

export async function collectRelativeFilePaths(rootPath, directory = '') {
  const currentPath = path.join(rootPath, directory)
  const entries = await readdir(currentPath, { withFileTypes: true })
  const results = []

  for (const entry of entries) {
    const relativePath = directory ? path.posix.join(directory, entry.name) : entry.name
    if (entry.isDirectory()) {
      results.push(...await collectRelativeFilePaths(rootPath, relativePath))
      continue
    }
    if (entry.isFile()) {
      results.push(relativePath)
    }
  }

  return results
}

export async function collectLocalCommandReferences(fileUrl) {
  const source = await readUtf8(fileUrl)
  return {
    pythonScripts: [...new Set(collectMatches(source, LOCAL_PYTHON_SCRIPT_PATTERN))],
    bashScripts: [...new Set(collectMatches(source, LOCAL_BASH_SCRIPT_PATTERN))],
    pytestTargets: [...new Set(collectPytestTargetsFromSource(source))],
  }
}

export async function findMissingLocalCommandTargets(fileUrl) {
  const repoRootPath = fileURLToPath(REPO_ROOT)
  const testFiles = await collectRelativeFilePaths(repoRootPath, 'tests')
  const { pythonScripts, bashScripts, pytestTargets } = await collectLocalCommandReferences(fileUrl)

  const missingScripts = [...pythonScripts, ...bashScripts].filter((relativePath) => {
    return !testFiles.includes(relativePath) && !existsSync(path.join(repoRootPath, relativePath))
  })

  const missingPytestTargets = pytestTargets.filter((target) => {
    if (target.includes('*')) {
      const pattern = globPatternToRegExp(target)
      return !testFiles.some((candidate) => pattern.test(candidate))
    }
    return !testFiles.includes(target)
  })

  return {
    totalReferences: pythonScripts.length + bashScripts.length + pytestTargets.length,
    missingScripts,
    missingPytestTargets,
  }
}

export async function collectLocalMarkdownLinks(fileUrl) {
  return [...new Set([...await readUtf8(fileUrl).then((source) => source.matchAll(LOCAL_MARKDOWN_LINK_PATTERN))].map((match) => match[1]))]
}
