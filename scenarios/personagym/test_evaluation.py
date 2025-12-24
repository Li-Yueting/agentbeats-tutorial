#!/usr/bin/env python3
"""
Test script to run a PersonaGym evaluation manually.

This script sends an evaluation request to the green agent,
which will evaluate the white agent.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add the src directory to the path
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentbeats.client import send_message


async def test_evaluation(
    green_agent_url: str = "http://127.0.0.1:9009",
    white_agent_url: str = "http://127.0.0.1:8001",
    num_questions: int = 4,
):
    """Test the PersonaGym evaluation."""
    print("=" * 60)
    print("PersonaGym Evaluation Test")
    print("=" * 60)
    print(f"Green Agent (Evaluator): {green_agent_url}")
    print(f"White Agent (Agent): {white_agent_url}")
    print(f"Number of Questions: {num_questions}")
    print("-" * 60)

    # Create evaluation request
    eval_request = {
        "participants": {"agent": white_agent_url},
        "config": {
            "num_questions": num_questions,
            "domain": "general",
        },
    }

    print("\nSending evaluation request...")
    print(f"Request: {json.dumps(eval_request, indent=2)}")
    print("\n" + "-" * 60)

    try:
        result = await send_message(
            message=json.dumps(eval_request),
            base_url=green_agent_url,
            streaming=False,
        )

        print("\n" + "=" * 60)
        print("Evaluation Results:")
        print("=" * 60)
        print(result.get("response", "No response received"))

        if result.get("context_id"):
            print(f"\nContext ID: {result['context_id']}")

        return result

    except Exception as e:
        print(f"\n❌ Error during evaluation: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test PersonaGym evaluation between green and white agents"
    )
    parser.add_argument(
        "--green-url",
        type=str,
        default="http://127.0.0.1:9009",
        help="Green agent (evaluator) URL",
    )
    parser.add_argument(
        "--white-url",
        type=str,
        default="http://127.0.0.1:8001",
        help="White agent URL",
    )
    parser.add_argument(
        "--num-questions",
        type=int,
        default=4,
        help="Number of questions to ask",
    )
    args = parser.parse_args()

    print("\n⚠️  Make sure both agents are running:")
    print(f"   White Agent: {args.white_url}")
    print(f"   Green Agent: {args.green_url}")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)

    result = asyncio.run(
        test_evaluation(
            green_agent_url=args.green_url,
            white_agent_url=args.white_url,
            num_questions=args.num_questions,
        )
    )

    if result:
        print("\n✅ Evaluation completed!")
        sys.exit(0)
    else:
        print("\n❌ Evaluation failed!")
        sys.exit(1)

