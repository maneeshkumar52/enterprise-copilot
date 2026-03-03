"""Tests for user memory management."""
import pytest
import asyncio
from src.memory import UserMemoryManager, MEMORY_STORE
from src.models import UserMemory


@pytest.fixture(autouse=True)
def clear_memory():
    """Clear in-process memory store before each test."""
    MEMORY_STORE.clear()
    yield
    MEMORY_STORE.clear()


@pytest.mark.asyncio
async def test_get_context_returns_none_for_new_user():
    mgr = UserMemoryManager()
    result = await mgr.get_context("new-user", "tenant-test")
    assert result is None


@pytest.mark.asyncio
async def test_update_memory_creates_entry():
    mgr = UserMemoryManager()
    memory = await mgr.update_memory("user-001", "tenant-test", "How do I apply for parental leave?", "You can apply by...")
    assert memory.user_id == "user-001"
    assert memory.tenant_id == "tenant-test"
    assert len(memory.recent_queries) == 1
    assert "How do I apply for parental leave?" in memory.recent_queries


@pytest.mark.asyncio
async def test_memory_tracks_topic_frequency():
    mgr = UserMemoryManager()
    await mgr.update_memory("user-001", "tenant-test", "What are the leave policies?", "Response 1")
    await mgr.update_memory("user-001", "tenant-test", "What are the leave entitlements?", "Response 2")
    memory = await mgr.get_context("user-001", "tenant-test")
    assert "leave" in memory.topic_frequencies
    assert memory.topic_frequencies["leave"] >= 2


@pytest.mark.asyncio
async def test_memory_tenant_isolation():
    mgr = UserMemoryManager()
    await mgr.update_memory("user-001", "tenant-a", "Question for tenant A", "Answer A")
    await mgr.update_memory("user-001", "tenant-b", "Question for tenant B", "Answer B")
    memory_a = await mgr.get_context("user-001", "tenant-a")
    memory_b = await mgr.get_context("user-001", "tenant-b")
    assert memory_a is not None
    assert memory_b is not None
    assert memory_a.recent_queries[0] != memory_b.recent_queries[0]


@pytest.mark.asyncio
async def test_memory_keeps_last_10_queries():
    mgr = UserMemoryManager()
    for i in range(15):
        await mgr.update_memory("user-001", "tenant-test", f"Query number {i}", f"Response {i}")
    memory = await mgr.get_context("user-001", "tenant-test")
    assert len(memory.recent_queries) <= 10


@pytest.mark.asyncio
async def test_create_test_token():
    from src.auth import create_test_token, get_current_user
    token = create_test_token("user-t1-001")
    user = get_current_user(f"Bearer {token}")
    assert user.user_id == "user-t1-001"
    assert user.tenant_id == "tenant-contoso"
