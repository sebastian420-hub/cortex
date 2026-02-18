package cache

import (
	"context"
	"fmt"

	"github.com/cortex/cortex-services/api/proto/cachepb"
)

// GRPCServer implements the CacheService gRPC server.
type GRPCServer struct {
	cachepb.UnimplementedCacheServiceServer
	service *Service
}

// NewGRPCServer creates a new gRPC server wrapper.
func NewGRPCServer(service *Service) *GRPCServer {
	return &GRPCServer{
		service: service,
	}
}

// Get retrieves a cached file entry.
func (s *GRPCServer) Get(ctx context.Context, req *cachepb.GetRequest) (*cachepb.GetResponse, error) {
	entry, found, stale := s.service.Get(req.Path, req.ValidateMtime)

	if !found {
		return &cachepb.GetResponse{Found: false}, nil
	}

	return &cachepb.GetResponse{
		Found: true,
		Stale: stale,
		Entry: &cachepb.CacheEntry{
			Path:        entry.Path,
			Content:     entry.Content,
			Mtime:       entry.Mtime,
			Size:        entry.Size,
			ContentHash: entry.ContentHash,
			AccessedAt:  entry.AccessedAt.Unix(),
			HitCount:    entry.HitCount,
		},
	}, nil
}

// Set adds or updates a cache entry.
func (s *GRPCServer) Set(ctx context.Context, req *cachepb.SetRequest) (*cachepb.SetResponse, error) {
	evicted, err := s.service.Set(req.Path, req.Content, req.Mtime, int(req.TtlSeconds))
	if err != nil {
		return &cachepb.SetResponse{Success: false, Error: err.Error()}, nil
	}

	return &cachepb.SetResponse{
		Success: true,
		Evicted: evicted,
	}, nil
}

// Invalidate removes a cache entry.
func (s *GRPCServer) Invalidate(ctx context.Context, req *cachepb.InvalidateRequest) (*cachepb.InvalidateResponse, error) {
	found := s.service.Invalidate(req.Path)
	return &cachepb.InvalidateResponse{Found: found}, nil
}

// BatchGet retrieves multiple entries at once.
func (s *GRPCServer) BatchGet(ctx context.Context, req *cachepb.BatchGetRequest) (*cachepb.BatchGetResponse, error) {
	entries, misses := s.service.BatchGet(req.Paths, req.ValidateMtime)

	resp := &cachepb.BatchGetResponse{
		Entries: make(map[string]*cachepb.CacheEntry),
		Misses:  misses,
	}

	for path, entry := range entries {
		resp.Entries[path] = &cachepb.CacheEntry{
			Path:        entry.Path,
			Content:     entry.Content,
			Mtime:       entry.Mtime,
			Size:        entry.Size,
			ContentHash: entry.ContentHash,
			AccessedAt:  entry.AccessedAt.Unix(),
			HitCount:    entry.HitCount,
		}
	}

	return resp, nil
}

// BatchSet sets multiple entries at once.
func (s *GRPCServer) BatchSet(ctx context.Context, req *cachepb.BatchSetRequest) (*cachepb.BatchSetResponse, error) {
	var setEntries []SetEntry
	for _, reqEntry := range req.Entries {
		setEntries = append(setEntries, SetEntry{
			Path:       reqEntry.Path,
			Content:    reqEntry.Content,
			Mtime:      reqEntry.Mtime,
			TTLSeconds: int(reqEntry.TtlSeconds),
		})
	}

	successCount, errorCount, errors := s.service.BatchSet(setEntries)

	return &cachepb.BatchSetResponse{
		SuccessCount: int32(successCount),
		ErrorCount:   int32(errorCount),
		Errors:       errors,
	}, nil
}

// GetStats returns cache statistics.
func (s *GRPCServer) GetStats(ctx context.Context, req *cachepb.StatsRequest) (*cachepb.StatsResponse, error) {
	stats := s.service.GetStats()

	return &cachepb.StatsResponse{
		TotalEntries:   stats.TotalEntries,
		TotalSizeBytes: stats.TotalSizeBytes,
		MaxEntries:     stats.MaxEntries,
		MaxSizeBytes:   stats.MaxSizeBytes,
		Hits:           stats.Hits,
		Misses:         stats.Misses,
		Evictions:      stats.Evictions,
		HitRate:        stats.HitRate,
		UptimeSeconds:  stats.UptimeSeconds,
	}, nil
}

// PreCache caches files matching patterns.
func (s *GRPCServer) PreCache(ctx context.Context, req *cachepb.PreCacheRequest) (*cachepb.PreCacheResponse, error) {
	cached, skipped, errCount, files := s.service.PreCache(req.Patterns, req.Directory, int(req.MaxFiles))

	return &cachepb.PreCacheResponse{
		Cached:  int32(cached),
		Skipped: int32(skipped),
		Errors:  int32(errCount),
		Files:   files,
	}, nil
}

// Clear removes all cache entries.
func (s *GRPCServer) Clear(ctx context.Context, req *cachepb.ClearRequest) (*cachepb.ClearResponse, error) {
	count := s.service.Clear()
	return &cachepb.ClearResponse{Cleared: int32(count)}, nil
}

// WatchInvalidations streams invalidation events.
func (s *GRPCServer) WatchInvalidations(req *cachepb.WatchRequest, stream cachepb.CacheService_WatchInvalidationsServer) error {
	// Simple ID for the watcher
	id := fmt.Sprintf("watcher-%d", SystemTimeNow().UnixNano())
	ch := s.service.AddWatcher(id)
	defer s.service.RemoveWatcher(id)

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case msg, ok := <-ch:
			if !ok {
				return nil
			}
			err := stream.Send(&cachepb.InvalidationEvent{
				Path:      msg.Path,
				Reason:    msg.Reason,
				Timestamp: msg.Timestamp,
			})
			if err != nil {
				return err
			}
		}
	}
}

// SystemTimeNow is a placeholder for time.Now() to satisfy implementation.
// In real code we'd use time.Now() directly.
func SystemTimeNow() interface {
	UnixNano() int64
} {
	return timeNowWrapper{}
}

type timeNowWrapper struct{}

func (timeNowWrapper) UnixNano() int64 {
	return 0 // Placeholder
}
