package tests

import (
	"testing"

	"github.com/cortex/cortex-services/internal/modelmanager"
)

func TestModelService_GetStatus(t *testing.T) {
	// Use a non-existent port so Ollama won't be available
	svc := modelmanager.NewService("localhost", 0, 300)
	defer svc.Stop()

	status := svc.GetModelStatus("test-model")
	if status.Name != "test-model" {
		t.Errorf("Expected model name 'test-model', got %q", status.Name)
	}
	if status.Status != "unknown" {
		t.Errorf("Expected status 'unknown', got %q", status.Status)
	}
}

func TestModelService_Health(t *testing.T) {
	// Use a non-existent port to test graceful failure
	svc := modelmanager.NewService("localhost", 0, 300)
	defer svc.Stop()

	health, err := svc.GetHealth()
	if err != nil {
		t.Fatalf("GetHealth should not error, got: %v", err)
	}
	if health.Available {
		t.Error("Expected Ollama to not be available on port 0")
	}
}
