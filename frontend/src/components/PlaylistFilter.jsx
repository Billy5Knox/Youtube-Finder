import { useState, useEffect } from "react";
import { fetchPlaylists } from "../api";

function PlaylistFilter({ selectedPlaylist, setSelectedPlaylist }) {
  const [playlists, setPlaylists] = useState([]);

  useEffect(() => {
    fetchPlaylists()
      .then(setPlaylists)
      .catch((err) => console.error("Failed to load playlists:", err));
  }, []);

  if (playlists.length === 0) return null;

  return (
    <div className="playlist-filter">
      <button
        className={`filter-chip ${selectedPlaylist === null ? "active" : ""}`}
        onClick={() => setSelectedPlaylist(null)}
      >
        All Playlists
      </button>
      {playlists.map((pl) => (
        <button
          key={pl.id}
          className={`filter-chip ${selectedPlaylist === pl.id ? "active" : ""}`}
          onClick={() =>
            setSelectedPlaylist(selectedPlaylist === pl.id ? null : pl.id)
          }
        >
          {pl.title} ({pl.item_count})
        </button>
      ))}
    </div>
  );
}

export default PlaylistFilter;
