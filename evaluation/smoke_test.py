from src.luna_api import call_structured

schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}

result, meta = call_structured(
    system_prompt="Return JSON with ok=true.",
    user_payload={"test": "ping"},
    json_schema=schema,
    max_output_tokens=50,
)

print(result)
print(meta)
