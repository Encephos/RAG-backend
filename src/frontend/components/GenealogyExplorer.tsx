import { useState, useRef, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Search, GitGraph, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import ScientificLineageTree from './ScientificLineageTree';

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

    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    // Initial load or effect
    useEffect(() => {
        // Optional: Load a default view or random strain?
    }, []);

    // Close sidebar on node selection change if it's open solely for that?
    // Actually, on mobile, if I select a node, I want to see details, so sidebar should OPEN.
    useEffect(() => {
        if (selectedNode) {
            setIsMobileMenuOpen(true);
        }
    }, [selectedNode]);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchTerm.trim()) return;

        setLoading(true);
        setError(null);
        setData({ nodes: [], links: [] }); // Clear prev
        setSelectedNode(null);

        // Auto close menu on mobile to show results after search, 
        // BUT only if we actually find something? 
        // UX: User searches -> Loading -> Tree appears. 
        // If sidebar stays open, they can't see tree on mobile.
        // So close it.
        setIsMobileMenuOpen(false);

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
                setIsMobileMenuOpen(true); // Re-open if error so they can try again
            } else {
                setData(graphData);
            }
        } catch (err: any) {
            console.error("Genealogy Fetch Error:", err);
            setError(err.message || "An error occurred");
            setIsMobileMenuOpen(true); // Re-open if error
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-row h-full bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-100 via-slate-100 to-emerald-100 relative overflow-hidden">

            {/* Mobile Toggle Button (Visible only when sidebar is closed on mobile) */}
            {!isMobileMenuOpen && (
                <button
                    onClick={() => setIsMobileMenuOpen(true)}
                    className="md:hidden absolute bottom-6 right-6 z-50 p-4 bg-emerald-600 text-white rounded-full shadow-2xl hover:bg-emerald-700 hover:scale-105 transition-all duration-300 animate-bounce-subtle"
                    aria-label="Open Search"
                >
                    <Search className="w-6 h-6" />
                </button>
            )}

            {/* Sidebar / Details Panel */}
            <div className={`
                absolute md:static inset-y-0 left-0 z-30 
                w-full md:w-96 bg-white/70 backdrop-blur-xl border-r border-white/50 shadow-2xl md:shadow-glass
                transform transition-all duration-500 cubic-bezier(0.4, 0, 0.2, 1) flex flex-col
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-80'}
            `}>
                {/* Search Header (Always Visible on Desktop) */}
                <div className="p-4 border-b border-white/40 bg-transparent relative">
                    {/* Header Top Row */}
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <GitGraph className="text-emerald-600 w-5 h-5" />
                            <h2 className="font-bold text-gray-800 tracking-tight">Genealogy Explorer</h2>
                        </div>

                        {/* Mobile Close Button */}
                        <button
                            onClick={() => setIsMobileMenuOpen(false)}
                            className="md:hidden p-1 text-gray-400 hover:text-gray-600"
                        >
                            ✕
                        </button>
                    </div>

                    <form onSubmit={handleSearch} className="relative">
                        <input
                            type="text"
                            placeholder="Search Strain..."
                            className="w-full pl-9 pr-4 py-2 bg-white/50 backdrop-blur-md border border-white/60 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:bg-white/80 transition-all duration-300 text-sm shadow-inner"
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
                                        {selectedNode.group === 'Target' ? 'Selected Strain' : 'Lineage Ancestor'}
                                    </span>
                                </div>
                                <h1 className="text-3xl font-extrabold text-gray-900 leading-tight">
                                    {selectedNode.label}
                                </h1>
                                {(selectedNode.type) && (
                                    <p className="text-sm font-medium text-gray-500 mt-1">{selectedNode.type}</p>
                                )}
                            </div>

                            {/* Key Stats Grid */}
                            <div className="grid grid-cols-2 gap-3">
                                <DetailCard title="Breeder" value={selectedNode.breeder} />
                                <DetailCard title="Flavor" value={selectedNode.flavor || (selectedNode.flavors ? selectedNode.flavors[0] : null)} />
                                <DetailCard title="THC" value={selectedNode.thc} color="emerald" />
                                <DetailCard title="CBD" value={selectedNode.cbd} color="blue" />
                            </div>

                            {/* Description (Expandable) */}
                            {selectedNode.description && (
                                <ExpandableSection title="Description">
                                    <p className="text-sm text-gray-600 leading-relaxed">
                                        {selectedNode.description.replace(/<[^>]*>?/gm, '')}
                                    </p>
                                </ExpandableSection>
                            )}

                            {/* Effects */}
                            <TagSection title="Effects" items={selectedNode.effects} color="purple" />

                            {/* Medical */}
                            <TagSection title="Medical Uses" items={selectedNode.medical} color="red" />

                            {/* Terpenes */}
                            <TagSection title="Terpenes" items={selectedNode.terpenes} color="amber" />

                            {/* Flavors (Full List) */}
                            {selectedNode.flavors && selectedNode.flavors.length > 1 && (
                                <TagSection title="Flavors" items={selectedNode.flavors} color="orange" />
                            )}

                            {/* Aromas */}
                            <TagSection title="Aromas" items={selectedNode.aromas} color="teal" />

                            {/* Cannabinoids List */}
                            <TagSection title="Cannabinoids" items={selectedNode.cannabinoids} color="cyan" />

                        </div>
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400">
                            <GitGraph className="w-12 h-12 mb-4 opacity-20" />
                            <p className="text-sm">Search for a strain or click a node in the tree to view full genetic details.</p>
                        </div>
                    )}
                </div>
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
                        {(!loading && !error) && (
                            <div className="text-center p-6">
                                <Search className="w-12 h-12 mx-auto mb-2 opacity-20" />
                                <p>Use the search panel to explore genetics.</p>
                                <button
                                    onClick={() => setIsMobileMenuOpen(true)}
                                    className="md:hidden mt-4 px-4 py-2 bg-emerald-600 text-white text-sm rounded-full shadow-md"
                                >
                                    Open Search
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// --- Helper Components ---

function DetailCard({ title, value, color = "gray" }: { title: string, value: any, color?: string }) {
    if (!value || value === "Unknown") return null;

    const colors: any = {
        emerald: "text-emerald-600",
        blue: "text-blue-600",
        gray: "text-gray-800"
    };

    return (
        <div className="p-3 bg-white/40 backdrop-blur-sm rounded-xl border border-white/60 shadow-sm hover:bg-white/60 hover:shadow-md transition-all duration-300 group">
            <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-1">{title}</div>
            <div className={`font-semibold text-sm truncate ${colors[color] || colors.gray}`}>
                {value}
            </div>
        </div>
    );
}

function TagSection({ title, items, color }: { title: string, items: string[] | string, color: string }) {
    if (!items || (Array.isArray(items) && items.length === 0)) return null;

    // Normalize to array
    const list = Array.isArray(items) ? items : items.split(',').map(s => s.trim());

    const colorStyles: any = {
        purple: "bg-purple-50 text-purple-700 border-purple-100",
        red: "bg-red-50 text-red-700 border-red-100",
        amber: "bg-amber-50 text-amber-700 border-amber-100",
        orange: "bg-orange-50 text-orange-700 border-orange-100",
        teal: "bg-teal-50 text-teal-700 border-teal-100",
        cyan: "bg-cyan-50 text-cyan-700 border-cyan-100",
    };

    return (
        <div>
            <h3 className="text-xs font-bold text-gray-900 uppercase tracking-widest mb-2 opacity-80">{title}</h3>
            <div className="flex flex-wrap gap-1.5">
                {list.map((item, i) => (
                    <span key={i} className={`px-2 py-1 text-xs rounded-md border font-medium ${colorStyles[color]}`}>
                        {item}
                    </span>
                ))}
            </div>
        </div>
    );
}

function ExpandableSection({ title, children }: { title: string, children: React.ReactNode }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="bg-white/30 rounded-xl p-3 border border-white/50">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex justify-between items-center text-xs font-bold text-gray-900 uppercase tracking-widest opacity-80 mb-1 hover:opacity-100 transition-opacity"
            >
                {title}
                <span className="text-gray-400 text-lg">{expanded ? '−' : '+'}</span>
            </button>
            <div className={`overflow-hidden transition-all duration-500 ease-in-out ${expanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'}`}>
                {children}
            </div>
            {!expanded && (
                <div onClick={() => setExpanded(true)} className="text-xs text-gray-400 cursor-pointer hover:text-emerald-600 mt-1">
                    Click to view details...
                </div>
            )}
        </div>
    );
}


// Import helper
// Removed from bottom
