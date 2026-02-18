package modelmanager

import (
	"context"
	"time"

	"github.com/cortex/cortex-services/api/proto/modelpb"
)

// GRPCServer implements the ModelService gRPC server.
type GRPCServer struct {
	modelpb.UnimplementedModelServiceServer
	service *Service
}

// NewGRPCServer creates a new gRPC server wrapper.
func NewGRPCServer(service *Service) *GRPCServer {
	return &GRPCServer{
		service: service,
	}
}

// GetHealth checks the health of the Ollama backend.
func (s *GRPCServer) GetHealth(ctx context.Context, req *modelpb.HealthRequest) (*modelpb.HealthResponse, error) {
	health, err := s.service.GetHealth()
	if err != nil {
		return nil, err
	}

	return &modelpb.HealthResponse{
		OllamaAvailable:  health.Available,
		OllamaVersion:    health.Version,
		ModelsLoaded:     health.ModelsLoaded,
		MemoryUsedBytes:  health.MemoryUsed,
		MemoryTotalBytes: health.MemoryTotal,
		GpuDevices:       health.GPUDevices,
		UptimeSeconds:    int64(health.Uptime.Seconds()),
	}, nil
}

// ListModels returns all available models.
func (s *GRPCServer) ListModels(ctx context.Context, req *modelpb.ListModelsRequest) (*modelpb.ListModelsResponse, error) {
	models, err := s.service.ListModels()
	if err != nil {
		return nil, err
	}

	var infos []*modelpb.ModelInfo
	for _, m := range models {
		infos = append(infos, &modelpb.ModelInfo{
			Name:      m.Name,
			SizeBytes: m.Size,
			// Other fields would be populated if available in OllamaModel
		})
	}

	return &modelpb.ListModelsResponse{
		Models: infos,
	}, nil
}

// PreloadModel loads a model into Ollama's memory.
func (s *GRPCServer) PreloadModel(ctx context.Context, req *modelpb.PreloadRequest) (*modelpb.PreloadResponse, error) {
	loadTime, err := s.service.PreloadModel(ctx, req.ModelName)
	if err != nil {
		return &modelpb.PreloadResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &modelpb.PreloadResponse{
		Success:    true,
		LoadTimeMs: loadTime,
	}, nil
}

// GetModelStatus returns the status of a specific model.
func (s *GRPCServer) GetModelStatus(ctx context.Context, req *modelpb.ModelStatusRequest) (*modelpb.ModelStatusResponse, error) {
	status := s.service.GetModelStatus(req.ModelName)

	return &modelpb.ModelStatusResponse{
		ModelName:        status.Name,
		Status:           status.Status,
		MemoryUsedBytes:  status.MemoryUsed,
		LastUsed:         status.LastUsed,
		InferenceCount:   status.InferenceCount,
		AvgLatencyMs:     status.AvgLatencyMs,
	}, nil
}

// WatchStatus streams model status updates.
func (s *GRPCServer) WatchStatus(req *modelpb.WatchStatusRequest, stream modelpb.ModelService_WatchStatusServer) error {
	interval := time.Duration(req.IntervalSeconds) * time.Second
	if interval <= 0 {
		interval = 10 * time.Second
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case <-ticker.C:
			// In a real implementation, we would check for changes or events.
			// For now, just send a periodic health heartbeat if requested.
			health, _ := s.service.GetHealth()
			
			event := &modelpb.StatusEvent{
				EventType: "heartbeat",
				Details:   "Service active",
				Timestamp: time.Now().Unix(),
			}
			
			if health.Available {
				event.Details = "Ollama available"
			} else {
				event.Details = "Ollama unavailable"
			}

			if err := stream.Send(event); err != nil {
				return err
			}
		case <-s.service.stopCh:
			return nil
		}
	}
}
