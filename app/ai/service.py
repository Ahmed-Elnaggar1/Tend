import os 
from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.ai.prompts import TRIAGE_SYSTEM_INSTRUCTION, build_triage_prompt
from app.ai.schemas import TriageResult

load_dotenv()
MODEL_NAME = "gemini-flash-lite-latest"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def triage_issue_with_ai(title: str, body: str | None) -> TriageResult:
  prompt = build_triage_prompt(title, body)
  response = client.models.generate_content(
      model=MODEL_NAME,
      contents=prompt,
      config=types.GenerateContentConfig(
        system_instruction= TRIAGE_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=TriageResult,
      ),
  )

  if not response.text:
    raise RuntimeError("Empty response from AI model")
  return response.parsed

async def generate_embedding(text:str) -> list[float]:
    response = client.models.embed_content(
        model = "gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type = "SEMANTIC_SIMILARITY",
            output_dimensionality = 768,
        )
    )
    return response.embeddings[0].values

#   try:
#     return TriageResult.model_validate_json(response.text)
#   except ValidationError as e:
#     raise RuntimeError(f"Invalid AI response format: {e}") from e
