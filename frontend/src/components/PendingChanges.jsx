import React from 'react'

export function PendingChanges({ preview, onCommit, onRollback }) {
  if (!preview) return null

  return (
    <div className="pending-changes">
      <div className="pending-header">
        <span className="pending-icon">⚠</span>
        <span>Pending {preview.query_type} on '{preview.table}'</span>
      </div>
      <pre className="pending-sql">{preview.query}</pre>
      <div className="pending-actions">
        <button className="commit-btn" onClick={onCommit}>
          Commit
        </button>
        <button className="rollback-btn" onClick={onRollback}>
          Rollback
        </button>
      </div>
    </div>
  )
}
