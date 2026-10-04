"""Long-term memory: what is allowed in, how duplicates are handled, and how entries are ranked.

The contract: store decisions, conventions, explicit facts and summaries of solved problems.
Do not store the user's raw requests, repeated failures or "file operation" noise. Writing the
same fact twice leaves one record. Confidence and recency decay is computed when reading (no
background job), and a verified fact outranks an older unverified one of equal similarity.
"""

from datetime import datetime, timedelta

import pytest

from cortex.core.memory.contract import should_index
from cortex.core.memory.core_memory import MemoryItem, MemorySource, MemoryType
from cortex.core.memory.embeddings import LocalEmbeddingModel
from cortex.core.memory.semantic import ChromaMemoryManager, content_id
from cortex.core.memory_layers.session import EnhancedMemoryBank

pytestmark = pytest.mark.usefixtures("stub_sentence_transformers")

NOW = datetime(2026, 6, 1, 12, 0, 0)


def item(kind, content="the project uses pytest for tests", source=MemorySource.INFERRED, **meta):
    return MemoryItem(type=kind, content=content, source=source, metadata=meta)


# ---- what may be stored ------------------------------------------------------------------


@pytest.mark.parametrize("kind", [MemoryType.DECISION, MemoryType.PREFERENCE, MemoryType.FACT])
def test_decisions_conventions_and_facts_are_stored(kind):
    assert should_index(item(kind)) is True


@pytest.mark.parametrize("kind", [MemoryType.ERROR, MemoryType.FILE])
def test_raw_errors_and_file_references_are_not_stored(kind):
    assert should_index(item(kind)) is False


@pytest.mark.parametrize(
    "marker",
    ["goal_set", "session_insight", "progress_marker", "context_summary", "failed_approach"],
)
def test_the_sessions_own_bookkeeping_is_not_stored(marker):
    assert should_index(item(MemoryType.CONTEXT, **{marker: True})) is False
    assert should_index(item(MemoryType.FACT, **{marker: True})) is False


def test_a_summary_of_a_solved_problem_is_stored():
    assert should_index(item(MemoryType.CONTEXT, synthetic=True)) is True
    assert should_index(item(MemoryType.CONTEXT, solved_problem=True)) is True


def test_plain_context_is_not_stored():
    assert should_index(item(MemoryType.CONTEXT)) is False


def test_something_the_user_asked_to_remember_is_always_stored():
    assert should_index(item(MemoryType.CONTEXT, remembered=True)) is True


def test_transient_facts_are_not_stored_even_if_they_are_facts():
    assert should_index(item(MemoryType.FACT, transient=True)) is False


def test_trivially_short_content_is_not_stored():
    assert should_index(item(MemoryType.FACT, content="ok")) is False


# ---- the vector store --------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return ChromaMemoryManager(
        persist_directory=tmp_path / "db",
        collection_name="contract",
        embedding_model=LocalEmbeddingModel(),
    )


def meta(**overrides):
    base = {
        "type": "fact",
        "source": "inferred",
        "confidence": 0.8,
        "session_id": "s1",
        "last_verified": NOW.isoformat(),
    }
    base.update(overrides)
    return base


def test_the_same_fact_written_twice_is_one_record(store):
    first = store.add_document("Use black with line length 100", meta())
    second = store.add_document("Use black with line length 100", meta())

    assert first == second
    assert store.count() == 1


def test_case_and_spacing_do_not_make_a_fact_new(store):
    store.add_document("Use black with line length 100", meta())
    store.add_document("  use BLACK  with line   length 100 ", meta())

    assert store.count() == 1
    assert content_id("Use black") == content_id("  use   BLACK ")


def test_a_different_fact_is_a_different_record(store):
    store.add_document("Use black with line length 100", meta())
    store.add_document("Run the tests with pytest -x", meta())

    assert store.count() == 2


def test_rewriting_a_fact_keeps_its_history_and_raises_its_confidence(store):
    doc_id = store.add_document(
        "Use black with line length 100",
        meta(created=(NOW - timedelta(days=40)).isoformat(), confidence=0.6),
    )
    store.add_document("Use black with line length 100", meta(confidence=0.9))

    record = store.get_document(doc_id)
    assert record["metadata"]["created"] == (NOW - timedelta(days=40)).isoformat()
    assert record["metadata"]["times_seen"] == 2
    assert record["metadata"]["confidence"] == 0.9


def test_a_lower_confidence_rewrite_does_not_weaken_a_fact(store):
    doc_id = store.add_document("Use black with line length 100", meta(confidence=0.9))
    store.add_document("Use black with line length 100", meta(confidence=0.3))

    assert store.get_document(doc_id)["metadata"]["confidence"] == 0.9


# ---- ranking -----------------------------------------------------------------------------


def test_a_verified_fact_outranks_an_older_unverified_one_of_equal_similarity(store):
    # same words in a different order: identical embeddings, so equal similarity
    old = store.add_document(
        "alpha beta gamma delta",
        meta(last_verified=(NOW - timedelta(days=90)).isoformat()),
    )
    verified = store.add_document("delta gamma beta alpha", meta(last_verified=NOW.isoformat()))

    results = store.search_documents("alpha beta gamma delta", top_k=2, now=NOW)

    assert [r["id"] for r in results] == [verified, old]
    assert results[0]["similarity"] == pytest.approx(results[1]["similarity"], abs=1e-6)
    assert results[0]["score"] > results[1]["score"]


def test_higher_confidence_ranks_first_when_everything_else_is_equal(store):
    low = store.add_document("alpha beta gamma delta", meta(confidence=0.3))
    high = store.add_document("delta gamma beta alpha", meta(confidence=0.95))

    results = store.search_documents("alpha beta gamma delta", top_k=2, now=NOW)

    assert [r["id"] for r in results] == [high, low]


def test_similarity_still_matters_most(store):
    relevant_but_old = store.add_document(
        "database connection pool settings",
        meta(last_verified=(NOW - timedelta(days=120)).isoformat(), confidence=0.6),
    )
    store.add_document("lunch menu on friday", meta(confidence=1.0))

    results = store.search_documents("database connection pool", top_k=2, now=NOW)

    assert results[0]["id"] == relevant_but_old


def test_explicit_user_instructions_do_not_fade(store):
    stated = store.add_document(
        "alpha beta gamma delta",
        meta(source="user", last_verified=(NOW - timedelta(days=365)).isoformat()),
    )
    inferred = store.add_document(
        "delta gamma beta alpha",
        meta(source="inferred", last_verified=(NOW - timedelta(days=365)).isoformat()),
    )

    results = store.search_documents("alpha beta gamma delta", top_k=2, now=NOW)

    assert [r["id"] for r in results] == [stated, inferred]


def test_decay_is_computed_when_reading_and_never_written_back(store):
    doc_id = store.add_document(
        "alpha beta gamma delta", meta(last_verified=(NOW - timedelta(days=60)).isoformat())
    )
    before = store.get_document(doc_id)["metadata"]

    store.search_documents("alpha beta", top_k=1, now=NOW + timedelta(days=500))

    assert store.get_document(doc_id)["metadata"] == before


def test_the_same_entry_scores_lower_as_time_passes(store):
    store.add_document("alpha beta gamma delta", meta())

    soon = store.search_documents("alpha beta gamma delta", now=NOW)[0]["score"]
    later = store.search_documents("alpha beta gamma delta", now=NOW + timedelta(days=200))[0][
        "score"
    ]

    assert later < soon


# ---- verification ------------------------------------------------------------------------


def test_verifying_a_fact_raises_confidence_and_resets_its_age(store):
    doc_id = store.add_document(
        "the config lives in config.yaml",
        meta(confidence=0.7, last_verified=(NOW - timedelta(days=50)).isoformat()),
    )

    assert store.verify(doc_id, success=True, now=NOW) is True

    updated = store.get_document(doc_id)["metadata"]
    assert updated["confidence"] == pytest.approx(0.8)
    assert updated["last_verified"] == NOW.isoformat()


def test_a_failed_check_lowers_confidence_but_not_below_the_floor(store):
    doc_id = store.add_document("the config lives in config.yaml", meta(confidence=0.5))

    store.verify(doc_id, success=False, now=NOW)
    assert store.get_document(doc_id)["metadata"]["confidence"] == pytest.approx(0.2)
    store.verify(doc_id, success=False, now=NOW)
    assert store.get_document(doc_id)["metadata"]["confidence"] == pytest.approx(0.1)


def test_verifying_an_unknown_id_is_reported(store):
    assert store.verify("mem_does_not_exist", success=True) is False


def test_verify_matching_updates_every_record_that_mentions_the_text(store):
    a = store.add_document("settings are read from config.yaml at start", meta(confidence=0.5))
    b = store.add_document("config.yaml must stay valid yaml", meta(confidence=0.5))
    other = store.add_document("deploys run from the main branch", meta(confidence=0.5))

    assert store.verify_matching("config.yaml", success=True, now=NOW) == 2

    assert store.get_document(a)["metadata"]["confidence"] == pytest.approx(0.6)
    assert store.get_document(b)["metadata"]["confidence"] == pytest.approx(0.6)
    assert store.get_document(other)["metadata"]["confidence"] == pytest.approx(0.5)


# ---- listing and editing -----------------------------------------------------------------


def test_list_documents_shows_the_most_recently_verified_first(store):
    old = store.add_document(
        "an old fact", meta(last_verified=(NOW - timedelta(days=30)).isoformat())
    )
    new = store.add_document("a new fact", meta(last_verified=NOW.isoformat()))

    assert [d["id"] for d in store.list_documents()] == [new, old]


def test_editing_a_memory_replaces_its_text_and_keeps_its_history(store):
    for _ in range(4):  # seen four times
        original = store.add_document(
            "use tabs for indentation", meta(created=(NOW - timedelta(days=10)).isoformat())
        )

    edited = store.update_document(original, "use four spaces for indentation", now=NOW)

    assert edited != original
    assert store.get_document(original) is None
    record = store.get_document(edited)
    assert record["document"] == "use four spaces for indentation"
    assert record["metadata"]["created"] == (NOW - timedelta(days=10)).isoformat()
    assert record["metadata"]["times_seen"] == 4
    assert record["metadata"]["last_verified"] == NOW.isoformat()
    assert store.count() == 1


def test_editing_a_memory_into_one_that_already_exists_merges_them(store):
    first = store.add_document("use four spaces for indentation", meta())
    second = store.add_document("use tabs for indentation", meta())

    result = store.update_document(second, "use four spaces for indentation", now=NOW)

    assert result == first
    assert store.count() == 1


def test_a_memory_can_be_deleted(store):
    doc_id = store.add_document("something to forget", meta())

    store.delete_document(doc_id)

    assert store.get_document(doc_id) is None
    assert store.count() == 0


# ---- the session memory bank applies the contract ----------------------------------------


@pytest.fixture
def bank(tmp_path):
    return EnhancedMemoryBank(
        semantic_config={
            "enabled": True,
            "persist_directory": str(tmp_path / "bank_db"),
            "collection_name": "bank",
        },
        session_id="s1",
    )


def test_the_users_raw_request_is_not_stored_as_a_memory(bank):
    bank.add(
        MemoryItem(
            type=MemoryType.CONTEXT,
            content="Primary goal set: fix the login bug",
            source=MemorySource.USER,
            metadata={"goal_set": True},
        )
    )

    assert bank.semantic_manager.count() == 0


def test_a_failed_tool_call_is_not_stored_in_long_term_memory(bank):
    bank.record_failed_approach("Tool: read_file", "execution: not found")

    assert bank.semantic_manager.count() == 0
    assert len(bank.failed_approaches) == 1  # still available for this session


def test_repeating_the_same_failure_is_counted_not_listed_again(bank):
    for _ in range(3):
        bank.record_failed_approach("Tool: read_file", "execution: not found")

    assert len(bank.failed_approaches) == 1
    assert bank.failed_approaches[0].occurrences == 3


def test_file_operations_are_not_recorded_as_patterns(bank):
    bank.extract_learnings_from_tool_results(
        [
            {"success": True, "tool_name": "read_file", "data": {"path": "a.py"}},
            {"success": True, "tool_name": "grep", "data": {"matches": [1], "match_count": 1}},
        ]
    )

    assert bank.successful_patterns == []


def test_a_reflection_on_solved_work_is_stored_once(bank):
    result = {
        "success": True,
        "tool_name": "metacognitive_reflect",
        "data": {"synthetic_experience": {"task": "fix bug", "insight": "check imports first"}},
    }

    bank.extract_learnings_from_tool_results([result])
    bank.extract_learnings_from_tool_results([result])

    assert bank.semantic_manager.count() == 1


def test_a_decision_is_stored_and_a_repeat_adds_nothing(bank):
    bank.add_decision("Use SQLAlchemy for all database access")
    bank.add_decision("Use SQLAlchemy for all database access")

    assert bank.semantic_manager.count() == 1
