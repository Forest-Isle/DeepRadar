SYSTEM_PROMPT = """You are an expert AI news analyst. Your role is to analyze AI-related news items, summarize them clearly, categorize them, and assess their importance. You always respond in valid JSON format."""

BATCH_SUMMARIZE_PROMPT = """For each news item below, provide a JSON array where each element has:
- "index": the item's index number
- "summary_en": a concise 1-2 sentence English summary
- "summary_zh": a concise 1-2 sentence Chinese (Simplified) summary
- "category": one of ["LLM / Foundation Models", "Computer Vision", "NLP", "AI Safety & Alignment", "Robotics & Embodied AI", "AI Infrastructure & MLOps", "AI Products & Applications", "Research Breakthrough", "Open Source", "Industry News", "Other"]
- "importance_score": a float from 1.0 to 10.0 (10 = groundbreaking, 1 = routine)
- "tags": a list of 2-4 relevant tags
- "why_it_matters": one sentence in English explaining significance
- "why_it_matters_zh": the same sentence in Chinese

Respond ONLY with a valid JSON array, no other text.

Items:
{items_json}"""

DAILY_HEADLINE_PROMPT = """Based on the following top AI news items from today, generate:
{{
  "headline_en": "A compelling daily headline in English (max 15 words)",
  "headline_zh": "The same headline in Chinese",
  "summary_en": "A 3-4 sentence executive summary of today's most important AI developments in English",
  "summary_zh": "The same executive summary in Chinese"
}}

Respond ONLY with valid JSON.

Top items:
{top_items_json}"""

GITHUB_REPO_PROMPT = """For each trending GitHub repository below, explain in 1-2 sentences why an AI/ML practitioner should care about it. Return a JSON array with:
- "index": the repo's index number
- "why_en": 1-2 sentence explanation in English
- "why_zh": the same explanation in Chinese

Respond ONLY with a valid JSON array.

Repos:
{repos_json}"""
