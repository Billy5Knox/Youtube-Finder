import VideoCard from "./VideoCard";

function ResultsGrid({ results, query }) {
  if (!query.trim()) {
    return (
      <div className="empty-state">
        <p>Start typing to search your saved videos.</p>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="empty-state">
        <p>No videos found for "{query}".</p>
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
