import React, { useState } from 'react';
import { 
  MessageSquare, 
  Menu, 
  Share2, 
  SlidersHorizontal, 
  User, 
  PanelLeftOpen,
  Check
} from 'lucide-react';
import { ModelSelector } from './ModelSelector';

export function ChatHeader({
  title,
  category,
  selectedModelId,
  onSelectModel,
  onOpenMobileSidebar,
  isCollapsedDesktop,
  onToggleCollapseDesktop,
  backendHealth,
}) {
  const [activeNav, setActiveNav] = useState('Studio');
  const [copiedShare, setCopiedShare] = useState(false);

  const handleShare = () => {
    navigator.clipboard?.writeText(window.location.href);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  return (
    <header className="h-16 bg-surface/85 backdrop-blur-xl border-b border-[#EAEAE7] sticky top-0 z-30 flex items-center justify-between px-4 sm:px-6 shadow-[0_1px_8px_rgba(0,0,0,0.03)]">
      {/* Left Title and Controls */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Mobile menu button */}
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="md:hidden p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
          aria-label="Open navigation drawer"
        >
          <Menu className="w-5 h-5 text-on-surface" />
        </button>

        {/* Desktop expand sidebar button when collapsed */}
        {isCollapsedDesktop && (
          <button
            type="button"
            onClick={onToggleCollapseDesktop}
            className="hidden md:flex p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen className="w-4 h-4 text-outline" />
          </button>
        )}

        <div className="flex items-center gap-2 min-w-0">
          <MessageSquare className="w-4 h-4 text-primary shrink-0" />
          <h2 className="font-semibold text-[14px] sm:text-[14.5px] text-on-surface truncate">
            {title}
          </h2>
          <span className="text-outline text-[12.5px] hidden sm:inline truncate">
            · {category || 'Growth Strategy'}
          </span>
        </div>
      </div>

      {/* Right Navigation & Tools */}
      <div className="flex items-center gap-2.5 sm:gap-4 shrink-0">
        {/* Top workspace nav pills */}
        <nav className="hidden lg:flex items-center gap-5 text-[13px] font-medium" aria-label="Workbench context">
          {['Studio', 'Library', 'Notebook'].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveNav(tab)}
              className={`transition-colors ${
                activeNav === tab
                  ? 'text-on-surface font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>

        <div className="hidden lg:block h-4 w-px bg-surface-container-highest" />

        {/* Ollama Local Model Selector */}
        <ModelSelector
          selectedModelId={selectedModelId}
          onSelectModel={onSelectModel}
          backendHealth={backendHealth}
        />

        {/* Share Button */}
        <button
          type="button"
          onClick={handleShare}
          title={copiedShare ? 'Link copied!' : 'Share discussion'}
          aria-label="Share discussion link"
          className="p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors relative"
        >
          {copiedShare ? (
            <Check className="w-4 h-4 text-emerald-600" />
          ) : (
            <Share2 className="w-4 h-4 text-outline hover:text-on-surface" />
          )}
        </button>

        {/* Preferences Button */}
        <button
          type="button"
          onClick={() => alert(`Active Engine: ${selectedModelId}\nActive Provider: ${backendHealth?.activeProvider || 'ollama'}\nBackend Status: ${backendHealth?.connected ? 'Online (FastAPI port 8000)' : 'Offline'}`)}
          title="Preferences & Telemetry"
          aria-label="Preferences"
          className="p-1.5 text-on-surface-variant hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors hidden sm:inline-flex"
        >
          <SlidersHorizontal className="w-4 h-4 text-outline" />
        </button>

        {/* User Avatar */}
        <div 
          className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white cursor-pointer shadow-sm hover:opacity-90 transition-opacity"
          title="Elena Vance (Chief Growth Officer)"
        >
          <User className="w-3.5 h-3.5" />
        </div>
      </div>
    </header>
  );
}
