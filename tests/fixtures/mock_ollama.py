"""Mock Ollama for testing"""

from typing import List, Dict, Any, Optional


class MockOllama:
    """Mock Ollama for testing"""
    
    def __init__(self):
        self.responses: List[Dict[str, Any]] = []
        self.call_count = 0
    
    def set_response(self, response: Dict[str, Any]):
        """Set the next response to return"""
        self.responses.append(response)
    
    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Mock chat method"""
        self.call_count += 1
        
        if self.responses:
            return self.responses.pop(0)
        
        # Default response
        return {
            "message": {
                "role": "assistant",
                "content": "Mock response"
            }
        }
    
    def reset(self):
        """Reset mock state"""
        self.responses.clear()
        self.call_count = 0


def create_mock_response(
    content: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Helper to create mock response"""
    response = {
        "message": {
            "role": "assistant"
        }
    }
    
    if content:
        response["message"]["content"] = content
    
    if tool_calls:
        response["message"]["tool_calls"] = tool_calls
    
    return response


def create_tool_call(tool_name: str, arguments: Dict[str, Any], call_id: str = "call_1") -> Dict[str, Any]:
    """Helper to create tool call"""
    return {
        "id": call_id,
        "function": {
            "name": tool_name,
            "arguments": arguments
        }
    }
