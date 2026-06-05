import { useEffect, useState } from 'react'
import { subscribeToGlobalErrors } from '../api/errorBus'

function buildToast(message) {
  return {
    id: `${Date.now()}-${Math.random()}`,
    message
  }
}

export default function GlobalErrorToastContainer() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    const unsubscribe = subscribeToGlobalErrors((message) => {
      const toast = buildToast(message)
      setToasts((prev) => [...prev, toast])
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== toast.id))
      }, 3500)
    })

    return unsubscribe
  }, [])

  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div className="toast" key={toast.id}>
          {toast.message}
        </div>
      ))}
    </div>
  )
}
