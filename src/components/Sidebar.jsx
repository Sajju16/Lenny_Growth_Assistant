import React, { useState } from 'react';
import { 
  Plus, 
  Search, 
  MessageSquare, 
  Bookmark, 
  BookOpen, 
  Settings, 
  ChevronsUpDown, 
  PanelLeftClose, 
  X,
  Trash2
} from 'lucide-react';
import { BrandLogo } from './BrandLogo';

export function Sidebar({
  conversations = [],
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  isOpenMobile,
  onCloseMobile,
  isCollapsedDesktop,
  onToggleCollapseDesktop,
  isInitialHydrating = false,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'saved-insights' | 'knowledge-base'

  // Filter conversations if user searches
  const filteredConversations = conversations.filter((c) =>
    (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group conversations by period (default to 'Today' if not specified)
  const groups = ['Today', 'Previous 7 Days', '30 Days Ago'];
  const grouped = groups.reduce((acc, group) => {
    acc[group] = filteredConversations.filter((c) => (c.group || 'Today') === group);
    return acc;
  }, {});

  const content = (
    <div className="flex flex-col h-full bg-surface-container-lowest border-r border-[#EAEAE7] text-on-surface select-none">
      {/* Brand Header */}
      <div className="p-space-md flex items-center justify-between gap-space-sm border-b border-transparent">
        <div className="flex items-center gap-2.5">
          <BrandLogo className="w-7 h-7" />
          <span className="font-semibold text-[17px] tracking-tight text-on-surface">Lenny Growth</span>
        </div>
        <div className="flex items-center gap-1">
          {/* Mobile close button */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="md:hidden p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
            aria-label="Close navigation sidebar"
          >
            <X className="w-4 h-4" />
          </button>
          {/* Desktop collapse button */}
          <button
            type="button"
            onClick={onToggleCollapseDesktop}
            className="hidden md:flex p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
            title="Toggle sidebar"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose className="w-4 h-4 text-outline" />
          </button>
        </div>
      </div>

      {/* New Chat Primary Button */}
      <div className="px-space-md pb-space-sm">
        <button
          type="button"
          onClick={() => {
            onNewChat();
            if (isOpenMobile) onCloseMobile();
          }}
          className="w-full flex items-center justify-between px-space-md py-2.5 bg-primary-container text-on-primary rounded-xl hover:bg-primary transition-all duration-150 shadow-sm active:scale-[0.99] group"
        >
          <span className="flex items-center gap-2 font-medium text-[13.5px]">
            <Plus className="w-4 h-4 transition-transform group-hover:rotate-90 duration-200" />
            New chat
          </span>
          <kbd className="font-mono text-[11px] bg-white/20 text-white px-1.5 py-0.5 rounded shadow-none font-semibold">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Search Input */}
      <div className="px-space-md pb-space-md">
        <div className="relative flex items-center">
          <Search className="absolute left-2.5 w-3.5 h-3.5 text-outline pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search strategy, memos..."
            className="w-full bg-surface-container-low font-normal text-[13px] text-on-surface placeholder:text-outline pl-8 pr-2.5 py-1.5 rounded-xl border border-transparent focus:border-[#D6D6D2] focus:bg-surface-container-lowest focus:outline-none transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 text-outline hover:text-on-surface text-[12px] p-0.5"
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Main Navigation links */}
      <div className="px-space-sm">
        <nav className="space-y-0.5">
          <button
            type="button"
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center gap-2.5 px-space-md py-2 rounded-xl transition-colors text-[13px] font-medium ${
              activeTab === 'chat'
                ? 'bg-surface-container-high text-on-surface font-semibold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            <MessageSquare className="w-4 h-4 text-primary" />
            <span>Chat</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('saved-insights')}
            className={`w-full flex items-center gap-2.5 px-space-md py-2 rounded-xl transition-colors text-[13px] font-medium ${
              activeTab === 'saved-insights'
                ? 'bg-surface-container-high text-on-surface font-semibold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            <Bookmark className="w-4 h-4 text-outline" />
            <span>Saved insights</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('knowledge-base')}
            className={`w-full flex items-center gap-2.5 px-space-md py-2 rounded-xl transition-colors text-[13px] font-medium ${
              activeTab === 'knowledge-base'
                ? 'bg-surface-container-high text-on-surface font-semibold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            <BookOpen className="w-4 h-4 text-outline" />
            <span>Knowledge base</span>
          </button>
        </nav>
      </div>

      {/* Scrollable Conversation Stream */}
      <div className="flex-1 overflow-y-auto px-space-sm pt-space-md space-y-space-md">
        {isInitialHydrating ? (
          <div className="px-space-md space-y-3 pt-1">
            <div className="h-3 w-16 bg-[#EAEAE7] animate-pulse rounded" />
            <div className="space-y-2">
              <div className="h-8 w-full bg-[#EAEAE7]/70 animate-pulse rounded-lg" />
              <div className="h-8 w-4/5 bg-[#EAEAE7]/50 animate-pulse rounded-lg" />
              <div className="h-8 w-3/4 bg-[#EAEAE7]/40 animate-pulse rounded-lg" />
            </div>
          </div>
        ) : (
          groups.map((group) => {
          const items = grouped[group];
          if (!items || items.length === 0) return null;
          return (
            <div key={group} className="px-space-md">
              <span className="font-semibold text-[11px] text-outline uppercase tracking-wider block mb-1">
                {group}
              </span>
              <div className="space-y-0.5">
                {items.map((conv) => {
                  const isActive = conv.id === activeConversationId;
                  return (
                    <div
                      key={conv.id}
                      className={`group/item flex items-center justify-between rounded-lg px-2.5 py-1.5 transition-colors ${
                        isActive
                          ? 'bg-surface-container-high text-on-surface font-semibold shadow-none'
                          : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          onSelectConversation(conv.id);
                          if (isOpenMobile) onCloseMobile();
                        }}
                        className="flex-1 text-left text-[13px] leading-tight truncate mr-1"
                        title={conv.title}
                      >
                        {conv.title}
                      </button>
                      {onDeleteConversation && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Delete conversation "${conv.title}"?`)) {
                              onDeleteConversation(conv.id);
                            }
                          }}
                          className="opacity-0 group-hover/item:opacity-100 p-1 text-outline hover:text-red-600 rounded transition-opacity shrink-0"
                          title="Delete session"
                          aria-label={`Delete ${conv.title}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        }))}

        {filteredConversations.length === 0 && (
          <div className="text-center py-6 px-4 text-outline text-[13px]">
            No conversations matching "{searchQuery}"
          </div>
        )}
      </div>

      {/* Bottom Footer User & Settings */}
      <div className="p-space-sm bg-surface-container-lowest border-t border-[#EAEAE7] space-y-1">
        <button
          type="button"
          onClick={() => alert('Workspace settings: Lenny Growth Assistant v0.3.0\nTheme: Executive Editorial\nEngine: Ollama Local API + PostgreSQL Persistence')}
          className="w-full flex items-center justify-between px-space-md py-2 rounded-xl text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors text-[13px] font-medium"
        >
          <span className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-outline" />
            Workspace settings
          </span>
          <kbd className="font-mono text-[11px] text-outline">⌘,</kbd>
        </button>

        <div className="flex items-center justify-between p-2 rounded-xl hover:bg-surface-container transition-colors cursor-pointer group">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center font-semibold text-[12px] shrink-0">
              EV
            </div>
            <div className="flex flex-col min-w-0 text-left">
              <span className="text-[13px] font-medium text-on-surface truncate">Elena Vance</span>
              <span className="text-[11px] text-outline truncate">Chief Growth Officer</span>
            </div>
          </div>
          <ChevronsUpDown className="w-4 h-4 text-outline group-hover:text-on-surface shrink-0" />
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen z-40 transition-all duration-200 hidden md:block ${
          isCollapsedDesktop ? 'w-0 -translate-x-full' : 'w-64 translate-x-0'
        }`}
      >
        {content}
      </aside>

      {/* Mobile Drawer Overlay */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {content}
          </div>
        </div>
      )}
    </>
  );
}
