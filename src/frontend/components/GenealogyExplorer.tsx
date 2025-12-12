'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Search, GitGraph, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

// Dynamically import ForceGraph to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-full bg-slate-50 text-slate-400">Loading Graph Engine...</div>
});

interface GraphData {
    nodes: any[];
    links: any[];
}

export default function GenealogyExplorer() {
    const [searchTerm, setSearchTerm] = useState('');
    const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const graphRef = useRef<any>(null);

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

    const handleNodeClick = (node: any) => {
        // Center view on node
        if (graphRef.current) {
            graphRef.current.centerAt(node.x, node.y, 1000);
            graphRef.current.zoom(4, 2000);
        }
        // If it's an ancestor, maybe we want to fetch *its* lineage?
        // simple update: setSearchTerm(node.label); handleSearch(...)
    };

    return (
        <div className="flex flex-col h-full bg-white relative">
            {/* Toolbar / Search */}
            <div className="absolute top-16 md:top-4 left-4 right-4 md:right-auto z-10 bg-white/90 backdrop-blur shadow-lg rounded-xl p-4 md:w-96 flex flex-col gap-4 border border-gray-100">
                <div className="flex items-center gap-2 pb-2 border-b border-gray-100">
                    <GitGraph className="text-emerald-600 w-5 h-5" />
                    <h2 className="font-semibold text-gray-800">Genealogy Explorer</h2>
                </div>

                <form onSubmit={handleSearch} className="relative">
                    <input
                        type="text"
                        placeholder="Search Strain (e.g., White Widow)..."
                        className="w-full pl-10 pr-4 py-3 md:py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all text-base"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    <Search className="absolute left-3 top-3.5 md:top-2.5 text-gray-400 w-4 h-4" />
                </form>

                {error && (
                    <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                        {error}
                    </div>
                )}

                {data.nodes.length > 0 && (
                    <div className="text-xs text-gray-500 flex flex-col gap-1">
                        <div className="flex items-center gap-2">
                            <span className="w-3 h-3 rounded-full bg-emerald-500"></span> Target
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="w-3 h-3 rounded-full bg-blue-400"></span> Ancestor (Parent)
                        </div>
                        <div className="mt-2 text-gray-400">
                            Found {data.nodes.length} relatives.
                        </div>
                    </div>
                )}
            </div>

            {/* Configs (Zoom etc) - Floating Bottom Right */}
            <div className="absolute bottom-6 right-6 z-10 flex flex-col gap-2">
                <button onClick={() => graphRef.current?.zoomIn()} className="p-3 md:p-3 p-4 bg-white shadow-md rounded-full hover:bg-gray-50 text-gray-600 active:scale-95 transition-transform"><ZoomIn className="w-6 h-6 md:w-5 md:h-5" /></button>
                <button onClick={() => graphRef.current?.zoomOut()} className="p-3 md:p-3 p-4 bg-white shadow-md rounded-full hover:bg-gray-50 text-gray-600 active:scale-95 transition-transform"><ZoomOut className="w-6 h-6 md:w-5 md:h-5" /></button>
                <button onClick={() => graphRef.current?.zoomToFit(400)} className="p-3 md:p-3 p-4 bg-white shadow-md rounded-full hover:bg-gray-50 text-gray-600 active:scale-95 transition-transform"><Maximize className="w-6 h-6 md:w-5 md:h-5" /></button>
            </div>

            {/* Main Graph Canvas */}
            <div className="flex-1 overflow-hidden bg-slate-50 cursor-move touch-none">
                {loading && (
                    <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/50 backdrop-blur-sm">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
                    </div>
                )}

                <ForceGraph2D
                    ref={graphRef}
                    graphData={data}
                    nodeLabel="label"
                    nodeColor={(node: any) => node.group === 'Target' ? '#10b981' : node.group === 'Ancestor' ? '#3b82f6' : '#9ca3af'}
                    nodeRelSize={6}
                    linkColor={() => '#e2e8f0'}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    onNodeClick={handleNodeClick}
                    cooldownTicks={100}
                    onEngineStop={() => graphRef.current?.zoomToFit(400)}
                />
            </div>
        </div>
    );
}
