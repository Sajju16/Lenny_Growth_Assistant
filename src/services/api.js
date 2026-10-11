const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * Helper to try the proxied endpoint first, falling back to direct port 8000
 */
async function fetchWithFallback(endpoint, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const isMutation = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);

  // For non-idempotent operations like chat or essay generation, only target the primary URL
  // to avoid cascading duplicate inference tasks on CPU if a socket drops
  const urls = isMutation
    ? [`${API_BASE}${endpoint}`]
    : [
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
      const httpError = new Error(errorDetail);
      httpError.status = res.status;
      throw httpError;
    } catch (err) {
      lastError = err;
      // Immediately surface HTTP status responses (504 timeout, 502 gateway, 400 bad request, etc.)
      if (err.status || (err.message && (err.message.includes('HTTP') || err.message.includes('Ollama')))) {
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
  model = null,
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
 * Stream a chat message with live token updates via SSE (/api/chat/stream)
 */
export async function streamChatMessage({
  message,
  model = null,
  provider = null,
  useAgent = false,
  history = [],
  useRag = true,
  conversationId = null,
  skill = null,
  createArtifact = false,
  artifactType = 'markdown',
  artifactTitle = null,
  onToken = () => {},
  onMeta = () => {},
}) {
  const url = `${API_BASE}/api/chat/stream`;
  const response = await fetch(url, {
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

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson?.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {}
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let finalDoneData = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';

    for (const part of parts) {
      const lines = part.split('\n');
      let currentEvent = 'message';
      let currentData = '';

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.replace('event:', '').trim();
        } else if (line.startsWith('data:')) {
          currentData = line.replace('data:', '').trim();
        }
      }

      if (currentData) {
        try {
          const parsed = JSON.parse(currentData);
          if (currentEvent === 'token') {
            onToken(parsed.delta);
          } else if (currentEvent === 'meta') {
            onMeta(parsed);
          } else if (currentEvent === 'done') {
            finalDoneData = parsed;
          } else if (currentEvent === 'error') {
            throw new Error(parsed.error || 'Stream execution failed');
          }
        } catch (e) {
          if (e.message?.includes('Stream execution failed')) throw e;
        }
      }
    }
  }

  if (buffer.trim()) {
    const lines = buffer.trim().split('\n');
    let currentEvent = 'message';
    let currentData = '';
    for (const line of lines) {
      if (line.startsWith('event:')) currentEvent = line.replace('event:', '').trim();
      else if (line.startsWith('data:')) currentData = line.replace('data:', '').trim();
    }
    if (currentData) {
      try {
        const parsed = JSON.parse(currentData);
        if (currentEvent === 'done') finalDoneData = parsed;
        else if (currentEvent === 'token') onToken(parsed.delta);
      } catch {}
    }
  }

  return finalDoneData;
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

