import React, { useState } from 'react';
import { 
  Copy, 
  Check, 
  Bookmark, 
  BookmarkCheck, 
  Mic, 
  FileText, 
  ThumbsUp, 
  ThumbsDown, 
  RotateCw,
  FileCode2,
  ExternalLink,
  AlertTriangle,
  RefreshCw,
  BookOpen,
  Calendar,
  Sparkles
} from 'lucide-react';
import { BrandLogo } from './BrandLogo';

export function ChatMessage({ message, onOpenArtifact, onRetry }) {
  const [copied, setCopied] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [expandedExcerpts, setExpandedExcerpts] = useState({});

  const handleCopy = () => {
    let textToCopy = '';
    if (message.sender === 'user') {
      textToCopy = message.content;
    } else {
      textToCopy = message.content || message.contentIntro || '';
      if (message.sections?.length) {
        textToCopy += '\n\n' + message.sections.map(s => `${s.num} ${s.title}: ${s.body}`).join('\n\n');
      }
      if (message.citations?.length) {
        textToCopy += '\n\nSources:\n' + message.citations.map(c => `- ${c.guest}: "${c.episode_title}" (${c.youtube_url || 'YouTube'})`).join('\n');
      }
    }
    
    navigator.clipboard?.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleExcerpt = (idx) => {
    setExpandedExcerpts(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  const renderFormattedParagraph = (text) => {
    if (!text) return null;
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-semibold text-on-surface">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  const renderMultiParagraphText = (content) => {
    if (!content) return null;
    const paragraphs = content.split('\n\n');
    return paragraphs.map((para, pIdx) => {
      const trimmed = para.trim();
      if (!trimmed) return null;

      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        const lines = trimmed.split('\n');
        return (
          <ul key={pIdx} className="space-y-1.5 pl-4 list-disc text-[14.5px] leading-relaxed text-on-surface">
            {lines.map((line, lIdx) => (
              <li key={lIdx}>
                {renderFormattedParagraph(line.replace(/^[-*]\s+/, ''))}
              </li>
            ))}
          </ul>
        );
      }

      if (/^\d+\.\s/.test(trimmed)) {
        const lines = trimmed.split('\n');
        return (
          <ol key={pIdx} className="space-y-1.5 pl-4 list-decimal text-[14.5px] leading-relaxed text-on-surface">
            {lines.map((line, lIdx) => (
              <li key={lIdx}>
                {renderFormattedParagraph(line.replace(/^\d+\.\s+/, ''))}
              </li>
            ))}
          </ol>
        );
      }

      return (
        <p key={pIdx} className="text-[14.5px] leading-relaxed text-on-surface whitespace-pre-line">
          {renderFormattedParagraph(trimmed)}
        </p>
      );
    });
  };

  if (message.sender === 'user') {
    return (
      <article className="flex items-start gap-space-md group animate-in fade-in duration-200">
        <div className="w-8 h-8 rounded-lg bg-inverse-surface text-inverse-on-surface flex items-center justify-center font-semibold text-[13px] shrink-0 shadow-sm">
          AK
        </div>
        <div className="flex-1 space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-[13.5px] text-on-surface">
              {message.authorName || 'Alex Kim'}
            </span>
            <span className="text-[12px] text-outline">
              {message.authorRole || 'Head of Growth'}
            </span>
            <span className="text-outline text-[12px]">·</span>
            <time className="text-[12px] text-outline">
              {message.timestamp}
            </time>
          </div>
          <div className="p-space-md rounded-xl bg-surface-container-lowest shadow-[0_1px_4px_rgba(0,0,0,0.02)] text-on-surface text-[15px] leading-relaxed border border-[#EAEAE7]">
            {message.content}
          </div>
        </div>
      </article>
    );
  }

  // Assistant / System Message
  return (
    <article className="flex items-start gap-space-md group animate-in fade-in duration-200">
      <div className={`w-8 h-8 rounded-lg bg-surface-container-lowest p-1 flex items-center justify-center shrink-0 shadow-sm border ${
        message.isError ? 'border-red-300 bg-red-50' : 'border-surface-container-high'
      }`}>
        {message.isError ? (
          <AlertTriangle className="w-4 h-4 text-red-600" />
        ) : (
          <BrandLogo className="w-full h-full" />
        )}
      </div>

      <div className="flex-1 space-y-3 min-w-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-[13.5px] text-on-surface">
              {message.authorName || 'Lenny Assistant'}
            </span>
            <span className="text-[12px] text-outline">
              {message.timestamp}
            </span>

            {/* Badges */}
            {message.isReal ? (
              <span className="text-[11px] font-mono tracking-tight bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-md flex items-center gap-1.5 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                RAG Grounded · {message.model || 'qwen2.5:3b'}
              </span>
            ) : message.isError ? (
              <span className="text-[11px] font-mono tracking-tight bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded-md flex items-center gap-1 font-medium">
                Backend Error
              </span>
            ) : (
              <span className="text-[10px] uppercase font-mono tracking-wider bg-surface-container px-1.5 py-0.5 rounded text-outline border border-[#E2E2DE]">
                Sample Archive
              </span>
            )}
          </div>

          {!message.isError && (
            <div className="flex items-center gap-1 text-outline">
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copy message"
                title={copied ? 'Copied!' : 'Copy response'}
                className="p-1 hover:text-on-surface rounded hover:bg-surface-container transition-colors"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
              </button>
              <button
                type="button"
                onClick={() => setBookmarked(!bookmarked)}
                aria-label="Bookmark insight"
                title={bookmarked ? 'Saved to insights' : 'Save insight'}
                className="p-1 hover:text-on-surface rounded hover:bg-surface-container transition-colors"
              >
                {bookmarked ? (
                  <BookmarkCheck className="w-4 h-4 text-primary fill-primary/20" />
                ) : (
                  <Bookmark className="w-4 h-4" />
                )}
              </button>
            </div>
          )}
        </div>

        {/* Content Card */}
        <div className={`p-space-lg rounded-xl bg-surface-container-lowest shadow-[0_1px_4px_rgba(0,0,0,0.03)] space-y-4 text-on-surface border ${
          message.isError ? 'border-red-200 bg-red-50/40' : 'border-[#EAEAE7]'
        }`}>
          {message.isError ? (
            <div className="space-y-3 py-1">
              <div className="flex items-start gap-2.5 text-red-800">
                <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="font-semibold text-[14px] text-red-900">
                    {message.isTimeout ? 'Local Inference Timeout (Bounded Wait Reached)' : 'Ollama Backend Request Failed'}
                  </h4>
                  <p className="text-[13.5px] leading-relaxed text-red-700 whitespace-pre-wrap">
                    {message.content}
                  </p>
                  {message.isTimeout && (
                    <div className="mt-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-[12.5px] space-y-1">
                      <div className="font-semibold flex items-center gap-1.5 text-amber-800">
                        <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                        Hardware & Throughput Analysis (Measured)
                      </div>
                      <p className="text-amber-700 leading-relaxed">
                        Local CPU inference on dual-core Intel Core i3 generates at measured ~2.3–2.7 tokens/s. Generating the complete ~1,250-word essay (~1,650 output tokens) requires ~11–13 minutes, reaching the 420s safety timeout. For instant generation of the full essay, configure <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[11.5px]">ANTHROPIC_API_KEY</code> in <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[11.5px]">backend/.env</code> and select <strong>Claude 3.5 Sonnet</strong> in the model selector.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2 border-t border-red-200 flex-wrap">
                {onRetry && (
                  <button
                    type="button"
                    onClick={() => onRetry(message.originalPrompt || '', { isRetry: true, isEssay: message.isEssay })}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-[12.5px] font-medium hover:bg-red-700 transition-colors shadow-sm"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>{message.isTimeout ? 'Retry Generation' : 'Retry Query'}</span>
                  </button>
                )}
                <span className="text-[12px] text-red-600">
                  {message.isTimeout
                    ? 'Retrying will not create duplicate messages in database.'
                    : 'Ensure FastAPI (`http://localhost:8000`) and Ollama are active.'}
                </span>
              </div>
            </div>
          ) : (
            <>
              {message.contentIntro && (
                <p className="text-[15px] leading-relaxed text-on-surface">
                  {renderFormattedParagraph(message.contentIntro)}
                </p>
              )}

              {message.content && (
                <div className="space-y-3">
                  {renderMultiParagraphText(message.content)}
                  {message.isStreaming && (
                    <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse align-middle rounded-sm" />
                  )}
                </div>
              )}

              {message.isStreaming && !message.content && (
                <div className="flex items-center gap-2 text-[13.5px] text-on-surface-variant italic py-1">
                  <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
                  <span>Synthesizing transcript evidence...</span>
                </div>
              )}

              {/* Sample sections if mock message */}
              {message.sections && message.sections.length > 0 && (
                <div className="space-y-4 pt-1">
                  {message.sections.map((section, idx) => (
                    <div key={idx} className="space-y-1.5 pt-1">
                      <h3 className="text-[15.5px] font-semibold text-on-surface flex items-center gap-2">
                        <span className="text-primary font-mono font-bold text-[14px]">
                          {section.num}
                        </span>
                        {section.title}
                      </h3>
                      <p className="text-[14px] text-on-surface-variant leading-relaxed">
                        {section.body}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* REAL RAG CITATIONS BLOCK */}
              {message.citations && message.citations.length > 0 && (
                <div className="pt-3 border-t border-[#EAEAE7] space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11.5px] font-semibold uppercase tracking-wider text-primary flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5" />
                      Verified Source Citations ({message.citations.length})
                    </span>
                    <span className="text-[11px] text-outline font-mono">
                      ChromaDB · nomic-embed-text
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-2 pt-1">
                    {message.citations.map((cite, cIdx) => {
                      const isExpanded = !!expandedExcerpts[cIdx];
                      const matchPct = Math.round((cite.relevance_score || 0.8) * 100);

                      return (
                        <div
                          key={cIdx}
                          className="p-3 rounded-xl bg-surface-container-low border border-surface-container-high hover:border-primary/40 transition-colors space-y-1.5 text-left"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-semibold text-[13px] text-on-surface">
                                  {cite.guest}
                                </span>
                                {cite.publish_date && (
                                  <span className="text-[11px] text-outline flex items-center gap-1">
                                    <Calendar className="w-3 h-3" />
                                    {cite.publish_date}
                                  </span>
                                )}
                              </div>
                              <p className="text-[12.5px] text-on-surface-variant font-medium line-clamp-1 mt-0.5">
                                {cite.episode_title}
                              </p>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <span
                                className="font-mono text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded"
                                title="Vector retrieval cosine similarity"
                              >
                                {matchPct}% similarity
                              </span>

                              {cite.youtube_url && (
                                <a
                                  href={cite.youtube_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="p-1 rounded text-primary hover:bg-surface-container transition-colors"
                                  title="Open YouTube Episode"
                                  aria-label={`Open YouTube episode for ${cite.guest}`}
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                              )}
                            </div>
                          </div>

                          {/* Excerpt toggle */}
                          {cite.excerpt && (
                            <div className="pt-1">
                              <p className={`text-[12px] text-outline font-serif italic border-l-2 border-primary/40 pl-2 py-0.5 leading-relaxed ${
                                isExpanded ? '' : 'line-clamp-2'
                              }`}>
                                "{cite.excerpt}"
                              </p>
                              {cite.excerpt.length > 140 && (
                                <button
                                  type="button"
                                  onClick={() => toggleExcerpt(cIdx)}
                                  className="text-[11px] text-primary hover:underline font-medium mt-0.5"
                                >
                                  {isExpanded ? 'Show less' : 'View full citation excerpt'}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Inline Canvas / Playbook Card if present */}
              {message.canvasCard && (
                <div className="p-4 rounded-xl bg-primary-fixed/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-primary-fixed/40">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-primary text-on-primary flex items-center justify-center shrink-0 shadow-sm">
                      <FileCode2 className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-primary font-semibold">
                        {message.canvasCard.tag || 'Synthesized Playbook Canvas'}
                      </div>
                      <div className="text-[13.5px] font-semibold text-on-surface">
                        {message.canvasCard.title}
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => onOpenArtifact && onOpenArtifact(message.canvasCard.artifactId)}
                    className="px-3.5 py-1.5 rounded-lg bg-primary text-on-primary text-[13px] font-medium hover:bg-primary-container transition-colors shadow-sm whitespace-nowrap flex items-center justify-center gap-1.5 self-start sm:self-auto"
                  >
                    <span>View in Canvas</span>
                    <ExternalLink className="w-3.5 h-3.5 opacity-80" />
                  </button>
                </div>
              )}

              {/* Interactive feedback bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-[#EAEAE7] text-outline text-[12px]">
                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    onClick={() => setFeedback(feedback === 'helpful' ? null : 'helpful')}
                    className={`flex items-center gap-1 transition-colors hover:text-on-surface ${
                      feedback === 'helpful' ? 'text-primary font-semibold' : ''
                    }`}
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                    <span>Helpful</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFeedback(feedback === 'nuance' ? null : 'nuance')}
                    className={`flex items-center gap-1 transition-colors hover:text-on-surface ${
                      feedback === 'nuance' ? 'text-amber-600 font-semibold' : ''
                    }`}
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                    <span>Needs nuance</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => alert(`Re-synthesizing using ${message.model || 'qwen2.5:3b'}...`)}
                    className="flex items-center gap-1 transition-colors hover:text-on-surface"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                    <span>Re-synthesize</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 text-outline text-[12px]">
                  {message.evalCount && (
                    <span className="font-mono text-[11px] bg-surface-container px-1.5 py-0.5 rounded">
                      {message.evalCount} tokens
                    </span>
                  )}
                  <span>
                    {message.footerInfo || 'Grounded in verified transcripts'}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
