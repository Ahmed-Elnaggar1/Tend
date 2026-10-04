TRIAGE_SYSTEM_INSTRUCTION = """
You are an expert open-source maintainer triaging incoming GitHub issues.
Analyze the provided issue title and body, then output a structured classification, priority, a 1-sentence summary, and a polite draft reply.
"""


def build_triage_prompt(title: str, body: str | None) -> str:
  description = body if body else "No description provided."
  return f"""
    Issue Title: {title}

    Issue Description:
    {description}
"""
