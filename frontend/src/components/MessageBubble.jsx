import React from 'react'

export function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-bubble ${isUser ? 'user' : 'agent'}`}>
      <div className="message-content">
        <pre className={isUser ? '' : 'agent-response'}>{message.content}</pre>
      </div>
    </div>
  )
}
