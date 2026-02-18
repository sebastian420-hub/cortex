//! Token counting module - tiktoken-rs based token counting.
//!
//! Provides native token counting using tiktoken-rs for 10x faster
//! token estimation compared to Python tiktoken.

mod counter;

pub use counter::{count_tokens, count_message_tokens, count_messages_tokens};
