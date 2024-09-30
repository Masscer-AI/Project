from .models import Conversation, Message
from openai import OpenAI


def create_completion_ollama(
    system_prompt, user_message, model="llama3.1", max_tokens=3000
):
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="llama3")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def generate_conversation_title(conversation_id: str):
    system = """
    Given some conversation messages, please generate a title related to the conversation. The title must have an emoji at the end.

    The title must be a plain string without double quotes and the start or end.

    Return ONLY the title with the emoji please bro
    """
    c = Conversation.objects.get(id=conversation_id)

    messages = c.messages.order_by("created_at")[:2]
    formatted_messages = []
    for message in messages:
        role = "AI" if message.type == "assistant" else "User"
        formatted_messages.append(f"{role}: {message.text}")

    user_message = "\n".join(formatted_messages)

    title = create_completion_ollama(system, user_message, max_tokens=100)

    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]

    c.title = title
    c.save()
    return True
