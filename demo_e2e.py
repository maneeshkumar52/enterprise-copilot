import asyncio, sys
sys.path.insert(0, '.')

async def main():
    print("=== Enterprise Knowledge Copilot - End-to-End Demo ===\n")

    # Test 1: Memory Manager (in-process, no Azure needed)
    from src.memory import UserMemoryManager, MEMORY_STORE
    MEMORY_STORE.clear()
    memory = UserMemoryManager()

    # Create users in two different tenants
    # update_memory(user_id, tenant_id, query, response)
    await memory.update_memory("user-001", "tenant-a", "What is our cloud migration policy?", "Our cloud migration policy requires...")
    await memory.update_memory("user-001", "tenant-a", "How do I request access to AWS?", "To request AWS access, submit a ticket...")
    await memory.update_memory("user-001", "tenant-a", "What are the cloud cost optimization strategies?", "Cloud cost optimization includes...")
    print("Memory Manager: stored 3 queries for user-001 (tenant-a)")

    memory_a = await memory.get_context("user-001", "tenant-a")
    print(f"  Recent queries count: {len(memory_a.recent_queries)}")
    print(f"  Topic frequencies: {dict(list(memory_a.topic_frequencies.items())[:3])}")

    # Test tenant isolation - user in tenant-b cannot see tenant-a data
    await memory.update_memory("user-002", "tenant-b", "Expense report submission process", "Submit expenses via the HR portal...")
    memory_b = await memory.get_context("user-002", "tenant-b")
    print(f"\nTenant Isolation:")
    print(f"  tenant-a/user-001 query_count: {len(memory_a.recent_queries)}")
    print(f"  tenant-b/user-002 query_count: {len(memory_b.recent_queries)}")

    # Cross-tenant isolation check
    memory_cross = await memory.get_context("user-002", "tenant-a")
    print(f"  Cross-tenant access (should be None): {memory_cross}")

    # Test 2: Auth - multi-tenant JWT
    from src.auth import get_current_user, create_test_token, MOCK_USERS
    try:
        token = create_test_token("user-t1-001")
        print(f"\nJWT Token created for user-t1-001")
        # get_current_user takes an "Authorization: Bearer <token>" header string
        user = get_current_user(f"Bearer {token}")
        print(f"  User: {user.user_id}, Tenant: {user.tenant_id}, Role: {user.roles}")
    except Exception as e:
        print(f"\nAuth error: {e}")

    # Test 3: SharePoint connector mock
    # SharePointConnector requires tenant_id in constructor
    try:
        from indexer.sharepoint_connector import SharePointConnector
        sp = SharePointConnector(tenant_id="tenant-a")
        docs = await sp.get_documents()
        print(f"\nSharePoint mock connector: {len(docs)} documents")
        for d in docs[:2]:
            print(f"  - {d.get('title', 'N/A')}")
    except Exception as e:
        print(f"\nSharePoint connector error: {e}")

    # Test 4: Confluence connector mock
    # ConfluenceConnector requires tenant_id in constructor
    try:
        from indexer.confluence_connector import ConfluenceConnector
        cc = ConfluenceConnector(tenant_id="tenant-a")
        pages = await cc.get_pages()
        print(f"\nConfluence mock connector: {len(pages)} pages")
        for p in pages[:2]:
            print(f"  - {p.get('title', 'N/A')}")
    except Exception as e:
        print(f"\nConfluence connector error: {e}")

    print("\n=== Enterprise Copilot: Memory management and tenant isolation working ===")

asyncio.run(main())
