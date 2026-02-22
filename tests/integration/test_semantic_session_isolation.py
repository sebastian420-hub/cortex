"""
Integration tests for semantic memory session isolation.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch

from cortex.agent import Cortex
from cortex.config import AgentConfig


class TestSemanticSessionIsolation:
    """Tests that semantic memory correctly filters and isolates sessions."""

    @pytest.fixture
    def semantic_config(self, tmp_path):
        """Config for semantic memory."""
        return {
            "enabled": True,
            "persist_directory": str(tmp_path / "semantic_db"),
            "collection_name": "test_session_isolation",
            "clear_on_init": True
        }

    def test_session_isolation_and_global_retrieval(self, tmp_path, semantic_config):
        """
        Verify:
        1. Session A indexes a fact.
        2. Session B cannot see Session A's fact by default.
        3. Session B CAN see Session A's fact via global search.
        """
        config = AgentConfig(
            model="llama3.2",
            enable_layered_memory=True,
            semantic_memory=semantic_config
        )
        
        # --- SESSION A ---
        with patch('cortex.core.providers.factory.ProviderFactory.get_provider'):
            agent_a = Cortex(config=config, project_dir=tmp_path)
            session_a_id = agent_a.state_manager.state.session_id
            
            # Index a fact in Session A
            agent_a.memory_bank.add_fact("The secret of Session A is 'APPLE-PIE'", source="user")
            
            # Wait for indexing
            time.sleep(0.5)
            
            # Verify retrieval within Session A
            res_a = agent_a.memory_bank.retrieve_semantic_context("secret", global_search=False)
            assert len(res_a) > 0
            assert "APPLE-PIE" in res_a[0]["document"]

        # --- SESSION B ---
        # Note: We reuse the same persistent directory (simulating a new run in same project)
        # We must set clear_on_init to False for Session B to keep Session A's data
        config.semantic_memory["clear_on_init"] = False
        
        with patch('cortex.core.providers.factory.ProviderFactory.get_provider'):
            agent_b = Cortex(config=config, project_dir=tmp_path)
            session_b_id = agent_b.state_manager.state.session_id
            
            assert session_a_id != session_b_id
            
            # Index a different fact in Session B
            agent_b.memory_bank.add_fact("The secret of Session B is 'BANANA-SPLIT'", source="user")
            time.sleep(0.5)
            
            # 1. Search in Session B for Session A's secret (should FAIL by default)
            res_b_local = agent_b.memory_bank.retrieve_semantic_context("APPLE-PIE", global_search=False)
            # It might find nothing, or only Session B things
            for r in res_b_local:
                assert "APPLE-PIE" not in r["document"]
                
            # 2. Search in Session B for Session B's secret (should PASS)
            res_b_self = agent_b.memory_bank.retrieve_semantic_context("BANANA-SPLIT", global_search=False)
            assert len(res_b_self) > 0
            assert "BANANA-SPLIT" in res_b_self[0]["document"]
            
            # 3. Search GLOBAL in Session B (should see BOTH)
            res_b_global = agent_b.memory_bank.retrieve_semantic_context("secret", global_search=True)
            # Find APPLE-PIE in global results
            global_docs = [r["document"] for r in res_b_global]
            assert any("APPLE-PIE" in d for d in global_docs)
            assert any("BANANA-SPLIT" in d for d in global_docs)
            
            # Verify session_id metadata in global results
            session_ids = [r["metadata"]["session_id"] for r in res_b_global]
            assert session_a_id in session_ids
            assert session_b_id in session_ids
