import React, { useEffect } from 'react'
import { useChat } from './hooks/useChat'
import { ChatWindow } from './components/ChatWindow'
import { InputBar } from './components/InputBar'
import { PendingChanges } from './components/PendingChanges'

function App() {
  const {
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
  } = useChat()

  useEffect(() => {
    connectWebSocket('default')
  }, [connectWebSocket])

  const handleSend = (msg) => {
    const lower = msg.toLowerCase().trim()
    if (lower === 'commit' || lower === 'commit_transaction()') {
      commitChanges()
    } else if (lower === 'rollback' || lower === 'rollback_transaction()') {
      rollbackChanges()
    } else {
      sendMessage(msg)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>SQL Agent</h1>
        <div className="header-actions">
          <button onClick={clearChat} className="clear-btn">
            Clear Chat
          </button>
        </div>
      </header>
      <div className="app-body">
        <ChatWindow messages={messages} isTyping={isTyping} />
        {error && <div className="error-banner">{error}</div>}
        {hasPendingChanges && (
          <PendingChanges
            preview={pendingPreview}
            onCommit={commitChanges}
            onRollback={rollbackChanges}
          />
        )}
        <InputBar
          onSend={handleSend}
          isTyping={isTyping}
          hasPendingChanges={hasPendingChanges}
        />
      </div>
    </div>
  )
}

export default App
