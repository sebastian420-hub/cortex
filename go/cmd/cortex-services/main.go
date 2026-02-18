// Package main provides the entry point for Cortex Go services.
//
// This binary runs the cache and model manager gRPC services
// that provide high-performance caching and model management
// for the Cortex Python application.
package main

import (
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/cortex/cortex-services/internal/cache"
	"github.com/cortex/cortex-services/internal/config"
	"github.com/cortex/cortex-services/internal/modelmanager"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	"github.com/cortex/cortex-services/api/proto/cachepb"
	"github.com/cortex/cortex-services/api/proto/modelpb"
)

func main() {
	cfg := config.FromEnv()

	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Printf("Starting Cortex Services...")
	log.Printf("Cache port: %d, Model port: %d", cfg.CachePort, cfg.ModelPort)

	// Initialize cache service
	cacheSvc := cache.NewService(
		cfg.CacheMaxEntries,
		cfg.CacheMaxSizeMB,
		cfg.CacheTTLSeconds,
	)

	// Initialize model manager service
	modelSvc := modelmanager.NewService(
		cfg.OllamaHost,
		cfg.OllamaPort,
		cfg.HealthInterval,
	)

	// Verify cache service is working
	log.Printf("Cache service initialized (max entries: %d, max size: %dMB)",
		cfg.CacheMaxEntries, cfg.CacheMaxSizeMB)

	// Verify Ollama connection
	health, err := modelSvc.GetHealth()
	if err != nil {
		log.Printf("Warning: Could not check Ollama health: %v", err)
	} else if health.Available {
		log.Printf("Ollama connected: %d models available", health.ModelsLoaded)
	} else {
		log.Printf("Warning: Ollama not available at %s:%d", cfg.OllamaHost, cfg.OllamaPort)
	}

	// Start cache listener
	cacheListener, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.CachePort))
	if err != nil {
		log.Fatalf("Failed to listen on cache port %d: %v", cfg.CachePort, err)
	}
	log.Printf("Cache service listening on :%d", cfg.CachePort)

	// Start model listener
	modelListener, err := net.Listen("tcp", fmt.Sprintf(":%d", cfg.ModelPort))
	if err != nil {
		log.Fatalf("Failed to listen on model port %d: %v", cfg.ModelPort, err)
	}
	log.Printf("Model service listening on :%d", cfg.ModelPort)

	// Create gRPC servers
	cacheGrpcSrv := grpc.NewServer()
	cachepb.RegisterCacheServiceServer(cacheGrpcSrv, cache.NewGRPCServer(cacheSvc))
	reflection.Register(cacheGrpcSrv)

	modelGrpcSrv := grpc.NewServer()
	modelpb.RegisterModelServiceServer(modelGrpcSrv, modelmanager.NewGRPCServer(modelSvc))
	reflection.Register(modelGrpcSrv)

	// Start servers in goroutines
	go func() {
		if err := cacheGrpcSrv.Serve(cacheListener); err != nil {
			log.Fatalf("Cache gRPC server failed: %v", err)
		}
	}()

	go func() {
		if err := modelGrpcSrv.Serve(modelListener); err != nil {
			log.Fatalf("Model gRPC server failed: %v", err)
		}
	}()

	log.Printf("Cortex Services ready. Waiting for connections...")

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh

	log.Printf("Received signal %v, shutting down...", sig)

	// Graceful shutdown
	cacheSvc.Stop()
	modelSvc.Stop()

	log.Printf("Cortex Services stopped.")
}
