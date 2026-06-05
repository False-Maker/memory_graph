import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDefaultApiBaseUrl,
  buildDefaultBackendHealthUrl,
  buildDefaultSidecarHealthUrl,
  isLocalFrontendWindowLocation,
  isLoopbackHostname,
  resolveRuntimeOrigin,
  stripTrailingSlash,
} from './runtime-config.js'

test('stripTrailingSlash removes trailing slashes', () => {
  assert.equal(stripTrailingSlash('http://127.0.0.1:8000///'), 'http://127.0.0.1:8000')
})

test('isLoopbackHostname recognizes localhost variants', () => {
  assert.equal(isLoopbackHostname('127.0.0.1'), true)
  assert.equal(isLoopbackHostname('localhost'), true)
  assert.equal(isLoopbackHostname('[::1]'), true)
  assert.equal(isLoopbackHostname('example.com'), false)
})

test('isLocalFrontendWindowLocation only matches loopback preview/dev ports', () => {
  assert.equal(
    isLocalFrontendWindowLocation({
      origin: 'http://127.0.0.1:4174',
      hostname: '127.0.0.1',
      port: '4174',
    }),
    true
  )
  assert.equal(
    isLocalFrontendWindowLocation({
      origin: 'http://localhost:5173',
      hostname: 'localhost',
      port: '5173',
    }),
    true
  )
  assert.equal(
    isLocalFrontendWindowLocation({
      origin: 'http://127.0.0.1:8000',
      hostname: '127.0.0.1',
      port: '8000',
    }),
    false
  )
  assert.equal(
    isLocalFrontendWindowLocation({
      origin: 'http://127.0.0.1:38000',
      hostname: '127.0.0.1',
      port: '38000',
    }),
    false
  )
  assert.equal(
    isLocalFrontendWindowLocation({
      origin: 'https://memory-graph.example.com',
      hostname: 'memory-graph.example.com',
      port: '',
    }),
    false
  )
})

test('resolveRuntimeOrigin routes local preview/dev ports back to backend origin', () => {
  assert.equal(
    resolveRuntimeOrigin({
      origin: 'http://127.0.0.1:4174',
      hostname: '127.0.0.1',
      port: '4174',
    }),
    'http://127.0.0.1:8000'
  )
  assert.equal(
    resolveRuntimeOrigin({
      origin: 'https://memory-graph.example.com',
      hostname: 'memory-graph.example.com',
      port: '',
    }),
    'https://memory-graph.example.com'
  )
})

test('default runtime endpoints stay aligned for local preview/dev ports', () => {
  const locationLike = {
    origin: 'http://127.0.0.1:4174',
    hostname: '127.0.0.1',
    port: '4174',
  }

  assert.equal(buildDefaultApiBaseUrl(locationLike), 'http://127.0.0.1:8000/api/v1')
  assert.equal(buildDefaultBackendHealthUrl(locationLike), 'http://127.0.0.1:8000/health')
  assert.equal(buildDefaultSidecarHealthUrl(locationLike), 'http://127.0.0.1:3001/health')
})

test('default runtime endpoints stay same-origin for deployed hosts', () => {
  const locationLike = {
    origin: 'https://memory-graph.example.com',
    hostname: 'memory-graph.example.com',
    port: '',
  }

  assert.equal(buildDefaultApiBaseUrl(locationLike), 'https://memory-graph.example.com/api/v1')
  assert.equal(buildDefaultBackendHealthUrl(locationLike), 'https://memory-graph.example.com/health')
  assert.equal(buildDefaultSidecarHealthUrl(locationLike), 'https://memory-graph.example.com/sidecar/health')
})
