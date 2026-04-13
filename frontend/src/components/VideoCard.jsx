function VideoCard({ video }) {
  return (
    <a
      href={video.youtube_url}
      target="_blank"
      rel="noopener noreferrer"
      className="video-card"
    >
      <div className="video-thumbnail">
        {video.thumbnail_url ? (
          <img src={video.thumbnail_url} alt={video.title} />
        ) : (
          <div className="thumbnail-placeholder" />
        )}
      </div>
      <div className="video-info">
        <h3 className="video-title">{video.title}</h3>
        <p className="video-channel">{video.channel_name}</p>
        <div className="video-playlists">
          {video.playlist_names.map((name) => (
            <span key={name} className="playlist-tag">
              {name}
            </span>
          ))}
        </div>
      </div>
    </a>
  );
}

export default VideoCard;
