#!/usr/bin/env python3
"""
Simple test script to verify the personagym white agent is working locally.
"""
import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentbeats.client import send_message


async def test_agent(base_url: str = "http://127.0.0.1:8001"):
    """Test the personagym white agent."""
    print(f"Testing agent at {base_url}...")
    print("-" * 50)
    
    # Test 1: Check /profile endpoint
    print("\n1. Testing /profile endpoint...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/profile")
            if response.status_code == 200:
                profile = response.json()
                print(f"✓ Profile endpoint works!")
                print(f"  Persona: {profile.get('persona_description', 'N/A')[:80]}...")
            else:
                print(f"✗ Profile endpoint returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Failed to connect to /profile: {e}")
        print("  Make sure the agent is running!")
        return False
    
    # Test 2: Check agent card (A2A endpoint)
    print("\n2. Testing A2A agent card...")
    try:
        from a2a.client import A2ACardResolver
        async with httpx.AsyncClient(timeout=10.0) as client:
            resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
            card = await resolver.get_agent_card()
            print(f"✓ Agent card retrieved!")
            print(f"  Name: {card.name}")
            print(f"  Description: {card.description[:80]}...")
    except Exception as e:
        print(f"✗ Failed to get agent card: {e}")
        return False
    
    # Test 3: Send a test question
    print("\n3. Testing message sending...")
    try:
        test_question = "What is your role and how do you help users?"
        print(f"  Sending question: '{test_question}'")
        result = await send_message(
            message=test_question,
            base_url=base_url,
            streaming=False
        )
        if result.get("response"):
            print(f"✓ Received response!")
            print(f"  Response: {result['response'][:200]}...")
            if result.get("context_id"):
                print(f"  Context ID: {result['context_id']}")
        else:
            print(f"✗ No response received")
            return False
    except Exception as e:
        print(f"✗ Failed to send message: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed! The agent is working correctly.")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test the personagym white agent")
    parser.add_argument(
        "--url",
        type=str,
        default="http://127.0.0.1:8001",
        help="Base URL of the agent (default: http://127.0.0.1:8001)"
    )
    args = parser.parse_args()
    
    success = asyncio.run(test_agent(args.url))
    sys.exit(0 if success else 1)

