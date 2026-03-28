/**
 * OpenTelemetry GenAI Semantic Convention attribute names.
 * Mirrors ocw/otel/semconv.py — keep in sync.
 */
export declare const GenAIAttributes: {
    readonly AGENT_ID: "gen_ai.agent.id";
    readonly AGENT_NAME: "gen_ai.agent.name";
    readonly AGENT_VERSION: "gen_ai.agent.version";
    readonly PROVIDER_NAME: "gen_ai.provider.name";
    readonly REQUEST_MODEL: "gen_ai.request.model";
    readonly REQUEST_TYPE: "gen_ai.request.type";
    readonly INPUT_TOKENS: "gen_ai.usage.input_tokens";
    readonly OUTPUT_TOKENS: "gen_ai.usage.output_tokens";
    readonly CACHE_READ_TOKENS: "gen_ai.usage.cache_read_tokens";
    readonly CACHE_CREATE_TOKENS: "gen_ai.usage.cache_creation_tokens";
    readonly TOOL_NAME: "gen_ai.tool.name";
    readonly TOOL_DESCRIPTION: "gen_ai.tool.description";
    readonly TOOL_INPUT: "gen_ai.tool.input";
    readonly TOOL_OUTPUT: "gen_ai.tool.output";
    readonly CONVERSATION_ID: "gen_ai.conversation.id";
    readonly PROMPT_CONTENT: "gen_ai.prompt.content";
    readonly COMPLETION_CONTENT: "gen_ai.completion.content";
    readonly SPAN_INVOKE_AGENT: "invoke_agent";
    readonly SPAN_CREATE_AGENT: "create_agent";
    readonly SPAN_TOOL_CALL: "gen_ai.tool.call";
    readonly SPAN_LLM_CALL: "gen_ai.llm.call";
};
export declare const OcwAttributes: {
    readonly COST_USD: "ocw.cost_usd";
    readonly ALERT_TYPE: "ocw.alert.type";
    readonly ALERT_SEVERITY: "ocw.alert.severity";
    readonly SANDBOX_EVENT: "ocw.sandbox.event";
    readonly EGRESS_HOST: "ocw.sandbox.egress_host";
    readonly EGRESS_PORT: "ocw.sandbox.egress_port";
    readonly FILESYSTEM_PATH: "ocw.sandbox.filesystem_path";
    readonly SYSCALL_NAME: "ocw.sandbox.syscall_name";
};
