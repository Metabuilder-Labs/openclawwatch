import anthropic
from ocw.sdk import watch
from ocw.sdk.integrations.anthropic import patch_anthropic

# Intercept all Anthropic API calls
patch_anthropic()

@watch(agent_id="toy-agent")
def run(task: str) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{"role": "user", "content": task}]
    )
    return response.content[0].text

if __name__ == "__main__":
    result = run("What is 2 + 2? Answer in one sentence.")
    print(f"Agent said: {result}")