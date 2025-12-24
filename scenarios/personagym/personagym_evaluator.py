"""
PersonaGym Evaluator - Green agent that evaluates white agents using PersonaGym.

This evaluator:
1. Gets the persona from the white agent's /profile endpoint
2. Generates questions appropriate for the persona
3. Sends questions to the white agent and collects answers
4. Scores the answers based on persona consistency and quality
"""
import argparse
import asyncio
import json
import logging
import time
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DataPart,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message

from agentbeats.client import send_message
from agentbeats.green_executor import GreenAgent, GreenExecutor
from agentbeats.models import EvalRequest

logging.basicConfig(level=logging.INFO)


# Default tasks for PersonaGym evaluation
DEFAULT_TASKS = [
    "Expected Action",
    "Action Justification",
    "Linguistic Habits",
    "Persona Consistency",
    "Toxicity",
]


class PersonaGymEvaluator(GreenAgent):
    """Green agent that evaluates white agents using PersonaGym framework."""

    def __init__(self):
        self._required_roles = ["agent"]  # The white agent being tested
        self._required_config_keys = []  # No required config keys

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        """Validate the evaluation request."""
        missing_roles = set(self._required_roles) - set(request.participants.keys())
        if missing_roles:
            return False, f"Missing roles: {missing_roles}"
        return True, "ok"

    async def run_eval(self, req: EvalRequest, updater: TaskUpdater) -> None:
        """Run the PersonaGym evaluation."""
        logger.info(f"Starting PersonaGym evaluation: {req}")
        start_time = time.time()

        # Get the white agent URL
        white_agent_url = str(req.participants["agent"])
        num_questions = req.config.get("num_questions", 4)
        domain = req.config.get("domain", "general")

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                f"Starting PersonaGym evaluation of agent at {white_agent_url}"
            ),
        )

        try:
            # Step 1: Get persona from white agent
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("Fetching persona from white agent..."),
            )
            persona = await self._get_persona_from_profile(white_agent_url)
            logger.info(f"Discovered persona: '{persona[:80]}...'")

            if persona.startswith("Error"):
                raise ValueError(f"Failed to get persona: {persona}")

            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"Persona: {persona[:100]}..."),
            )

            # Step 2: Generate questions
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("Generating evaluation questions..."),
            )
            questions = self._generate_questions(persona, num_questions, domain)
            logger.info(f"Generated {len(questions)} questions")

            # Step 3: Ask questions and collect answers
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"Asking {len(questions)} questions..."),
            )
            qa_pairs = await self._ask_questions(white_agent_url, questions)
            logger.info(f"Collected {len(qa_pairs)} answers")

            # Step 4: Score answers
            await updater.update_status(
                TaskState.working,
                new_agent_text_message("Scoring answers..."),
            )
            scores = self._score_answers(persona, qa_pairs)

            # Step 5: Calculate final metrics
            time_used = time.time() - start_time
            persona_score = scores.get("overall_score", 0.0)
            per_task_scores = scores.get("per_task_scores", {})

            result_data = {
                "persona": persona,
                "persona_score": persona_score,
                "per_task_scores": per_task_scores,
                "num_questions": len(questions),
                "time_used": time_used,
            }

            # Format results for display
            task_results_str = "\n".join(
                f"  {task}: {score:.2f}" for task, score in per_task_scores.items()
            )

            summary = f"""PersonaGym Evaluation Results
Persona: {persona[:100]}...
Overall Score: {persona_score:.2f}/5.0
Questions: {len(questions)}
Time: {time_used:.1f}s

Task Scores:
{task_results_str}"""

            await updater.add_artifact(
                parts=[
                    Part(root=TextPart(text=summary)),
                    Part(root=DataPart(data=result_data)),
                ],
                name="Result",
            )

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            await updater.failed(
                new_agent_text_message(f"Evaluation failed: {str(e)}")
            )
            raise

    async def _get_persona_from_profile(self, white_agent_url: str) -> str:
        """Get the persona description from the white agent's /profile endpoint."""
        profile_url = f"{white_agent_url.rstrip('/')}/profile"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(profile_url)
                response.raise_for_status()
                profile_json = response.json()
                return profile_json.get(
                    "persona_description", "Error: Persona description not found."
                )
        except httpx.RequestError as exc:
            logger.error(f"HTTP request failed: {exc}")
            return f"Error: Failed to connect to White Agent at {profile_url}"
        except Exception as e:
            logger.error(f"Failed to get persona: {e}")
            return "Error: Could not retrieve persona."

    def _generate_questions(
        self, persona: str, num_questions: int, domain: str
    ) -> list[dict]:
        """Generate evaluation questions for the persona."""
        # Simplified question generation
        # In full implementation, this would use LLM-based generation or templates
        questions = []
        question_templates = [
            "How would you introduce yourself?",
            "What is your professional background?",
            "How do you typically approach problem-solving?",
            "What are your key strengths?",
            "Describe a challenging situation you've handled.",
        ]

        for i in range(min(num_questions, len(question_templates))):
            questions.append(
                {
                    "task": DEFAULT_TASKS[i % len(DEFAULT_TASKS)],
                    "question": question_templates[i],
                }
            )

        return questions

    async def _ask_questions(
        self, white_agent_url: str, questions: list[dict]
    ) -> list[dict]:
        """Ask questions to the white agent and collect answers."""
        qa_pairs = []
        context_id = None

        for i, q_data in enumerate(questions):
            question = q_data["question"]
            task = q_data["task"]
            logger.info(f"Asking question {i+1}/{len(questions)}: {question[:50]}...")

            try:
                result = await send_message(
                    message=question,
                    base_url=white_agent_url,
                    context_id=context_id,
                )
                answer = result.get("response", "Error: No response")
                context_id = result.get("context_id", context_id)

                qa_pairs.append(
                    {
                        "task": task,
                        "question": question,
                        "answer": answer,
                    }
                )
                logger.info(f"Received answer: {answer[:100]}...")

            except Exception as e:
                logger.error(f"Failed to get answer for question {i+1}: {e}")
                qa_pairs.append(
                    {
                        "task": task,
                        "question": question,
                        "answer": f"Error: {str(e)}",
                    }
                )

        return qa_pairs

    def _score_answers(self, persona: str, qa_pairs: list[dict]) -> dict:
        """Score the answers based on persona consistency and quality."""
        # Simplified scoring - in full implementation, this would use LLM-based rubric scoring
        per_task_scores = {}
        task_counts = {}

        for qa in qa_pairs:
            task = qa["task"]
            answer = qa["answer"]

            # Simple heuristic scoring (0-5 scale)
            # In full implementation, this would use LLM-based rubric evaluation
            if answer.startswith("Error"):
                score = 0.0
            else:
                # Basic scoring: check if answer is reasonable length and not empty
                score = min(5.0, max(1.0, len(answer) / 50.0))

            if task not in per_task_scores:
                per_task_scores[task] = 0.0
                task_counts[task] = 0
            per_task_scores[task] += score
            task_counts[task] += 1

        # Average scores per task
        for task in per_task_scores:
            if task_counts[task] > 0:
                per_task_scores[task] = per_task_scores[task] / task_counts[task]

        # Calculate overall score
        if per_task_scores:
            overall_score = sum(per_task_scores.values()) / len(per_task_scores)
        else:
            overall_score = 0.0

        return {
            "overall_score": overall_score,
            "per_task_scores": per_task_scores,
        }


def personagym_evaluator_agent_card(name: str, url: str) -> AgentCard:
    """Create the agent card for the PersonaGym evaluator."""
    skill = AgentSkill(
        id="personagym_evaluation",
        name="PersonaGym Evaluation",
        description="Evaluates white agents on persona consistency and quality using PersonaGym framework",
        tags=["benchmark", "evaluation", "personagym"],
        examples=[
            '{"participants": {"agent": "http://localhost:8001"}, "config": {"num_questions": 4, "domain": "general"}}'
        ],
    )
    return AgentCard(
        name=name,
        description="PersonaGym evaluator - tests agents on persona consistency and quality",
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


async def main():
    parser = argparse.ArgumentParser(description="Run the PersonaGym evaluator agent.")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=9009, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL for the agent card"
    )
    args = parser.parse_args()

    agent_url = args.card_url or f"http://{args.host}:{args.port}/"

    agent = PersonaGymEvaluator()
    executor = GreenExecutor(agent)
    agent_card = personagym_evaluator_agent_card("PersonaGymEvaluator", agent_url)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    uvicorn_config = uvicorn.Config(server.build(), host=args.host, port=args.port)
    uvicorn_server = uvicorn.Server(uvicorn_config)
    await uvicorn_server.serve()


if __name__ == "__main__":
    asyncio.run(main())

