"""
OpenTelemetry GenAI Semantic Conventions attribute names.
Based on OTel GenAI SemConv v1.37+.
"""


class GenAIAttributes:
    # Agent identity
    AGENT_ID      = "gen_ai.agent.id"
    AGENT_NAME    = "gen_ai.agent.name"
    AGENT_VERSION = "gen_ai.agent.version"

    # Provider (anthropic | openai | aws.bedrock | google | hud | ...)
    PROVIDER_NAME = "gen_ai.provider.name"

    # LLM request
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_TYPE  = "gen_ai.request.type"

    # Token usage
    INPUT_TOKENS        = "gen_ai.usage.input_tokens"
    OUTPUT_TOKENS       = "gen_ai.usage.output_tokens"
    CACHE_READ_TOKENS   = "gen_ai.usage.cache_read_tokens"
    CACHE_CREATE_TOKENS = "gen_ai.usage.cache_creation_tokens"

    # Tool calls
    TOOL_NAME        = "gen_ai.tool.name"
    TOOL_DESCRIPTION = "gen_ai.tool.description"
    TOOL_INPUT       = "gen_ai.tool.input"
    TOOL_OUTPUT      = "gen_ai.tool.output"

    # Conversation / session continuity
    CONVERSATION_ID = "gen_ai.conversation.id"

    # Prompt / completion capture (off by default)
    PROMPT_CONTENT     = "gen_ai.prompt.content"
    COMPLETION_CONTENT = "gen_ai.completion.content"

    # Standard span names
    SPAN_INVOKE_AGENT = "invoke_agent"
    SPAN_CREATE_AGENT = "create_agent"
    SPAN_TOOL_CALL    = "gen_ai.tool.call"
    SPAN_LLM_CALL     = "gen_ai.llm.call"


class OcwAttributes:
    """ocw-specific span attributes (non-standard extensions)."""
    COST_USD         = "ocw.cost_usd"
    ALERT_TYPE       = "ocw.alert.type"
    ALERT_SEVERITY   = "ocw.alert.severity"
    # NemoClaw / OpenShell sandbox events
    SANDBOX_EVENT    = "ocw.sandbox.event"
    EGRESS_HOST      = "ocw.sandbox.egress_host"
    EGRESS_PORT      = "ocw.sandbox.egress_port"
    FILESYSTEM_PATH  = "ocw.sandbox.filesystem_path"
    SYSCALL_NAME     = "ocw.sandbox.syscall_name"
