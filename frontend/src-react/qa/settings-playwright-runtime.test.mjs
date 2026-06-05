import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'
import os from 'node:os'

import {
  applyBrowserLibEnv,
  buildSettingsSmokeMatrixChildEnv,
  buildBaseUrl,
  buildBrowserLibDir,
  getDefaultPlaywrightPreviewStartPort,
  getSettingsSmokeMatrixBaseUrl,
  getSettingsSmokeMatrixBrowserWsEndpoint,
  getSettingsSmokeMatrixPreviewLogPath,
  openSettingsSmokeBrowser,
  previewServerOutputIndicatesReady,
  resetSettingsSmokePage,
  resolvePlaywrightPreviewStartPort,
  resolveSettingsSmokeBaseUrl,
  SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV,
  SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV,
  SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV,
  SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV,
  SETTINGS_SMOKE_MATRIX_BASE_URL_ENV,
  SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV,
  shouldSkipSettingsSmokeBuild,
  shouldSkipSettingsSmokeBrowser,
  shouldSkipSettingsSmokePreview,
  withSettingsSmokeContext,
  withSettingsSmokePage,
  writeSharedSettingsSmokePreviewLog,
} from './settings-playwright-runtime.mjs'

test('buildBaseUrl uses 127.0.0.1', () => {
  assert.equal(buildBaseUrl(4173), 'http://127.0.0.1:4173')
})

test('preview port helpers return stable non-overlapping defaults', () => {
  assert.equal(getDefaultPlaywrightPreviewStartPort('t7'), 4233)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t8'), 4243)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t9'), 4253)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t10'), 4263)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t11'), 4173)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t13'), 4183)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t18'), 4273)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t12'), 4193)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t19'), 4203)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t20'), 4213)
  assert.equal(getDefaultPlaywrightPreviewStartPort('t21'), 4223)
  assert.equal(getDefaultPlaywrightPreviewStartPort('missing'), 4173)
})

test('resolvePlaywrightPreviewStartPort prefers explicit env override', () => {
  assert.equal(resolvePlaywrightPreviewStartPort('t13', 'T13_PREVIEW_PORT', {}), 4183)
  assert.equal(
    resolvePlaywrightPreviewStartPort('t13', 'T13_PREVIEW_PORT', { T13_PREVIEW_PORT: '4301' }),
    4301
  )
  assert.throws(
    () => resolvePlaywrightPreviewStartPort('t13', 'T13_PREVIEW_PORT', { T13_PREVIEW_PORT: 'abc' }),
    /Invalid preview port override/
  )
})

test('previewServerOutputIndicatesReady only accepts vite preview ready output', () => {
  assert.equal(previewServerOutputIndicatesReady('  ➜  Local:   http://127.0.0.1:4173/'), true)
  assert.equal(previewServerOutputIndicatesReady('error when starting preview server:'), false)
  assert.equal(previewServerOutputIndicatesReady(''), false)
})

test('buildBrowserLibDir resolves repo cache path from frontend root', () => {
  const frontendRoot = '/workspace/Memory_graph/frontend'
  assert.equal(
    buildBrowserLibDir(frontendRoot),
    path.resolve('/workspace/Memory_graph/.cache/browser-libs/extracted/usr/lib/x86_64-linux-gnu')
  )
})

test('applyBrowserLibEnv prefixes LD_LIBRARY_PATH on non-windows', () => {
  const browserLibDir = '/tmp/browser-libs'
  const env = applyBrowserLibEnv(browserLibDir, { LD_LIBRARY_PATH: '/usr/lib' })
  if (process.platform === 'win32') {
    assert.equal(env.LD_LIBRARY_PATH, '/usr/lib')
    return
  }
  assert.equal(env.LD_LIBRARY_PATH, '/tmp/browser-libs:/usr/lib')
})

test('shouldSkipSettingsSmokeBuild only honors explicit matrix skip-build env', () => {
  assert.equal(shouldSkipSettingsSmokeBuild({}), false)
  assert.equal(shouldSkipSettingsSmokeBuild({ [SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV]: '0' }), false)
  assert.equal(shouldSkipSettingsSmokeBuild({ [SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV]: ' 1 ' }), true)
})

test('buildSettingsSmokeMatrixChildEnv enables skip-build without mutating input', () => {
  const baseEnv = { PATH: '/usr/bin' }
  const env = buildSettingsSmokeMatrixChildEnv(baseEnv)

  assert.deepEqual(baseEnv, { PATH: '/usr/bin' })
  assert.equal(env.PATH, '/usr/bin')
  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV], '1')
  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV], undefined)
  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV], undefined)
})

test('buildSettingsSmokeMatrixChildEnv enables shared preview and browser env when matrix provides it', () => {
  const env = buildSettingsSmokeMatrixChildEnv(
    { PATH: '/usr/bin' },
    {
      baseUrl: 'http://127.0.0.1:4273',
      previewLogPath: '/tmp/task-21-settings-smoke-matrix-preview.log',
      browserWsEndpoint: 'ws://127.0.0.1:44123/browser',
    }
  )

  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV], '1')
  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV], '1')
  assert.equal(env[SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV], '1')
  assert.equal(env[SETTINGS_SMOKE_MATRIX_BASE_URL_ENV], 'http://127.0.0.1:4273')
  assert.equal(
    env[SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV],
    '/tmp/task-21-settings-smoke-matrix-preview.log'
  )
  assert.equal(
    env[SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV],
    'ws://127.0.0.1:44123/browser'
  )
})

test('preview helpers read matrix env and resolve shared base URL', () => {
  const env = {
    [SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV]: '1',
    [SETTINGS_SMOKE_MATRIX_BASE_URL_ENV]: '  http://127.0.0.1:4273  ',
    [SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV]: ' /tmp/task-21-settings-smoke-matrix-preview.log ',
  }

  assert.equal(shouldSkipSettingsSmokePreview({}), false)
  assert.equal(shouldSkipSettingsSmokePreview(env), true)
  assert.equal(getSettingsSmokeMatrixBaseUrl(env), 'http://127.0.0.1:4273')
  assert.equal(
    getSettingsSmokeMatrixPreviewLogPath(env),
    '/tmp/task-21-settings-smoke-matrix-preview.log'
  )
  assert.equal(resolveSettingsSmokeBaseUrl(4173, env), 'http://127.0.0.1:4273')
  assert.equal(resolveSettingsSmokeBaseUrl(4173, {}), 'http://127.0.0.1:4173')
})

test('browser helpers read matrix env and decide whether to reuse shared browser', () => {
  const env = {
    [SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV]: '1',
    [SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV]: '  ws://127.0.0.1:44123/browser  ',
  }

  assert.equal(shouldSkipSettingsSmokeBrowser({}), false)
  assert.equal(shouldSkipSettingsSmokeBrowser(env), true)
  assert.equal(
    getSettingsSmokeMatrixBrowserWsEndpoint(env),
    'ws://127.0.0.1:44123/browser'
  )
})

test('openSettingsSmokeBrowser launches local browser by default', async () => {
  const calls = []
  const browser = { mode: 'launch' }
  const browserType = {
    launch: async () => {
      calls.push('launch')
      return browser
    },
    connect: async () => {
      calls.push('connect')
      throw new Error('connect should not be called')
    },
  }

  const result = await openSettingsSmokeBrowser(browserType, {})
  assert.equal(result, browser)
  assert.deepEqual(calls, ['launch'])
})

test('openSettingsSmokeBrowser connects to shared browser when matrix provides ws endpoint', async () => {
  const calls = []
  const browser = { mode: 'connect' }
  const browserType = {
    launch: async () => {
      calls.push('launch')
      throw new Error('launch should not be called')
    },
    connect: async (wsEndpoint) => {
      calls.push(`connect:${wsEndpoint}`)
      return browser
    },
  }

  const result = await openSettingsSmokeBrowser(browserType, {
    [SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV]: '1',
    [SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV]: 'ws://127.0.0.1:44123/browser',
  })
  assert.equal(result, browser)
  assert.deepEqual(calls, ['connect:ws://127.0.0.1:44123/browser'])
})

test('openSettingsSmokeBrowser rejects missing shared browser ws endpoint', async () => {
  const browserType = {
    launch: async () => ({ mode: 'launch' }),
    connect: async () => ({ mode: 'connect' }),
  }

  await assert.rejects(
    () => openSettingsSmokeBrowser(browserType, {
      [SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV]: '1',
    }),
    /Missing shared browser ws endpoint/
  )
})

test('withSettingsSmokeContext creates one context and closes it after success', async () => {
  const calls = []
  const context = {
    close: async () => {
      calls.push('context.close')
    },
  }
  const browser = {
    newContext: async () => {
      calls.push('browser.newContext')
      return context
    },
  }

  const result = await withSettingsSmokeContext(browser, async (receivedContext) => {
    calls.push(`run:${receivedContext === context}`)
    return 'ok'
  })

  assert.equal(result, 'ok')
  assert.deepEqual(calls, ['browser.newContext', 'run:true', 'context.close'])
})

test('withSettingsSmokeContext closes context after failure', async () => {
  const calls = []
  const context = {
    close: async () => {
      calls.push('context.close')
    },
  }
  const browser = {
    newContext: async () => {
      calls.push('browser.newContext')
      return context
    },
  }

  await assert.rejects(
    () => withSettingsSmokeContext(browser, async () => {
      calls.push('run')
      throw new Error('boom')
    }),
    /boom/
  )

  assert.deepEqual(calls, ['browser.newContext', 'run', 'context.close'])
})

test('withSettingsSmokePage creates one page and closes it after success', async () => {
  const calls = []
  const page = {
    close: async () => {
      calls.push('page.close')
    },
  }
  const context = {
    newPage: async () => {
      calls.push('context.newPage')
      return page
    },
  }

  const result = await withSettingsSmokePage(context, async (receivedPage) => {
    calls.push(`run:${receivedPage === page}`)
    return 'ok'
  })

  assert.equal(result, 'ok')
  assert.deepEqual(calls, ['context.newPage', 'run:true', 'page.close'])
})

test('resetSettingsSmokePage clears routes before navigating to blank page', async () => {
  const calls = []
  const page = {
    unrouteAll: async (options) => {
      calls.push(`unrouteAll:${options.behavior}`)
    },
    goto: async (url, options) => {
      calls.push(`goto:${url}:${options.waitUntil}`)
    },
  }

  await resetSettingsSmokePage(page)

  assert.deepEqual(calls, ['unrouteAll:wait', 'goto:about:blank:load'])
})

test('resetSettingsSmokePage can keep routes while navigating to blank page', async () => {
  const calls = []
  const page = {
    unrouteAll: async () => {
      calls.push('unrouteAll')
    },
    goto: async (url, options) => {
      calls.push(`goto:${url}:${options.waitUntil}`)
    },
  }

  await resetSettingsSmokePage(page, { clearRoutes: false })

  assert.deepEqual(calls, ['goto:about:blank:load'])
})

test('writeSharedSettingsSmokePreviewLog creates task-local artifact for shared preview', async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), 'settings-preview-log-'))
  const previewLogPath = path.join(tempDir, 'task-12-preview.log')

  await writeSharedSettingsSmokePreviewLog(previewLogPath, {
    [SETTINGS_SMOKE_MATRIX_BASE_URL_ENV]: 'http://127.0.0.1:4273',
    [SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV]: '/tmp/task-21-settings-smoke-matrix-preview.log',
  })

  const raw = await readFile(previewLogPath, 'utf8')
  assert.match(raw, /shared preview reused via http:\/\/127\.0\.0\.1:4273/)
  assert.match(raw, /preview server owned by qa:settings-playwright:matrix/)
  assert.match(raw, /shared_preview_log=task-21-settings-smoke-matrix-preview\.log/)
})
