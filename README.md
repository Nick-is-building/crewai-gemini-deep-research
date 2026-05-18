# 🔬 CrewAI Gemini Deep Research Tool

A native **CrewAI BaseTool** that wraps Google's **Gemini Deep Research Agent** — the most powerful autonomous web research API available today.

**Drop it into any existing CrewAI pipeline. No MCP servers, no framework changes, no async headaches.**

## The Problem

Google's Gemini Deep Research Agent performs 80–160 autonomous web searches and returns cited Markdown reports. But it runs exclusively on the **Interactions API** — a completely different, asynchronous API surface that is incompatible with CrewAI's synchronous tool model.

This tool bridges that gap.

## What It Does

- **Async-to-sync bridging**: Handles the entire `background=True` → polling → result extraction lifecycle inside CrewAI's `_run()` method
- **Cost protection**: `max_usage_count=2` prevents runaway API calls (each call costs $1–5)
- **Hard timeout**: 30-minute default prevents infinite polling loops
- **Clean auth isolation**: Uses explicit API key — no conflicts with Vertex AI ADC credentials
- **Breaking Change ready**: Updated for the May 2026 `outputs[]` → `steps[]` migration, with backward-compatible fallback

## Quick Start

### 1. Install dependencies

```bash
pip install crewai google-genai pydantic python-dotenv
```

### 2. Set your API key

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) and set it:

```bash
export GEMINI_API_KEY="your-key-here"
```

### 3. Use in your CrewAI pipeline

```python
from crewai import Agent, Task, Crew
from deep_research_tool import GeminiDeepResearchTool

# Initialize the tool
deep_research = GeminiDeepResearchTool()

# Give it to an agent
researcher = Agent(
    role="Senior Research Analyst",
    goal="Produce comprehensive research reports with verified sources",
    backstory="You are an expert analyst who uses deep research to investigate topics thoroughly.",
    tools=[deep_research],
    max_iter=3,              # Low — each call takes minutes and costs $1-5
    max_execution_time=3600, # 60 min — must exceed tool timeout
    verbose=True,
)

# Define a task
research_task = Task(
    description="Research the competitive landscape of solid-state batteries in 2026.",
    expected_output="A detailed research report with citations and data.",
    agent=researcher,
)

# Run
crew = Crew(agents=[researcher], tasks=[research_task])
result = crew.kickoff()
```

That's it. The agent calls the tool, the tool handles the 5–20 minute Deep Research cycle in the background, and returns a full Markdown report with inline citations.

## Configuration

All parameters are overridable at instantiation:

```python
tool = GeminiDeepResearchTool(
    api_key="your-key",                              # Or set GEMINI_API_KEY env var
    agent_name="deep-research-max-preview-04-2026",  # Use Max for deeper research
    max_polling_time=2400,                           # 40 min timeout
    polling_interval=20,                             # Poll every 20 sec
    max_usage_count=3,                               # Allow 3 calls per task
)
```

### Available Models

| Model | Use Case | Speed | Depth |
|-------|----------|-------|-------|
| `deep-research-preview-04-2026` (default) | Interactive research, user-facing | 3–15 min | ~80 searches |
| `deep-research-max-preview-04-2026` | Background batch jobs, due diligence | 10–40 min | ~160 searches |

## Multi-Agent Pipeline Tips

When using this tool across multiple agents in a sequential pipeline:

**Set `max_iter=3` on research agents.** Each Deep Research call is expensive. Two calls per agent (controlled by `max_usage_count=2`) is the sweet spot — first call broad, second call targeted.

**Set `max_execution_time=3600` on research agents.** This must exceed the tool's `max_polling_time` (default 1800s), or CrewAI will kill the agent mid-research.

**Keep audit/synthesis agents tool-free.** Agents that only analyze predecessor outputs don't need Deep Research. Removing the tool from these agents prevents accidental expensive calls and enforces clean separation between research and analysis.

**Guide the queries in your task descriptions.** Deep Research performs dramatically better with specific, structured queries. Include example query structures in your `tasks.yaml`:

```yaml
description: >
  Before calling the Deep Research Tool, formulate a precise query.
  Include: company name, technical architecture, compliance exposure,
  cloud providers, regulatory landscape.
  Example: "{company} technical infrastructure EU compliance GDPR 2026"
```

## How It Works Under the Hood

```
Agent calls tool._run(query)
         │
         ▼
   POST interactions.create(background=True)
         │
         ▼
   Receive interaction_id immediately
         │
         ▼
   ┌─── Poll loop (every 15s) ───┐
   │                              │
   │  GET interactions.get(id)    │
   │  Status: in_progress? ──────►│ (continue polling)
   │  Status: completed? ────────►│ Extract report from steps[-1]
   │  Status: failed? ──────────►│ Return error message
   │  Timeout reached? ─────────►│ Return timeout message
   └──────────────────────────────┘
         │
         ▼
   Return Markdown report to agent
```

## Authentication Note

Deep Research requires a **Google AI Studio API key** — it is NOT available on Vertex AI (as of May 2026). If you're already using Vertex AI for your LLM (via ADC), this tool keeps the two auth paths cleanly separated. Your Vertex AI agents use ADC, the Deep Research tool uses the explicit API key. No conflicts.

## Cost Awareness

| Scenario | Est. Cost |
|----------|-----------|
| Single research call (standard) | $1–3 |
| Single research call (Max) | $3–5 |
| 6-agent pipeline, 2 calls each | $15–30 |
| Your infra cost per call | ~$0.00 (runs on Google's servers) |

The `max_usage_count` parameter is your primary cost control. At default settings (2 calls per task), a single agent costs at most ~$6–10 for two Deep Research calls.

## Requirements

- Python 3.10+
- CrewAI 0.80+
- `google-genai` 1.55.0+
- A paid-tier Gemini API key ([get one here](https://aistudio.google.com/apikey))

## License

MIT — use it however you want.

---

Built by a solo developer who needed Gemini Deep Research in CrewAI and couldn't find it anywhere. So I built it.
