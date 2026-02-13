"""
Reusable agent loop for OpenAI function calling with the Responses API.

Handles the conversation flow with tool execution, optional structured output
parsing via Pydantic, and an on_event callback for real-time notifications.

Usage:
    from api.ai_layers.agent_loop import AgentLoop, make_notifier

    loop = AgentLoop(
        tools=[...],
        instructions="You are a helpful assistant.",
        model="gpt-4o",
        output_schema=MyResponseModel,       # optional Pydantic model
        on_event=make_notifier(user_id=42),   # optional real-time callback
    )
    result = loop.run("Hello, what can you do?")
    print(result.output)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AgentTool(TypedDict, total=False):
    """
    Tool definition for the agent loop.

    - name: unique tool name (used by OpenAI to reference it)
    - description: human-readable description shown to the model
    - parameters: either a Pydantic BaseModel *class* or a raw JSON Schema dict
    - function: the Python callable to invoke when the tool is called
    """

    name: str               # required
    description: str        # required
    parameters: Any         # type[BaseModel] | dict — required
    function: Callable      # required


class ToolCallRecord(TypedDict, total=False):
    """Record of a single tool execution for logging/inspection."""

    tool_name: str
    arguments: dict
    result: str
    duration: float
    iteration: int
    error: str | None


@dataclass
class AgentLoopResult:
    """
    Result returned by AgentLoop.run().

    - output: parsed Pydantic model if output_schema was provided, else raw string
    - messages: full conversation history (for inspection/logging)
    - iterations: how many loop iterations ran
    - tool_calls: log of every tool execution that happened
    """

    output: BaseModel | str
    messages: list[dict]
    iterations: int
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

LOOP_START = "loop_start"
ITERATION_START = "iteration_start"
TOOL_CALL_START = "tool_call_start"
TOOL_CALL_END = "tool_call_end"
RESPONSE = "response"
ERROR = "error"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_pydantic_class(obj: Any) -> bool:
    """Check if obj is a Pydantic BaseModel *class* (not instance)."""
    return isinstance(obj, type) and issubclass(obj, BaseModel)


def _add_additional_properties_false(schema_obj: dict) -> None:
    """
    Recursively add additionalProperties: false to all object schemas.
    Required for OpenAI strict mode.
    """
    if not isinstance(schema_obj, dict):
        return

    if schema_obj.get("type") == "object":
        schema_obj["additionalProperties"] = False
        # For strict mode all properties must be listed in required
        if "properties" in schema_obj:
            schema_obj["required"] = list(schema_obj["properties"].keys())

    for key, value in schema_obj.items():
        if key == "properties" and isinstance(value, dict):
            for prop_schema in value.values():
                _add_additional_properties_false(prop_schema)
        elif key == "items" and isinstance(value, dict):
            _add_additional_properties_false(value)
        elif key == "$defs" and isinstance(value, dict):
            for def_schema in value.values():
                _add_additional_properties_false(def_schema)
        elif key == "anyOf" and isinstance(value, list):
            for item in value:
                _add_additional_properties_false(item)


def _to_dict(obj: Any) -> Any:
    """
    Safely convert an OpenAI SDK Pydantic model to a plain dict.

    This avoids the ``by_alias: NoneType cannot be converted to PyBool``
    error that occurs in certain pydantic/pydantic-core versions when
    the SDK re-serialises its own output objects.
    """
    if isinstance(obj, dict):
        return obj
    # OpenAI SDK >=1.x objects expose to_dict()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    # Pydantic v2 model_dump — no kwargs to dodge the by_alias bug
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Last resort: json round-trip
    if hasattr(obj, "model_dump_json"):
        try:
            return json.loads(obj.model_dump_json())
        except Exception:
            pass
    return obj


def _serialize_tool_result(result: Any) -> str:
    """Serialize a tool function's return value to a string for OpenAI."""
    if result is None:
        return '{"result": null}'
    if isinstance(result, str):
        return result
    if isinstance(result, BaseModel):
        return json.dumps(result.model_dump(), default=str)
    if isinstance(result, dict):
        return json.dumps(result, default=str)
    # Fallback
    return json.dumps({"result": str(result)}, default=str)


def _extract_output_text(response) -> str:
    """Extract text content from an OpenAI Responses API response object."""
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text.strip()

    chunks = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") == "message":
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") in ("output_text", "text"):
                    text = getattr(content, "text", "")
                    if text:
                        chunks.append(text)
    return "".join(chunks).strip()


def _extract_json_from_text(text: str) -> dict:
    """Parse JSON from text, handling markdown code fences."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty response received for structured output")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if "```" in raw:
            for part in raw.split("```"):
                candidate = part.replace("json", "", 1).strip()
                if not candidate:
                    continue
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise


# ---------------------------------------------------------------------------
# Notifier helper
# ---------------------------------------------------------------------------

def make_notifier(user_id: int) -> Callable[[str, dict], None]:
    """
    Convenience factory: returns an on_event callback that pushes events
    to the frontend via Redis pub/sub -> streaming server -> Socket.IO.

    Usage:
        loop = AgentLoop(..., on_event=make_notifier(user_id=42))
    """
    def _on_event(event_type: str, data: dict) -> None:
        from api.notify.actions import notify_user
        notify_user(user_id, f"agent_{event_type}", data)

    return _on_event


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------

class AgentLoop:
    """
    Reusable agent loop for function calling using OpenAI Responses API.

    Handles the conversation flow with tool execution and optional
    structured output parsing.
    """

    def __init__(
        self,
        tools: list[AgentTool],
        instructions: str,
        model: str = "gpt-4o",
        output_schema: type[BaseModel] | None = None,
        max_iterations: int = 10,
        on_event: Callable[[str, dict], None] | None = None,
        api_key: str | None = None,
    ):
        self.instructions = instructions
        self.model = model
        self.output_schema = output_schema
        self.max_iterations = max_iterations
        self.on_event = on_event

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=resolved_key)

        # Process tools: separate OpenAI definitions from callable functions
        self.tool_definitions: list[dict] = []
        self.tool_functions: dict[str, Callable] = {}
        self.tool_param_models: dict[str, type[BaseModel] | None] = {}

        for tool in tools:
            self._register_tool(tool)

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tool(self, tool: AgentTool) -> None:
        """Process a single AgentTool and register it."""
        name = tool["name"]
        description = tool["description"]
        parameters = tool["parameters"]
        func = tool["function"]

        # Resolve parameters: Pydantic class or raw dict
        if _is_pydantic_class(parameters):
            schema = parameters.model_json_schema()
            self.tool_param_models[name] = parameters
        elif isinstance(parameters, dict):
            schema = dict(parameters)  # copy
            self.tool_param_models[name] = None
        else:
            raise TypeError(
                f"Tool '{name}' parameters must be a Pydantic BaseModel class "
                f"or a JSON Schema dict, got {type(parameters)}"
            )

        # Inject additionalProperties: false for strict mode
        _add_additional_properties_false(schema)

        definition = {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": schema,
            "strict": True,
        }

        self.tool_definitions.append(definition)
        self.tool_functions[name] = func

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, user_message: str) -> AgentLoopResult:
        """
        Run the agent loop.

        Args:
            user_message: the user's input message

        Returns:
            AgentLoopResult with the final output, conversation history,
            iteration count, and tool call log.

        Raises:
            ValueError: if the agent fails to produce output within max_iterations
        """
        self._emit(LOOP_START, {"model": self.model, "max_iterations": self.max_iterations})

        messages: list[Any] = [
            {"role": "user", "content": user_message},
        ]
        tool_call_log: list[ToolCallRecord] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            self._emit(ITERATION_START, {"iteration": iteration})

            # --- Call OpenAI ---
            try:
                response = self.client.responses.create(
                    model=self.model,
                    instructions=self.instructions,
                    input=messages,
                    tools=self.tool_definitions if self.tool_definitions else None,
                    tool_choice="auto" if self.tool_definitions else None,
                )
            except Exception as e:
                self._emit(ERROR, {"error": str(e), "iteration": iteration})
                raise

            # --- Process response output items ---
            tool_calls_found = []
            message_outputs = []

            if hasattr(response, "output") and response.output:
                for output_item in response.output:
                    item_type = getattr(output_item, "type", None)
                    if item_type == "function_call":
                        tool_calls_found.append(output_item)
                    elif item_type == "message":
                        message_outputs.append(output_item)
                    # Convert to plain dict to avoid Pydantic serialization
                    # issues (by_alias bug) when items are fed back to the SDK
                    messages.append(_to_dict(output_item))

            # --- Tool calls: execute and loop ---
            if tool_calls_found:
                logger.info(
                    "Iteration %d: %d tool call(s) requested",
                    iteration, len(tool_calls_found),
                )

                for tool_call in tool_calls_found:
                    record = self._execute_tool_call(tool_call, iteration)
                    tool_call_log.append(record)

                    # Feed result back to the model
                    messages.append({
                        "type": "function_call_output",
                        "call_id": getattr(tool_call, "call_id", f"call_{record['tool_name']}"),
                        "output": record.get("result", ""),
                    })

                continue  # next iteration

            # --- No tool calls: extract final response ---
            text = _extract_output_text(response)

            if text:
                output = self._parse_output(text)
                self._emit(RESPONSE, {
                    "output": str(output),
                    "iterations": iteration,
                })
                return AgentLoopResult(
                    output=output,
                    messages=messages,
                    iterations=iteration,
                    tool_calls=tool_call_log,
                )

            # No text and no tool calls — unusual, keep going
            logger.warning("Iteration %d: no tool calls and no text output", iteration)

        # Exhausted iterations
        self._emit(ERROR, {"error": "Max iterations reached", "iterations": iteration})
        raise ValueError(
            f"Agent failed to produce a response after {self.max_iterations} iterations"
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool_call(self, tool_call: Any, iteration: int) -> ToolCallRecord:
        """Execute a single tool call and return a record."""
        tool_name = getattr(tool_call, "name", "unknown")
        raw_arguments = getattr(tool_call, "arguments", "{}")

        # Parse arguments
        if isinstance(raw_arguments, str):
            try:
                parsed_args = json.loads(raw_arguments)
            except json.JSONDecodeError:
                parsed_args = {}
        else:
            parsed_args = raw_arguments

        self._emit(TOOL_CALL_START, {
            "tool_name": tool_name,
            "arguments": parsed_args,
            "iteration": iteration,
        })

        record: ToolCallRecord = {
            "tool_name": tool_name,
            "arguments": parsed_args,
            "iteration": iteration,
            "error": None,
        }

        start = time.time()
        try:
            if tool_name not in self.tool_functions:
                raise ValueError(f"Unknown tool: {tool_name}")

            func = self.tool_functions[tool_name]

            # If we have a Pydantic model for params, validate first
            param_model = self.tool_param_models.get(tool_name)
            if param_model is not None:
                validated = param_model(**parsed_args)
                result = func(**validated.model_dump())
            else:
                result = func(**parsed_args)

            result_str = _serialize_tool_result(result)
            record["result"] = result_str

        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, str(e))
            result_str = json.dumps({"error": f"Tool execution failed: {str(e)}"})
            record["result"] = result_str
            record["error"] = str(e)

        duration = time.time() - start
        record["duration"] = duration

        self._emit(TOOL_CALL_END, {
            "tool_name": tool_name,
            "duration": duration,
            "result_length": len(result_str),
            "error": record.get("error"),
            "iteration": iteration,
        })

        logger.info(
            "Tool %s completed in %.2fs (result_length=%d)",
            tool_name, duration, len(result_str),
        )

        return record

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def _parse_output(self, text: str) -> BaseModel | str:
        """Parse the final text into output_schema if provided, else raw string."""
        if self.output_schema is None:
            return text

        # Try direct JSON parsing first
        try:
            json_data = _extract_json_from_text(text)
            return self.output_schema.model_validate(json_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.info("Direct JSON parse failed (%s), trying AI-assisted parse", e)

        # Fallback: use a cheap model to parse into the schema
        try:
            schema = self.output_schema.model_json_schema()
            text_format = {
                "type": "json_schema",
                "name": self.output_schema.__name__,
                "schema": schema,
                "strict": True,
            }
            parse_response = self.client.responses.create(
                model="gpt-4o-mini",
                instructions=(
                    "Parse the following response into the required JSON format. "
                    "Do not change the wording, simply extract and structure the information."
                ),
                input=text,
                text={"format": text_format},
            )
            parsed_text = _extract_output_text(parse_response)
            json_data = _extract_json_from_text(parsed_text)
            return self.output_schema.model_validate(json_data)
        except Exception as parse_error:
            logger.error("AI-assisted parse failed: %s", parse_error)
            # Return raw text as last resort
            return text

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data: dict) -> None:
        """Emit an event via the on_event callback if one is registered."""
        if self.on_event is not None:
            try:
                self.on_event(event_type, data)
            except Exception as e:
                logger.warning("on_event callback failed for %s: %s", event_type, e)
