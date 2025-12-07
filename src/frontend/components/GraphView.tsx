'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../utils/api';
import dynamic from 'next/dynamic';
import { Network, Loader2, Maximize2, Minimize2 } from 'lucide-react';
import { clsx } from 'clsx';

// Dynamic import for client-side only rendering (canvas dependency)
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

interface GraphData {
    nodes: { id: string; label: string; group: string; val: number }[];
    links: { source: string; target: string; label: string }[];
}

export default function GraphView({ query, data: initialData, className }: { query?: string; data?: GraphData; className?: string }) {
    const [data, setData] = useState<GraphData | null>(initialData || null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Size management
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

    const fetchGraph = useCallback(async () => {
        if (!query) return;
        setLoading(true);
        setError(null);
        try {
            const res = await api.get(`/graph/visualize?query=${encodeURIComponent(query)}`);
            if (res.data && res.data.nodes && res.data.nodes.length > 0) {
                setData(res.data);
            } else {
                setError("No graph connection found for this topic.");
            }
        } catch (e: any) {
            setError(e.response?.data?.detail || "Failed to load graph.");
        } finally {
            setLoading(false);
        }
    }, [query]);

    useEffect(() => {
        if (initialData) {
            setData(initialData);
        } else if (query) {
            fetchGraph();
        }
    }, [fetchGraph, initialData, query]);

    useEffect(() => {
        fetchGraph();
    }, [fetchGraph]);

    useEffect(() => {
        const updateDims = () => {
            if (containerRef.current) {
                setDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight
                });
            }
        };

        window.addEventListener('resize', updateDims);
        // Initial delay to allow layout to settle
        setTimeout(updateDims, 100);

        return () => window.removeEventListener('resize', updateDims);
    }, [isFullscreen, data]);

    const fgRef = useRef<any>(null);

    if (loading) return (
        <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-xl border border-gray-100">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-2" />
            <span className="text-sm text-gray-500">Analysiere Zusammenhänge...</span>
        </div>
    );

    if (error) return (
        <div className="flex flex-col items-center justify-center p-6 bg-gray-50 rounded-xl border border-dashed border-gray-200">
            <Network className="w-8 h-8 text-gray-300 mb-2" />
            <span className="text-sm text-gray-400">{error}</span>
        </div>
    );

    if (!data) return null;

    return (
        <div
            ref={containerRef}
            className={clsx(
                "relative bg-gray-900 border border-gray-800 transition-all duration-300 overflow-hidden shadow-2xl",
                isFullscreen ? "fixed inset-0 z-50 rounded-none w-screen h-screen" : "w-full h-[400px] rounded-2xl"
            )}
        >
            <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-gray-900/80 backdrop-blur px-3 py-1.5 rounded-full border border-gray-700">
                <Network className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-semibold text-gray-200 uppercase tracking-widest">Knowledge Graph</span>
                <span className="text-[10px] text-gray-500 px-1 border-l border-gray-700">{data.nodes.length} Nodes</span>
            </div>

            <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="absolute top-4 right-4 z-10 p-2 bg-gray-900/80 hover:bg-gray-800 text-gray-400 hover:text-white rounded-full border border-gray-700 transition-colors"
            >
                {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={data}
                nodeLabel="label"
                nodeColor={node => {
                    const group = (node as any).group;
                    return group === 'concept' ? '#a78bfa' : // purple
                        group === 'target' ? '#60a5fa' : // blue
                            '#fbbf24'; // amber
                }}
                nodeRelSize={6}
                linkColor={() => '#4b5563'} // gray-600
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
                d3VelocityDecay={0.1} // More movement
                cooldownTicks={100}
                onEngineStop={() => fgRef.current?.zoomToFit(400)}
            />

            <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-1 pointer-events-none">
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                    <span className="w-2 h-2 rounded-full bg-[#a78bfa]"></span> Konzept / Source
                </div>
                <div className="flex items-center gap-2 text-[10px] text-gray-400">
                    <span className="w-2 h-2 rounded-full bg-[#60a5fa]"></span> Target Entity
                </div>
            </div>
        </div>
    );
}
