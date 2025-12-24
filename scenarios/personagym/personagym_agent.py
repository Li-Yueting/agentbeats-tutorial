"""
PersonaGym White Agent - Persona-conditioned agent that answers questions.

This agent:
1. Receives questions from the green agent
2. Answers questions while staying strictly in character according to a persona
3. Returns direct text responses
"""

import argparse
import os
import traceback
import uvicorn
from dotenv import load_dotenv
from loguru import logger
from openai import AsyncOpenAI
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

load_dotenv()


# ---------------------------
# Agent Card
# ---------------------------

def prepare_agent_card(url: str, persona: str) -> AgentCard:
    """Create the agent card for the PersonaGym white agent."""
    skill = AgentSkill(
        id="persona_qa",
        name="Persona Question Answering",
        description="Answers questions while staying strictly in character according to a persona",
        tags=["benchmark", "personagym"],
        examples=[],
    )
    return AgentCard(
        name="personagym_white_agent",
        description=f"PersonaGym white agent: {persona[:100]}...",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(),
        skills=[skill],
    )


# ---------------------------
# White Agent Logic
# ---------------------------

class WhiteAgent:
    """White agent that answers questions while staying in character."""

    def __init__(self, persona: str, model: str):
        self.persona = persona
        self.model = model
        self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    async def invoke(self, question: str) -> str:
        """Answer a question while staying in character."""
        try:
            system_prompt = (
                f"You are acting as: {self.persona}. "
                "You must answer the following question while staying strictly in character."
            )
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.0,
            )
            return completion.choices[0].message.content or "Error: Empty response from LLM."
        except Exception as e:
            logger.error(f"ERROR calling OpenAI: {e}")
            return f"Error calling OpenAI: {str(e)}"


# ---------------------------
# Agent Executor
# ---------------------------

class WhiteAgentExecutor(AgentExecutor):
    """Executor for the PersonaGym white agent."""

    def __init__(self, persona: str, model: str):
        self.persona = persona
        self.model = model
        logger.info(f"White Agent Executor Initialized. Persona: '{self.persona[:50]}...'")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute the agent logic to answer a question."""
        try:
            question_text = context.get_user_input()
            
            if not question_text:
                error_msg = "Error: No question text was provided in the request."
                logger.error(error_msg)
                await event_queue.enqueue_event(new_agent_text_message(error_msg))
                return

            logger.info(f"White Agent: Received question: '{question_text[:100]}...'")

            agent_logic = WhiteAgent(persona=self.persona, model=self.model)
            
            logger.info("White Agent: Awaiting response from OpenAI...")
            result = await agent_logic.invoke(question_text)
            
            logger.info(f"White Agent: Received answer. Sending: '{result[:100]}...'")
            await event_queue.enqueue_event(
                new_agent_text_message(result, context_id=context.context_id)
            )

        except Exception as e:
            tb_str = traceback.format_exc()
            error_message = f"WHITE AGENT CRASHED:\n{e}\n\nTRACEBACK:\n{tb_str}"
            logger.error(error_message)
            await event_queue.enqueue_event(new_agent_text_message(error_message))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancellation not supported.")


# ---------------------------
# Profile Endpoint
# ---------------------------

async def get_profile(request, persona: str):
    """Return agent profile/metadata."""
    try:
        metadata = {
            "persona_description": persona,
        }
        return JSONResponse(metadata)
    except Exception as e:
        logger.error(f"ERROR reading profile: {e}")
        return JSONResponse({"error": "Could not load agent profile."}, status_code=500)


# ---------------------------
# Main Entrypoint
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Run the PersonaGym white agent.")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=8001, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL for the agent card"
    )
    parser.add_argument(
        "--agent-llm", type=str, default="gpt-4o-mini", help="LLM model to use"
    )
    parser.add_argument(
        "--persona",
        type=str,
        default="A 29-year-old Muslim woman from Malaysia, working as a software developer and advocating for women in STEM fields",
        help="Persona description for the agent",
    )
    args = parser.parse_args()

    logger.info("Starting PersonaGym White Agent...")

    card_url = args.card_url or f"http://{args.host}:{args.port}/"
    card = prepare_agent_card(url=card_url, persona=args.persona)

    request_handler = DefaultRequestHandler(
        agent_executor=WhiteAgentExecutor(persona=args.persona, model=args.agent_llm),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    # Add custom /profile endpoint
    app_instance = app.build()
    
    # Create a closure to capture persona for the profile endpoint
    async def profile_endpoint(request):
        return await get_profile(request, args.persona)
    
    app_instance.routes.append(
        Route("/profile", endpoint=profile_endpoint, methods=["GET"])
    )
    logger.info("Added custom /profile endpoint.")

    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(
        app_instance,
        host=args.host,
        port=args.port,
        timeout_keep_alive=300,
    )


if __name__ == "__main__":
    main()
