"""10-line LLM hello world — confirms the Anthropic key + quota work.

Owner: Jerry. Run:  ANTHROPIC_API_KEY=sk-ant-... python hello_llm.py
Raises AuthenticationError on a bad key, RateLimitError if out of quota.
"""
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
resp = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=256,
    messages=[{"role": "user", "content": "Reply with one sentence confirming the JESKers car recommender LLM is online."}],
)
print(resp.content[0].text)
print(f"[ok] model={resp.model}  tokens in={resp.usage.input_tokens} out={resp.usage.output_tokens}")
