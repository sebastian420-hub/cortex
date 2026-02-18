//! Token counting implementation using tiktoken-rs.

use pyo3::prelude::*;
use tiktoken_rs::{cl100k_base, o200k_base};

/// Get the appropriate encoding name for a model.
fn get_encoding_for_model(model: &str) -> &'static str {
    let model_lower = model.to_lowercase();

    if model_lower.contains("claude")
        || model_lower.contains("anthropic")
        || model_lower.contains("deepseek")
    {
        "cl100k_base"
    } else if model_lower.contains("llama")
        || model_lower.contains("mistral")
        || model_lower.contains("mixtral")
        || model_lower.contains("qwen")
    {
        "o200k_base"
    } else if model_lower.contains("gpt-4o") || model_lower.contains("o1") {
        "o200k_base"
    } else {
        // Default for GPT-4, GPT-3.5, and unknown models
        "cl100k_base"
    }
}

/// Count tokens in a text string using the model-appropriate encoding.
///
/// Args:
///     text: Text to count tokens for
///     model: Model name to determine encoding (e.g., "gpt-4", "claude-3")
///
/// Returns:
///     Number of tokens
#[pyfunction]
#[pyo3(signature = (text, model = "gpt-4"))]
pub fn count_tokens(text: &str, model: &str) -> PyResult<usize> {
    let encoding_name = get_encoding_for_model(model);

    let bpe = match encoding_name {
        "o200k_base" => o200k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Failed to load o200k_base encoding: {}",
                e
            ))
        })?,
        _ => cl100k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Failed to load cl100k_base encoding: {}",
                e
            ))
        })?,
    };

    let tokens = bpe.encode_with_special_tokens(text);
    Ok(tokens.len())
}

/// Count tokens in a single message (JSON string).
///
/// Parses the message JSON and counts tokens for all fields
/// including role, content, tool_calls, etc.
///
/// Args:
///     message_json: JSON string of a message dict
///     model: Model name
///
/// Returns:
///     Token count for the entire message
#[pyfunction]
#[pyo3(signature = (message_json, model = "gpt-4"))]
pub fn count_message_tokens(message_json: &str, model: &str) -> PyResult<usize> {
    let encoding_name = get_encoding_for_model(model);

    let bpe = match encoding_name {
        "o200k_base" => o200k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to load encoding: {}", e))
        })?,
        _ => cl100k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to load encoding: {}", e))
        })?,
    };

    // Parse message JSON
    let msg: serde_json::Value = serde_json::from_str(message_json).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e))
    })?;

    let mut total = 3; // message overhead (role, etc.)

    // Count role tokens
    if let Some(role) = msg.get("role").and_then(|v| v.as_str()) {
        total += bpe.encode_with_special_tokens(role).len();
    }

    // Count content tokens
    if let Some(content) = msg.get("content") {
        match content {
            serde_json::Value::String(s) => {
                total += bpe.encode_with_special_tokens(s).len();
            }
            serde_json::Value::Array(blocks) => {
                for block in blocks {
                    if let Some(text) = block.get("text").and_then(|v| v.as_str()) {
                        total += bpe.encode_with_special_tokens(text).len();
                    } else {
                        total += 100; // approximate for non-text blocks
                    }
                }
            }
            _ => {}
        }
    }

    // Count tool_calls tokens
    if let Some(tool_calls) = msg.get("tool_calls").and_then(|v| v.as_array()) {
        for tc in tool_calls {
            total += 10; // tool call overhead
            if let Some(func) = tc.get("function") {
                if let Some(name) = func.get("name").and_then(|v| v.as_str()) {
                    total += bpe.encode_with_special_tokens(name).len();
                }
                if let Some(args) = func.get("arguments").and_then(|v| v.as_str()) {
                    total += bpe.encode_with_special_tokens(args).len();
                }
            }
        }
    }

    // Count tool_call_id tokens
    if let Some(id) = msg.get("tool_call_id").and_then(|v| v.as_str()) {
        total += bpe.encode_with_special_tokens(id).len();
    }

    Ok(total)
}

/// Count tokens for multiple messages in batch.
///
/// More efficient than calling count_message_tokens repeatedly
/// because the encoding is loaded only once.
///
/// Args:
///     messages_json: JSON string of a list of message dicts
///     model: Model name
///
/// Returns:
///     List of token counts, one per message
#[pyfunction]
#[pyo3(signature = (messages_json, model = "gpt-4"))]
pub fn count_messages_tokens(messages_json: &str, model: &str) -> PyResult<Vec<usize>> {
    let encoding_name = get_encoding_for_model(model);

    let bpe = match encoding_name {
        "o200k_base" => o200k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to load encoding: {}", e))
        })?,
        _ => cl100k_base().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to load encoding: {}", e))
        })?,
    };

    let messages: Vec<serde_json::Value> =
        serde_json::from_str(messages_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e))
        })?;

    let mut counts = Vec::with_capacity(messages.len());

    for msg in &messages {
        let mut total = 3;

        if let Some(role) = msg.get("role").and_then(|v| v.as_str()) {
            total += bpe.encode_with_special_tokens(role).len();
        }

        if let Some(content) = msg.get("content").and_then(|v| v.as_str()) {
            total += bpe.encode_with_special_tokens(content).len();
        }

        if let Some(tool_calls) = msg.get("tool_calls").and_then(|v| v.as_array()) {
            for tc in tool_calls {
                total += 10;
                if let Some(func) = tc.get("function") {
                    if let Some(name) = func.get("name").and_then(|v| v.as_str()) {
                        total += bpe.encode_with_special_tokens(name).len();
                    }
                    if let Some(args) = func.get("arguments").and_then(|v| v.as_str()) {
                        total += bpe.encode_with_special_tokens(args).len();
                    }
                }
            }
        }

        counts.push(total);
    }

    Ok(counts)
}
