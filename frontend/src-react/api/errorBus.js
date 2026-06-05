const listeners = new Set()

export function subscribeToGlobalErrors(listener) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function publishGlobalError(message) {
  listeners.forEach((listener) => listener(message))
}
