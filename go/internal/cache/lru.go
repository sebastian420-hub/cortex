// Package cache provides a high-performance LRU cache with TTL support.
package cache

import (
	"container/list"
	"crypto/md5"
	"fmt"
	"sync"
	"time"
)

// Entry represents a cached file entry.
type Entry struct {
	Path        string
	Content     []byte
	Mtime       int64
	Size        int64
	ContentHash string
	AccessedAt  time.Time
	CreatedAt   time.Time
	HitCount    int32
	TTL         time.Duration
}

// IsExpired checks if the entry has expired based on TTL.
func (e *Entry) IsExpired() bool {
	if e.TTL <= 0 {
		return false
	}
	return time.Since(e.CreatedAt) > e.TTL
}

// LRUCache is a thread-safe LRU cache with TTL and size limits.
type LRUCache struct {
	mu          sync.RWMutex
	maxEntries  int
	maxSizeBytes int64
	defaultTTL  time.Duration
	items       map[string]*list.Element
	evictList   *list.List
	currentSize int64
	stats       Stats
	startTime   time.Time
}

// Stats holds cache statistics.
type Stats struct {
	Hits      int64
	Misses    int64
	Evictions int64
}

// NewLRUCache creates a new LRU cache.
func NewLRUCache(maxEntries int, maxSizeMB int, defaultTTLSeconds int) *LRUCache {
	return &LRUCache{
		maxEntries:   maxEntries,
		maxSizeBytes: int64(maxSizeMB) * 1024 * 1024,
		defaultTTL:   time.Duration(defaultTTLSeconds) * time.Second,
		items:        make(map[string]*list.Element),
		evictList:    list.New(),
		startTime:    time.Now(),
	}
}

// Get retrieves an entry from the cache.
// Returns the entry and whether it was found.
func (c *LRUCache) Get(path string) (*Entry, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, ok := c.items[path]
	if !ok {
		c.stats.Misses++
		return nil, false
	}

	entry := elem.Value.(*Entry)

	// Check TTL expiration
	if entry.IsExpired() {
		c.removeElement(elem)
		c.stats.Misses++
		return nil, false
	}

	// Move to front (most recently used)
	c.evictList.MoveToFront(elem)
	entry.AccessedAt = time.Now()
	entry.HitCount++
	c.stats.Hits++

	return entry, true
}

// Set adds or updates an entry in the cache.
// Returns true if an existing entry was evicted to make room.
func (c *LRUCache) Set(path string, content []byte, mtime int64, ttlSeconds int) bool {
	c.mu.Lock()
	defer c.mu.Unlock()

	evicted := false
	size := int64(len(content))

	// Determine TTL
	ttl := c.defaultTTL
	if ttlSeconds > 0 {
		ttl = time.Duration(ttlSeconds) * time.Second
	}

	// If entry already exists, update it
	if elem, ok := c.items[path]; ok {
		entry := elem.Value.(*Entry)
		c.currentSize -= entry.Size
		entry.Content = content
		entry.Mtime = mtime
		entry.Size = size
		entry.ContentHash = computeHash(content)
		entry.AccessedAt = time.Now()
		entry.CreatedAt = time.Now()
		entry.TTL = ttl
		c.currentSize += size
		c.evictList.MoveToFront(elem)
		return false
	}

	// Evict entries if needed
	for c.evictList.Len() >= c.maxEntries || (c.maxSizeBytes > 0 && c.currentSize+size > c.maxSizeBytes) {
		if c.evictList.Len() == 0 {
			break
		}
		c.evictOldest()
		evicted = true
	}

	// Add new entry
	entry := &Entry{
		Path:        path,
		Content:     content,
		Mtime:       mtime,
		Size:        size,
		ContentHash: computeHash(content),
		AccessedAt:  time.Now(),
		CreatedAt:   time.Now(),
		HitCount:    0,
		TTL:         ttl,
	}

	elem := c.evictList.PushFront(entry)
	c.items[path] = elem
	c.currentSize += size

	return evicted
}

// Invalidate removes an entry from the cache.
func (c *LRUCache) Invalidate(path string) bool {
	c.mu.Lock()
	defer c.mu.Unlock()

	elem, ok := c.items[path]
	if !ok {
		return false
	}

	c.removeElement(elem)
	return true
}

// Clear removes all entries from the cache.
func (c *LRUCache) Clear() int {
	c.mu.Lock()
	defer c.mu.Unlock()

	count := c.evictList.Len()
	c.items = make(map[string]*list.Element)
	c.evictList.Init()
	c.currentSize = 0

	return count
}

// GetStats returns cache statistics.
func (c *LRUCache) GetStats() Stats {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.stats
}

// Len returns the number of entries in the cache.
func (c *LRUCache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.evictList.Len()
}

// Size returns the total size of cached content in bytes.
func (c *LRUCache) Size() int64 {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.currentSize
}

// Uptime returns the cache uptime.
func (c *LRUCache) Uptime() time.Duration {
	return time.Since(c.startTime)
}

// HitRate returns the cache hit rate (0.0 - 1.0).
func (c *LRUCache) HitRate() float64 {
	c.mu.RLock()
	defer c.mu.RUnlock()

	total := c.stats.Hits + c.stats.Misses
	if total == 0 {
		return 0.0
	}
	return float64(c.stats.Hits) / float64(total)
}

// CleanExpired removes all expired entries.
func (c *LRUCache) CleanExpired() int {
	c.mu.Lock()
	defer c.mu.Unlock()

	removed := 0
	for elem := c.evictList.Back(); elem != nil; {
		entry := elem.Value.(*Entry)
		prev := elem.Prev()
		if entry.IsExpired() {
			c.removeElement(elem)
			removed++
		}
		elem = prev
	}

	return removed
}

func (c *LRUCache) evictOldest() {
	elem := c.evictList.Back()
	if elem != nil {
		c.removeElement(elem)
		c.stats.Evictions++
	}
}

func (c *LRUCache) removeElement(elem *list.Element) {
	entry := elem.Value.(*Entry)
	delete(c.items, entry.Path)
	c.evictList.Remove(elem)
	c.currentSize -= entry.Size
}

func computeHash(data []byte) string {
	return fmt.Sprintf("%x", md5.Sum(data))
}
