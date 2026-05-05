import VideoCard from "./VideoCard";

function ResultsGrid({ results, query, selectedPlaylist }) {
  const browsing = !query.trim() && selectedPlaylist;

  if (!query.trim() && !selectedPlaylist) {
    return (
      <div className="empty-state">
        <p>Start typing to search your saved videos, or pick a playlist to browse.</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="empty-state">
        <p>{browsing ? "No videos in this playlist yet." : `No videos found for "${query}".`}</p>
      </div>
    );
  }

  return (
    <div className="results-grid">
      {results.map((video) => (
        <VideoCard key={video.video_id} video={video} />
      ))}
    </div>
  );
}

export default ResultsGrid;
