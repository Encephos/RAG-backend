'use client';

import { useState } from 'react';
import { Upload, Link, FileText, Loader2, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '../utils/api'; // Import just to keep potential types, though not used for fetch

export default function IngestForm() {
    const [activeTab, setActiveTab] = useState<'text' | 'file' | 'url'>('text');
    const [loading, setLoading] = useState(false);
    const [progress, setProgress] = useState<{ step: string; message: string; percent: number } | null>(null);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    // Form states
    const [text, setText] = useState('');
    const [url, setUrl] = useState('');
    const [recursive, setRecursive] = useState(false);
    const [file, setFile] = useState<File | null>(null);

    const handleIngest = async () => {
        setLoading(true);
        setMessage(null);
        setProgress({ step: 'start', message: 'Starting...', percent: 0 });

        const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'secret-api-key';
        const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

        try {
            let endpoint = '';
            let body: any;
            let headers: any = {
                'X-API-Key': API_KEY
            };

            if (activeTab === 'text') {
                endpoint = '/ingest';
                body = JSON.stringify({ text, metadata: { source: 'manual' } });
                headers['Content-Type'] = 'application/json';
            } else if (activeTab === 'url') {
                endpoint = '/ingest/url';
                body = JSON.stringify({ url, recursive });
                headers['Content-Type'] = 'application/json';
            } else if (activeTab === 'file' && file) {
                endpoint = '/ingest/file';
                const formData = new FormData();
                formData.append('file', file);
                body = formData;
                // Do NOT set Content-Type for FormData, browser does it with boundary
            }

            // Using fetch for streaming support
            const response = await fetch(`${BASE_URL}${endpoint}`, {
                method: 'POST',
                headers,
                body
            });

            if (!response.ok) throw new Error(response.statusText);
            if (!response.body) throw new Error('No response body');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line);
                        if (event.step === 'error') throw new Error(event.message);

                        setProgress({
                            step: event.step,
                            message: event.message,
                            percent: event.progress * 100
                        });

                        if (event.step === 'complete') {
                            setMessage({ type: 'success', text: event.message });
                            // Reset forms
                            setText('');
                            setUrl('');
                            setFile(null);
                        }
                    } catch (e: any) {
                        console.error("Error parsing stream:", e);
                    }
                }
            }
        } catch (error: any) {
            setMessage({
                type: 'error',
                text: error.message || 'Ingestion failed'
            });
        } finally {
            setLoading(false);
            setTimeout(() => setProgress(null), 3000); // Hide progress after delay
        }
    };

    return (
        <div className="glass-panel p-6 rounded-2xl shadow-lg shadow-black/10">
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-3 text-gray-200">
                <div className="p-2 bg-violet-600/20 rounded-lg border border-violet-500/30">
                    <Upload className="w-5 h-5 text-violet-400" />
                </div>
                Ingest Content
            </h2>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 p-1 bg-slate-900/50 rounded-xl border border-white/5">
                {['text', 'file', 'url'].map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab as any)}
                        className={clsx(
                            'flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2',
                            activeTab === tab
                                ? 'bg-violet-600 text-white shadow-lg shadow-violet-900/20'
                                : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                        )}
                    >
                        {tab === 'text' && <FileText className="w-4 h-4" />}
                        {tab === 'file' && <Upload className="w-4 h-4" />}
                        {tab === 'url' && <Link className="w-4 h-4" />}
                        <span className="capitalize">{tab}</span>
                    </button>
                ))}
            </div>

            {/* Content */}
            <div className="space-y-5">
                {activeTab === 'text' && (
                    <div className="group">
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            placeholder="Paste text content here..."
                            className="w-full h-40 p-4 rounded-xl bg-slate-900/50 border border-slate-700 text-gray-200 placeholder-gray-600 outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all resize-none"
                        />
                    </div>
                )}

                {activeTab === 'file' && (
                    <div className="border-2 border-dashed border-slate-700 hover:border-violet-500/50 rounded-xl p-10 text-center transition-all bg-slate-900/20 group cursor-pointer hover:bg-slate-900/40">
                        <input
                            type="file"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            className="hidden"
                            id="file-upload"
                            accept=".pdf,.docx,.txt,.md,.html"
                        />
                        <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-4">
                            <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center group-hover:scale-110 transition-transform duration-300 border border-slate-700 group-hover:border-violet-500/30">
                                <Upload className="w-8 h-8 text-gray-400 group-hover:text-violet-400 transition-colors" />
                            </div>
                            <div className="space-y-1">
                                <span className="block text-sm font-medium text-gray-300">
                                    {file ? file.name : 'Click to upload'}
                                </span>
                                <span className="block text-xs text-gray-500">
                                    PDF, DOCX, TXT, MD
                                </span>
                            </div>
                        </label>
                    </div>
                )}

                {activeTab === 'url' && (
                    <div className="space-y-4">
                        <input
                            type="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://example.com"
                            className="w-full p-4 rounded-xl bg-slate-900/50 border border-slate-700 text-gray-200 placeholder-gray-600 outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all"
                        />
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-slate-900/30 border border-slate-800">
                            <input
                                type="checkbox"
                                checked={recursive}
                                onChange={(e) => setRecursive(e.target.checked)}
                                className="w-4 h-4 rounded border-slate-600 text-violet-600 focus:ring-violet-500/50 bg-slate-800"
                                id="recursive"
                            />
                            <label htmlFor="recursive" className="text-sm text-gray-400 cursor-pointer select-none">
                                Recursive Crawling (Max 5 pages)
                            </label>
                        </div>
                    </div>
                )}

                {/* Progress Bar */}
                {progress && (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                        <div className="flex justify-between text-xs text-gray-400 font-medium">
                            <span className="flex items-center gap-2">
                                <RefreshCw className="w-3 h-3 animate-spin text-violet-400" />
                                {progress.message}
                            </span>
                            <span>{Math.round(progress.percent)}%</span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded-full overflow-hidden border border-slate-700/50">
                            <div
                                className="h-full bg-gradient-to-r from-violet-600 to-indigo-500 transition-all duration-500 ease-out relative"
                                style={{ width: `${progress.percent}%` }}
                            >
                                <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Action Button */}
                {!progress && (
                    <button
                        onClick={handleIngest}
                        disabled={loading || (activeTab === 'text' && !text) || (activeTab === 'url' && !url) || (activeTab === 'file' && !file)}
                        className="w-full py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white rounded-xl font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-violet-900/20 hover:shadow-violet-900/40 transform active:scale-[0.99]"
                    >
                        Ingest Content
                    </button>
                )}

                {/* Feedback Message */}
                {message && !progress && (
                    <div className={clsx(
                        'p-4 rounded-xl flex items-center gap-3 text-sm animate-in fade-in slide-in-from-bottom-2',
                        message.type === 'success'
                            ? 'bg-emerald-900/20 text-emerald-300 border border-emerald-500/20'
                            : 'bg-red-900/20 text-red-300 border border-red-500/20'
                    )}>
                        {message.type === 'success' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
                        <p className="font-medium">{message.text}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
