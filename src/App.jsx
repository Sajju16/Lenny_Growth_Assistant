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
  const [conversations, setConversations] = useState(mockConversations);
  const [activeConversationId, setActiveConversationId] = useState('first-100-customers');
  const [selectedModelId, setSelectedModelId] = useState(mockModels[0].id); // 'qwen2.5:3b'
  const [isArtifactOpen, setIsArtifactOpen] = useState(true);
  const [activeArtifact, setActiveArtifact] = useState(mockArtifacts['artifact-first-100']);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isDesktopSidebarCollapsed, setIsDesktopSidebarCollapsed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [backendHealth, setBackendHealth] = useState({ connected: false, checking: true });
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');

  const chatStreamRef = useRef(null);

  // Active conversation object
  const activeConversation = conversations.find((c) => c.id === activeConversationId) || conversations[0] || {
    id: 'default',
    title: 'New Strategy Discussion',
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
          const mapped = serverConvs.map((sc) => ({
            id: sc.id,
            title: sc.title,
            category: sc.category || 'Strategic Planning',
            artifactId: sc.artifact_id,
            group: getConversationGroup(sc.updated_at),
            messages: [],
          }));
          setConversations(mapped);

          // Restore saved session from localStorage or use most recent
          const savedId = localStorage.getItem('lenny_active_conv');
          const targetId = (savedId && mapped.some((m) => m.id === savedId)) ? savedId : mapped[0].id;
          setActiveConversationId(targetId);

          // Load full messages and artifacts for active conversation
          try {
            const detail = await getConversation(targetId);
            if (isMounted && detail) {
              const currentArt = detail.active_artifact || (detail.artifacts && detail.artifacts[0]) || (detail.artifact_id && mockArtifacts[detail.artifact_id]) || null;
              setActiveArtifact(currentArt);
              if (currentArt) {
                setIsArtifactOpen(true);
              }

              if (detail.messages) {
                setConversations((prev) =>
                  prev.map((c) =>
                    c.id === targetId
                      ? {
                          ...c,
                          messages: detail.messages.map(formatDbMessageForUi),
                          artifactId: detail.artifact_id,
                        }
                      : c
                  )
                );
              }
            }
          } catch (e) {
            console.error('Error loading detail for conversation:', e);
          }
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
            }
          } catch (e) {
            console.warn('Could not seed initial conversation in DB:', e);
          }
        }
      } catch (err) {
        if (isMounted) {
          setBackendHealth({ connected: false, error: err.message, checking: false });
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

    try {
      const detail = await getConversation(id);
      if (detail) {
        const resolvedArt = detail.active_artifact || (detail.artifacts && detail.artifacts[0]) || (detail.artifact_id && mockArtifacts[detail.artifact_id]) || null;
        setActiveArtifact(resolvedArt);
        if (resolvedArt) {
          setIsArtifactOpen(true);
        } else {
          setActiveArtifact(null);
        }

        if (detail.messages) {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === id
                ? {
                    ...c,
                    title: detail.title,
                    category: detail.category,
                    artifactId: detail.artifact_id,
                    messages: detail.messages.map(formatDbMessageForUi),
                  }
                : c
            )
          );
        }
      }
    } catch (err) {
      console.error('Failed to load conversation details from PostgreSQL:', err);
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

    const isEssayCommand = text.startsWith('/essay') || text.startsWith('@essay') || options?.skill === 'essay';
    const cleanText = (text.startsWith('/essay') || text.startsWith('@essay'))
      ? text.replace(/^(\/essay|@essay)\s*/i, '').trim()
      : text;

    const userMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      authorName: 'Alex Kim',
      authorRole: 'Head of Growth',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      content: attachment ? `${cleanText}\n[Attached: ${attachment}]` : cleanText
    };

    const currentMessages = activeConversation.messages || [];
    const updatedMessagesWithUser = [...currentMessages, userMessage];

    // If it was a new empty chat, update title
    const newTitle = currentMessages.length === 0
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

    // Prepare conversation history for the backend
    const historyPayload = currentMessages
      .filter((m) => !m.isError)
      .map((m) => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.content || m.contentIntro || ''
      }));

    try {
      // Real FastAPI POST /api/chat with active conversation_id and provider selection
      const selectedModelObj = mockModels.find((m) => m.id === selectedModelId) || mockModels[0];
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
    } catch (err) {
      console.error('Failed to get response from backend:', err);
      const errorMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
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
      />

      {/* Main Workspace (Shifts with sidebar) */}
      <div
        className={`flex-1 flex flex-col min-w-0 h-screen transition-all duration-200 ${
          isDesktopSidebarCollapsed ? 'md:pl-0' : 'md:pl-64'
        }`}
      >
        {/* Top Header */}
        <ChatHeader
          title={activeConversation.title}
          category={activeConversation.category}
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
                      {activeConversation.title}
                    </h1>
                    <button
                      type="button"
                      onClick={() => {
                        setEditedTitle(activeConversation.title);
                        setIsEditingTitle(true);
                      }}
                      aria-label="Edit title"
                      className="p-1 text-outline hover:text-on-surface rounded hover:bg-surface-container transition-colors shrink-0"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
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
                {/* Empty State when chat has no messages */}
                {(!activeConversation.messages || activeConversation.messages.length === 0) && (
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
                {activeConversation.messages?.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onOpenArtifact={handleOpenArtifact}
                    onRetry={(prompt) => handleSendMessage(prompt, null)}
                  />
                ))}

                {/* Loading / Thinking Indicator */}
                {isLoading && (
                  <div className="flex items-start gap-space-md animate-in fade-in duration-200">
                    <div className="w-8 h-8 rounded-lg bg-surface-container-lowest p-1 flex items-center justify-center shrink-0 shadow-sm border border-surface-container-high">
                      <Sparkles className="w-4 h-4 text-primary animate-spin" />
                    </div>
                    <div className="p-4 rounded-xl bg-surface-container-lowest border border-[#EAEAE7] shadow-[0_1px_4px_rgba(0,0,0,0.02)] flex items-center gap-3 text-[13.5px] text-on-surface-variant">
                      <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                      <span>Generating strategic analysis via Ollama ({selectedModelId})...</span>
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
