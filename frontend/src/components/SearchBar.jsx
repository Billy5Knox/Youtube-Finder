import { useSearch } from "../hooks/useSearch";

function SearchBar({ query, setQuery, setResults, selectedPlaylist }) {
  useSearch(query, selectedPlaylist, setResults);

  return (
    <div className="search-bar">
      <input
        type="text"
        className="search-input"
        placeholder="Search your saved videos..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
      />
    </div>
  );
}

export default SearchBar;
