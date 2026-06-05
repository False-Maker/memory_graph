import { spawn } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import http from 'node:http'
import path from 'node:path'

export async function startFakeOllamaServer(port) {
  let tagRequests = 0
  let embeddingRequests = 0
  let generateRequests = 0

  const server = http.createServer((request, response) => {
    const chunks = []
    request.on('data', (chunk) => chunks.push(chunk))
    request.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8')
      const payload = raw ? JSON.parse(raw) : {}

      if (request.method === 'GET' && request.url === '/api/tags') {
        tagRequests += 1
        response.writeHead(200, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ models: [{ name: 'qwen2.5:14b' }] }))
        return
      }

      if (request.method === 'POST' && request.url === '/api/embeddings') {
        embeddingRequests += 1
        response.writeHead(200, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ embedding: [1.0, 0.0, 0.0, 0.0] }))
        return
      }

      if (request.method === 'POST' && request.url === '/api/generate') {
        generateRequests += 1
        const prompt = String(payload?.prompt || '')
        const answer = prompt.includes('Output Format (JSON)')
          ? JSON.stringify({
              entities: [
                {
                  id: 'raw-alice',
                  name: 'Alice',
                  type: 'person',
                  properties: { role: 'owner' },
                  confidence: 0.98,
                },
              ],
              relationships: [],
              facts: ['Alice owns the launch checklist.'],
              summary: 'Launch ownership context',
            })
          : (
            prompt.includes('## Community Context:')
            && (
              prompt.includes('Generate a 4-6 sentence summary')
              || prompt.includes('Generate a 2-3 sentence summary')
              || prompt.includes('Generate a thematic summary')
              || prompt.includes('Generate a summary for a parent community')
            )
          )
            ? 'Launch Owners is a refreshed summary covering Alice, the launch checklist, and release coordination.'
          : prompt.includes('launch checklist')
            ? 'Alice owns the launch checklist and coordinates the release.'
            : 'Launch Owners summarizes the release ownership context.'
        response.writeHead(200, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ response: answer }))
        return
      }

      response.writeHead(404, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ detail: 'not found' }))
    })
  })

  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(port, '127.0.0.1', resolve)
  })

  return {
    getCounts() {
      return {
        tagRequests,
        embeddingRequests,
        generateRequests,
      }
    },
    async close() {
      await new Promise((resolve) => server.close(resolve))
    },
  }
}

export async function runSeedFixture({ workspaceRoot, configPath, outputPath, repoRoot, profile = 'basic' }) {
  const stdout = []
  const stderr = []
  const child = spawn(
    'python3',
    [path.join(repoRoot, 'scripts', 'qa', 'seed_search_real_smoke.py')],
    {
      cwd: workspaceRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        MEMORY_GRAPH_SETTINGS_PATH: configPath,
        SEED_OUTPUT_PATH: outputPath,
        SEED_PROFILE: profile,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
    }
  )

  child.stdout.on('data', (chunk) => stdout.push(String(chunk)))
  child.stderr.on('data', (chunk) => stderr.push(String(chunk)))

  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject)
    child.once('close', resolve)
  })
  if (exitCode !== 0) {
    throw new Error(`seed_search_real_smoke.py failed with ${exitCode}\n${stderr.join('') || stdout.join('')}`)
  }

  return JSON.parse(await readFile(outputPath, 'utf8'))
}
