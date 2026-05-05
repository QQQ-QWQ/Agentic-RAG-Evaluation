# langchain_intro

> 来源: https://python.langchain.com/docs/introduction/
> 爬取时间: 2026-05-06 01:47

---

LangChain overview - Docs by LangChain
Skip to main content
Join us May 13th & May 14th at Interrupt, the Agent Conference by LangChain. 
Buy tickets >
Docs by LangChain home page
Open source
Search...
⌘K
Search...
Navigation
LangChain overview
Deep Agents
LangChain
LangGraph
Integrations
Learn
Reference
Contribute
Python
Overview
Get started
Install
Quickstart
Changelog
Philosophy
Core components
Agents
Models
Messages
Tools
Short-term memory
Streaming
Structured output
Middleware
Overview
Prebuilt middleware
Custom middleware
Frontend
Overview
Patterns
Integrations
Advanced usage
Guardrails
Runtime
Context engineering
Model Context Protocol (MCP)
Human-in-the-loop
Multi-agent
Retrieval
Long-term memory
Agent development
LangSmith Studio
Test
Agent Chat UI
Deploy with LangSmith
Deployment
Observability
On this page
 Create an agent
 Core benefits
LangChain overview
Copy page
LangChain is an open source framework with a prebuilt agent architecture and integrations for any model or tool—so you can build agents that adapt as fast as the ecosystem evolves
Copy page
Documentation Index
Fetch the complete documentation index at: 
https://docs.langchain.com/llms.txt
Use this file to discover all available pages before exploring further.
Build completely custom agents and applications powered by LLMs in under 10 lines of code, with integrations for 
OpenAI, Anthropic, Google, and more
.
LangChain provides a prebuilt agent architecture and model integrations to help you get started quickly and seamlessly incorporate LLMs into your agents and applications.
LangChain vs. LangGraph vs. Deep Agents
Start with 
Deep Agents
 for a “batteries-included” agent with features like automatic context compression, a virtual filesystem, and subagent-spawning. Deep Agents are built on LangChain 
agents
 which you can also use LangChain directly.
Use 
LangGraph
, our low-level orchestration framework, for advanced needs combining deterministic and agentic workflows.
​
 Create an agent
OpenAI
Google Gemini
Claude (Anthropic)
OpenRouter
Fireworks
Baseten
Ollama
Azure
AWS Bedrock
HuggingFace
# pip install -qU langchain "langchain[openai]"
from
 langchain
.
agents 
import
 create_agent
def
 get_weather
(
city
:
 str
)
 ->
 str
:
    """Get weather for a given city."""
    return
 f
"It's always sunny in 
{
city
}
!"
agent 
=
 create_agent
(
    model
=
"openai:gpt-5.4"
,
    tools
=
[
get_weather
],
    system_prompt
=
"You are a helpful assistant"
,
)
result 
=
 agent
.
invoke
(
    {
"messages"
:
 [{
"role"
:
 "user"
,
 "content"
:
 "What's the weather in San Francisco?"
}]}
)
print
(
result
[
"
messages
"
][
-
1
].
content_blocks
)
See the 
Installation instructions
 and 
Quickstart guide
 to get started building your own agents and applications with LangChain.
Use 
LangSmith
 to trace requests, debug agent behavior, and evaluate outputs. Set 
LANGSMITH_TRACING=true
 and your API key to get started.
​
 Core benefits
Standard model interface
Different providers have unique APIs for interacting with models, including the format of responses. LangChain standardizes how you interact with models so that you can seamlessly swap providers and avoid lock-in.
Learn more
Easy to use, highly flexible agent
LangChain’s agent abstraction is designed to be easy to get started with, letting you build a simple agent in under 10 lines of code. But it also provides enough flexibility to allow you to do all the context engineering your heart desires.
Learn more
Built on top of LangGraph
LangChain’s agents are built on top of LangGraph. This allows us to take advantage of LangGraph’s durable execution, human-in-the-loop support, persistence, and more.
Learn more
Debug with LangSmith
Gain deep visibility into complex agent behavior with visualization tools that trace execution paths, capture state transitions, and provide detailed runtime metrics.
Learn more
Connect these docs
 to Claude, VSCode, and more via MCP for real-time answers.
Edit this page on GitHub
 or 
file an issue
.
Was this page helpful?
Yes
No
Install LangChain
Next
⌘I