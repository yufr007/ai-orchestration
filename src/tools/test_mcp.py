"""Test MCP connections."""

import asyncio

from src.tools.perplexity import perplexity_search, perplexity_research


async def test_perplexity() -> None:
    """Test Perplexity MCP connection."""
    print("\n=== Testing Perplexity MCP ===")

    # Test simple search
    print("\n1. Testing simple search...")
    try:
        result = await perplexity_search("What is LangGraph?")
        print(f"  ✅ Search successful")
        print(f"  Answer: {result['answer'][:200]}...")
        print(f"  Citations: {len(result.get('citations', []))} sources")
    except Exception as e:
        print(f"  ❌ Search failed: {e}")

    # Test research
    print("\n2. Testing research mode...")
    try:
        result = await perplexity_research(
            "Python async best practices", ["error handling", "performance"]
        )
        print(f"  ✅ Research successful")
        print(f"  Length: {len(result)} characters")
    except Exception as e:
        print(f"  ❌ Research failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_perplexity())
