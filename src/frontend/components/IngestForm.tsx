'use client';

import { useState, useRef } from 'react';
import { Upload, Link, FileText, Loader2, CheckCircle, AlertCircle, RefreshCw, X, Play, Clock, Database, GraduationCap } from 'lucide-react';
import { clsx } from 'clsx';

type IngestItem = {
    id: string;
    type: 'text' | 'file' | 'url' | 'database' | 'academic';
    content: string | File;
    status: 'pending' | 'processing' | 'completed' | 'error';
    message?: string;
    progress?: number;
    collections: string[];
    // Extra fields for academic
    metadata?: { category?: string; limit?: number };
};

export default function IngestForm() {
    const [activeTab, setActiveTab] = useState<'text' | 'file' | 'url' | 'database' | 'academic'>('text');
    const [queue, setQueue] = useState<IngestItem[]>([]);
    const [processing, setProcessing] = useState(false);

    // Input states
    const [textInput, setTextInput] = useState('');
    const [urlInput, setUrlInput] = useState('');
    const [recursive, setRecursive] = useState(false);
    const [maxPages, setMaxPages] = useState(10);
    const [maxDepth, setMaxDepth] = useState(2);
    const [academicQuery, setAcademicQuery] = useState('');
    const [academicCategory, setAcademicCategory] = useState('General');

    // API Config
    const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'secret-api-key';
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

    // Collections state
    const [selectedCollections, setSelectedCollections] = useState<string[]>([]);

    const COLLECTIONS = [
        { id: 'botanical', label: 'Botanisches Wissen' },
        { id: 'pharmacological', label: 'Pharmakologisches Wissen' },
        { id: 'studies', label: 'Daten und Studien' },
        { id: 'production', label: 'Produktionswissen' },
    ];

    const toggleCollection = (id: string) => {
        if (selectedCollections.includes(id)) {
            setSelectedCollections(prev => prev.filter(c => c !== id));
        } else {
            setSelectedCollections(prev => [...prev, id]);
        }
    };

    const addToQueue = (files?: FileList | null) => {
        const newItems: IngestItem[] = [];
        const collections = [...selectedCollections];

        if (activeTab === 'text' && textInput.trim()) {
            newItems.push({
                id: crypto.randomUUID(),
                type: 'text',
                content: textInput,
                status: 'pending',
                collections
            });
            setTextInput('');
        } else if (activeTab === 'url' && urlInput.trim()) {
            const urls = urlInput.split('\n').filter(u => u.trim());
            urls.forEach(url => {
                newItems.push({
                    id: crypto.randomUUID(),
                    type: 'url',
                    content: url.trim(),
                    status: 'pending',
                    collections
                });
            });
            setUrlInput('');
        } else if (activeTab === 'file' && files) {
            Array.from(files).forEach(file => {
                newItems.push({
                    id: crypto.randomUUID(),
                    type: 'file',
                    content: file,
                    status: 'pending',
                    collections
                });
            });
        } else if (activeTab === 'database') {
            newItems.push({
                id: crypto.randomUUID(),
                type: 'database',
                content: 'Cannabis Compounds Database (XML)',
                status: 'pending',
                collections // Although backend hardcodes collections for this specific task, we pass them for UI consistency
            });
        } else if (activeTab === 'academic' && academicQuery.trim()) {
            newItems.push({
                id: crypto.randomUUID(),
                type: 'academic',
                content: academicQuery,
                status: 'pending',
                collections,
                metadata: { category: academicCategory, limit: 3 }
            });
            setAcademicQuery('');
        }

        setQueue(prev => [...prev, ...newItems]);
    };

    const processQueue = async () => {
        if (processing) return;
        setProcessing(true);

        const itemsToProcess = queue.filter(item => item.status === 'pending');

        for (const item of itemsToProcess) {
            // Update status to processing
            updateItemStatus(item.id, 'processing', 'Starting...');

            try {
                await processItem(item);
                updateItemStatus(item.id, 'completed', 'Ingestion complete', 100);
            } catch (error: any) {
                updateItemStatus(item.id, 'error', error.message || 'Failed');
            }
        }

        setProcessing(false);
    };

    const updateItemStatus = (id: string, status: IngestItem['status'], message?: string, progress?: number) => {
        setQueue(prev => prev.map(item => {
            if (item.id === id) {
                return { ...item, status, message, progress: progress ?? item.progress };
            }
            return item;
        }));
    };

    const processItem = async (item: IngestItem) => {
        let endpoint = '';
        let body: any;
        let headers: any = {
            'X-API-Key': API_KEY
        };

        if (item.type === 'text') {
            endpoint = '/ingest';
            body = JSON.stringify({
                text: item.content as string,
                metadata: { source: 'manual' },
                collections: item.collections
            });
            headers['Content-Type'] = 'application/json';
        } else if (item.type === 'url') {
            endpoint = '/ingest/url';
            body = JSON.stringify({
                url: item.content as string,
                recursive: recursive,
                max_pages: maxPages,
                max_depth: maxDepth,
                collections: item.collections
            });
            headers['Content-Type'] = 'application/json';
        } else if (item.type === 'file') {
            endpoint = '/ingest/file';
            const formData = new FormData();
            formData.append('file', item.content as File);
            if (item.collections.length > 0) {
                formData.append('collections', item.collections.join(','));
            }
            body = formData;
        } else if (item.type === 'database') {
            endpoint = '/ingest/compounds';
            body = null; // No body needed, trigger only
            // headers['Content-Type'] is not needed or json
        } else if (item.type === 'academic') {
            endpoint = '/ingest/academic';
            body = JSON.stringify({
                query: item.content as string,
                limit: item.metadata?.limit || 3,
                category: item.metadata?.category || "General",
                collections: item.collections
            });
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers,
            body
        });

        if (!response.ok) throw new Error(response.statusText);
        if (!response.body) throw new Error('No response body');

        // Streaming logic
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);
                    if (event.step === 'error') throw new Error(event.message);

                    // Update item progress
                    updateItemStatus(item.id, 'processing', event.message, event.progress * 100);
                } catch (e: any) {
                    if (e.message && e.message !== "Unexpected end of JSON input") {
                        // If it's a real error from the stream
                        throw e;
                    }
                }
            }
        }
    };

    const removeFromQueue = (id: string) => {
        setQueue(prev => prev.filter(i => i.id !== id));
    };

    return (
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex flex-col h-[800px]">
            <h2 className="text-2xl font-bold mb-6 text-gray-800 flex items-center gap-3 flex-shrink-0">
                <div className="p-2 bg-blue-100 rounded-lg border border-blue-200">
                    <Upload className="w-5 h-5 text-blue-600" />
                </div>
                Inhalte aufnehmen
            </h2>

            {/* Input Area (Scrollable if needed, but fixed height helps) */}
            <div className="flex-none space-y-6 mb-8">
                {/* Tabs */}
                <div className="flex gap-2 p-1 bg-gray-100 rounded-2xl w-fit">
                    {['text', 'file', 'url', 'database', 'academic'].map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab as any)}
                            className={clsx(
                                'px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2',
                                activeTab === tab
                                    ? 'bg-white text-gray-900 shadow-sm'
                                    : 'text-gray-500 hover:text-gray-700'
                            )}
                        >
                            {tab === 'text' && <FileText className="w-4 h-4" />}
                            {tab === 'file' && <Upload className="w-4 h-4" />}
                            {tab === 'url' && <Link className="w-4 h-4" />}
                            {tab === 'database' && <Database className="w-4 h-4" />}
                            {tab === 'academic' && <GraduationCap className="w-4 h-4" />}
                            <span className="capitalize">{tab}</span>
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="space-y-4">
                    {activeTab === 'text' && (
                        <textarea
                            value={textInput}
                            onChange={(e) => setTextInput(e.target.value)}
                            placeholder="Textinhalt hier einfügen..."
                            className="w-full h-32 p-4 rounded-xl bg-gray-50 border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
                        />
                    )}

                    {activeTab === 'file' && (
                        <div className="border-2 border-dashed border-gray-200 hover:border-blue-400 rounded-2xl p-8 text-center transition-all bg-gray-50/50 hover:bg-blue-50/10 cursor-pointer">
                            <input
                                type="file"
                                onChange={(e) => addToQueue(e.target.files)}
                                className="hidden"
                                id="file-upload"
                                multiple
                                accept=".pdf,.docx,.txt,.md,.html"
                            />
                            <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-2">
                                <Upload className="w-8 h-8 text-gray-400" />
                                <span className="text-sm font-medium text-gray-700">Dateien auswählen (Mehrfachauswahl möglich)</span>
                                <span className="text-xs text-gray-400">PDF, DOCX, TXT, MD</span>
                            </label>
                        </div>
                    )}

                    {activeTab === 'url' && (
                        <div className="space-y-3">
                            <textarea
                                value={urlInput}
                                onChange={(e) => setUrlInput(e.target.value)}
                                placeholder="URLs hier eingeben (eine pro Zeile)...&#10;https://example.com&#10;https://another.com"
                                className="w-full h-32 p-4 rounded-xl bg-gray-50 border border-gray-200 text-sm focus:ring-2 focus:ring-blue-500/20 outline-none font-mono"
                            />
                            <div className="flex flex-wrap items-center gap-6 mt-2">
                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={recursive}
                                        onChange={(e) => setRecursive(e.target.checked)}
                                        id="recursive"
                                        className="rounded border-gray-300 w-4 h-4 text-blue-600 focus:ring-blue-500"
                                    />
                                    <label htmlFor="recursive" className="text-sm text-gray-700 font-medium">Rekursiv Crawlen</label>
                                </div>

                                {recursive && (
                                    <>
                                        <div className="flex items-center gap-2">
                                            <label htmlFor="maxPages" className="text-xs text-gray-500">Max Seiten:</label>
                                            <input
                                                type="number"
                                                id="maxPages"
                                                value={maxPages}
                                                onChange={(e) => setMaxPages(parseInt(e.target.value) || 1)}
                                                min={1}
                                                max={100}
                                                className="w-16 p-1 text-sm border border-gray-200 rounded text-center"
                                            />
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <label htmlFor="maxDepth" className="text-xs text-gray-500">Tiefe:</label>
                                            <input
                                                type="number"
                                                id="maxDepth"
                                                value={maxDepth}
                                                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 1)}
                                                min={1}
                                                max={5}
                                                className="w-16 p-1 text-sm border border-gray-200 rounded text-center"
                                            />
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    )}

                    {activeTab === 'database' && (
                        <div className="p-6 bg-blue-50 rounded-xl border border-blue-100">
                            <div className="flex items-start gap-4">
                                <Database className="w-8 h-8 text-blue-600 mt-1" />
                                <div>
                                    <h4 className="font-semibold text-blue-900 mb-1">Cannabis Compounds Datenbank</h4>
                                    <p className="text-sm text-blue-800 mb-3">
                                        Importieren Sie die lokale XML-Datenbank mit ~500+ chemischen Verbindungen.
                                        Dies füllt automatisch die Graphen 'Pharmakologisch' und 'Master' sowie den Vektorindex.
                                    </p>
                                    <p className="text-xs text-blue-600 font-mono bg-blue-100 inline-block px-2 py-1 rounded">
                                        Quelle: data/sources/compounds.xml
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'academic' && (
                        <div className="space-y-4">
                            <div className="p-4 bg-purple-50 rounded-xl border border-purple-100 mb-2">
                                <div className="flex items-start gap-3">
                                    <GraduationCap className="w-6 h-6 text-purple-600 mt-1" />
                                    <div>
                                        <h4 className="font-semibold text-purple-900 text-sm">Wissenschaftliche Suche</h4>
                                        <p className="text-xs text-purple-700">
                                            Durchsucht Semantic Scholar und Crossref nach wissenschaftlichen Papern.
                                            Gefundene OpenAccess Inhalte werden automatisch importiert.
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <textarea
                                value={academicQuery}
                                onChange={(e) => setAcademicQuery(e.target.value)}
                                placeholder="Suchbegriff (z.B. 'Cannabis sativa trichome morphology')..."
                                className="w-full h-24 p-4 rounded-xl bg-gray-50 border border-gray-200 text-sm focus:ring-2 focus:ring-purple-500/20 outline-none"
                            />

                            <div className="flex gap-4">
                                <div className="flex-1">
                                    <label className="text-xs font-medium text-gray-500 mb-1 block">Kategorie / Fokus</label>
                                    <select
                                        value={academicCategory}
                                        onChange={(e) => setAcademicCategory(e.target.value)}
                                        className="w-full p-2 rounded-lg border border-gray-200 text-sm bg-white"
                                    >
                                        <option value="General">Allgemein</option>
                                        <option value="Botanik">Botanik (Frontiers...)</option>
                                        <option value="Medizin">Medizin/Pharmakologie</option>
                                        <option value="Production">Produktion</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Collection & Add Button */}
                    <div className="flex flex-col gap-4">
                        <div className="grid grid-cols-2 gap-2">
                            {COLLECTIONS.map((col) => (
                                <div
                                    key={col.id}
                                    onClick={() => toggleCollection(col.id)}
                                    className={clsx(
                                        "flex items-center gap-2 p-2 rounded-lg border cursor-pointer text-xs h-10 select-none",
                                        selectedCollections.includes(col.id)
                                            ? "bg-blue-50 border-blue-200 text-blue-800"
                                            : "bg-white border-gray-100 text-gray-600"
                                    )}
                                >
                                    <div className={clsx("w-4 h-4 rounded border flex items-center justify-center", selectedCollections.includes(col.id) ? "bg-blue-600 border-blue-600" : "bg-white")}>
                                        {selectedCollections.includes(col.id) && <CheckCircle className="w-3 h-3 text-white" />}
                                    </div>
                                    {col.label}
                                </div>
                            ))}
                        </div>

                        {(activeTab !== 'file') && (
                            <button
                                onClick={() => addToQueue()}
                                disabled={!((activeTab === 'text' && textInput) || (activeTab === 'url' && urlInput) || activeTab === 'database' || (activeTab === 'academic' && academicQuery))}
                                className="w-full py-2 bg-gray-900 text-white rounded-xl text-sm font-medium hover:bg-black transition-all disabled:opacity-50"
                            >
                                {activeTab === 'database' ? 'Datenbank-Import starten' : 'Zur Pipeline hinzufügen'}
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Pipeline / Queue Area (Flexible space) */}
            <div className="flex-1 overflow-hidden flex flex-col border-t border-gray-100 pt-6">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        Verarbeitungs-Pipeline ({queue.length})
                    </h3>
                    {queue.length > 0 && (
                        <button
                            onClick={processQueue}
                            disabled={processing || queue.every(i => i.status === 'completed')}
                            className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-xs font-bold hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 transition-all shadow-sm"
                        >
                            {processing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                            {processing ? 'Verarbeite...' : 'Starten'}
                        </button>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto space-y-2 pr-2">
                    {queue.length === 0 ? (
                        <div className="text-center text-gray-400 py-8 text-sm">
                            Die Pipeline ist leer. Fügen Sie Inhalte hinzu.
                        </div>
                    ) : (
                        queue.map((item) => (
                            <div key={item.id} className="p-3 bg-gray-50 border border-gray-100 rounded-xl relative group">
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        {item.status === 'pending' && <Clock className="w-4 h-4 text-gray-400 flex-shrink-0" />}
                                        {item.status === 'processing' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />}
                                        {item.status === 'completed' && <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" />}
                                        {item.status === 'error' && <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />}

                                        <span className="text-sm font-medium text-gray-700 truncate">
                                            {item.type === 'file' ? (item.content as File).name : item.content as string}
                                        </span>
                                    </div>
                                    <button onClick={() => removeFromQueue(item.id)} className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>

                                {item.status !== 'pending' && (
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-xs text-gray-500">
                                            <span>{item.message || 'Warte...'}</span>
                                            <span>{Math.round(item.progress || 0)}%</span>
                                        </div>
                                        <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
                                            <div
                                                className={clsx(
                                                    "h-full transition-all duration-300",
                                                    item.status === 'error' ? "bg-red-500" : "bg-blue-500"
                                                )}
                                                style={{ width: `${item.progress || 0}%` }}
                                            />
                                        </div>
                                    </div>
                                )}
                                <div className="mt-2 flex gap-1 flex-wrap">
                                    {item.collections.map(c => (
                                        <span key={c} className="text-[10px] px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-500">
                                            {COLLECTIONS.find(col => col.id === c)?.label}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
