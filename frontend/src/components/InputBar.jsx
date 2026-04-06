import React, { useState } from 'react'

export function InputBar({ onSend, isTyping, hasPendingChanges }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return
    onSend(input.trim())
    setInput('')
  }

  return (
    <form className="input-bar" onSubmit={handleSubmit}>
      {hasPendingChanges && (
        <div className="pending-notice">
          You have pending changes. Type "commit" or "rollback" to proceed.
        </div>
      )}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={isTyping ? 'Agent is thinking...' : 'Ask a question about your database...'}
        disabled={isTyping}
      />
      <button type="submit" disabled={isTyping || !input.trim()}>
        Send
      </button>
    </form>
  )
}
