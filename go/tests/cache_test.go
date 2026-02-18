package tests

import (
	"testing"

	"github.com/cortex/cortex-services/internal/cache"
)

func TestLRUCache_SetGet(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	content := []byte("def hello():\n    return 'world'")
	evicted := c.Set("/path/to/file.py", content, 1234567890, 0)
	if evicted {
		t.Error("Expected no eviction on first set")
	}

	entry, found := c.Get("/path/to/file.py")
	if !found {
		t.Fatal("Expected to find entry")
	}
	if string(entry.Content) != string(content) {
		t.Errorf("Content mismatch: got %q, want %q", entry.Content, content)
	}
	if entry.Mtime != 1234567890 {
		t.Errorf("Mtime mismatch: got %d, want %d", entry.Mtime, 1234567890)
	}
}

func TestLRUCache_Miss(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	_, found := c.Get("/nonexistent")
	if found {
		t.Error("Expected miss for nonexistent key")
	}
}

func TestLRUCache_Eviction(t *testing.T) {
	c := cache.NewLRUCache(3, 100, 3600)

	c.Set("file1", []byte("a"), 1, 0)
	c.Set("file2", []byte("b"), 2, 0)
	c.Set("file3", []byte("c"), 3, 0)
	c.Set("file4", []byte("d"), 4, 0) // should evict file1

	_, found := c.Get("file1")
	if found {
		t.Error("Expected file1 to be evicted")
	}

	_, found = c.Get("file4")
	if !found {
		t.Error("Expected file4 to be present")
	}
}

func TestLRUCache_LRUOrder(t *testing.T) {
	c := cache.NewLRUCache(3, 100, 3600)

	c.Set("file1", []byte("a"), 1, 0)
	c.Set("file2", []byte("b"), 2, 0)
	c.Set("file3", []byte("c"), 3, 0)

	// Access file1 to make it recently used
	c.Get("file1")

	// Adding file4 should evict file2 (least recently used)
	c.Set("file4", []byte("d"), 4, 0)

	_, found := c.Get("file2")
	if found {
		t.Error("Expected file2 to be evicted (LRU)")
	}

	_, found = c.Get("file1")
	if !found {
		t.Error("Expected file1 to still be present (recently accessed)")
	}
}

func TestLRUCache_Invalidate(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	c.Set("file1", []byte("a"), 1, 0)
	found := c.Invalidate("file1")
	if !found {
		t.Error("Expected invalidation to find entry")
	}

	_, found = c.Get("file1")
	if found {
		t.Error("Expected entry to be removed after invalidation")
	}
}

func TestLRUCache_Clear(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	c.Set("file1", []byte("a"), 1, 0)
	c.Set("file2", []byte("b"), 2, 0)
	c.Set("file3", []byte("c"), 3, 0)

	count := c.Clear()
	if count != 3 {
		t.Errorf("Expected 3 cleared, got %d", count)
	}

	if c.Len() != 0 {
		t.Errorf("Expected empty cache after clear, got %d entries", c.Len())
	}
}

func TestLRUCache_Stats(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	c.Set("file1", []byte("a"), 1, 0)
	c.Get("file1") // hit
	c.Get("file2") // miss

	stats := c.GetStats()
	if stats.Hits != 1 {
		t.Errorf("Expected 1 hit, got %d", stats.Hits)
	}
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}
}

func TestLRUCache_HitRate(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	// No operations = 0 hit rate
	if c.HitRate() != 0.0 {
		t.Errorf("Expected 0.0 hit rate, got %f", c.HitRate())
	}

	c.Set("file1", []byte("a"), 1, 0)
	c.Get("file1") // hit
	c.Get("file2") // miss

	rate := c.HitRate()
	if rate != 0.5 {
		t.Errorf("Expected 0.5 hit rate, got %f", rate)
	}
}

func TestLRUCache_Update(t *testing.T) {
	c := cache.NewLRUCache(10, 1, 3600)

	c.Set("file1", []byte("old"), 1, 0)
	c.Set("file1", []byte("new"), 2, 0) // update

	entry, found := c.Get("file1")
	if !found {
		t.Fatal("Expected to find updated entry")
	}
	if string(entry.Content) != "new" {
		t.Errorf("Expected 'new' content, got %q", entry.Content)
	}
	if entry.Mtime != 2 {
		t.Errorf("Expected mtime 2, got %d", entry.Mtime)
	}
}

func TestCacheService_Basic(t *testing.T) {
	svc := cache.NewService(100, 10, 3600)
	defer svc.Stop()

	// Set and get
	_, err := svc.Set("test.py", []byte("hello"), 12345, 0)
	if err != nil {
		t.Fatalf("Set failed: %v", err)
	}

	entry, found, stale := svc.Get("test.py", false)
	if !found {
		t.Fatal("Expected to find entry")
	}
	if stale {
		t.Error("Expected entry to not be stale")
	}
	if string(entry.Content) != "hello" {
		t.Errorf("Content mismatch: got %q", entry.Content)
	}
}

func TestCacheService_BatchGet(t *testing.T) {
	svc := cache.NewService(100, 10, 3600)
	defer svc.Stop()

	svc.Set("file1", []byte("a"), 1, 0)
	svc.Set("file2", []byte("b"), 2, 0)

	entries, misses := svc.BatchGet([]string{"file1", "file2", "file3"}, false)

	if len(entries) != 2 {
		t.Errorf("Expected 2 entries, got %d", len(entries))
	}
	if len(misses) != 1 {
		t.Errorf("Expected 1 miss, got %d", len(misses))
	}
	if misses[0] != "file3" {
		t.Errorf("Expected miss for 'file3', got %q", misses[0])
	}
}

func TestCacheService_Stats(t *testing.T) {
	svc := cache.NewService(100, 10, 3600)
	defer svc.Stop()

	svc.Set("file1", []byte("a"), 1, 0)
	svc.Get("file1", false) // hit
	svc.Get("file2", false) // miss

	stats := svc.GetStats()
	if stats.TotalEntries != 1 {
		t.Errorf("Expected 1 entry, got %d", stats.TotalEntries)
	}
	if stats.Hits != 1 {
		t.Errorf("Expected 1 hit, got %d", stats.Hits)
	}
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}
}
