import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Cpu, Server, Cloud, Bot, Key } from 'lucide-react';
import { mockModels } from '../data/mockModels';

export function ModelSelector({ selectedModelId, onSelectModel, backendHealth }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const selectedModel = mockModels.find((m) => m.id === selectedModelId) || mockModels[0];
  const isOllamaConnected = backendHealth?.ollama?.connected ?? true;
  const isAnthropicConfigured = backendHealth?.anthropic?.api_key_configured ?? false;

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const activeIsReady = selectedModel.isCloud ? isAnthropicConfigured : isOllamaConnected;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label="Select LLM Provider or Model"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface text-label-sm transition-colors border border-transparent hover:border-surface-container-highest focus:outline-none focus:ring-2 focus:ring-primary/20"
      >
        <span 
          className={`w-1.5 h-1.5 rounded-full ${
            activeIsReady ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
          }`} 
          aria-hidden="true" 
        />
        <span className="font-medium text-[13px]">{selectedModel.tag}</span>
        <span className="text-outline text-[12px] hidden sm:inline">({selectedModel.name})</span>
        <ChevronDown className={`w-3.5 h-3.5 text-outline transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div
          role="listbox"
          aria-label="Available LLM Providers and Models"
          className="absolute right-0 mt-2 w-88 sm:w-96 bg-surface-container-lowest rounded-xl shadow-[0_12px_32px_-4px_rgba(26,26,26,0.12),0_4px_8px_-2px_rgba(26,26,26,0.04)] border border-[#E2E2DE] py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150"
        >
          {/* Header Status Bar */}
          <div className="px-3.5 py-2 border-b border-[#EAEAE7] mb-1">
            <div className="flex items-center justify-between">
              <span className="font-label-md text-label-md text-on-surface font-semibold flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5 text-primary" />
                LLM Providers & Agents
              </span>
              <span className="text-[11px] font-mono text-outline">FastAPI Port 8000</span>
            </div>
            <div className="flex items-center gap-3 mt-1.5 text-[11px]">
              <span className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${isOllamaConnected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                Ollama: {isOllamaConnected ? 'Ready (Local)' : 'Offline'}
              </span>
              <span className="text-outline">·</span>
              <span className="flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${isAnthropicConfigured ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                Claude: {isAnthropicConfigured ? 'Ready (Cloud)' : 'Key Required in .env'}
              </span>
            </div>
          </div>

          {/* Model Options */}
          <div className="max-h-80 overflow-y-auto px-1.5 py-1 space-y-1">
            {mockModels.map((model) => {
              const isSelected = model.id === selectedModel.id;
              const isCloudKeyMissing = model.isCloud && !isAnthropicConfigured;

              return (
                <button
                  key={model.id}
                  role="option"
                  aria-selected={isSelected}
                  type="button"
                  onClick={() => {
                    onSelectModel(model.id);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left p-2.5 rounded-lg transition-colors flex items-start justify-between gap-2 ${
                    isSelected
                      ? 'bg-primary-fixed/25 border border-primary-fixed/50'
                      : 'hover:bg-surface-container text-on-surface'
                  }`}
                >
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {model.useAgent ? (
                        <Bot className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                      ) : model.isCloud ? (
                        <Cloud className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                      ) : (
                        <Cpu className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      )}
                      <span className="font-medium text-[13px] text-on-surface">{model.name}</span>
                      <span className="font-mono text-[11px] text-outline bg-surface-container px-1.5 py-0.2 rounded">
                        {model.version}
                      </span>
                      {isCloudKeyMissing && (
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.2 rounded-full">
                          <Key className="w-2.5 h-2.5" />
                          Key Required
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] text-on-surface-variant line-clamp-1">
                      {model.description}
                    </p>
                    <div className="flex items-center gap-2 pt-0.5 text-[11px] text-outline">
                      <span className="font-medium">{model.provider}</span>
                      <span>·</span>
                      <span className="font-mono">{model.contextSize}</span>
                    </div>
                  </div>

                  {isSelected && (
                    <span className="text-primary mt-1 shrink-0">
                      <Check className="w-4 h-4" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Footer Active Indicator */}
          <div className="px-3.5 pt-2 mt-1 border-t border-[#EAEAE7] flex items-center justify-between text-[11px] text-outline">
            <span className="flex items-center gap-1 font-mono">
              Provider: {selectedModel.providerType}
            </span>
            <span>Active: <code className="font-mono text-on-surface">{selectedModel.id}</code></span>
          </div>
        </div>
      )}
    </div>
  );
}
