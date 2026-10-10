const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Helper to try the proxied endpoint first, falling back to direct port 8000
 */
async function fetchWithFallback(endpoint, options = {}) {
  const urls = [
    `${API_BASE}${endpoint}`,
    `http://localhost:8000${endpoint}`,
    `http://127.0.0.1:8000${endpoint}`,
  ];

  let lastError = null;

  for (const url of urls) {
    try {
      const res = await fetch(url, options);
      if (res.ok) {
        return await res.json();
      }
      let errorDetail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data && data.detail) {
          errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        }
      } catch {
        // use default status
      }
      throw new Error(errorDetail);
    } catch (err) {
      lastError = err;
      if (err.message && (err.message.includes('HTTP 502') || err.message.includes('HTTP 503') || err.message.includes('HTTP 504') || err.message.includes('Ollama'))) {
        throw err;
      }
    }
  }

  throw lastError || new Error(`Failed to connect to backend at ${endpoint}`);
}

/**
 * Check backend, PostgreSQL, and Ollama health
 */
export async function checkBackendHealth() {
  return fetchWithFallback('/health');
}

/**
 * Get knowledge base indexing status
 */
export async function getKnowledgeStatus() {
  return fetchWithFallback('/api/knowledge/status');
}

/**
 * List all persistent conversations from PostgreSQL
 */
export async function listConversations() {
  return fetchWithFallback('/api/conversations');
}

/**
 * Get a specific conversation with full message history and citations
 */
export async function getConversation(conversationId) {
  return fetchWithFallback(`/api/conversations/${encodeURIComponent(conversationId)}`);
}

/**
 * Create a new conversation session in PostgreSQL
 */
export async function createConversation({ id, title = 'New Strategy Discussion', category = 'Strategic Planning', artifactId = null }) {
  return fetchWithFallback('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id,
      title,
      category,
      artifact_id: artifactId,
    }),
  });
}

/**
 * Update conversation title or metadata
 */
export async function updateConversation(conversationId, { title, category, artifactId }) {
  return fetchWithFallback(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      category,
      artifact_id: artifactId,
    }),
  });
}

/**
 * Delete a conversation and its messages
 */
export async function deleteConversation(conversationId) {
  return fetchWithFallback(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  });
}

/**
 * Send a chat message with history, active conversation ID, RAG grounding, optional skill or dynamic artifact generation
 */
export async function sendChatMessage({
  message,
  model = 'qwen2.5:3b',
  provider = null,
  useAgent = false,
  history = [],
  useRag = true,
  conversationId = null,
  skill = null,
  createArtifact = false,
  artifactType = 'markdown',
  artifactTitle = null,
}) {
  return fetchWithFallback('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      model,
      provider,
      use_agent: useAgent,
      history,
      use_rag: useRag,
      conversation_id: conversationId,
      skill,
      create_artifact: createArtifact,
      artifact_type: artifactType,
      artifact_title: artifactTitle,
    }),
  });
}

/**
 * Generate a dedicated Ship 30 for 30 executive essay (~1,250 words)
 */
export async function generateEssay({
  topic,
  conversationId = null,
  provider = null,
  model = null,
}) {
  return fetchWithFallback('/api/skills/essay', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic,
      conversation_id: conversationId,
      provider,
      model,
    }),
  });
}

/**
 * Fetch a specific dynamic artifact by ID
 */
export async function getArtifact(artifactId) {
  return fetchWithFallback(`/api/artifacts/${encodeURIComponent(artifactId)}`);
}

/**
 * List all artifacts generated within a conversation
 */
export async function listConversationArtifacts(conversationId) {
  return fetchWithFallback(`/api/conversations/${encodeURIComponent(conversationId)}/artifacts`);
}

/**
 * Create a dynamic artifact directly (Markdown or HTML)
 */
export async function createArtifact(artifactData) {
  return fetchWithFallback('/api/artifacts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(artifactData),
  });
}

/**
 * Delete an artifact by ID
 */
export async function deleteArtifact(artifactId) {
  return fetchWithFallback(`/api/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'DELETE',
  });
}

