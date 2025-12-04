'use client';

import { useState } from 'react';
import { api } from '../utils/api';
import { Upload, Link, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';

export default function IngestForm() {
    const [activeTab, setActiveTab] = useState<'text' | 'file' | 'url'>('text');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    // Form states
    const [text, setText] = useState('');
    const [url, setUrl] = useState('');
    const [recursive, setRecursive] = useState(false);
    const [file, setFile] = useState<File | null>(null);

    const handleIngest = async () => {
        setLoading(true);
        setMessage(null);
        try {
            let response;
            if (activeTab === 'text') {
                response = await api.post('/ingest', { text, metadata: { source: 'manual' } });
            } else if (activeTab === 'url') {
                response = await api.post('/ingest/url', { url, recursive });
            } else if (activeTab === 'file' && file) {
                const formData = new FormData();
                formData.append('file', file);
                response = await api.post('/ingest/file', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
            }

            if (response?.data.status === 'success') {
                setMessage({ type: 'success', text: response.data.message });
                // Reset forms
                setText('');
                setUrl('');
                setFile(null);
            }
        } catch (error: any) {
            setMessage({
                type: 'error',
                text: error.response?.data?.detail || 'Ingestion failed'
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-600" />
                Ingest Content
            </h2>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-gray-100 pb-2">
                <button
                    onClick={() => setActiveTab('text')}
                    className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                        activeTab === 'text' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'
                    )}
                >
                    <FileText className="w-4 h-4" /> Text
                </button>
                <button
                    onClick={() => setActiveTab('file')}
                    className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                        activeTab === 'file' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'
                    )}
                >
                    <Upload className="w-4 h-4" /> File
                </button>
                <button
                    onClick={() => setActiveTab('url')}
                    className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                        activeTab === 'url' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'
                    )}
                >
                    <Link className="w-4 h-4" /> URL
                </button>
            </div>

            {/* Content */}
            <div className="space-y-4">
                {activeTab === 'text' && (
                    <textarea
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Paste text content here..."
                        className="w-full h-32 p-3 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none text-black"
                    />
                )}

                {activeTab === 'file' && (
                    <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
                        <input
                            type="file"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            className="hidden"
                            id="file-upload"
                            accept=".pdf,.docx,.txt,.md,.html"
                        />
                        <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-2">
                            <Upload className="w-8 h-8 text-gray-400" />
                            <span className="text-sm text-gray-600">
                                {file ? file.name : 'Click to upload PDF, DOCX, or TXT'}
                            </span>
                        </label>
                    </div>
                )}

                {activeTab === 'url' && (
                    <div className="space-y-3">
                        <input
                            type="url"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://example.com"
                            className="w-full p-3 rounded-lg border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-black"
                        />
                        <label className="flex items-center gap-2 text-sm text-gray-600">
                            <input
                                type="checkbox"
                                checked={recursive}
                                onChange={(e) => setRecursive(e.target.checked)}
                                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                            Recursive Crawling (Max 5 pages)
                        </label>
                    </div>
                )}

                {/* Action Button */}
                <button
                    onClick={handleIngest}
                    disabled={loading || (activeTab === 'text' && !text) || (activeTab === 'url' && !url) || (activeTab === 'file' && !file)}
                    className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" /> Processing...
                        </>
                    ) : (
                        <>
                            Ingest Content
                        </>
                    )}
                </button>

                {/* Feedback Message */}
                {message && (
                    <div className={clsx(
                        'p-3 rounded-lg flex items-center gap-2 text-sm',
                        message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                    )}>
                        {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                        {message.text}
                    </div>
                )}
            </div>
        </div>
    );
}
