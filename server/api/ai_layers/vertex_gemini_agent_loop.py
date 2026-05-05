"""
Vertex AI Gemini agent loop: multi-turn ``generate_content`` with function calling.

Implements :class:`BaseAgentLoop` using the same ``AgentTool`` definitions as
:class:`OpenAIAgentLoop`. Stored ``messages`` include synthetic OpenAI-shaped
``function_call`` / ``function_call_output`` dicts so
:func:`api.ai_layers.serializers.extract_tool_calls_from_messages` works unchanged.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from pydantic import BaseModel

from api.ai_layers.agent_loop import (
    ERROR,
    ITERATION_START,
    LOOP_START,
    RESPONSE,
    TOOL_CALL_END,
    TOOL_CALL_START,
    AgentLoopResult,
    AgentProvider,
    AgentTool,
    BaseAgentLoop,
    CancelledError,
    ToolCallRecord,
    _extract_json_from_text,
    _is_pydantic_class,
    _serialize_tool_result,
)
from api.utils.vertex_gemini_text import (
    VertexGeminiText,
    _extract_text_from_response,
    _openai_style_messages_to_contents,
    _usage_to_dict,
)

logger = logging.getLogger(__name__)


def _merge_usage(acc: dict[str, int], usage_metadata: Any) -> None:
    d = _usage_to_dict(usage_metadata)
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        acc[k] = acc.get(k, 0) + d.get(k, 0)


def _fc_args_to_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            out = json.loads(raw)
            return out if isinstance(out, dict) else {}
        except json.JSONDecodeError:
            return {}
    if hasattr(raw, "items"):
        try:
            return dict(raw.items())
        except Exception:
            pass
    return {}


class VertexGeminiAgentLoop(BaseAgentLoop):
    """Agent loop using Vertex Gemini ``generate_content`` with tools."""

    def __init__(
        self,
        tools: list[AgentTool],
        instructions: str,
        model: str,
        output_schema: type[BaseModel] | None = None,
        max_iterations: int = 10,
        on_event: Callable[[str, dict], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ):
        self.instructions = instructions
        self.model = model
        self.output_schema = output_schema
        self.max_iterations = max_iterations
        self.on_event = on_event
        self.check_cancelled = check_cancelled

        self.tool_functions: dict[str, Callable] = {}
        self.tool_param_models: dict[str, type[BaseModel] | None] = {}
        self._tool_specs: list[dict[str, Any]] = []

        for tool in tools:
            self._register_tool(tool)

    @property
    def provider(self) -> AgentProvider:
        return "google"

    def _register_tool(self, tool: AgentTool) -> None:
        name = tool["name"]
        description = tool["description"]
        parameters = tool["parameters"]
        func = tool["function"]

        if _is_pydantic_class(parameters):
            schema = parameters.model_json_schema()
            self.tool_param_models[name] = parameters
        elif isinstance(parameters, dict):
            schema = dict(parameters)
            self.tool_param_models[name] = None
        else:
            raise TypeError(
                f"Tool '{name}' parameters must be a Pydantic BaseModel class "
                f"or a JSON Schema dict, got {type(parameters)}"
            )

        self._tool_specs.append(
            {
                "name": name,
                "description": description,
                "parameters_json_schema": schema,
            }
        )
        self.tool_functions[name] = func

    def _emit(self, event_type: str, data: dict) -> None:
        if self.on_event is not None:
            try:
                self.on_event(event_type, data)
            except Exception as e:
                logger.warning("on_event callback failed for %s: %s", event_type, e)

    def _parse_output(self, text: str) -> BaseModel | str:
        if self.output_schema is None:
            return text
        try:
            json_data = _extract_json_from_text(text)
            return self.output_schema.model_validate(json_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "VertexGeminiAgentLoop: structured output parse failed (%s); returning raw text",
                e,
            )
            return text

    def _execute_tool(
        self,
        tool_name: str,
        parsed_args: dict[str, Any],
        iteration: int,
    ) -> ToolCallRecord:
        self._emit(
            TOOL_CALL_START,
            {
                "tool_name": tool_name,
                "arguments": parsed_args,
                "iteration": iteration,
            },
        )

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

        self._emit(
            TOOL_CALL_END,
            {
                "tool_name": tool_name,
                "duration": duration,
                "result_length": len(result_str),
                "error": record.get("error"),
                "iteration": iteration,
            },
        )

        logger.info(
            "Tool %s completed in %.2fs (result_length=%d)",
            tool_name,
            duration,
            len(result_str),
        )

        return record

    def _function_response_payload(self, result_str: str) -> dict[str, Any]:
        try:
            parsed = json.loads(result_str)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {"result": result_str}

    def run(self, inputs: list[Any]) -> AgentLoopResult:
        """
        Run the agent loop. *inputs* must be ``[{"role","content"}, ...]`` items
        (same shape as :func:`api.ai_layers.tasks._build_agent_loop_inputs`).
        """
        self._emit(
            LOOP_START,
            {"model": self.model, "max_iterations": self.max_iterations},
        )

        if not inputs or not isinstance(inputs, list):
            raise ValueError(
                "run(inputs=...) requires a non-empty list of input messages"
            )

        vx = VertexGeminiText()
        try:
            from google.genai import types as genai_types

            contents = _openai_style_messages_to_contents(
                [dict(x) for x in inputs],
                genai_types=genai_types,
            )

            trace: list[dict[str, Any]] = [dict(x) for x in inputs]
            tool_call_log: list[ToolCallRecord] = []
            total_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

            gemini_tools = None
            if self._tool_specs:
                declarations = [
                    genai_types.FunctionDeclaration(
                        name=spec["name"],
                        description=spec["description"],
                        parameters_json_schema=spec["parameters_json_schema"],
                    )
                    for spec in self._tool_specs
                ]
                gemini_tools = [
                    genai_types.Tool(function_declarations=declarations),
                ]

            client = vx._get_client()
            iteration = 0

            while iteration < self.max_iterations:
                if self.check_cancelled and self.check_cancelled():
                    logger.info(
                        "Iteration %d: Loop cancelled by check_cancelled",
                        iteration,
                    )
                    self._emit(ERROR, {"error": "Cancelled", "iteration": iteration})
                    raise CancelledError("Agent loop was cancelled")

                iteration += 1
                self._emit(ITERATION_START, {"iteration": iteration})

                cfg_kwargs: dict[str, Any] = {}
                if iteration == 1:
                    cfg_kwargs["system_instruction"] = self.instructions
                if gemini_tools:
                    cfg_kwargs["tools"] = gemini_tools
                    cfg_kwargs["tool_config"] = genai_types.ToolConfig(
                        function_calling_config=genai_types.FunctionCallingConfig(
                            mode=genai_types.FunctionCallingConfigMode.AUTO,
                        )
                    )

                config = genai_types.GenerateContentConfig(**cfg_kwargs)

                try:
                    response = client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                except Exception as e:
                    self._emit(ERROR, {"error": str(e), "iteration": iteration})
                    raise

                _merge_usage(total_usage, getattr(response, "usage_metadata", None))

                if not response.candidates:
                    logger.warning("Iteration %d: no candidates", iteration)
                    continue

                cand = response.candidates[0]
                if not cand.content or not cand.content.parts:
                    logger.warning("Iteration %d: empty content", iteration)
                    continue

                parts = list(cand.content.parts)
                function_calls = [
                    p.function_call
                    for p in parts
                    if getattr(p, "function_call", None) is not None
                ]

                if function_calls:
                    contents.append(cand.content)

                    for fc in function_calls:
                        if self.check_cancelled and self.check_cancelled():
                            self._emit(
                                ERROR,
                                {"error": "Cancelled", "iteration": iteration},
                            )
                            raise CancelledError("Agent loop was cancelled")

                        tool_name = getattr(fc, "name", "") or "unknown"
                        parsed_args = _fc_args_to_dict(getattr(fc, "args", None))
                        call_id = getattr(fc, "id", None) or getattr(
                            fc, "_id", None
                        )
                        if not call_id:
                            call_id = f"call_{iteration}_{tool_name}_{len(tool_call_log)}"

                        record = self._execute_tool(
                            tool_name, parsed_args, iteration
                        )
                        tool_call_log.append(record)

                        args_for_trace = parsed_args
                        try:
                            args_trace = json.loads(
                                json.dumps(args_for_trace, default=str)
                            )
                        except Exception:
                            args_trace = args_for_trace

                        trace.append(
                            {
                                "type": "function_call",
                                "name": tool_name,
                                "arguments": args_trace,
                                "call_id": call_id,
                            }
                        )
                        trace.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": record.get("result", ""),
                            }
                        )

                        payload = self._function_response_payload(
                            record.get("result", "")
                        )
                        fr_kw: dict[str, Any] = {
                            "name": tool_name,
                            "response": payload,
                        }
                        if call_id:
                            fr_kw["id"] = str(call_id)
                        fr = genai_types.FunctionResponse(**fr_kw)
                        contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[genai_types.Part(function_response=fr)],
                            )
                        )

                    continue

                text = _extract_text_from_response(response)
                if text:
                    trace.append({"role": "assistant", "content": text})
                    output = self._parse_output(text)
                    self._emit(
                        RESPONSE,
                        {"output": str(output), "iterations": iteration},
                    )
                    return AgentLoopResult(
                        output=output,
                        messages=trace,
                        iterations=iteration,
                        tool_calls=tool_call_log,
                        usage=total_usage,
                    )

                logger.warning(
                    "Iteration %d: no tool calls and no text output",
                    iteration,
                )

            self._emit(
                ERROR,
                {"error": "Max iterations reached", "iterations": iteration},
            )
            raise ValueError(
                f"Agent failed to produce a response after {self.max_iterations} iterations"
            )
        finally:
            vx.close()
