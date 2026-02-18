// Package config provides configuration for Cortex Go services.
package config

import (
	"os"
	"strconv"
)

// Config holds all service configuration.
type Config struct {
	CachePort      int
	ModelPort      int
	CacheMaxEntries int
	CacheMaxSizeMB int
	CacheTTLSeconds int
	OllamaHost     string
	OllamaPort     int
	HealthInterval int // seconds
	LogLevel       string
}

// DefaultConfig returns the default configuration.
func DefaultConfig() *Config {
	return &Config{
		CachePort:       50051,
		ModelPort:       50052,
		CacheMaxEntries: 1000,
		CacheMaxSizeMB:  100,
		CacheTTLSeconds: 3600,
		OllamaHost:     "localhost",
		OllamaPort:     11434,
		HealthInterval:  30,
		LogLevel:        "info",
	}
}

// FromEnv loads configuration from environment variables.
func FromEnv() *Config {
	cfg := DefaultConfig()

	if v := os.Getenv("CORTEX_CACHE_PORT"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.CachePort = n
		}
	}
	if v := os.Getenv("CORTEX_MODEL_PORT"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.ModelPort = n
		}
	}
	if v := os.Getenv("CORTEX_CACHE_MAX_ENTRIES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.CacheMaxEntries = n
		}
	}
	if v := os.Getenv("CORTEX_CACHE_MAX_SIZE_MB"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.CacheMaxSizeMB = n
		}
	}
	if v := os.Getenv("CORTEX_CACHE_TTL"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.CacheTTLSeconds = n
		}
	}
	if v := os.Getenv("OLLAMA_HOST"); v != "" {
		cfg.OllamaHost = v
	}
	if v := os.Getenv("CORTEX_LOG_LEVEL"); v != "" {
		cfg.LogLevel = v
	}

	return cfg
}
