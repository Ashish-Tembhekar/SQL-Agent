import { useState, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const [hasPendingChanges, setHasPendingChanges] = useState(false)
  const [pendingPreview, setPendingPreview] = useState(null)
  const [error, setError] = useState(null)
  const [ws, setWs] = useState(null)

  const connectWebSocket = useCallback((sessionId = 'default') => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${sessionId}`
    const socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      setWs(socket)
      setError(null)
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'done') {
        setMessages((prev) => [...prev, { role: 'agent', content: data.content }])
        setIsTyping(false)
        setHasPendingChanges(data.has_pending_changes || false)
        setPendingPreview(data.pending_preview || null)
      } else if (data.type === 'error') {
        setError(data.content)
        setIsTyping(false)
      }
    }

    socket.onclose = () => {
      setWs(null)
    }

    socket.onerror = () => {
      setError('WebSocket connection failed')
    }

    return socket
  }, [])

  const sendMessage = useCallback(
    (message, useOllama = false) => {
      if (!message.trim() || isTyping) return

      setMessages((prev) => [...prev, { role: 'user', content: message }])
      setIsTyping(true)
      setError(null)
      setPendingPreview(null)

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message, use_ollama: useOllama }))
      } else {
        fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, session_id: 'default' }),
        })
          .then((res) => res.json())
          .then((data) => {
            setMessages((prev) => [...prev, { role: 'agent', content: data.response }])
            setHasPendingChanges(data.has_pending_changes || false)
            setIsTyping(false)
          })
          .catch((err) => {
            setError(err.message)
            setIsTyping(false)
          })
      }
    },
    [ws, isTyping]
  )

  const commitChanges = useCallback(() => {
    fetch(`${API_BASE}/api/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: 'default' }),
    })
      .then((res) => res.json())
      .then((data) => {
        setMessages((prev) => [...prev, { role: 'agent', content: data.response }])
        setHasPendingChanges(false)
        setPendingPreview(null)
      })
      .catch((err) => setError(err.message))
  }, [])

  const rollbackChanges = useCallback(() => {
    fetch(`${API_BASE}/api/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: 'default' }),
    })
      .then((res) => res.json())
      .then((data) => {
        setMessages((prev) => [...prev, { role: 'agent', content: data.response }])
        setHasPendingChanges(false)
        setPendingPreview(null)
      })
      .catch((err) => setError(err.message))
  }, [])

  const clearChat = useCallback(() => {
    setMessages([])
    setHasPendingChanges(false)
    setPendingPreview(null)
    setError(null)
  }, [])

  return {
    messages,
    isTyping,
    hasPendingChanges,
    pendingPreview,
    error,
    sendMessage,
    commitChanges,
    rollbackChanges,
    clearChat,
    connectWebSocket,
  }
}
