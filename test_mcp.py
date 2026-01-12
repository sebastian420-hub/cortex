#!/usr/bin/env python3
"""Test MCP client implementation."""

import json
import subprocess
import sys
import time
from pathlib import Path

# Add cortex to path
sys.path.insert(0, '.')

from cortex.mcp.client import MCPClient, MCPServerConfig, TransportType
from cortex.mcp.protocol import MCPRequest

def test_mcp_client():
    """Test MCP client with a mock server."""
    print("Testing MCP client...")
    
    # Create a mock MCP server script
    mock_server_script = '''
import sys
import json

def read_request():
    """Read a JSON-RPC request from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())

def write_response(response):
    """Write a JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(response) + '\\n')
    sys.stdout.flush()

# Simple mock MCP server
while True:
    try:
        request = read_request()
        if request is None:
            break
            
        method = request.get('method')
        request_id = request.get('id')
        
        if method == 'initialize':
            response = {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {},
                    'serverInfo': {
                        'name': 'Mock MCP Server',
                        'version': '1.0.0'
                    }
                }
            }
        elif method == 'tools/list':
            response = {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'tools': [
                        {
                            'name': 'get_time',
                            'description': 'Get current time',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'format': {
                                        'type': 'string',
                                        'description': 'Time format',
                                        'enum': ['iso', 'unix', 'human']
                                    }
                                }
                            }
                        },
                        {
                            'name': 'echo',
                            'description': 'Echo back input',
                            'inputSchema': {
                                'type': 'object',
                                'properties': {
                                    'text': {
                                        'type': 'string',
                                        'description': 'Text to echo'
                                    }
                                },
                                'required': ['text']
                            }
                        }
                    ]
                }
            }
        elif method == 'tools/call':
            params = request.get('params', {})
            name = params.get('name', '')
            arguments = params.get('arguments', {})
            
            if name == 'get_time':
                import datetime
                format_type = arguments.get('format', 'iso')
                if format_type == 'iso':
                    result = datetime.datetime.now().isoformat()
                elif format_type == 'unix':
                    result = str(time.time())
                else:
                    result = str(datetime.datetime.now())
                    
                response = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {
                        'content': [
                            {
                                'type': 'text',
                                'text': f'Current time: {result}'
                            }
                        ]
                    }
                }
            elif name == 'echo':
                text = arguments.get('text', '')
                response = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'result': {
                        'content': [
                            {
                                'type': 'text',
                                'text': f'Echo: {text}'
                            }
                        ]
                    }
                }
            else:
                response = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {name}'
                    }
                }
        elif method == 'initialized':
            # Notification, no response needed
            continue
        else:
            response = {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }
        
        write_response(response)
        
    except Exception as e:
        error_response = {
            'jsonrpc': '2.0',
            'id': request_id if 'request_id' in locals() else None,
            'error': {
                'code': -32603,
                'message': f'Internal error: {e}'
            }
        }
        write_response(error_response)
'''

    # Write mock server to a file
    mock_server_path = Path('mock_mcp_server.py')
    mock_server_path.write_text(mock_server_script, encoding='utf-8')
    
    try:
        # Create MCP client
        client = MCPClient()
        
        # Add mock server
        server_config = MCPServerConfig(
            name='mock',
            command=f'{sys.executable} {mock_server_path}',
            transport=TransportType.STDIO
        )
        client.add_server(server_config)
        
        # Start client (this will start the server)
        print("Starting MCP client...")
        client.start()
        
        # Check if tools were discovered
        tools = client.get_tools()
        print(f"Discovered {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.server_name}.{tool.name}: {tool.description}")
        
        # Test calling a tool
        print("\nTesting tool call...")
        result = client.call_tool('mock', 'get_time', {'format': 'iso'})
        print(f"Tool call result: {result}")
        
        # Test another tool
        result = client.call_tool('mock', 'echo', {'text': 'Hello MCP!'})
        print(f"Echo result: {result}")
        
        # Stop client
        client.stop()
        print("\nMCP test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"MCP test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if mock_server_path.exists():
            mock_server_path.unlink()

if __name__ == '__main__':
    success = test_mcp_client()
    sys.exit(0 if success else 1)