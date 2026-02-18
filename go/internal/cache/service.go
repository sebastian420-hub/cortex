// Package cache implements the gRPC CacheService.
package cache

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Service implements the CacheService gRPC server.
type Service struct {
	cache      *LRUCache
	watchers   map[string]chan InvalidationMsg
	watchersMu sync.RWMutex
	stopCh     chan struct{}
}

// InvalidationMsg represents a cache invalidation event.
type InvalidationMsg struct {
	Path      string
	Reason    string
	Timestamp int64
}

// NewService creates a new cache service.
func NewService(maxEntries int, maxSizeMB int, ttlSeconds int) *Service {
	s := &Service{
		cache:    NewLRUCache(maxEntries, maxSizeMB, ttlSeconds),
		watchers: make(map[string]chan InvalidationMsg),
		stopCh:   make(chan struct{}),
	}

	// Start background TTL cleaner
	go s.cleanerLoop()

	return s
}

// Get retrieves a cached file entry.
func (s *Service) Get(path string, validateMtime bool) (*Entry, bool, bool) {
	entry, found := s.cache.Get(path)
	if !found {
		return nil, false, false
	}

	stale := false
	if validateMtime {
		info, err := os.Stat(path)
		if err != nil {
			// File no longer exists, invalidate
			s.cache.Invalidate(path)
			s.notifyWatchers(path, "deleted")
			return nil, false, false
		}
		if info.ModTime().Unix() != entry.Mtime {
			stale = true
		}
	}

	return entry, true, stale
}

// Set adds or updates a cache entry.
func (s *Service) Set(path string, content []byte, mtime int64, ttlSeconds int) (bool, error) {
	evicted := s.cache.Set(path, content, mtime, ttlSeconds)
	return evicted, nil
}

// Invalidate removes a cache entry.
func (s *Service) Invalidate(path string) bool {
	found := s.cache.Invalidate(path)
	if found {
		s.notifyWatchers(path, "manual")
	}
	return found
}

// BatchGet retrieves multiple entries at once.
func (s *Service) BatchGet(paths []string, validateMtime bool) (map[string]*Entry, []string) {
	entries := make(map[string]*Entry)
	var misses []string

	for _, path := range paths {
		entry, found, stale := s.Get(path, validateMtime)
		if found && !stale {
			entries[path] = entry
		} else {
			misses = append(misses, path)
		}
	}

	return entries, misses
}

// BatchSet sets multiple entries at once.
func (s *Service) BatchSet(entries []SetEntry) (int, int, []string) {
	successCount := 0
	errorCount := 0
	var errors []string

	for _, e := range entries {
		_, err := s.Set(e.Path, e.Content, e.Mtime, e.TTLSeconds)
		if err != nil {
			errorCount++
			errors = append(errors, fmt.Sprintf("%s: %v", e.Path, err))
		} else {
			successCount++
		}
	}

	return successCount, errorCount, errors
}

// SetEntry represents a batch set entry.
type SetEntry struct {
	Path       string
	Content    []byte
	Mtime      int64
	TTLSeconds int
}

// GetStats returns cache statistics.
func (s *Service) GetStats() ServiceStats {
	stats := s.cache.GetStats()
	return ServiceStats{
		TotalEntries:  int64(s.cache.Len()),
		TotalSizeBytes: s.cache.Size(),
		MaxEntries:    int64(s.cache.maxEntries),
		MaxSizeBytes:  s.cache.maxSizeBytes,
		Hits:          stats.Hits,
		Misses:        stats.Misses,
		Evictions:     stats.Evictions,
		HitRate:       s.cache.HitRate(),
		UptimeSeconds: int64(s.cache.Uptime().Seconds()),
	}
}

// ServiceStats holds service-level statistics.
type ServiceStats struct {
	TotalEntries   int64
	TotalSizeBytes int64
	MaxEntries     int64
	MaxSizeBytes   int64
	Hits           int64
	Misses         int64
	Evictions      int64
	HitRate        float64
	UptimeSeconds  int64
}

// PreCache caches files matching patterns in a directory.
func (s *Service) PreCache(patterns []string, directory string, maxFiles int) (int, int, int, []string) {
	cached := 0
	skipped := 0
	errCount := 0
	var files []string

	for _, pattern := range patterns {
		fullPattern := filepath.Join(directory, "**", pattern)
		matches, err := filepath.Glob(fullPattern)
		if err != nil {
			// Try simpler pattern
			matches, err = filepath.Glob(filepath.Join(directory, pattern))
			if err != nil {
				errCount++
				continue
			}
		}

		for _, match := range matches {
			if maxFiles > 0 && cached >= maxFiles {
				break
			}

			info, err := os.Stat(match)
			if err != nil || info.IsDir() {
				skipped++
				continue
			}

			// Skip large files (> 1MB)
			if info.Size() > 1024*1024 {
				skipped++
				continue
			}

			content, err := os.ReadFile(match)
			if err != nil {
				errCount++
				continue
			}

			s.cache.Set(match, content, info.ModTime().Unix(), 0)
			files = append(files, match)
			cached++
		}
	}

	return cached, skipped, errCount, files
}

// Clear removes all cache entries.
func (s *Service) Clear() int {
	count := s.cache.Clear()
	return count
}

// AddWatcher adds a new invalidation watcher.
func (s *Service) AddWatcher(id string) chan InvalidationMsg {
	s.watchersMu.Lock()
	defer s.watchersMu.Unlock()

	ch := make(chan InvalidationMsg, 100)
	s.watchers[id] = ch
	return ch
}

// RemoveWatcher removes an invalidation watcher.
func (s *Service) RemoveWatcher(id string) {
	s.watchersMu.Lock()
	defer s.watchersMu.Unlock()

	if ch, ok := s.watchers[id]; ok {
		close(ch)
		delete(s.watchers, id)
	}
}

// Stop gracefully stops the service.
func (s *Service) Stop() {
	close(s.stopCh)

	s.watchersMu.Lock()
	for id, ch := range s.watchers {
		close(ch)
		delete(s.watchers, id)
	}
	s.watchersMu.Unlock()
}

func (s *Service) notifyWatchers(path string, reason string) {
	s.watchersMu.RLock()
	defer s.watchersMu.RUnlock()

	msg := InvalidationMsg{
		Path:      path,
		Reason:    reason,
		Timestamp: time.Now().Unix(),
	}

	for _, ch := range s.watchers {
		select {
		case ch <- msg:
		default:
			// Channel full, skip notification
		}
	}
}

func (s *Service) cleanerLoop() {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			removed := s.cache.CleanExpired()
			if removed > 0 {
				log.Printf("Cleaned %d expired cache entries", removed)
			}
		case <-s.stopCh:
			return
		}
	}
}

// HealthCheck returns the health status of the cache service.
func (s *Service) HealthCheck(_ context.Context) error {
	// Simple health check - ensure cache is operational
	if s.cache == nil {
		return fmt.Errorf("cache not initialized")
	}
	return nil
}
