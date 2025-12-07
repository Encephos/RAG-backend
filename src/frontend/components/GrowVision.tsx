import { useState, useRef } from 'react';
import { Upload, ScanEye, Leaf, Loader2, AlertCircle, ExternalLink } from 'lucide-react';
import GraphView from './GraphView';
import { clsx } from 'clsx';
import Markdown from 'react-markdown';

export default function GrowVision() {
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0];
            setFile(selectedFile);
            setPreview(URL.createObjectURL(selectedFile));
            setResult(null);
            setError(null);
        }
    };

    const handleDiagnose = async () => {
        if (!file) return;

        setIsLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/api/v1/tools/diagnose-leaf', {
                method: 'POST',
                headers: {
                    'X-API-Key': 'secret-api-key' // Hardcoded for dev/demo
                },
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(`Server Error: ${response.status} - ${errorData}`);
            }

            const data = await response.json();
            setResult(data);
        } catch (err: any) {
            setError(err.message || "An error occurred during diagnosis.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full overflow-y-auto">
            <div className="p-8 max-w-4xl mx-auto w-full pt-12 animate-in fade-in slide-in-from-bottom-4 duration-500">

                {/* Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center p-3 bg-green-100 rounded-2xl mb-4 text-green-600">
                        <ScanEye className="w-8 h-8" />
                    </div>
                    <h1 className="text-3xl font-medium tracking-tight text-gray-900">
                        Grow Vision <span className="text-green-600">Blatt-Diagnose</span>
                    </h1>
                    <p className="text-gray-500 mt-2 max-w-lg mx-auto">
                        Lade ein Foto deiner Pflanze hoch. Unsere KI und der Botaniker-Agent analysieren Mangelerscheinungen und Schädlinge.
                    </p>
                </div>

                {/* Main Content - Centered Stack */}
                <div className="max-w-3xl mx-auto space-y-12">

                    {/* Upload Section */}
                    <div className="space-y-6">
                        <div
                            className={clsx(
                                "border-2 border-dashed rounded-3xl p-8 text-center transition-all cursor-pointer relative overflow-hidden group hover:border-green-400 hover:bg-green-50/30",
                                preview ? "border-green-200 bg-green-50/10" : "border-gray-200"
                            )}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <input
                                type="file"
                                className="hidden"
                                ref={fileInputRef}
                                onChange={handleFileSelect}
                                accept="image/*"
                            />

                            {preview ? (
                                <div className="relative aspect-video max-h-[400px] mx-auto rounded-xl overflow-hidden shadow-sm">
                                    <img src={preview} alt="Upload Preview" className="w-full h-full object-contain bg-black/5" />
                                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                                        <div className="opacity-0 group-hover:opacity-100 bg-white/90 px-4 py-2 rounded-full shadow-lg text-sm font-medium">
                                            Anderes Bild wählen
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="py-12 flex flex-col items-center gap-4 text-gray-400">
                                    <div className="p-4 bg-gray-50 rounded-full group-hover:bg-white group-hover:scale-110 transition-all shadow-sm">
                                        <Upload className="w-8 h-8 text-gray-400 group-hover:text-green-500" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-gray-600">Bild hier ablegen oder klicken</p>
                                        <p className="text-xs">JPG, PNG bis 10MB</p>
                                    </div>
                                </div>
                            )}
                        </div>

                        <button
                            onClick={handleDiagnose}
                            disabled={!file || isLoading}
                            className={clsx(
                                "w-full py-4 px-6 rounded-xl font-medium text-lg shadow-lg shadow-green-900/5 transition-all flex items-center justify-center gap-2",
                                (!file || isLoading)
                                    ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                    : "bg-gradient-to-r from-green-600 to-emerald-600 text-white hover:shadow-green-900/20 hover:scale-[1.02] active:scale-[0.98]"
                            )}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Analysiere Blattstruktur...
                                </>
                            ) : (
                                <>
                                    <Leaf className="w-5 h-5" />
                                    Diagnose starten
                                </>
                            )}
                        </button>

                        {error && (
                            <div className="bg-red-50 text-red-700 p-4 rounded-xl flex items-start gap-3 text-sm">
                                <AlertCircle className="w-5 h-5 shrink-0" />
                                <div>{error}</div>
                            </div>
                        )}
                    </div>

                    {/* Results Section */}
                    <div className="space-y-8">
                        {!result && !isLoading && (
                            <div className="border border-gray-100 rounded-3xl bg-gray-50/50 flex flex-col items-center justify-center text-center p-12 text-gray-400 border-dashed">
                                <ScanEye className="w-12 h-12 mb-4 opacity-20" />
                                <p>Die Diagnose erscheint hier nach der Analyse.</p>
                            </div>
                        )}

                        {result && (
                            <div className="space-y-8 animate-in slide-in-from-bottom-8 fade-in duration-700">

                                {/* Botanical Diagnosis Card (Priority) */}
                                <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-100 rounded-3xl p-8 shadow-sm relative overflow-hidden">
                                    <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
                                        <Leaf className="w-64 h-64 text-green-900" />
                                    </div>
                                    <div className="relative z-10">
                                        <div className="flex items-center gap-2 mb-6 text-sm font-bold text-green-700 uppercase tracking-widest border-b border-green-200 pb-4">
                                            <Leaf className="w-4 h-4" />
                                            Diagnose & Behandlung (Botaniker-Agent)
                                        </div>
                                        <div className="prose prose-lg prose-green prose-p:text-gray-700 prose-headings:text-green-800 max-w-none font-leading-relaxed">
                                            <Markdown>{result.diagnosis}</Markdown>
                                        </div>
                                    </div>
                                </div>

                                {/* Visual Analysis Card (Secondary) */}
                                <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm">
                                    <div className="flex items-center gap-2 mb-4 text-xs font-bold text-gray-400 uppercase tracking-widest">
                                        <ScanEye className="w-4 h-4" />
                                        Visuelle Beobachtung (Gemini Flash)
                                    </div>
                                    <div className="prose prose-green bg-gray-50 p-6 rounded-2xl text-gray-600 text-sm leading-relaxed border border-gray-100">
                                        <Markdown>{result.visual_analysis}</Markdown>
                                    </div>
                                </div>

                                {/* Sources List */}
                                <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm">
                                    <div className="flex items-center gap-2 mb-4 text-xs font-bold text-gray-400 uppercase tracking-widest">
                                        <ExternalLink className="w-4 h-4" />
                                        Verwendete Quellen ({result.rag_context?.length || 0})
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        {result.rag_context?.map((doc: any, i: number) => (
                                            <a
                                                key={i}
                                                href={doc.metadata?.source_url || '#'}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex items-center gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100 hover:border-green-300 hover:shadow-md transition-all text-sm group"
                                            >
                                                <div className="w-8 h-8 rounded-full bg-white border border-gray-200 text-green-600 flex items-center justify-center text-xs font-bold shrink-0 shadow-sm group-hover:scale-110 transition-transform">
                                                    {i + 1}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium text-gray-800 truncate group-hover:text-green-700">
                                                        {doc.metadata?.name || doc.metadata?.title || "Unbekannte Quelle"}
                                                    </div>
                                                    <div className="text-xs text-gray-500 truncate mt-0.5">
                                                        {doc.metadata?.source || "Keine URL verfügbar"}
                                                    </div>
                                                </div>
                                                <ExternalLink className="w-3 h-3 text-gray-300 group-hover:text-green-400" />
                                            </a>
                                        ))}
                                    </div>
                                </div>

                                {/* Graph Visualization */}
                                {result.graph_data && result.graph_data.nodes && result.graph_data.nodes.length > 0 && (
                                    <div className="bg-gray-900 rounded-3xl overflow-hidden shadow-lg border border-gray-800">
                                        <div className="p-4 border-b border-gray-800 bg-gray-900/50 backdrop-blur">
                                            <div className="flex items-center gap-2 text-xs font-bold text-gray-400 uppercase tracking-widest">
                                                <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                                                Wissensgraph Visualisierung
                                            </div>
                                        </div>
                                        <div className="h-[500px]">
                                            <GraphView data={result.graph_data} className="w-full h-full" />
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
