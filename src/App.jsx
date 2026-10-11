import React, { useState, useEffect, useRef } from 'react';
import {
  Sidebar
} from './components/Sidebar';
import {
  ChatHeader
} from './components/ChatHeader';
import {
  ChatMessage
} from './components/ChatMessage';
import {
  MessageComposer
} from './components/MessageComposer';
import {
  ArtifactViewer
} from './components/ArtifactViewer';
import {
  mockConversations
} from './data/mockConversations';
import {
  mockArtifacts
} from './data/mockArtifacts';
import {
  mockModels
} from './data/mockModels';
import {
  sendChatMessage,
  streamChatMessage,
  checkBackendHealth,
  listConversations,
  getConversation,
  createConversation,
  updateConversation,
  deleteConversation,
  getArtifact,
} from './services/api';
import {
  PanelRightOpen,
  PanelRightClose,
  Edit3,
  Check,
  Sparkles,
  ArrowRight,
  Database,
} from 'lucide-react';

function getConversationGroup(dateStr) {
  if (!dateStr) return 'Today';
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return 'Today';
  if (diffDays <= 7) return 'Previous 7 Days';
  return '30 Days Ago';
}

function formatDbMessageForUi(msg) {
  const modelLabel = msg.model || 'qwen2.5:3b';
  return {
    id: msg.id,
    sender: msg.role === 'user' ? 'user' : 'assistant',
    authorName: msg.role === 'user' ? 'Alex Kim' : 'Lenny Assistant',
    authorRole: msg.role === 'user' ? 'Head of Growth' : undefined,
    timestamp: msg.created_at
      ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    content: msg.content,
    model: modelLabel,
    citations: msg.citations || [],
    hasSufficientContext: msg.has_sufficient_context,
    evalCount: msg.eval_count,
    totalDuration: msg.total_duration,
    isReal: msg.role === 'assistant',
    footerInfo: msg.citations && msg.citations.length > 0
      ? `${msg.citations.length} verified citation${msg.citations.length > 1 ? 's' : ''} · ${modelLabel}`
      : `${modelLabel} · Strict grounding`,
  };
}

export default function App() {
  const [isInitialHydrating, setIsInitialHydrating] = useState(true);
  const [loadingConvId, setLoadingConvId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(() => {
    return localStorage.getItem('lenny_active_conv') || null;
  });
  const [selectedModelId, setSelectedModelId] = useState(mockModels[0].id); // 'qwen2.5:3b'
  const [isArtifactOpen, setIsArtifactOpen] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isDesktopSidebarCollapsed, setIsDesktopSidebarCollapsed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [isEssayGeneration, setIsEssayGeneration] = useState(false);
  const [backendHealth, setBackendHealth] = useState({ connected: false, checking: true });
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');

  const chatStreamRef = useRef(null);

  // Track progress timer during active inference
  useEffect(() => {
    let interval;
    if (isLoading) {
      interval = setInterval(() => {
        setLoadingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setLoadingSeconds(0);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  // Active conversation object
  const activeConversation = conversations.find((c) => c.id === activeConversationId)
    || (isInitialHydrating ? null : conversations[0])
    || {
      id: 'default',
      title: 'New Strategy Discussion',
      category: 'Strategic Planning',
      messages: []
    };

  // 1. Initial Load & Health Verification
  useEffect(() => {
    let isMounted = true;
    async function verifyHealthAndLoadConvs() {
      try {
        const healthData = await checkBackendHealth();
        if (isMounted) {
          setBackendHealth({
            connected: healthData.status === 'ok' || healthData.backend === 'healthy',
            ollama: healthData.ollama,
            anthropic: healthData.anthropic,
            gemini: healthData.gemini,
            database: healthData.database,
            activeProvider: healthData.active_provider || healthData.llm_provider || 'ollama',
            activeModel: healthData.active_model,
            checking: false
          });
          if (healthData.active_model && mockModels.some((m) => m.id === healthData.active_model)) {
            setSelectedModelId(healthData.active_model);
          }
        }

        // Fetch persistent conversations from PostgreSQL
        const serverConvs = await listConversations();
        if (!isMounted) return;

        if (serverConvs && serverConvs.length > 0) {
          // Restore saved session from localStorage or use most recent
          const savedId = localStorage.getItem('lenny_active_conv');
          const targetId = (savedId && serverConvs.some((m) => m.id === savedId))
            ? savedId
            : serverConvs[0].id;

          // Load full messages and artifacts for target conversation BEFORE committing state
          let detail = null;
          try {
            detail = await getConversation(targetId);
          } catch (e) {
            console.error('Error loading detail for conversation:', e);
          }
          if (!isMounted) return;

          let uiMessages = [];
          let currentArt = null;

          if (detail) {
            currentArt = detail.active_artifact || (detail.artifacts && detail.artifacts[0]) || (detail.artifact_id && mockArtifacts[detail.artifact_id]) || null;
            if (detail.messages) {
              uiMessages = detail.messages.map(formatDbMessageForUi);
              const assistantWithModel = detail.messages.filter((m) => m.role === 'assistant' && m.model);
              if (assistantWithModel.length > 0) {
                const lastUsedModel = assistantWithModel[assistantWithModel.length - 1].model;
                if (mockModels.some((m) => m.id === lastUsedModel)) {
                  setSelectedModelId(lastUsedModel);
                }
              }
              const lastDbMsg = detail.messages[detail.messages.length - 1];
              if (lastDbMsg && lastDbMsg.role === 'user') {
                uiMessages.push({
                  id: `interrupted-${lastDbMsg.id}`,
                  sender: 'assistant',
                  authorName: 'Lenny Assistant',
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  isError: true,
                  isTimeout: false,
                  originalPrompt: lastDbMsg.content,
                  content: 'Generation was interrupted before completion (such as by a browser refresh). You can retry or re-generate below.',
                });
              }
            }
          }

          setActiveArtifact(currentArt);
          setIsArtifactOpen(Boolean(currentArt));
          setActiveConversationId(targetId);

          const mapped = serverConvs.map((sc) => ({
            id: sc.id,
            title: sc.title,
            category: sc.category || 'Strategic Planning',
            artifactId: sc.artifact_id,
            group: getConversationGroup(sc.updated_at),
            messages: sc.id === targetId ? uiMessages : [],
          }));
          setConversations(mapped);
        } else {
          // Initialize fresh PostgreSQL database with default conversation
          try {
            const initConv = await createConversation({
              id: 'first-100-customers',
              title: 'Acquiring First 100 Customers',
              category: 'Growth & GTM',
              artifactId: 'artifact-first-100',
            });
            if (isMounted && initConv) {
              setConversations([{
                id: initConv.id,
                title: initConv.title,
                category: initConv.category,
                artifactId: initConv.artifact_id,
                group: 'Today',
                messages: mockConversations[0]?.messages || [],
              }]);
              setActiveConversationId(initConv.id);
              setActiveArtifact(mockArtifacts['artifact-first-100']);
              setIsArtifactOpen(true);
            }
          } catch (e) {
            console.warn('Could not seed initial conversation in DB:', e);
            if (isMounted) {
              setConversations(mockConversations);
              setActiveConversationId(mockConversations[0]?.id || 'first-100-customers');
              setActiveArtifact(mockArtifacts['artifact-first-100']);
              setIsArtifactOpen(true);
            }
          }
        }
      } catch (err) {
        if (isMounted) {
          setBackendHealth({ connected: false, error: err.message, checking: false });
          // Fallback to offline mock conversations if backend is unreachable
          setConversations(mockConversations);
          setActiveConversationId(mockConversations[0]?.id || 'first-100-customers');
          setActiveArtifact(mockArtifacts['artifact-first-100']);
          setIsArtifactOpen(true);
        }
      } finally {
        if (isMounted) {
          setIsInitialHydrating(false);
        }
      }
    }

    verifyHealthAndLoadConvs();
    const interval = setInterval(async () => {
      try {
        const data = await checkBackendHealth();
        if (isMounted) {
          setBackendHealth({
            connected: data.status === 'ok' || data.backend === 'healthy',
            ollama: data.ollama,
            database: data.database,
            checking: false
          });
        }
      } catch {
        if (isMounted) setBackendHealth((prev) => ({ ...prev, connected: false }));
      }
    }, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Scroll to bottom when messages change
  const scrollToBottom = () => {
    if (chatStreamRef.current) {
      chatStreamRef.current.scrollTo({
        top: chatStreamRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeConversation?.messages?.length, isLoading]);

  // Global keyboard shortcuts (⌘K for new chat)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [conversations]);

  // Select conversation & restore messages and dynamic artifacts from PostgreSQL
  const handleSelectConversation = async (id) => {
    setActiveConversationId(id);
    localStorage.setItem('lenny_active_conv', id);
    setLoadingConvId(id);

    try {
      const detail = await getConversation(id);
      if (detail) {
        const resolvedArt = detail.active_artifact || (detail.artifacts && detail.artifacts[0]) || (detail.artifact_id && mockArtifacts[detail.artifact_id]) || null;
        setActiveArtifact(resolvedArt);
        setIsArtifactOpen(Boolean(resolvedArt));

        if (detail.messages) {
          const uiMessages = detail.messages.map(formatDbMessageForUi);
          const assistantWithModel = detail.messages.filter((m) => m.role === 'assistant' && m.model);
          if (assistantWithModel.length > 0) {
            const lastUsedModel = assistantWithModel[assistantWithModel.length - 1].model;
            if (mockModels.some((m) => m.id === lastUsedModel)) {
              setSelectedModelId(lastUsedModel);
            }
          }
          const lastDbMsg = detail.messages[detail.messages.length - 1];
          if (lastDbMsg && lastDbMsg.role === 'user') {
            uiMessages.push({
              id: `interrupted-${lastDbMsg.id}`,
              sender: 'assistant',
              authorName: 'Lenny Assistant',
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              isError: true,
              isTimeout: false,
              originalPrompt: lastDbMsg.content,
              content: 'Generation was interrupted before completion (such as by a browser refresh). You can retry or re-generate below.',
            });
          }
          setConversations((prev) =>
            prev.map((c) =>
              c.id === id
                ? {
                    ...c,
                    title: detail.title,
                    category: detail.category,
                    artifactId: detail.artifact_id,
                    messages: uiMessages,
                  }
                : c
            )
          );
        }
      }
    } catch (err) {
      console.error('Failed to load conversation details from PostgreSQL:', err);
    } finally {
      setLoadingConvId(null);
    }
  };

  // Create new persistent session
  const handleNewChat = async () => {
    const newId = `conv-${Date.now()}`;
    const newChat = {
      id: newId,
      title: 'New Strategy Discussion',
      category: 'Strategic Planning',
      group: 'Today',
      artifactId: null,
      messages: []
    };

    setConversations([newChat, ...conversations]);
    setActiveConversationId(newId);
    localStorage.setItem('lenny_active_conv', newId);
    setActiveArtifact(null);
    setIsArtifactOpen(false);

    try {
      await createConversation({
        id: newId,
        title: 'New Strategy Discussion',
        category: 'Strategic Planning',
      });
    } catch (err) {
      console.warn('New conversation will be persisted upon first message submission:', err);
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (id) => {
    try {
      await deleteConversation(id);
      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);

      if (activeConversationId === id) {
        if (remaining.length > 0) {
          handleSelectConversation(remaining[0].id);
        } else {
          handleNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      alert(`Could not delete conversation: ${err.message}`);
    }
  };

  const handleOpenArtifact = async (artifactId) => {
    if (artifactId) {
      try {
        const art = await getArtifact(artifactId);
        if (art) {
          setActiveArtifact(art);
          setIsArtifactOpen(true);
          return;
        }
      } catch (err) {
        console.warn('Could not fetch artifact from backend:', err);
      }
      if (mockArtifacts[artifactId]) {
        setActiveArtifact(mockArtifacts[artifactId]);
        setIsArtifactOpen(true);
        return;
      }
    }
    setIsArtifactOpen(true);
  };

  const handleSaveTitle = async () => {
    if (editedTitle.trim()) {
      const newTitle = editedTitle.trim();
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId ? { ...c, title: newTitle } : c
        )
      );

      try {
        await updateConversation(activeConversationId, { title: newTitle });
      } catch (err) {
        console.error('Failed to update title in PostgreSQL:', err);
      }
    }
    setIsEditingTitle(false);
  };

  const handleSendMessage = async (text, attachment, options = {}) => {
    if (!text?.trim()) return;

    const isEssayCommand = Boolean(
      text.startsWith('/essay') ||
      text.startsWith('@essay') ||
      options?.skill === 'essay' ||
      options?.isEssay ||
      /^\s*(?:write|generate)\s+(?:an?\s+)?(?:ship\s*30\s*(?:for\s*30)?\s+)?essay\b/i.test(text)
    );
    const cleanText = (text.startsWith('/essay') || text.startsWith('@essay'))
      ? text.replace(/^(\/essay|@essay)\s*/i, '').trim()
      : text;

    setIsEssayGeneration(Boolean(isEssayCommand));

    const currentMessages = activeConversation.messages || [];

    // Filter out previous trailing error messages if retrying
    const baseMessages = options?.isRetry
      ? currentMessages.filter((m) => !m.isError)
      : currentMessages;

    // Check if the last message in baseMessages is already an identical user prompt
    const lastMsg = baseMessages[baseMessages.length - 1];
    const isDuplicateUserPrompt = Boolean(
      lastMsg && lastMsg.sender === 'user' && lastMsg.content?.trim() === cleanText.trim()
    );

    const userMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      authorName: 'Alex Kim',
      authorRole: 'Head of Growth',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      content: attachment ? `${cleanText}\n[Attached: ${attachment}]` : cleanText
    };

    const updatedMessagesWithUser = isDuplicateUserPrompt
      ? baseMessages
      : [...baseMessages, userMessage];

    // If it was a new empty chat, update title
    const newTitle = baseMessages.length === 0
      ? (cleanText.length > 32 ? cleanText.slice(0, 32) + '...' : cleanText)
      : activeConversation.title;

    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeConversationId
          ? { ...c, title: newTitle, messages: updatedMessagesWithUser }
          : c
      )
    );

    setIsLoading(true);

    // Ensure the current user prompt / essay topic is not duplicated in prior history:
    // If the last message in baseMessages was the user prompt being retried or executed,
    // exclude it from prior messages sent to the backend.
    const priorMessages = (isDuplicateUserPrompt && baseMessages.length > 0)
      ? baseMessages.slice(0, -1)
      : baseMessages;

    // Prepare conversation history for the backend:
    // Filter out error messages, empty streaming placeholders, and messages with empty/whitespace content.
    const historyPayload = priorMessages
      .filter((m) => {
        if (m.isError) return false;
        if (m.isStreaming && !m.content?.trim()) return false;
        const textContent = m.content || m.contentIntro || '';
        return typeof textContent === 'string' && textContent.trim().length > 0;
      })
      .map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: (m.content || m.contentIntro || '').trim()
      }));

    const selectedModelObj = mockModels.find((m) => m.id === selectedModelId) || mockModels[0];
    const canStream = !isEssayCommand && !options?.createArtifact && !selectedModelObj.useAgent;

    try {
      if (canStream) {
        // --- Live SSE Streaming Path ---
        const assistantMessageId = `asst-${Date.now()}`;
        const providerBadge = selectedModelObj.providerType === 'anthropic'
          ? 'Anthropic Cloud'
          : selectedModelObj.providerType === 'gemini'
          ? 'Gemini Cloud'
          : 'Ollama Local';

        const initialAssistantMessage = {
          id: assistantMessageId,
          sender: 'assistant',
          authorName: 'Lenny Assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isReal: true,
          model: selectedModelId,
          content: '',
          isStreaming: true,
          citations: [],
          hasSufficientContext: true,
          footerInfo: `${providerBadge} (${selectedModelId}) · Streaming live`,
        };

        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId
              ? { ...c, title: newTitle, messages: [...updatedMessagesWithUser, initialAssistantMessage] }
              : c
          )
        );

        let streamedContent = '';
        const res = await streamChatMessage({
          message: cleanText,
          model: selectedModelId,
          provider: selectedModelObj.providerType,
          useAgent: false,
          history: historyPayload,
          conversationId: activeConversationId,
          skill: null,
          onToken: (token) => {
            streamedContent += token;
            setConversations((prev) =>
              prev.map((c) => {
                if (c.id !== activeConversationId) return c;
                const msgs = (c.messages || []).map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, content: streamedContent }
                    : m
                );
                return { ...c, messages: msgs };
              })
            );
            if (chatStreamRef.current) {
              chatStreamRef.current.scrollTop = chatStreamRef.current.scrollHeight;
            }
          },
        });

        const finalAssistantMessage = {
          id: assistantMessageId,
          sender: 'assistant',
          authorName: 'Lenny Assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isReal: true,
          model: res?.model || selectedModelId,
          content: res?.response || streamedContent,
          citations: res?.citations || [],
          hasSufficientContext: res?.has_sufficient_context !== false,
          evalCount: res?.eval_count,
          totalDuration: res?.total_duration,
          isStreaming: false,
          footerInfo: res?.citations?.length
            ? `${res.citations.length} verified citation${res.citations.length > 1 ? 's' : ''} · ${providerBadge} (${res?.model || selectedModelId})`
            : `${providerBadge} (${res?.model || selectedModelId}) · Strict grounding`,
        };

        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== activeConversationId) return c;
            const msgs = (c.messages || []).map((m) =>
              m.id === assistantMessageId ? finalAssistantMessage : m
            );
            return { ...c, messages: msgs };
          })
        );
      } else {
        // --- Standard / Non-streaming Path (Essay Skill or Agent Mode) ---
        setIsLoading(true);
        const res = await sendChatMessage({
          message: cleanText,
          model: selectedModelObj.useAgent ? null : selectedModelId,
          provider: selectedModelObj.providerType,
          useAgent: Boolean(selectedModelObj.useAgent),
          history: historyPayload,
          conversationId: activeConversationId,
          skill: isEssayCommand ? 'essay' : (options?.skill || null),
          createArtifact: Boolean(options?.createArtifact),
          artifactType: options?.artifactType || 'markdown',
        });

        if (res.artifact) {
          setActiveArtifact(res.artifact);
          setIsArtifactOpen(true);
        }

        const providerBadge = isEssayCommand
          ? 'Ship 30 for 30 Essay'
          : res.provider === 'anthropic'
          ? 'Anthropic Cloud'
          : res.provider === 'gemini'
          ? 'Gemini Cloud'
          : res.provider === 'anthropic-agent'
          ? 'Claude Agent'
          : 'Ollama Local';

        const assistantMessage = {
          id: `asst-${Date.now()}`,
          sender: 'assistant',
          authorName: 'Lenny Assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isReal: true,
          model: res.model || selectedModelId,
          content: res.response,
          citations: res.citations || [],
          hasSufficientContext: res.has_sufficient_context,
          evalCount: res.eval_count,
          totalDuration: res.total_duration,
          artifactId: res.artifact_id || (res.artifact ? res.artifact.id : undefined),
          footerInfo: res.citations?.length
              ? `${res.citations.length} verified citation${res.citations.length > 1 ? 's' : ''} · ${providerBadge} (${res.model || selectedModelId})`
              : `${providerBadge} (${res.model || selectedModelId}) · Strict grounding`,
        };

        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId
              ? {
                  ...c,
                  artifactId: res.artifact_id || c.artifactId,
                  messages: [...updatedMessagesWithUser, assistantMessage]
                }
              : c
          )
        );
      }
    } catch (err) {
      console.error('Failed to get response from backend:', err);
      const isTimeout = Boolean(
        err.message?.includes('timed out') ||
        err.message?.includes('504') ||
        err.status === 504
      );
      const isGeminiUnavailable = Boolean(
        err.message?.includes('503') ||
        err.message?.includes('high demand') ||
        err.message?.includes('Spikes in demand') ||
        err.message?.includes('temporarily unavailable')
      );
      const errorMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
        isTimeout,
        isGeminiUnavailable,
        isEssay: isEssayCommand,
        originalPrompt: cleanText,
        content: err.message || 'Failed to communicate with FastAPI backend or local Ollama runtime.',
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConversationId
            ? { ...c, messages: [...updatedMessagesWithUser, errorMessage] }
            : c
        )
      );
    } finally {
      setIsLoading(false);
      setIsEssayGeneration(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-background font-sans text-on-surface antialiased overflow-hidden">
      {/* 1. Left Navigation Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        isCollapsedDesktop={isDesktopSidebarCollapsed}
        onToggleCollapseDesktop={() => setIsDesktopSidebarCollapsed(!isDesktopSidebarCollapsed)}
        isInitialHydrating={isInitialHydrating}
      />

      {/* Main Workspace (Shifts with sidebar) */}
      <div
        className={`flex-1 flex flex-col min-w-0 h-screen transition-all duration-200 ${
          isDesktopSidebarCollapsed ? 'md:pl-0' : 'md:pl-64'
        }`}
      >
        {/* Top Header */}
        <ChatHeader
          title={isInitialHydrating ? 'Loading workspace...' : (activeConversation?.title || 'Lenny Assistant')}
          category={isInitialHydrating ? 'Restoring session' : (activeConversation?.category || 'Strategic Planning')}
          selectedModelId={selectedModelId}
          onSelectModel={setSelectedModelId}
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          isCollapsedDesktop={isDesktopSidebarCollapsed}
          onToggleCollapseDesktop={() => setIsDesktopSidebarCollapsed(!isDesktopSidebarCollapsed)}
          backendHealth={backendHealth}
        />

        {/* Workspace Body: Center Panel + Right Artifact Panel */}
        <div className="flex flex-1 w-full h-[calc(100vh-4rem)] overflow-hidden">
          {/* 2. Conversational Workspace (Center Panel) */}
          <section className="flex-1 min-w-0 flex flex-col h-full bg-surface-container-low border-r border-[#EAEAE7]">
            {/* Center Panel Utility Header */}
            <header className="h-14 px-4 sm:px-space-lg flex items-center justify-between bg-surface-container-lowest border-b border-[#EAEAE7] shadow-[0_1px_2px_rgba(0,0,0,0.02)] shrink-0 z-10">
              <div className="flex items-center gap-2 min-w-0">
                {isEditingTitle ? (
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={editedTitle}
                      onChange={(e) => setEditedTitle(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveTitle()}
                      autoFocus
                      className="text-[17px] font-semibold text-on-surface bg-surface-container-low px-2 py-0.5 rounded border border-primary focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleSaveTitle}
                      className="p-1 text-primary hover:bg-surface-container rounded"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <>
                    <h1 className="font-semibold text-[17px] text-on-surface truncate">
                      {isInitialHydrating ? (
                        <span className="inline-block w-48 h-5 bg-[#EAEAE7] animate-pulse rounded" />
                      ) : (
                        activeConversation?.title || 'New Strategy Discussion'
                      )}
                    </h1>
                    {!isInitialHydrating && (
                      <button
                        type="button"
                        onClick={() => {
                          setEditedTitle(activeConversation?.title || '');
                          setIsEditingTitle(true);
                        }}
                        aria-label="Edit title"
                        className="p-1 text-outline hover:text-on-surface rounded hover:bg-surface-container transition-colors shrink-0"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </>
                )}
              </div>

              <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                {/* Real-time backend status badge */}
                <div className="hidden sm:flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-full bg-surface-container border border-surface-container-high text-outline">
                  {backendHealth.connected ? (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-on-surface-variant font-medium flex items-center gap-1">
                        <Database className="w-3 h-3 text-emerald-600" />
                        PostgreSQL · Online
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                      <span>Checking Backend...</span>
                    </>
                  )}
                </div>

                {/* Artifact Toggle Button */}
                <button
                  type="button"
                  onClick={() => setIsArtifactOpen(!isArtifactOpen)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all shadow-sm ${
                    isArtifactOpen
                      ? 'bg-primary text-on-primary hover:bg-primary-container'
                      : 'bg-surface-container text-on-surface hover:bg-surface-container-high border border-[#E2E2DE]'
                  }`}
                  aria-label="Toggle Artifact Viewer"
                >
                  {isArtifactOpen ? (
                    <>
                      <PanelRightClose className="w-4 h-4" />
                      <span>Artifact (Open)</span>
                    </>
                  ) : (
                    <>
                      <PanelRightOpen className="w-4 h-4" />
                      <span>Open Artifact</span>
                    </>
                  )}
                </button>
              </div>
            </header>

            {/* Scrollable Chat Stream */}
            <div
              ref={chatStreamRef}
              className="flex-1 overflow-y-auto px-4 sm:px-space-lg py-5 sm:py-space-xl space-y-6"
              id="chat-stream"
            >
              <div className="max-w-[680px] mx-auto space-y-6">
                {isInitialHydrating || loadingConvId === activeConversationId ? (
                  <div className="space-y-6 pt-4 animate-in fade-in duration-200">
                    <div className="flex items-center justify-center gap-2 py-3 text-[13px] text-outline">
                      <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                      <span>Restoring conversation history and model context...</span>
                    </div>
                    {/* User message skeleton */}
                    <div className="flex justify-end">
                      <div className="w-2/3 max-w-sm p-4 rounded-2xl bg-surface-container-high/60 animate-pulse space-y-2">
                        <div className="h-3.5 bg-[#D5D5D0] rounded w-4/5" />
                        <div className="h-3.5 bg-[#D5D5D0] rounded w-2/3" />
                      </div>
                    </div>
                    {/* Assistant message skeleton */}
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-xl bg-surface-container-high animate-pulse shrink-0" />
                      <div className="flex-1 max-w-xl p-5 rounded-2xl bg-surface-container-lowest border border-[#EAEAE7] animate-pulse space-y-3">
                        <div className="h-3.5 bg-[#EAEAE7] rounded w-3/4" />
                        <div className="h-3.5 bg-[#EAEAE7] rounded w-full" />
                        <div className="h-3.5 bg-[#EAEAE7] rounded w-5/6" />
                        <div className="h-3 bg-[#EAEAE7]/80 rounded w-1/3 pt-1" />
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Empty State when chat has no messages */}
                    {(!activeConversation?.messages || activeConversation.messages.length === 0) && (
                      <div className="py-12 px-4 text-center space-y-4 max-w-md mx-auto">
                        <div className="w-12 h-12 rounded-2xl bg-primary-fixed/30 text-primary flex items-center justify-center mx-auto shadow-sm">
                          <Sparkles className="w-6 h-6 text-primary" />
                        </div>
                        <h2 className="text-[20px] font-bold text-on-surface">
                          How can Lenny Growth assist your strategy?
                        </h2>
                        <p className="text-[14px] text-on-surface-variant leading-relaxed">
                          Ask strategic questions on product-led growth, activation funnels, PMF benchmarks, or pricing architecture synthesized live by local Ollama ({selectedModelId}) and backed by PostgreSQL session storage.
                        </p>

                        <div className="pt-4 space-y-2 text-left">
                          <span className="text-[11px] font-semibold text-outline uppercase tracking-wider block">
                            Suggested Inquiries
                          </span>
                          {[
                            'According to April Dunford, what are the key steps for crafting a winning sales pitch?',
                            'What is the Sean Ellis benchmark for Product-Market Fit?',
                            'When should a SaaS company shift to usage-based pricing?'
                          ].map((prompt, pIdx) => (
                            <button
                              key={pIdx}
                              type="button"
                              onClick={() => handleSendMessage(prompt, null)}
                              className="w-full p-2.5 rounded-xl bg-surface-container-lowest border border-[#EAEAE7] hover:border-primary/50 text-[13px] text-on-surface hover:bg-surface-container transition-all flex items-center justify-between text-left group"
                            >
                              <span className="line-clamp-1">{prompt}</span>
                              <ArrowRight className="w-3.5 h-3.5 text-outline group-hover:text-primary transition-transform group-hover:translate-x-0.5 shrink-0 ml-2" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Render conversation messages */}
                    {activeConversation?.messages?.map((msg) => (
                      <ChatMessage
                        key={msg.id}
                        message={msg}
                        onOpenArtifact={handleOpenArtifact}
                        onRetry={(prompt, retryOpts) => handleSendMessage(prompt, null, { isRetry: true, ...retryOpts })}
                      />
                    ))}
                  </>
                )}

                {/* Loading / Progress Indicator with Multi-Phase Timer Feedback */}
                {isLoading && (
                  <div className="flex items-start gap-space-md animate-in fade-in duration-200">
                    <div className="w-8 h-8 rounded-lg bg-surface-container-lowest p-1 flex items-center justify-center shrink-0 shadow-sm border border-surface-container-high">
                      <Sparkles className="w-4 h-4 text-primary animate-spin" />
                    </div>
                    <div className="p-4 rounded-xl bg-surface-container-lowest border border-[#EAEAE7] shadow-[0_1px_4px_rgba(0,0,0,0.02)] space-y-1.5 text-[13.5px] text-on-surface-variant flex-1 max-w-lg">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 font-medium text-on-surface">
                          <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                          <span>
                            {isEssayGeneration
                              ? loadingSeconds < 15
                                ? 'Phase 1/3: Retrieving transcript evidence & verified guest citations...'
                                : loadingSeconds < 90
                                ? 'Phase 2/3: Model prefill & structuring Ship 30 narrative arc...'
                                : 'Phase 3/3: Generating full ~1,250-word deep-dive sections on CPU...'
                              : 'Synthesizing Strategic Analysis'}
                          </span>
                        </div>
                        <span className="font-mono text-[12px] bg-surface-container px-2 py-0.5 rounded text-primary font-semibold">
                          {loadingSeconds}s / {isEssayGeneration ? '420s' : '180s'}
                        </span>
                      </div>
                      <p className="text-[12px] text-outline leading-relaxed">
                        {isEssayGeneration
                          ? 'Local Qwen 2.5 3B CPU inference on 2-core i3 (~2.4 tokens/s measured). Full ~1,250-word target bounded by 420s timeout budget.'
                          : `Grounding via Lenny's transcripts and Ollama (${selectedModelId}). Bounded by 180s timeout.`}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Sticky Prompt Composer */}
            <MessageComposer
              onSendMessage={handleSendMessage}
              isLoading={isLoading}
            />
          </section>

          {/* 3. Artifact Viewer (Right Panel) */}
          <ArtifactViewer
            artifact={activeArtifact}
            isOpen={isArtifactOpen}
            onClose={() => setIsArtifactOpen(false)}
            onGenerateEssay={() => handleSendMessage("B2B Product Positioning and Context Setting", null, { skill: 'essay' })}
            activeConversationTitle={activeConversation?.title}
          />
        </div>
      </div>
    </div>
  );
}
