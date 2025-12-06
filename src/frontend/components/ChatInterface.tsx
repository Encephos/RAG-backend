'use client';

import { useState } from 'react';
import { api, QueryResponse, SearchResult } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, ChevronDown, ChevronRight, Network, FileText, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

export default function ChatInterface() {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [history, setHistory] = useState<Array<{ type: 'user' | 'bot'; content: string; context?: SearchResult[]; graph?: any }>>([]);

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
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 h-[600px] flex flex-col">
            <div className="p-4 border-b border-gray-100 flex items-center gap-2">
                <Bot className="w-5 h-5 text-blue-600" />
                <h2 className="font-semibold">RAG Assistant</h2>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {history.length === 0 && (
                    <div className="text-center text-gray-400 mt-20">
                        <Bot className="w-12 h-12 mx-auto mb-2 opacity-20" />
                        <p>Ask me anything about your documents...</p>
                    </div>
                )}

                {history.map((msg, idx) => (
                    <div key={idx} className={clsx('flex gap-3', msg.type === 'user' ? 'justify-end' : 'justify-start')}>
                        {msg.type === 'bot' && (
                            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                                <Bot className="w-5 h-5 text-blue-600" />
                            </div>
                        )}

                        <div className={clsx(
                            'max-w-[80%] rounded-2xl p-4',
                            msg.type === 'user'
                                ? 'bg-blue-600 text-white rounded-tr-none'
                                : 'bg-gray-50 text-gray-800 rounded-tl-none border border-gray-100'
                        )}>
                            <div className="prose prose-sm max-w-none dark:prose-invert">
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                            </div>

                            {/* Context & Graph Accordion */}
                            {msg.type === 'bot' && (msg.context || msg.graph) && (
                                <ContextAccordion context={msg.context} graph={msg.graph} />
                            )}
                        </div>

                        {msg.type === 'user' && (
                            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                                <User className="w-5 h-5 text-gray-600" />
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="flex gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                            <Bot className="w-5 h-5 text-blue-600" />
                        </div>
                        <div className="bg-gray-50 rounded-2xl rounded-tl-none p-4 border border-gray-100 flex items-center gap-2 text-gray-500">
                            <Loader2 className="w-4 h-4 animate-spin" /> Thinking...
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-gray-100">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
                        placeholder="Type your question..."
                        className="flex-1 p-3 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-black"
                    />
                    <button
                        onClick={handleQuery}
                        disabled={loading || !query.trim()}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}

function ContextAccordion({ context, graph }: { context?: SearchResult[], graph?: any }) {
    const [isOpen, setIsOpen] = useState(false);

    if ((!context || context.length === 0) && (!graph || Object.keys(graph).length === 0)) return null;

    return (
        <div className="mt-3 border-t border-gray-200/50 pt-2">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-blue-600 transition-colors"
            >
                {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                View Sources & Graph Context
            </button>

            {isOpen && (
                <div className="mt-2 space-y-3 text-sm">
                    {/* Vector Context */}
                    {context && context.length > 0 && (
                        <div>
                            <h4 className="flex items-center gap-1 text-xs font-semibold text-gray-400 uppercase mb-1">
                                <FileText className="w-3 h-3" /> Retrieved Chunks
                            </h4>
                            <div className="space-y-2">
                                {context.map((ctx, i) => (
                                    <div key={i} className="bg-white p-2 rounded border border-gray-100 text-xs text-gray-600">
                                        <p className="line-clamp-2 italic">"{ctx.text}"</p>
                                        <div className="mt-1 flex justify-between text-[10px] text-gray-400">
                                            <span>Score: {ctx.score.toFixed(2)}</span>
                                            <span>{ctx.metadata?.filename || ctx.metadata?.source || 'Unknown Source'}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Graph Context */}
                    {graph && graph.summary && (
                        <div>
                            <h4 className="flex items-center gap-1 text-xs font-semibold text-gray-400 uppercase mb-1">
                                <Network className="w-3 h-3" /> Knowledge Graph
                            </h4>
                            <div className="bg-blue-50/50 p-2 rounded border border-blue-100 text-xs text-blue-800">
                                {graph.summary}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
