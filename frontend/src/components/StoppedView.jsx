function StoppedView() {
  return (
    <div className="stopped-view">
      <h1>YouTube Finder has stopped</h1>
      <p>You can safely close this tab.</p>
      <p className="hint">Run <code>start.bat</code> to launch it again.</p>
    </div>
  );
}

export default StoppedView;
