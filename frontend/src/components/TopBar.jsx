// frontend/src/components/TopBar.jsx
import { useState } from "react";
import { triggerSync, shutdownApp } from "../api";

function TopBar({ user, onStopped }) {
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(user.last_sync_at);
  const [loggingOff, setLoggingOff] = useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await triggerSync();
      setLastSync(result.last_sync_at);
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }

  async function handleLogoff() {
    setLoggingOff(true);
    await shutdownApp();
    onStopped();
  }

  function formatSyncTime(isoString) {
    if (!isoString) return "Never";
    return new Date(isoString).toLocaleString();
  }

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <h1 className="logo">YouTube Finder</h1>
      </div>
      <div className="top-bar-right">
        <span className="sync-status">
          Last synced: {formatSyncTime(lastSync)}
        </span>
        <button
          className="sync-button"
          onClick={handleSync}
          disabled={syncing || loggingOff}
        >
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
        <div className="user-info">
          {user.picture && (
            <img src={user.picture} alt="" className="avatar" />
          )}
          <span className="user-name">{user.name}</span>
        </div>
        <button
          className="logoff-button"
          onClick={handleLogoff}
          disabled={loggingOff}
        >
          {loggingOff ? "Stopping..." : "Logoff"}
        </button>
      </div>
    </header>
  );
}

export default TopBar;
