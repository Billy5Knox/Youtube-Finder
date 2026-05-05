// frontend/src/App.jsx
import { useState, useEffect } from "react";
import { fetchCurrentUser } from "./api";
import TopBar from "./components/TopBar";
import SearchBar from "./components/SearchBar";
import ResultsGrid from "./components/ResultsGrid";
import PlaylistFilter from "./components/PlaylistFilter";
import StoppedView from "./components/StoppedView";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  if (stopped) {
    return <StoppedView />;
  }

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="login-page">
        <h1>YouTube Finder</h1>
        <p>Search across all your YouTube playlists.</p>
        <a href="/auth/login" className="login-button">
          Sign in with Google
        </a>
      </div>
    );
  }

  return (
    <div className="app">
      <TopBar user={user} onStopped={() => setStopped(true)} />
      <main className="main-content">
        <SearchBar
          query={query}
          setQuery={setQuery}
          setResults={setResults}
          selectedPlaylist={selectedPlaylist}
        />
        <PlaylistFilter
          selectedPlaylist={selectedPlaylist}
          setSelectedPlaylist={setSelectedPlaylist}
        />
        <ResultsGrid
          results={results}
          query={query}
          selectedPlaylist={selectedPlaylist}
        />
      </main>
    </div>
  );
}

export default App;
