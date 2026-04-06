import React, { useEffect, useRef } from 'react'

export function ChatWindow({ messages, isTyping }) {
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  return (
    <div className="chat-window">
      {messages.map((msg, i) => (
        <div key={i} className={`message ${msg.role}`}>
          <div className="message-label">{msg.role === 'user' ? 'You' : 'Agent'}</div>
          <div className="message-content">
            <pre>{msg.content}</pre>
          </div>
        </div>
      ))}
      {isTyping && (
        <div className="message agent">
          <div className="message-label">Agent</div>
          <div className="message-content typing">
            <span className="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}
