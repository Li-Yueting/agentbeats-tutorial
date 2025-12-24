# PersonaGym Scenario

This scenario evaluates white agents on persona consistency and quality using the PersonaGym framework.

## Setup

1. **Set your API key** in `.env`:
   ```
   OPENAI_API_KEY=your-key-here
   ```

## Testing Methods

### Method 1: Automated Testing (Recommended)

Run the full evaluation using the scenario runner:

```bash
uv run agentbeats-run scenarios/personagym/scenario.toml --show-logs
```

This will:
- Start the white agent (personagym_agent.py) on port 8001
- Start the green agent (personagym_evaluator.py) on port 9009
- Run the evaluation automatically
- Show logs from both agents

**Options:**
- `--show-logs`: See agent outputs during evaluation
- `--serve-only`: Start agents but don't run evaluation (for manual testing)

### Method 2: Manual Testing (Step by Step)

#### Step 1: Start the White Agent

In Terminal 1:
```bash
uv run scenarios/personagym/personagym_agent.py \
  --host 127.0.0.1 \
  --port 8001 \
  --persona "A polite and professional customer service agent."
```

Verify it's running:
```bash
curl http://127.0.0.1:8001/profile
```

#### Step 2: Start the Green Agent (Evaluator)

In Terminal 2:
```bash
uv run scenarios/personagym/personagym_evaluator.py \
  --host 127.0.0.1 \
  --port 9009
```

Verify it's running:
```bash
curl http://127.0.0.1:9009/
```

#### Step 3: Run the Evaluation

In Terminal 3:
```bash
cd /Users/yuetingli/Documents/Course/CS294/RDI-agentbeats-tutorial
uv run python -c "
import asyncio
from src.agentbeats.client import send_message

async def test():
    eval_request = {
        'participants': {'agent': 'http://127.0.0.1:8001'},
        'config': {'num_questions': 4, 'domain': 'general'}
    }
    import json
    result = await send_message(
        message=json.dumps(eval_request),
        base_url='http://127.0.0.1:9009'
    )
    print(result['response'])

asyncio.run(test())
"
```

### Method 3: Individual Component Testing

#### Test White Agent Only

```bash
# Start the white agent
uv run scenarios/personagym/personagym_agent.py \
  --host 127.0.0.1 \
  --port 8001 \
  --persona "A helpful software engineer."

# In another terminal, test it
uv run scenarios/personagym/test_agent.py --url http://127.0.0.1:8001
```

#### Test Green Agent Only

The green agent needs a white agent to evaluate. Use Method 2 above.

## Configuration

Edit `scenario.toml` to configure the evaluation:

```toml
[config]
domain = "general"        # Evaluation domain
num_questions = 4        # Number of questions to ask
```

## Expected Output

When running successfully, you should see:

1. **White Agent logs:**
   - "Starting PersonaGym White Agent..."
   - "White Agent Executor Initialized. Persona: '...'"
   - "White Agent: Received question: '...'"
   - "White Agent: Received answer. Sending: '...'"

2. **Green Agent logs:**
   - "Starting PersonaGym evaluation..."
   - "Fetching persona from white agent..."
   - "Generating evaluation questions..."
   - "Asking N questions..."
   - "Scoring answers..."

3. **Final Results:**
   - PersonaGym Evaluation Results
   - Overall Score (0-5.0)
   - Per-task scores
   - Time used

## Troubleshooting

### Port Already in Use
If you get "port already in use" errors:
- Check what's using the port: `lsof -i :8001` or `lsof -i :9009`
- Kill the process or use different ports

### White Agent Not Responding
- Check if the white agent is running: `curl http://127.0.0.1:8001/profile`
- Check logs for errors
- Verify OPENAI_API_KEY is set

### Green Agent Can't Connect
- Ensure white agent is running first
- Check the endpoint URL matches in scenario.toml
- Verify both agents are on the same network (localhost)

## Architecture

- **personagym_evaluator.py** (Green Agent): Evaluates white agents on persona consistency
- **personagym_agent.py** (White Agent): The agent being tested - answers questions while staying in character

