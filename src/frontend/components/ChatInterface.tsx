'use client';

import { useState, useRef, useEffect } from 'react';
import { api, QueryResponse, SearchResult } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, ChevronDown, ChevronRight, Network, FileText, Sparkles } from 'lucide-react';
import { clsx } from 'clsx';

export default function ChatInterface() {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState<Array<{ type: 'user' | 'bot'; content: string; context?: SearchResult[]; graph?: any }>>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, loading]);

    const handleQuery = async () => {
        if (!query.trim()) return;

        const userQuery = query;
        setQuery('');
        setHistory(prev => [...prev, { type: 'user', content: userQuery }]);
        setLoading(true);

        try {
            const response = await api.post<QueryResponse>('/query', { query: userQuery, limit: 5 });
            setHistory(prev => [...prev, {
                type: 'bot',
                content: response.data.answer,
                context: response.data.context,
                graph: response.data.graph_context
            }]);
        } catch (error: any) {
            setHistory(prev => [...prev, {
                type: 'bot',
                content: `Error: ${error.response?.data?.detail || 'Failed to get answer'}`
            }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="glass-panel rounded-2xl h-[700px] flex flex-col overflow-hidden shadow-2xl shadow-black/20">
            {/* Header */}
            <div className="p-5 border-b border-gray-700/50 flex items-center gap-3 bg-gradient-to-r from-violet-900/20 to-transparent">
                <div className="w-8 h-8 rounded-lg bg-violet-600/20 flex items-center justify-center border border-violet-500/30">
                    <Bot className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                    <h2 className="font-semibold text-gray-100">AI Assistant</h2>
                    <p className="text-xs text-gray-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Ready to help
                    </p>
                </div>
            </div>

            {/* Messages Area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
                {history.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-center p-8">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600/20 to-indigo-600/20 flex items-center justify-center mb-4 border border-violet-500/20 shadow-inner shadow-violet-500/10">
                            <Sparkles className="w-8 h-8 text-violet-400" />
                        </div>
                        <h3 className="text-xl font-medium text-gray-200 mb-2">How can I help you today?</h3>
                        <p className="text-gray-400 max-w-sm">
                            Ask me questions about your documents. I'll search the vector database and check the knowledge graph for insights.
                        </p>
                    </div>
                )}

                {history.map((msg, idx) => (
                    <div key={idx} className={clsx('flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300', msg.type === 'user' ? 'justify-end' : 'justify-start')}>
                        {msg.type === 'bot' && (
                            <div className="w-8 h-8 rounded-lg bg-violet-600/20 flex items-center justify-center flex-shrink-0 border border-violet-500/30 mt-1">
                                <Bot className="w-5 h-5 text-violet-400" />
                            </div>
                        )}

                        <div className={clsx(
                            'max-w-[85%] rounded-2xl p-5 shadow-sm',
                            msg.type === 'user'
                                ? 'bg-gradient-to-br from-violet-600 to-indigo-600 text-white rounded-tr-none shadow-violet-900/20'
                                : 'bg-slate-800/50 border border-slate-700/50 text-gray-200 rounded-tl-none backdrop-blur-sm'
                        )}>
                            <div className="prose prose-invert prose-sm max-w-none text-gray-300 prose-headings:text-gray-100 prose-strong:text-violet-300 prose-a:text-blue-400 prose-code:text-amber-300 prose-code:bg-slate-900/50 prose-code:px-1 prose-code:rounded prose-ul:marker:text-violet-500">
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                            </div>

                            {/* Context & Graph Accordion */}
                            {msg.type === 'bot' && (msg.context || msg.graph) && (
                                <ContextAccordion context={msg.context} graph={msg.graph} />
                            )}
                        </div>

                        {msg.type === 'user' && (
                            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-1 shadow-lg shadow-indigo-600/20">
                                <User className="w-5 h-5 text-white" />
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="flex gap-4 animate-pulse">
                        <div className="w-8 h-8 rounded-lg bg-violet-600/20 flex items-center justify-center flex-shrink-0 border border-violet-500/30">
                            <Bot className="w-5 h-5 text-violet-400" />
                        </div>
                        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl rounded-tl-none p-4 flex items-center gap-3">
                            <div className="flex gap-1">
                                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                            </div>
                            <span className="text-sm text-gray-400 font-medium">Analyzing...</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-5 border-t border-gray-700/50 bg-slate-900/30 backdrop-blur-md">
                <div className="flex gap-3 relative">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
                        placeholder="Type your question..."
                        className="flex-1 bg-slate-800/50 border border-slate-700 text-gray-200 placeholder-gray-500 rounded-xl px-4 py-3 focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 outline-none transition-all shadow-inner"
                    />
                    <button
                        onClick={handleQuery}
                        disabled={loading || !query.trim()}
                        className="px-5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-violet-600/20 flex items-center justify-center group"
                    >
                        <Send className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                </div>
                <div className="text-center mt-2">
                    <p className="text-[10px] text-gray-600 uppercase tracking-wider font-medium">Powered by Gemini 2.5 + Qdrant</p>
                </div>
            </div>
        </div>
    );
}

function ContextAccordion({ context, graph }: { context?: SearchResult[], graph?: any }) {
    const [isOpen, setIsOpen] = useState(false);

    if ((!context || context.length === 0) && (!graph || Object.keys(graph).length === 0)) return null;

    return (
        <div className="mt-4 border-t border-gray-700/50 pt-3">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 text-xs font-semibold text-gray-500 hover:text-violet-400 transition-colors uppercase tracking-wide group w-full"
            >
                {isOpen ? <ChevronDown className="w-3 h-3 group-hover:text-violet-400" /> : <ChevronRight className="w-3 h-3 group-hover:text-violet-400" />}
                Sources & Graph Context
            </button>

            {isOpen && (
                <div className="mt-3 space-y-4 animate-in slide-in-from-top-2 duration-200">
                    {/* Vector Context */}
                    {context && context.length > 0 && (
                        <div>
                            <h4 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase mb-2 tracking-wider">
                                <FileText className="w-3 h-3 text-sky-400" /> Retrieved Documents
                            </h4>
                            <div className="grid gap-2">
                                {context.map((ctx, i) => (
                                    <div key={i} className="bg-slate-900/50 p-3 rounded-lg border border-slate-700/50 group hover:border-violet-500/30 transition-colors">
                                        <p className="text-xs text-gray-400 line-clamp-2 italic font-serif">"{ctx.text}"</p>
                                        <div className="mt-2 flex items-center justify-between">
                                            <span className="text-[10px] font-mono text-violet-400 bg-violet-900/20 px-1.5 py-0.5 rounded">
                                                Score: {ctx.score.toFixed(2)}
                                            </span>
                                            {ctx.metadata?.source_url ? (
                                                <a
                                                    href={ctx.metadata.source_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-[10px] text-violet-400 hover:text-violet-300 truncate max-w-[150px] underline decoration-violet-500/30 transition-colors"
                                                    title="Open Source File"
                                                >
                                                    {ctx.metadata?.filename || 'Open Source'}
                                                </a>
                                            ) : (
                                                <span className="text-[10px] text-gray-500 truncate max-w-[150px]" title={ctx.metadata?.filename || ctx.metadata?.source}>
                                                    {ctx.metadata?.filename || ctx.metadata?.source || 'Unknown Source'}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Graph Context */}
                    {graph && graph.summary && (
                        <div>
                            <h4 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase mb-2 tracking-wider">
                                <Network className="w-3 h-3 text-emerald-400" /> Knowledge Graph
                            </h4>
                            <div className="bg-emerald-900/10 p-3 rounded-lg border border-emerald-500/20 text-xs text-emerald-200/80 leading-relaxed font-mono">
                                {graph.summary}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
