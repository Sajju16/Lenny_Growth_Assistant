export const mockModels = [
  {
    id: 'qwen2.5:3b',
    providerType: 'ollama',
    name: 'Qwen 2.5 (Local)',
    version: '3b-instruct-q4_K_M',
    tag: 'Ollama · Local',
    provider: 'Local Engine',
    contextSize: '32k context',
    description: 'Active local LLM running offline on Ollama with ChromaDB transcript retrieval.',
    isDefault: true,
    isCloud: false,
    useAgent: false,
    status: 'Ready'
  },
  {
    id: 'claude-3-5-sonnet-20241022',
    providerType: 'anthropic',
    name: 'Claude 3.5 Sonnet',
    version: 'v20241022',
    tag: 'Anthropic · Cloud',
    provider: 'Anthropic API',
    contextSize: '200k context',
    description: 'Cloud frontier LLM via official Anthropic Python SDK with RAG grounding.',
    isDefault: false,
    isCloud: true,
    useAgent: false,
    status: 'Cloud'
  },
  {
    id: 'claude-agent',
    providerType: 'anthropic',
    name: 'Claude Agent (Tool Use)',
    version: 'SDK Agent',
    tag: 'Claude Agent SDK',
    provider: 'Autonomous Agent',
    contextSize: '200k context',
    description: 'Assignment-required Claude Agent executing strict search_lenny_transcripts retrieval tool.',
    isDefault: false,
    isCloud: true,
    useAgent: true,
    status: 'Agent'
  }
];
