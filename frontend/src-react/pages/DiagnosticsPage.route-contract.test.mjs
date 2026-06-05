import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const routerFile = new URL('../router.jsx', import.meta.url)
const appFile = new URL('../App.jsx', import.meta.url)

test('router registers diagnostics page route', async () => {
  const source = await readFile(routerFile, 'utf8')
  assert.match(source, /import DiagnosticsPage from '\.\/pages\/DiagnosticsPage'/)
  assert.match(source, /<Route path="\/diagnostics" element={<DiagnosticsPage \/>} \/>/)
})

test('app navigation exposes diagnostics entry', async () => {
  const source = await readFile(appFile, 'utf8')
  assert.match(source, /label:\s*'Diagnostics'/)
  assert.match(source, /path:\s*'\/diagnostics'/)
})
