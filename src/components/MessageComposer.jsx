import React, { useState, useRef } from 'react';
import { Paperclip, Mic, Send, CornerDownLeft, Sparkles, FileText, Code2 } from 'lucide-react';

export function MessageComposer({ onSendMessage, isLoading }) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [composerMode, setComposerMode] = useState('chat'); // 'chat' | 'essay' | 'html'
  const textareaRef = useRef(null);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    let options = {};
    if (composerMode === 'essay') {
      options = { skill: 'essay' };
    } else if (composerMode === 'html') {
      options = { createArtifact: true, artifactType: 'html' };
    }

    onSendMessage(input.trim(), attachment, options);
    setInput('');
    setAttachment(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    // Send on Cmd+Enter / Ctrl+Enter or plain Enter without Shift
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaChange = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  const handleMockAttachment = () => {
    if (attachment) {
      setAttachment(null);
    } else {
      setAttachment('growth-metrics-q3.csv');
    }
  };

  const toggleMockRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      setTimeout(() => {
        setInput((prev) => (prev ? prev + ' ' : '') + 'How do we calculate net revenue retention across monthly cohorts?');
        setIsRecording(false);
      }, 1800);
    } else {
      setIsRecording(false);
    }
  };

  const getPlaceholder = () => {
    if (composerMode === 'essay') {
      return "Topic for 'Ship 30 for 30' essay (e.g. 'Founder-led B2B positioning frameworks')...";
    }
    if (composerMode === 'html') {
      return "Topic for HTML interactive artifact (e.g. 'Build an interactive retention cohort calculator')...";
    }
    return "Ask about product, growth, or startup strategy...";
  };

  return (
    <footer className="p-4 sm:p-space-lg bg-surface-container-lowest border-t border-[#EAEAE7] shadow-[0_-2px_12px_rgba(0,0,0,0.03)] shrink-0">
      <div className="max-w-[680px] mx-auto space-y-2">
        {/* Mode Selector Chips */}
        <div className="flex items-center gap-1.5 px-1">
          <button
            type="button"
            onClick={() => setComposerMode('chat')}
            className={`px-2.5 py-1 rounded-lg text-[12px] font-medium transition-all ${
              composerMode === 'chat'
                ? 'bg-surface-container-high text-on-surface font-semibold shadow-xs'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            Direct Q&A
          </button>

          <button
            type="button"
            onClick={() => setComposerMode('essay')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[12px] font-medium transition-all ${
              composerMode === 'essay'
                ? 'bg-primary-fixed text-primary font-semibold shadow-xs'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
            title="Generate a ~1,250-word structured Ship 30 for 30 essay"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#4E45D5]" />
            <span>Ship 30 for 30 Essay</span>
          </button>

          <button
            type="button"
            onClick={() => setComposerMode('html')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[12px] font-medium transition-all ${
              composerMode === 'html'
                ? 'bg-secondary-fixed text-on-secondary-fixed font-semibold shadow-xs'
                : 'text-outline hover:text-on-surface hover:bg-surface-container'
            }`}
            title="Generate a standalone HTML/CSS interactive artifact"
          >
            <Code2 className="w-3.5 h-3.5 text-[#4E45D5]" />
            <span>HTML Artifact</span>
          </button>
        </div>

        <div className="relative bg-surface-container-low rounded-xl p-2 sm:p-space-sm focus-within:bg-surface-container-lowest focus-within:shadow-md transition-all border border-surface-container-high focus-within:border-[#D6D6D2]">
          {/* Mock attachment chip if attached */}
          {attachment && (
            <div className="mb-2 flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high text-[12px] font-mono w-fit text-on-surface">
              <Paperclip className="w-3.5 h-3.5 text-primary" />
              <span>{attachment}</span>
              <button
                type="button"
                onClick={() => setAttachment(null)}
                className="ml-1 text-outline hover:text-on-surface font-bold text-[14px]"
              >
                ×
              </button>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={getPlaceholder()}
            rows={2}
            className="w-full bg-transparent text-[14px] text-on-surface placeholder:text-outline resize-none focus:outline-none px-1 leading-relaxed"
            aria-label="Message prompt composer"
          />

          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleMockAttachment}
                className={`p-1.5 rounded-lg transition-colors ${
                  attachment ? 'bg-primary-fixed text-primary' : 'text-outline hover:text-on-surface hover:bg-surface-container'
                }`}
                title="Attach notes or transcript"
                aria-label="Attach file"
              >
                <Paperclip className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={toggleMockRecording}
                className={`p-1.5 rounded-lg transition-colors ${
                  isRecording
                    ? 'bg-red-100 text-red-600 animate-pulse'
                    : 'text-outline hover:text-on-surface hover:bg-surface-container'
                }`}
                title={isRecording ? 'Listening...' : 'Voice input'}
                aria-label="Voice input"
              >
                <Mic className="w-4 h-4" />
              </button>

              {isRecording && (
                <span className="text-[12px] text-red-600 animate-pulse font-medium ml-1">
                  Listening...
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!input.trim() || isLoading}
                className="flex items-center gap-1.5 px-3.5 py-1.5 bg-primary text-on-primary rounded-lg text-[13px] font-medium hover:bg-primary-container transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                aria-label="Send message"
              >
                {isLoading ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Synthesizing...</span>
                  </span>
                ) : (
                  <>
                    <span>{composerMode === 'essay' ? 'Generate Essay' : composerMode === 'html' ? 'Build Artifact' : 'Send'}</span>
                    <kbd className="font-mono text-[11px] opacity-80 hidden sm:inline">⌘↵</kbd>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-[12px] text-outline">
          {composerMode === 'essay'
            ? "'Ship 30 for 30' essay module grounds ~1,250 words in verified Lenny's Podcast transcripts."
            : composerMode === 'html'
            ? 'Interactive HTML is sanitized and rendered in an isolated sandbox.'
            : "AI synthesized from Lenny's verified podcast transcripts. Cross-reference primary citations."}
        </p>
      </div>
    </footer>
  );
}
