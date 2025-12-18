import { useState, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Search, GitGraph, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

interface GraphData {
    nodes: any[];
    links: any[];
}

export default function GenealogyExplorer() {
    const [searchTerm, setSearchTerm] = useState('');
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<any | null>(null);

    // Initial load or effect
    useEffect(() => {
        // Optional: Load a default view or random strain?
    }, []);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchTerm.trim()) return;

        setLoading(true);
        setError(null);
        setData({ nodes: [], links: [] }); // Clear prev
        setSelectedNode(null);

        try {
            // Default to Prod URL if env is missing to ensure it works on Vercel without config
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://95.216.204.29.sslip.io/api/v1';
            const apiKey = process.env.NEXT_PUBLIC_BACKEND_API_KEY || 'secret-api-key';
            console.log("GenealogyExplorer: Fetching from", apiUrl);

            const res = await fetch(`${apiUrl}/graph/lineage?strain=${encodeURIComponent(searchTerm)}`, {
                headers: {
                    'x-api-key': apiKey,
                    'Content-Type': 'application/json'
                }
            });

            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`Failed to fetch lineage (${res.status}): ${errorText}`);
            }

            const graphData = await res.json();

            // Try/Catch block duplication removal - simply use one logic flow
            if (graphData.nodes.length === 0) {
                setError(`No lineage found for "${searchTerm}". Try another strain.`);
            } else {
                setData(graphData);
            }
        } catch (err: any) {
            console.error("Genealogy Fetch Error:", err);
            setError(err.message || "An error occurred");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-row h-full bg-slate-50 relative overflow-hidden">
            {/* Sidebar / Details Panel */}
            <div className={`
                absolute md:static inset-y-0 left-0 z-30 
                w-full md:w-96 bg-white border-r border-gray-200 shadow-xl md:shadow-none 
                transform transition-transform duration-300 ease-in-out flex flex-col
                ${selectedNode ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-80'}
            `}>
                {/* Search Header (Always Visible on Desktop) */}
                <div className="p-4 border-b border-gray-100 bg-white">
                    <div className="flex items-center gap-2 mb-4">
                        <GitGraph className="text-emerald-600 w-5 h-5" />
                        <h2 className="font-bold text-gray-800 tracking-tight">Genealogy Explorer</h2>
                    </div>

                    <form onSubmit={handleSearch} className="relative">
                        <input
                            type="text"
                            placeholder="Search Strain..."
                            className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-emerald-500 text-sm"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        <Search className="absolute left-3 top-2.5 text-gray-400 w-4 h-4" />
                    </form>

                    {error && (
                        <div className="mt-2 p-2 bg-red-50 text-red-600 text-xs rounded border border-red-100">
                            {error}
                        </div>
                    )}
                </div>

                {/* Details Content */}
                <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
                    {selectedNode ? (
                        <div className="space-y-6 animate-in fade-in slide-in-from-left-4 duration-300">
                            {/* Header */}
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${selectedNode.group === 'Target'
                                        ? 'bg-emerald-100 text-emerald-700'
                                        : 'bg-blue-100 text-blue-700'
                                        }`}>
                                        {selectedNode.group === 'Target' ? 'Selected Strain' : 'Ancestor'}
                                    </span>
                                </div>
                                <h1 className="text-2xl font-extrabold text-gray-900 leading-tight">
                                    {selectedNode.label}
                                </h1>
                                {(selectedNode.type) && (
                                    <p className="text-sm font-medium text-gray-500 mt-1">{selectedNode.type}</p>
                                )}
                            </div>

                            {/* Key Stats Grid */}
                            <div className="grid grid-cols-2 gap-3">
                                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-1">Breeder</div>
                                    <div className="font-semibold text-gray-800 text-sm truncate">
                                        {selectedNode.breeder || "Unknown"}
                                    </div>
                                </div>
                                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-1">THC Content</div>
                                    <div className="font-semibold text-emerald-600 text-sm">
                                        {selectedNode.thc || "N/A"}
                                    </div>
                                </div>
                                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-1">CBD Content</div>
                                    <div className="font-semibold text-blue-600 text-sm">
                                        {selectedNode.cbd || "N/A"}
                                    </div>
                                </div>
                                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                    <div className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-1">Flavor</div>
                                    <div className="font-semibold text-gray-800 text-sm truncate" title={selectedNode.flavor}>
                                        {selectedNode.flavor ? selectedNode.flavor.split('/')[0] : "N/A"}
                                    </div>
                                </div>
                            </div>

                            {/* Description */}
                            {selectedNode.description && (
                                <div>
                                    <h3 className="text-sm font-bold text-gray-900 mb-2">Description</h3>
                                    <p className="text-sm text-gray-600 leading-relaxed">
                                        {selectedNode.description.replace(/<[^>]*>?/gm, '')}
                                    </p>
                                </div>
                            )}

                            {/* Effects */}
                            {selectedNode.effects && (
                                <div>
                                    <h3 className="text-sm font-bold text-gray-900 mb-2">Effects</h3>
                                    <div className="flex flex-wrap gap-1.5">
                                        {selectedNode.effects.split(',').map((e: string, i: number) => (
                                            <span key={i} className="px-2 py-1 bg-purple-50 text-purple-700 text-xs rounded-md border border-purple-100">
                                                {e.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400">
                            <GitGraph className="w-12 h-12 mb-4 opacity-20" />
                            <p className="text-sm">Search for a strain or click a node in the tree to view full genetic details.</p>
                        </div>
                    )}
                </div>

                {/* Close Mobile Sidebar */}
                {selectedNode && (
                    <button
                        onClick={() => setSelectedNode(null)}
                        className="md:hidden absolute top-4 right-4 p-2 bg-white rounded-full shadow-md text-gray-500"
                    >
                        ✕
                    </button>
                )}
            </div>

            {/* Main Graph Canvas */}
            <div className={`flex-1 relative h-full transition-all duration-300`}>
                {loading && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/50 backdrop-blur-sm">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
                    </div>
                )}

                {data.nodes.length > 0 ? (
                    <ScientificLineageTree
                        data={data}
                        onNodeClick={setSelectedNode}
                    />
                ) : (
                    <div className="h-full flex items-center justify-center text-gray-400 text-sm">
                        Waiting for search...
                    </div>
                )}
            </div>
        </div>
    );
}

// Import helper
import ScientificLineageTree from './ScientificLineageTree';
