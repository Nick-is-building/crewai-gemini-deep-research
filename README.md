# 🔬 CrewAI Gemini Deep Research Tool

A native **CrewAI BaseTool** that wraps Google's **Gemini Deep Research Agent**, the most powerful autonomous web research API available today.

**Drop it into any existing CrewAI pipeline. No MCP servers, no framework changes, no async headaches.**

## The Problem

Google's Gemini Deep Research Agent autonomously searches the web, reads and cross-references sources, and returns detailed Markdown reports with inline citations. But it runs exclusively on the **Interactions API**, a completely different, asynchronous API surface that is incompatible with CrewAI's synchronous tool model.

This tool bridges that gap.

## What It Does

- **Async-to-sync bridging**: Handles the entire `background=True`, polling, and result extraction lifecycle inside CrewAI's `_run()` method
- **Cost protection**: `max_usage_count=2` prevents runaway API calls
- **Hard timeout**: 30-minute default prevents infinite polling loops
- **Clean auth isolation**: Uses explicit API key, no conflicts with Vertex AI ADC credentials
- **Breaking Change ready**: Updated for the May 2026 `outputs[]` to `steps[]` migration, with backward-compatible fallback

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
    max_iter=3,              # Low: each call takes minutes
    max_execution_time=3600, # 60 min: must exceed tool timeout
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

That's it. The agent calls the tool, the tool handles the multi-minute Deep Research cycle in the background, and returns a full Markdown report with inline citations.

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

| Model | Use Case | Speed |
|-------|----------|-------|
| `deep-research-preview-04-2026` (default) | Interactive research, user-facing | 3-15 min |
| `deep-research-max-preview-04-2026` | Background batch jobs, due diligence | 10-40 min |

## Cost Awareness

Deep Research runs on **Gemini 3.1 Pro** at standard API rates. There is no additional markup for the agent layer. The key pricing components (as of May 2026, from [Google's official pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)):

| Component | Rate |
|-----------|------|
| Gemini 3.1 Pro input tokens | $2.00 / 1M tokens |
| Gemini 3.1 Pro output tokens | $12.00 / 1M tokens |
| Google Search grounding (Gemini 3.x) | $14.00 / 1K queries |
| Long context (>200K tokens) | 2x standard rates |

Actual cost per Deep Research call depends on the complexity of your query and how many search iterations the agent performs. The `max_usage_count` parameter is your primary cost control. At default settings, a single agent can make at most 2 Deep Research calls per task.

For the latest pricing, always check [Google's official pricing page](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing).

## Multi-Agent Pipeline Tips

When using this tool across multiple agents in a sequential pipeline:

**Set `max_iter=3` on research agents.** Each Deep Research call is expensive. Two calls per agent (controlled by `max_usage_count=2`) is the sweet spot: first call broad, second call targeted.

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

## Why Is This Synchronous?

By design. CrewAI's tool execution model is synchronous. When an agent calls a tool, it waits for the result. Every built-in CrewAI tool works this way, including SerperDevTool, ScrapeWebsiteTool, and others that make network requests. This tool follows the same pattern.

If you need to run multiple Deep Research calls in parallel (for example, a pipeline with six research agents), the recommended architecture is to use CrewAI Flows to launch concurrent research tasks before feeding results into a sequential analysis crew. This keeps the tool simple and the parallelism where it belongs: at the orchestration layer, not inside the tool.

For web applications serving multiple users, wrap your crew execution in a background worker (Celery, `asyncio.to_thread`, or a task queue). This is standard practice for any long-running CrewAI pipeline, not specific to this tool.

## How It Works Under the Hood

```
Agent calls tool._run(query)
         |
         v
   POST interactions.create(background=True)
         |
         v
   Receive interaction_id immediately
         |
         v
   Poll loop (every 15s)
   - GET interactions.get(id)
   - Status: in_progress?    -> continue polling
   - Status: completed?      -> extract report from steps[-1]
   - Status: failed?         -> return error message
   - Timeout reached?        -> return timeout message
         |
         v
   Return Markdown report to agent
```

## Authentication Note

Deep Research requires a **Google AI Studio API key**. It is NOT available on Vertex AI (as of May 2026). If you're already using Vertex AI for your LLM (via ADC), this tool keeps the two auth paths cleanly separated. Your Vertex AI agents use ADC, the Deep Research tool uses the explicit API key. No conflicts.

## Requirements

- Python 3.10+
- CrewAI 0.80+
- `google-genai` 1.55.0+
- A Gemini API key ([get one here](https://aistudio.google.com/apikey))

## License

MIT

---

Built by a solo developer who needed Gemini Deep Research in CrewAI and couldn't find it anywhere. So I built it.
