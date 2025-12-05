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

    // Collections state
    const [selectedCollections, setSelectedCollections] = useState<string[]>([]);


    const toggleCollection = (id: string) => {
        if (selectedCollections.includes(id)) {
            setSelectedCollections(prev => prev.filter(c => c !== id));
        } else {
            setSelectedCollections(prev => [...prev, id]);
        }
    };

    const COLLECTIONS = [
        { id: 'botanical', label: 'Botanisches Wissen' },
        { id: 'pharmacological', label: 'Pharmakologisches Wissen' },
        { id: 'studies', label: 'Daten und Studien' },
        { id: 'production', label: 'Produktionswissen' },
    ];

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

            const collectionsPayload = selectedCollections.length > 0 ? selectedCollections : [];

            if (activeTab === 'text') {
                endpoint = '/ingest';
                body = JSON.stringify({
                    text,
                    metadata: { source: 'manual' },
                    collections: collectionsPayload
                });
                headers['Content-Type'] = 'application/json';
            } else if (activeTab === 'url') {
                endpoint = '/ingest/url';
                body = JSON.stringify({
                    url,
                    recursive,
                    collections: collectionsPayload
                });
                headers['Content-Type'] = 'application/json';
            } else if (activeTab === 'file' && file) {
                endpoint = '/ingest/file';
                const formData = new FormData();
                formData.append('file', file);

                // For list of strings in FormData, often comma-seperated is easiest if backend expects it
                // Or append same key multiple times. Our backend route logic splits comma-separated string `collections`.
                if (collectionsPayload.length > 0) {
                    formData.append('collections', collectionsPayload.join(','));
                }

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
                            setSelectedCollections([]);
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
        <div className="bg-white p-8 rounded-3xl shadow-sm border border-gray-100">
            <h2 className="text-2xl font-bold mb-8 text-gray-800 flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg border border-blue-200">
                    <Upload className="w-5 h-5 text-blue-600" />
                </div>
                Ingest Content
            </h2>

            {/* Tabs */}
            <div className="flex gap-2 mb-8 p-1 bg-gray-100 rounded-2xl w-fit">
                {['text', 'file', 'url'].map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab as any)}
                        className={clsx(
                            'px-6 py-2.5 rounded-xl text-sm font-medium transition-all flex items-center gap-2',
                            activeTab === tab
                                ? 'bg-white text-gray-900 shadow-sm'
                                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
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
            <div className="space-y-6">
                {activeTab === 'text' && (
                    <div className="group">
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            placeholder="Paste text content here..."
                            className="w-full h-40 p-4 rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder-gray-400 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all resize-none"
                        />
                    </div>
                )}

                {activeTab === 'file' && (
                    <div className="border-2 border-dashed border-gray-200 hover:border-blue-400 rounded-2xl p-12 text-center transition-all bg-gray-50/50 hover:bg-blue-50/10 group cursor-pointer">
                        <input
                            type="file"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            className="hidden"
                            id="file-upload"
                            accept=".pdf,.docx,.txt,.md,.html"
                        />
                        <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-4">
                            <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-sm border border-gray-100 group-hover:scale-110 transition-transform duration-300">
                                <Upload className="w-6 h-6 text-gray-400 group-hover:text-blue-500 transition-colors" />
                            </div>
                            <div className="space-y-1">
                                <span className="block text-sm font-medium text-gray-700">
                                    {file ? file.name : 'Click to upload'}
                                </span>
                                <span className="block text-xs text-gray-400">
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
                            className="w-full p-4 rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder-gray-400 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                        />
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-gray-50/50 border border-gray-100">
                            <input
                                type="checkbox"
                                checked={recursive}
                                onChange={(e) => setRecursive(e.target.checked)}
                                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                id="recursive"
                            />
                            <label htmlFor="recursive" className="text-sm text-gray-600 cursor-pointer select-none">
                                Recursive Crawling (Max 5 pages)
                            </label>
                        </div>
                    </div>
                )}

                {/* Collection Selector */}
                <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                    <label className="block text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wider text-xs">
                        Target RAG Collections (Master + Selection)
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {COLLECTIONS.map((col) => (
                            <div
                                key={col.id}
                                onClick={() => toggleCollection(col.id)}
                                className={clsx(
                                    "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all select-none",
                                    selectedCollections.includes(col.id)
                                        ? "bg-blue-50 border-blue-200 shadow-sm"
                                        : "bg-white border-gray-200 hover:border-gray-300"
                                )}
                            >
                                <div className={clsx(
                                    "w-5 h-5 rounded border flex items-center justify-center transition-colors",
                                    selectedCollections.includes(col.id)
                                        ? "bg-blue-600 border-blue-600"
                                        : "border-gray-300 bg-white"
                                )}>
                                    {selectedCollections.includes(col.id) && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                </div>
                                <span className={clsx(
                                    "text-sm font-medium",
                                    selectedCollections.includes(col.id) ? "text-blue-900" : "text-gray-600"
                                )}>
                                    {col.label}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Progress Bar */}
                {progress && (
                    <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                        <div className="flex justify-between text-xs text-gray-500 font-medium">
                            <span className="flex items-center gap-2">
                                <RefreshCw className="w-3 h-3 animate-spin text-blue-500" />
                                {progress.message}
                            </span>
                            <span>{Math.round(progress.percent)}%</span>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-red-500 transition-all duration-500 ease-out"
                                style={{ width: `${progress.percent}%` }}
                            ></div>
                        </div>
                    </div>
                )}

                {/* Action Button */}
                {!progress && (
                    <div className="flex justify-end">
                        <button
                            onClick={handleIngest}
                            disabled={loading || (activeTab === 'text' && !text) || (activeTab === 'url' && !url) || (activeTab === 'file' && !file)}
                            className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-medium transition-all shadow-md shadow-blue-600/20 hover:shadow-lg hover:shadow-blue-600/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
                        >
                            Ingest Content
                        </button>
                    </div>
                )}

                {/* Feedback Message */}
                {message && !progress && (
                    <div className={clsx(
                        'p-4 rounded-xl flex items-center gap-3 text-sm animate-in fade-in slide-in-from-bottom-2',
                        message.type === 'success'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                            : 'bg-red-50 text-red-700 border border-red-100'
                    )}>
                        {message.type === 'success' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
                        <p className="font-medium">{message.text}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
