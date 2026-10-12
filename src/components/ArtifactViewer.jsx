import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Code, 
  Copy, 
  Download, 
  X, 
  Lightbulb, 
  Check, 
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Eye,
  FileCode,
  BookOpen
} from 'lucide-react';

export function ArtifactViewer({
  artifact,
  isOpen,
  onClose,
  onGenerateEssay,
  activeConversationTitle,
}) {
  // Tab state: 'preview' | 'code'
  const [activeTab, setActiveTab] = useState('preview');
  const [copiedDoc, setCopiedDoc] = useState(false);
  const [notionPushed, setNotionPushed] = useState(false);

  // If artifact changes and is unsafe HTML, default to code view initially so user sees raw code & warning
  useEffect(() => {
    if (artifact && artifact.artifact_type === 'html' && !artifact.is_safe) {
      setActiveTab('code');
    } else {
      setActiveTab('preview');
    }
  }, [artifact?.id]);

  if (!isOpen) return null;

  // Empty State when no artifact has been generated for the conversation
  if (!artifact) {
    return (
      <aside
        className="w-full lg:w-[490px] shrink-0 bg-surface-container-lowest border-l border-[#EAEAE7] flex flex-col h-full z-20 shadow-[-4px_0_16px_rgba(0,0,0,0.02)] fixed lg:relative right-0 top-0 lg:top-auto bottom-0"
        aria-label="Artifact document viewer empty state"
      >
        <header className="h-14 px-4 sm:px-space-md flex items-center justify-between border-b border-[#EAEAE7] shrink-0 bg-surface-container-lowest">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-surface-container text-outline flex items-center justify-center">
              <FileText className="w-4 h-4" />
            </span>
            <span className="font-semibold text-[13.5px] text-on-surface">Artifact Canvas</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-outline hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
            title="Close viewer"
            aria-label="Close viewer"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-surface-container-low border border-surface-container-high flex items-center justify-center text-primary shadow-sm">
            <Sparkles className="w-6 h-6 text-[#4E45D5]" />
          </div>
          <div className="space-y-1.5 max-w-[320px]">
            <h3 className="text-[16px] font-semibold text-on-surface">No Artifact Generated Yet</h3>
            <p className="text-[13px] text-outline leading-relaxed">
              Artifacts are executive documents, 'Ship 30 for 30' essays, or interactive HTML blueprints generated dynamically alongside your strategy chat.
            </p>
          </div>

          {onGenerateEssay && (
            <button
              type="button"
              onClick={onGenerateEssay}
              className="mt-2 flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-xl text-[13px] font-medium hover:bg-primary-container transition-all shadow-sm"
            >
              <Sparkles className="w-4 h-4" />
              <span>Generate Ship 30 for 30 Essay</span>
            </button>
          )}
        </div>
      </aside>
    );
  }

  const isHtml = artifact.artifact_type === 'html';
  const isSafe = artifact.is_safe !== false;
  const rawContent = artifact.content || artifact.markdownContent || '';
  const wordCount = artifact.word_count || artifact.wordCount || (rawContent.split(/\s+/).filter(Boolean).length);
  const readTime = artifact.read_time || artifact.readTime || `${Math.max(1, Math.round(wordCount / 225))} min read`;
  const fileName = artifact.file_name || artifact.fileName || (isHtml ? 'playbook.html' : 'essay.md');

  const handleCopy = () => {
    navigator.clipboard?.writeText(rawContent);
    setCopiedDoc(true);
    setTimeout(() => setCopiedDoc(false), 2000);
  };

  const handleDownload = () => {
    const mimeType = isHtml ? 'text/html' : 'text/markdown';
    const blob = new Blob([rawContent], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePushToNotion = () => {
    setNotionPushed(true);
    setTimeout(() => setNotionPushed(false), 2500);
  };

  return (
    <aside
      className="w-full lg:w-[490px] shrink-0 bg-surface-container-lowest border-l border-[#EAEAE7] flex flex-col h-full z-20 shadow-[-4px_0_16px_rgba(0,0,0,0.02)] fixed lg:relative right-0 top-0 lg:top-auto bottom-0"
      aria-label="Artifact document viewer"
    >
      {/* 1. Header */}
      <header className="h-14 px-4 sm:px-space-md flex items-center justify-between border-b border-[#EAEAE7] shrink-0 bg-surface-container-lowest">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="p-1.5 rounded-lg bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center shrink-0">
            {isHtml ? <Code className="w-4 h-4 text-[#4E45D5]" /> : <FileText className="w-4 h-4 text-[#4E45D5]" />}
          </span>
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-[13.5px] text-on-surface truncate" title={artifact.title}>
              {artifact.title}
            </span>
            <div className="flex items-center gap-1.5 text-[11.5px] text-outline">
              <span className={`w-1.5 h-1.5 rounded-full ${isSafe ? 'bg-emerald-500' : 'bg-amber-500'} animate-pulse`} />
              <span className="uppercase font-mono text-[10px] tracking-wider font-semibold">
                {artifact.artifact_type || 'markdown'}
              </span>
              <span>·</span>
              <span>{isSafe ? 'Verified Safe' : 'Sanitized'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={handleCopy}
            title={copiedDoc ? 'Copied!' : 'Copy artifact content'}
            aria-label="Copy content"
            className="p-1.5 text-outline hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
          >
            {copiedDoc ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
          </button>

          <button
            type="button"
            onClick={handleDownload}
            title={`Download ${fileName}`}
            aria-label="Download artifact"
            className="p-1.5 text-outline hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={onClose}
            title="Close viewer"
            aria-label="Close viewer"
            className="p-1.5 text-outline hover:text-on-surface rounded-lg hover:bg-surface-container transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* 2. Security Notice Banner (Shown if HTML was sanitized or flagged) */}
      {isHtml && !isSafe && (
        <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-amber-900 flex items-start gap-2.5 text-[12px] shrink-0">
          <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold block">Security Notice: Untrusted Markup Neutralized</span>
            <p className="text-amber-800 leading-tight">
              Model-generated HTML contained disallowed scripts or event handlers. Unsafe code was stripped, and iframe execution is strictly isolated with sandbox restrictions.
            </p>
          </div>
        </div>
      )}

      {/* 3. Segmented Navigation & Stats */}
      <nav
        aria-label="Artifact view controls"
        className="px-4 py-1.5 flex items-center justify-between bg-surface-container-low border-b border-[#EAEAE7] shrink-0"
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('preview')}
            className={`flex items-center gap-1 px-2.5 py-1 text-[13px] font-medium transition-all ${
              activeTab === 'preview'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-[7px] pb-1'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>{isHtml ? 'Preview (Sandbox)' : 'Executive Preview'}</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('code')}
            className={`flex items-center gap-1 px-2.5 py-1 text-[13px] font-medium transition-all ${
              activeTab === 'code'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-[7px] pb-1'
                : 'text-outline hover:text-on-surface'
            }`}
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>{isHtml ? 'HTML Source' : 'Markdown Source'}</span>
          </button>
        </div>

        <span className="text-[12px] text-outline tabular-nums">
          {wordCount} words · {readTime}
        </span>
      </nav>

      {/* 4. Content Area */}
      <main className="flex-1 overflow-y-auto bg-surface-container-lowest flex flex-col">
        {activeTab === 'preview' ? (
          isHtml ? (
            /* Secure Sandboxed HTML iframe View:
               - sandbox="allow-popups"
               - NO allow-scripts
               - NO allow-same-origin
               Prevents cookie, storage, parent DOM, or network execution leakage
            */
            <div className="flex-1 w-full h-full p-2 bg-[#F9F9F8]">
              <iframe
                title={artifact.title || 'HTML Artifact Preview'}
                srcDoc={rawContent}
                sandbox="allow-popups"
                className="w-full h-full min-h-[500px] border border-[#EAEAE7] rounded-xl bg-white shadow-sm"
              />
            </div>
          ) : (
            /* Markdown Executive Preview */
            <div className="p-5 sm:p-6 space-y-6">
              {/* Header Badge & Title */}
              <header className="space-y-2">
                <div className="inline-block px-2.5 py-0.5 rounded bg-surface-container text-[11px] uppercase tracking-wider text-outline font-semibold">
                  {artifact.badge || 'Executive Playbook'}
                </div>
                <h2 className="text-[26px] font-bold text-on-surface tracking-tight leading-tight">
                  {artifact.title}
                </h2>
                {artifact.subtitle && (
                  <p className="text-[14px] text-on-surface-variant italic leading-relaxed">
                    {artifact.subtitle}
                  </p>
                )}
              </header>

              {/* Render Structured Content */}
              <div className="max-w-none text-[15.5px] leading-[1.7] text-on-surface">
                {rawContent.split('\n\n').map((block, idx) => {
                  const trimmed = block.trim();
                  if (!trimmed) return null;

                  if (trimmed.startsWith('# ')) {
                    return (
                      <h1 key={idx} className="text-[27px] font-bold text-on-surface tracking-tight mt-7 mb-3.5 pt-2 border-b border-[#EAEAE7] pb-2 leading-tight">
                        {trimmed.replace(/^#\s+/, '')}
                      </h1>
                    );
                  }
                  if (trimmed.startsWith('## ')) {
                    return (
                      <h2 key={idx} className="text-[22px] font-bold text-on-surface tracking-tight mt-6 mb-3 pt-2 border-b border-[#EAEAE7]/60 pb-1.5 leading-snug">
                        {trimmed.replace(/^##\s+/, '')}
                      </h2>
                    );
                  }
                  if (trimmed.startsWith('### ')) {
                    return (
                      <h3 key={idx} className="text-[18px] font-semibold text-on-surface mt-5 mb-2 leading-snug">
                        {trimmed.replace(/^###\s+/, '')}
                      </h3>
                    );
                  }
                  if (trimmed.startsWith('> ')) {
                    return (
                      <blockquote key={idx} className="p-3.5 rounded-xl bg-primary-fixed/20 border-l-4 border-primary text-[14.5px] text-on-surface italic my-4 leading-[1.7]">
                        {trimmed.replace(/^>\s+/, '')}
                      </blockquote>
                    );
                  }
                  if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    const items = trimmed.split('\n').filter((l) => l.trim().match(/^[-*]\s+/));
                    return (
                      <ul key={idx} className="list-disc pl-6 space-y-2 text-on-surface leading-[1.7] my-4">
                        {items.map((item, i) => (
                          <li key={i} className="leading-[1.7] pl-1" dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(item.replace(/^[-*]\s+/, '')) }} />
                        ))}
                      </ul>
                    );
                  }
                  if (trimmed.match(/^\d+\.\s+/)) {
                    const items = trimmed.split('\n').filter((l) => l.trim().match(/^\d+\.\s+/));
                    return (
                      <ol key={idx} className="list-decimal pl-6 space-y-2 text-on-surface leading-[1.7] my-4">
                        {items.map((item, i) => (
                          <li key={i} className="leading-[1.7] pl-1" dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(item.replace(/^\d+\.\s+/, '')) }} />
                        ))}
                      </ol>
                    );
                  }
                  return (
                    <p key={idx} className="my-4 text-[15.5px] leading-[1.7]" dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(trimmed) }} />
                  );
                })}
              </div>

              {/* Verified Transcript Citations */}
              {artifact.citations && artifact.citations.length > 0 && (
                <footer className="pt-5 space-y-3 border-t border-[#EAEAE7]">
                  <h4 className="text-[11px] uppercase tracking-wider text-outline font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Verified Podcast Evidence Citations</span>
                  </h4>
                  <div className="space-y-2 text-[13px]">
                    {artifact.citations.map((cite, cIdx) => (
                      <div key={cIdx} className="p-3 rounded-lg bg-surface-container-low border border-surface-container-high space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-on-surface">{cite.guest}</span>
                          {cite.episode_number && (
                            <span className="font-mono text-[11px] text-outline bg-surface-container px-1.5 py-0.5 rounded">
                              Ep. #{cite.episode_number}
                            </span>
                          )}
                        </div>
                        <p className="text-[12px] text-outline italic">
                          "{cite.quote || cite.excerpt}"
                        </p>
                        {cite.youtube_url && (
                          <a
                            href={cite.youtube_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11.5px] text-primary hover:underline pt-0.5"
                          >
                            <span>Watch episode</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </footer>
              )}
            </div>
          )
        ) : (
          /* Raw Code Source View (Markdown or HTML) */
          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between text-[12px] text-outline font-mono">
              <span>{fileName}</span>
              <button
                type="button"
                onClick={handleCopy}
                className="text-primary hover:underline flex items-center gap-1 font-sans text-[12px]"
              >
                {copiedDoc ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedDoc ? 'Copied' : `Copy ${isHtml ? 'HTML' : 'Markdown'}`}
              </button>
            </div>
            <pre className="p-5 rounded-xl bg-surface-container-low border border-surface-container-high text-[13px] font-mono leading-[1.6] overflow-x-auto whitespace-pre-wrap text-on-surface select-text">
              {rawContent}
            </pre>
          </div>
        )}
      </main>

      {/* 5. Footer Action Bar */}
      <footer className="p-3.5 border-t border-[#EAEAE7] bg-surface-container-low flex items-center justify-between shrink-0">
        <span className="font-mono text-[12px] text-outline truncate max-w-[180px]" title={fileName}>
          {fileName}
        </span>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-[13px] font-medium text-on-surface transition-colors"
          >
            {copiedDoc ? 'Copied!' : 'Copy Code'}
          </button>

          <button
            type="button"
            onClick={handlePushToNotion}
            className="px-3.5 py-1.5 rounded-lg bg-primary text-on-primary text-[13px] font-medium hover:bg-primary-container transition-colors shadow-sm flex items-center gap-1.5"
          >
            {notionPushed ? (
              <>
                <Check className="w-3.5 h-3.5 text-white" />
                <span>Pushed!</span>
              </>
            ) : (
              <span>Push to Notion</span>
            )}
          </button>
        </div>
      </footer>
    </aside>
  );
}

// Lightweight, safe inline markdown formatter (bold, italics, inline code)
function renderInlineMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code class="px-1 py-0.5 rounded bg-surface-container text-[12px] font-mono text-on-surface">$1</code>');
}
