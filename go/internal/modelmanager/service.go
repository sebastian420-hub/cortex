// Package modelmanager provides model health monitoring and management.
package modelmanager

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"
)

// ModelStatus represents the current status of a model.
type ModelStatus struct {
	Name           string
	Status         string  // "loaded", "loading", "unloaded", "error"
	MemoryUsed     int64
	LastUsed       int64
	InferenceCount int32
	AvgLatencyMs   float64
}

// HealthInfo represents the health of the Ollama backend.
type HealthInfo struct {
	Available    bool
	Version      string
	ModelsLoaded int32
	MemoryUsed   int64
	MemoryTotal  int64
	GPUDevices   []string
	Uptime       time.Duration
}

// OllamaModel represents a model from Ollama's API.
type OllamaModel struct {
	Name       string `json:"name"`
	Model      string `json:"model"`
	Size       int64  `json:"size"`
	Digest     string `json:"digest"`
	ModifiedAt string `json:"modified_at"`
}

// OllamaListResponse is the response from /api/tags.
type OllamaListResponse struct {
	Models []OllamaModel `json:"models"`
}

// Service implements model management functionality.
type Service struct {
	ollamaHost string
	ollamaPort int
	client     *http.Client
	startTime  time.Time

	mu      sync.RWMutex
	models  map[string]*ModelStatus
	stopCh  chan struct{}
}

// NewService creates a new model manager service.
func NewService(ollamaHost string, ollamaPort int, healthInterval int) *Service {
	s := &Service{
		ollamaHost: ollamaHost,
		ollamaPort: ollamaPort,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
		startTime: time.Now(),
		models:    make(map[string]*ModelStatus),
		stopCh:    make(chan struct{}),
	}

	// Start health monitoring
	go s.healthLoop(time.Duration(healthInterval) * time.Second)

	return s
}

// GetHealth checks the health of the Ollama backend.
func (s *Service) GetHealth() (*HealthInfo, error) {
	health := &HealthInfo{
		Uptime: time.Since(s.startTime),
	}

	// Check Ollama availability
	resp, err := s.client.Get(s.ollamaURL("/api/tags"))
	if err != nil {
		health.Available = false
		return health, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		health.Available = false
		return health, nil
	}

	health.Available = true

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return health, nil
	}

	var listResp OllamaListResponse
	if err := json.Unmarshal(body, &listResp); err != nil {
		return health, nil
	}

	health.ModelsLoaded = int32(len(listResp.Models))

	return health, nil
}

// ListModels returns all available models.
func (s *Service) ListModels() ([]OllamaModel, error) {
	resp, err := s.client.Get(s.ollamaURL("/api/tags"))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Ollama: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var listResp OllamaListResponse
	if err := json.Unmarshal(body, &listResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return listResp.Models, nil
}

// PreloadModel loads a model into Ollama's memory.
func (s *Service) PreloadModel(ctx context.Context, modelName string) (float64, error) {
	start := time.Now()

	// Send a minimal generate request to load the model
	reqBody := fmt.Sprintf(`{"model": "%s", "prompt": "", "stream": false}`, modelName)
	resp, err := s.client.Post(
		s.ollamaURL("/api/generate"),
		"application/json",
		io.NopCloser(
			io.LimitReader(
				stringReader(reqBody),
				int64(len(reqBody)),
			),
		),
	)
	if err != nil {
		return 0, fmt.Errorf("failed to preload model: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("preload failed (status %d): %s", resp.StatusCode, string(body))
	}

	loadTime := time.Since(start).Seconds() * 1000

	// Update status
	s.mu.Lock()
	s.models[modelName] = &ModelStatus{
		Name:     modelName,
		Status:   "loaded",
		LastUsed: time.Now().Unix(),
	}
	s.mu.Unlock()

	return loadTime, nil
}

// GetModelStatus returns the status of a specific model.
func (s *Service) GetModelStatus(modelName string) *ModelStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()

	status, ok := s.models[modelName]
	if !ok {
		return &ModelStatus{
			Name:   modelName,
			Status: "unknown",
		}
	}
	return status
}

// Stop gracefully stops the service.
func (s *Service) Stop() {
	close(s.stopCh)
}

func (s *Service) ollamaURL(path string) string {
	return fmt.Sprintf("http://%s:%d%s", s.ollamaHost, s.ollamaPort, path)
}

func (s *Service) healthLoop(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			health, err := s.GetHealth()
			if err != nil {
				log.Printf("Health check error: %v", err)
			} else if !health.Available {
				log.Printf("Ollama not available")
			}
		case <-s.stopCh:
			return
		}
	}
}

// stringReader creates a reader from a string.
type stringReaderType struct {
	s string
	i int
}

func stringReader(s string) io.Reader {
	return &stringReaderType{s: s}
}

func (r *stringReaderType) Read(p []byte) (n int, err error) {
	if r.i >= len(r.s) {
		return 0, io.EOF
	}
	n = copy(p, r.s[r.i:])
	r.i += n
	return n, nil
}
