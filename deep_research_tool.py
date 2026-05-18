# =============================================================================
# CrewAI Tool: Gemini Deep Research
# A native CrewAI BaseTool wrapper for Google's Gemini Deep Research API
#
# Solves: Gemini Deep Research runs on the async Interactions API with
#         background polling — incompatible with CrewAI's synchronous
#         tool model. This wrapper bridges that gap.
#
# Features:
#   - Automatic async-to-sync bridging (polling loop inside _run())
#   - Hard timeout protection (default: 30 min)
#   - Cost control via max_usage_count (default: 2 calls per task)
#   - Clean API key isolation (no ADC/Vertex AI conflicts)
#   - Updated for May 2026 Breaking Change (steps[] instead of outputs[])
#
# Usage:
#   from deep_research_tool import GeminiDeepResearchTool
#   tool = GeminiDeepResearchTool()
#   # Assign to any CrewAI agent:
#   agent = Agent(role="Researcher", tools=[tool], ...)
#
# Requirements:
#   pip install crewai google-genai pydantic python-dotenv
#
# Environment:
#   Set GEMINI_API_KEY from Google AI Studio (aistudio.google.com/apikey)
#   This is separate from Vertex AI credentials (ADC).
# =============================================================================

import os
import time
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from google import genai


class DeepResearchInput(BaseModel):
    """Input schema — what the agent passes to the tool."""
    query: str = Field(
        ...,
        description=(
            "The research question or topic to investigate thoroughly. "
            "Be specific: include company names, technologies, timeframes, "
            "and what kind of evidence you need. A precise query returns "
            "precise results."
        )
    )


class GeminiDeepResearchTool(BaseTool):
    """
    CrewAI tool that wraps Google's Gemini Deep Research Agent.

    Deep Research performs autonomous, multi-step web research (80-160 search
    queries per call) and returns a detailed Markdown report with inline
    citations. Each call takes 3-20 minutes.

    This tool handles the entire async lifecycle: starting the background
    research task, polling for completion, enforcing timeouts, and extracting
    the final report — all inside CrewAI's synchronous _run() method.
    """

    name: str = "Gemini Deep Research"
    description: str = (
        "Performs comprehensive, multi-step web research using Google's "
        "Gemini Deep Research agent. Returns a detailed Markdown report "
        "with citations. Takes 3-20 minutes per query. Use for complex "
        "research questions that require synthesizing information from "
        "many sources — NOT for simple fact lookups."
    )
    args_schema: Type[BaseModel] = DeepResearchInput

    # --- Configuration (all overridable at instantiation) ---
    api_key: str = Field(
        default_factory=lambda: os.environ.get("GEMINI_API_KEY", "")
    )
    agent_name: str = "deep-research-preview-04-2026"
    # Alternative: "deep-research-max-preview-04-2026" for maximum depth
    max_polling_time: int = 1800   # 30 minutes hard timeout
    polling_interval: int = 15     # Poll every 15 seconds
    max_usage_count: int = 2       # Max calls per task (cost protection)

    def _run(self, query: str) -> str:
        """
        Execute a Deep Research task synchronously.

        1. Validates API key
        2. Starts background research via Interactions API
        3. Polls until completed, failed, or timeout
        4. Extracts and returns the Markdown report
        """

        # --- Guard: API key check ---
        if not self.api_key:
            return (
                "Error: GEMINI_API_KEY is not set. "
                "Get your key at https://aistudio.google.com/apikey "
                "and set it as an environment variable."
            )

        # --- Client: explicit key, NOT from environment (avoids ADC conflict) ---
        client = genai.Client(api_key=self.api_key)

        # --- Step 1: Start research ---
        try:
            interaction = client.interactions.create(
                input=query,
                agent=self.agent_name,
                background=True
            )
            interaction_id = interaction.id
        except Exception as e:
            return f"Error starting Deep Research: {str(e)}"

        # --- Step 2: Poll for completion with hard timeout ---
        start_time = time.time()
        last_status = None

        while time.time() - start_time < self.max_polling_time:
            try:
                interaction = client.interactions.get(interaction_id)
            except Exception as e:
                return f"Error polling interaction {interaction_id}: {str(e)}"

            # Log status changes (visible in CrewAI verbose mode)
            if interaction.status != last_status:
                last_status = interaction.status

            if interaction.status == "completed":
                # --- Step 3: Extract report from steps array ---
                # (Updated for May 2026 Breaking Change: outputs[] → steps[])
                try:
                    report_text = interaction.steps[-1].content[0].text
                except (AttributeError, IndexError, TypeError):
                    # Fallback: try legacy format for backward compatibility
                    try:
                        report_text = interaction.outputs[-1].text
                    except (AttributeError, IndexError, TypeError):
                        return (
                            "Error: Could not extract report from API response. "
                            "The response structure may have changed. "
                            f"Interaction ID: {interaction_id}"
                        )

                elapsed = int(time.time() - start_time)
                return (
                    f"--- DEEP RESEARCH REPORT ---\n"
                    f"Query: {query}\n"
                    f"Completed in: {elapsed} seconds\n"
                    f"---\n\n"
                    f"{report_text}"
                )

            elif interaction.status == "failed":
                error_msg = getattr(interaction, "error", "Unknown error")
                return f"Deep Research failed for '{query}': {error_msg}"

            elif interaction.status == "cancelled":
                return f"Deep Research was cancelled for '{query}'."

            time.sleep(self.polling_interval)

        # --- Timeout reached ---
        return (
            f"Deep Research timed out after {self.max_polling_time} seconds "
            f"for query: '{query}'. The interaction {interaction_id} may still "
            f"be running on Google's servers. You can check its status manually "
            f"or retry with a more focused query."
        )
