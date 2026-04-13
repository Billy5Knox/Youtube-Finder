import { useEffect, useRef } from "react";
import { searchVideos } from "../api";

export function useSearch(query, selectedPlaylist, setResults) {
  const timerRef = useRef(null);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    if (!query.trim()) {
      setResults([]);
      return;
    }

    timerRef.current = setTimeout(async () => {
      try {
        const data = await searchVideos(query, selectedPlaylist);
        setResults(data.results);
      } catch (err) {
        console.error("Search error:", err);
      }
    }, 300);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [query, selectedPlaylist, setResults]);
}
