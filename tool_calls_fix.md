[THINK] Based on my research, I can now provide a comprehensive report on the tool   
calli...
Based on my research of the codebase and the OpenRouter tool calling issues, I've    
identified the problem. Let me provide a comprehensive analysis:

─────────────────────────────────────────────────────────────────────────────────────

                  Codebase Analysis: OpenRouter Tool Calling Issues

                          1. The "int + str" Error Location

The error is occurring at line 1305 in cortex/agent.py:

                                                                                     
 tool_calls_to_run.append(
     ToolCall(
         id=tool_call_data.get("id", f"call_{iteration}_{i}"),  # Potential type     
 issue
         name=tool_call_data["function"]["name"],
         arguments=parsed_arguments,
         index=i,
     )
 )
                                                                                     

                           2. Root Causes in the Codebase

                         Issue A: No Tool Call ID Validation

In cortex/core/providers/openrouter.py (lines 62-70), tool calls are extracted       
without validating the id field:

                                                                                     
 if hasattr(message, "tool_calls") and message.tool_calls:
     result["message"]["tool_calls"] = [
         {
             "function": {"name": tc.function.name, "arguments":
 tc.function.arguments},
             "id": tc.id,  # <-- No validation - could be int, None, or invalid      
 format
             "type": tc.type,
         }
         for tc in message.tool_calls
     ]
                                                                                     

Problem: Kimi K2.5 returns tool call IDs that:

 • May be integers instead of strings
 • May not match the regex pattern ^[a-zA-Z0-9_-]+$
 • May be missing entirely

                         Issue B: Empty/Malformed Arguments

In cortex/agent.py (lines 1297-1301):

                                                                                     
 try:
     parsed_arguments = json.loads(tool_call_data["function"]["arguments"])
 except (json.JSONDecodeError, KeyError, TypeError):
     parsed_arguments = {}
                                                                                     

Problem: Kimi K2.5 frequently returns:

 • Empty string "" for arguments (instead of {})
 • Plain text content instead of proper tool_calls structure
 • JSON embedded in content field instead of formatted tool_calls

                        Issue C: ToolResult ID Type Mismatch

The ToolCall dataclass in cortex/core/parallel.py (line 53) expects:

                                                                                     
 @dataclass
 class ToolCall:
     id: str  # Strictly typed as string
     name: str
     arguments: Dict[str, Any]
     index: int
                                                                                     

When results are added back to conversation (cortex/agent.py:1362, 1376):

                                                                                     
 self.conversation.add_tool_result(tool_result.id, result)
                                                                                     

If the ID was an integer from the model, this propagates the type error.

                 3. Specific Problems with Kimi K2.5 via OpenRouter

Based on the research:


  Problem                       Symptom                       Code Location          
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 
  Returns text instead of       AI_NoObjectGeneratedError     cortex/agent.py:1291   
  tool_calls
  Tool IDs don't match          String should match pattern   API returns 400        
  pattern                       error
  Empty arguments               JSON parsing fails            cortex/agent.py:1298   
  Invalid tool_call format      Failed to advance FSM         OpenRouter/vLLM layer  


                              4. Missing Defensive Code

The codebase lacks these validations:

 1 No ID type checking before creating ToolCall objects
 2 No tool_call structure validation in OpenRouter provider
 3 No fallback for models that return text-based tool calls
 4 No provider-level workarounds for known problematic models

                                5. Recommended Fixes

                    Fix 1: Validate Tool Call IDs (openrouter.py)

                                                                                     
 # In chat() and stream_chat() methods
 if hasattr(message, "tool_calls") and message.tool_calls:
     validated_tool_calls = []
     for tc in message.tool_calls:
         # Ensure ID is a valid string
         tool_id = tc.id
         if not isinstance(tool_id, str):
             tool_id = str(tool_id) if tool_id else f"call_{hash(str(tc))}"
                                                                                     
         validated_tool_calls.append({
             "function": {"name": tc.function.name, "arguments":
 tc.function.arguments},
             "id": tool_id,
             "type": getattr(tc, "type", "function"),
         })
     result["message"]["tool_calls"] = validated_tool_calls
                                                                                     

                      Fix 2: Handle Empty Arguments (agent.py)

                                                                                     
 # Before line 1298
 arguments = tool_call_data["function"].get("arguments", "{}")
 if not arguments or arguments == "":
     arguments = "{}"
 try:
     parsed_arguments = json.loads(arguments)
 except (json.JSONDecodeError, TypeError):
     parsed_arguments = {}
                                                                                     

                   Fix 3: Detect Text-Based Tool Calls (agent.py)

                                                                                     
 # Add after receiving response but before processing tool_calls
 if not response_message.get("tool_calls") and response_message.get("content"):      
     content = response_message["content"]
     # Check if content contains tool-like JSON
     if "```json" in content and any(pattern in content for pattern in ["tool_call", 
 "function"]):
         logger.warning("Model returned text-based tool call - attempting to parse") 
         # Add parsing logic to extract tool calls from markdown
                                                                                     

                               6. Immediate Workaround

For users experiencing this issue, add these providers to the OpenRouter ignore list:

 • Baseten
 • DeepInfra
 • Moonshot AI
 • Groq

This forces OpenRouter to route to providers that properly support tool calling.   