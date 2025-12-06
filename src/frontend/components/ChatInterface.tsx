'use client';

import { useState, useRef, useEffect } from 'react';
import { api, QueryResponse, SearchResult } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, ChevronDown, ChevronRight, FileText, Sparkles, Network, Check, Users, Sprout, FlaskConical, Activity, Scale } from 'lucide-react';
import { clsx } from 'clsx';

type SessionId = 'Nexus' | 'Nexus Council';

interface CouncilMember {
    id: string;
    name: string;
    role: string;
    icon: string;
    description: string;
}

const COUNCIL_MEMBERS_LIST: CouncilMember[] = [
    { id: 'botanist', name: 'Botaniker', role: 'Pflanze & Anbau', icon: '🌿', description: 'Genetik, Züchtung' },
    { id: 'chemist', name: 'Chemiker', role: 'Analyse', icon: '🧪', description: 'Inhaltsstoffe, Terpene' },
    { id: 'pharmacologist', name: 'Pharmakologe', role: 'Wirkung', icon: '💊', description: 'Endocannabinoid-System' },
    { id: 'toxicologist', name: 'Toxikologe', role: 'Risiken', icon: '⚠️', description: 'Nebenwirkungen' },
    { id: 'pain_specialist', name: 'Schmerzmediziner', role: 'Therapie', icon: '⚕️', description: 'Klinische Anwendung' },
    { id: 'psychiatrist', name: 'Psychiater', role: 'Mental Health', icon: '🧠', description: 'Psyche & Sucht' },
    { id: 'epidemiologist', name: 'Epidemiologe', role: 'Daten', icon: '📊', description: 'Konsumstudien' },
    { id: 'forensic', name: 'Forensiker', role: 'Recht & Verkehr', icon: '⚖️', description: 'Grenzwerte' },
    { id: 'product_expert', name: 'Produktexperte', role: 'Qualität', icon: '🏭', description: 'Herstellung' },
];

interface Message {
    type: 'user' | 'bot';
    content: string;
    context?: SearchResult[];
    graph?: any;
    council_results?: any[];
}

export default function ChatInterface() {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);

    // Multi-session state
    const [activeSession, setActiveSession] = useState<SessionId>('Nexus');
    const [sessions, setSessions] = useState<Record<SessionId, Message[]>>({
        'Nexus': [],
        'Nexus Council': []
    });

    // Council Selection State
    const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
    const [showCouncilSelector, setShowCouncilSelector] = useState(false);

    // Dropdown state
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const scrollRef = useRef<HTMLDivElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Current history convenience
    const history = sessions[activeSession];

    // Rotating Greetings
    const greetings = [
        "Wie kann Nexus dir heute helfen?",
        "Verbinde die Datenpunkte...",
        "Nexus ist bereit.",
        "Aktiviere Vektor-Suche...",
        "Fragen? Fragen Sie Nexus.",
        "Suche im Archiv nach Antworten..."
    ];
    const [greetingIndex, setGreetingIndex] = useState(0);

    // Close dropdown on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        if (history.length > 0) return;
        const interval = setInterval(() => {
            setGreetingIndex((prev) => (prev + 1) % greetings.length);
        }, 3500); // Slightly slower for better readability
        return () => clearInterval(interval);
    }, [history.length, activeSession]); // Added activeSession to dependencies

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, loading, activeSession]);

    const [stats, setStats] = useState<{ version: string; total_points: number } | null>(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await api.get('/stats');
                setStats(res.data);
            } catch (e) {
                console.error("Failed to fetch stats", e);
            }
        };
        fetchStats();
    }, []);

    const toggleMember = (id: string) => {
        setSelectedMembers(prev =>
            prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
        );
    };

    const handleQuery = async (text: string = query) => {
        if (!text.trim()) return;

        // Ensure council members are selected in council mode
        if (activeSession === 'Nexus Council' && selectedMembers.length === 0) {
            alert("Bitte wähle mindestens ein Council-Mitglied aus.");
            setShowCouncilSelector(true);
            return;
        }

        const userQuery = text;
        setQuery('');
        setShowCouncilSelector(false); // Close selector on send

        // Optimistic update for current session
        setSessions(prev => ({
            ...prev,
            [activeSession]: [...prev[activeSession], { type: 'user', content: userQuery }]
        }));
        setLoading(true);

        try {
            const payload: any = { query: userQuery, limit: 15 };
            if (activeSession === 'Nexus Council') {
                payload.selected_council_members = selectedMembers;
            }

            const response = await api.post<QueryResponse>('/query', payload);

            setSessions(prev => ({
                ...prev,
                [activeSession]: [...prev[activeSession], {
                    type: 'bot',
                    content: response.data.answer,
                    context: response.data.context,
                    graph: response.data.graph_context,
                    council_results: response.data.council_results
                }]
            }));
        } catch (error: any) {
            setSessions(prev => ({
                ...prev,
                [activeSession]: [...prev[activeSession], {
                    type: 'bot',
                    content: `Error: ${error.response?.data?.detail || 'Failed to get answer'}`
                }]
            }));
        } finally {
            setLoading(false);
        }
    };

    const suggestions = [
        { title: "Botanik & Anbau", subtitle: "Optimale Bedingungen für Blütephase", icon: <Sprout className="w-6 h-6 text-green-600" /> },
        { title: "Chemie & Wirkung", subtitle: "Was ist der Entourage-Effekt?", icon: <FlaskConical className="w-6 h-6 text-purple-600" /> },
        { title: "Medizinische Daten", subtitle: "Neueste Studien zu CBD & Schmerz", icon: <Activity className="w-6 h-6 text-red-600" /> },
        { title: "Recht & Regulierung", subtitle: "Aktuelle Grenzwerte im Verkehr", icon: <Scale className="w-6 h-6 text-blue-600" /> },
    ];

    return (
        <div className="flex flex-col h-full relative max-w-5xl mx-auto w-full">
            {/* Header with Dropdown and Stats */}
            <div className="absolute top-0 left-0 right-0 p-6 z-20 flex justify-between items-start" ref={dropdownRef}>
                <button
                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                    className="flex items-center gap-2 text-gray-700 font-semibold cursor-pointer hover:bg-gray-100 p-2 rounded-lg transition-colors group"
                >
                    <span className="text-xl tracking-tight">{activeSession}</span>
                    <ChevronDown className={clsx("w-4 h-4 text-gray-400 transition-transform duration-200", isDropdownOpen && "rotate-180")} />
                </button>

                {/* System Stats */}
                <div className="hidden md:flex flex-col items-end text-right">
                    <div className="text-[10px] font-mono text-gray-400 uppercase tracking-widest mb-1">Nexus AI v{stats?.version || '0.4.2'}</div>
                    <div className="flex items-center gap-1.5 bg-white/50 backdrop-blur-sm border border-gray-100 px-2 py-1 rounded-full shadow-sm">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                        <span className="text-xs font-medium text-gray-600">
                            {stats ? stats.total_points.toLocaleString() : '...'} Knowledge Points
                        </span>
                    </div>
                </div>

                {isDropdownOpen && (
                    <div className="absolute top-full left-6 mt-2 w-56 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                        <div className="p-1">
                            {(['Nexus', 'Nexus Council'] as SessionId[]).map((session) => (
                                <button
                                    key={session}
                                    onClick={() => { setActiveSession(session); setIsDropdownOpen(false); }}
                                    className={clsx(
                                        "w-full text-left px-4 py-3 rounded-lg flex items-center justify-between text-sm font-medium transition-colors",
                                        activeSession === session ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-50"
                                    )}
                                >
                                    <div className="flex items-center gap-3">
                                        {session === 'Nexus Council' ? <Users className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                                        {session}
                                    </div>
                                    {activeSession === session && <Check className="w-4 h-4" />}
                                </button>
                            ))}
                        </div>
                        <div className="bg-gray-50 px-4 py-2 text-[10px] text-gray-400 uppercase font-medium tracking-wider border-t border-gray-100">
                            Modus wechseln
                        </div>
                    </div>
                )}
            </div>

            {/* Messages Area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto w-full scroll-smooth pb-40 pt-24 px-4 md:px-20">
                {history.length === 0 ? (
                    <div className="flex flex-col h-full items-start justify-center max-w-4xl mx-auto pb-20 fade-in animate-in duration-700">
                        <h1 className="text-6xl font-medium tracking-tight mb-2">
                            <span className="text-gradient-gemini">
                                {activeSession === 'Nexus' ? 'Moin Stoner,' : 'Nexus Council Aktiv'}
                            </span>
                        </h1>
                        {/* Animated Greeting */}
                        <h2
                            key={greetingIndex}
                            className="text-6xl font-medium text-gray-300 tracking-tight mb-16 h-20 animate-in fade-in slide-in-from-bottom-2 duration-700 fill-mode-forwards"
                        >
                            {greetings[greetingIndex]}
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 w-full">
                            {suggestions.map((card, i) => (
                                <button
                                    key={i}
                                    onClick={() => handleQuery(card.subtitle)}
                                    className="p-4 rounded-2xl bg-gray-100 hover:bg-gray-200 transition-colors text-left h-48 flex flex-col justify-between group relative overflow-hidden"
                                >
                                    <div>
                                        <div className="font-medium text-gray-800 mb-1">{card.title}</div>
                                        <div className="text-sm text-gray-500">{card.subtitle}</div>
                                    </div>
                                    <div className="self-end p-2 bg-white rounded-full shadow-sm opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Send className="w-4 h-4 text-primary" />
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-10 max-w-3xl mx-auto">
                        {history.map((msg, idx) => (
                            <div key={idx} className={clsx('flex gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500')}>
                                {msg.type === 'bot' && (
                                    <div className={clsx(
                                        "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white mt-1 shadow-md",
                                        activeSession === 'Nexus Council' ? "bg-gradient-to-tr from-purple-600 to-amber-500" : "bg-gradient-to-tr from-blue-500 to-red-500"
                                    )}>
                                        {activeSession === 'Nexus Council' ? <Users className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
                                    </div>
                                )}
                                {msg.type === 'user' && (
                                    <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0 text-gray-600 mt-1 ml-auto order-2">
                                        <User className="w-5 h-5" />
                                    </div>
                                )}

                                <div className={clsx(
                                    'flex-1 space-y-2 min-w-0 w-full overflow-hidden',
                                    msg.type === 'user' ? 'text-right order-1' : ''
                                )}>
                                    <div className={clsx(
                                        "prose prose-lg max-w-none text-gray-800 prose-headings:font-medium prose-p:leading-relaxed prose-pre:bg-gray-900 prose-pre:rounded-xl min-w-0",
                                        msg.type === 'user' && "bg-gray-100 inline-block px-6 py-4 rounded-[2rem] rounded-tr-md text-left"
                                    )}>
                                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                                    </div>

                                    {/* Council Breakdown */}
                                    {msg.type === 'bot' && msg.council_results && msg.council_results.length > 0 && (
                                        <div className="mt-4 grid grid-flow-row gap-2">
                                            <h4 className="text-xs font-semibold text-gray-500 uppercase flex items-center gap-2">
                                                <Users className="w-3 h-3" /> Ratsberichte
                                            </h4>
                                            {msg.council_results.map((res, i) => {
                                                const isStandby = res.task === 'Standby';
                                                return (
                                                    <div key={i} className={clsx(
                                                        "border rounded-xl overflow-hidden shadow-sm transition-opacity",
                                                        isStandby ? "bg-gray-50 border-gray-100 opacity-60" : "bg-white border-gray-200"
                                                    )}>
                                                        <div className={clsx(
                                                            "px-4 py-3 border-b flex justify-between items-center",
                                                            isStandby ? "bg-gray-100 border-gray-200" : "bg-gray-50 border-gray-100"
                                                        )}>
                                                            <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                                                                <span className="text-lg">
                                                                    {COUNCIL_MEMBERS_LIST.find(m => m.id === res.member_id)?.icon || '👤'}
                                                                </span>
                                                                {COUNCIL_MEMBERS_LIST.find(m => m.id === res.member_id)?.name || res.role}
                                                            </div>
                                                            <span
                                                                title={res.task}
                                                                className={clsx(
                                                                    "text-[10px] px-2 py-1 rounded-full border text-right max-w-[60%] leading-tight",
                                                                    isStandby ? "text-gray-400 bg-gray-50 border-gray-200" : "text-gray-500 bg-white border-gray-200"
                                                                )}>
                                                                {res.task}
                                                            </span>
                                                        </div>
                                                        <div className={clsx(
                                                            "p-4 text-sm prose prose-sm max-w-none",
                                                            isStandby ? "text-gray-500 italic" : "text-gray-700 bg-white"
                                                        )}>
                                                            <ReactMarkdown>{res.answer}</ReactMarkdown>

                                                            {/* Expert Specific Sources */}
                                                            {((res.used_context && res.used_context.length > 0) || (res.graph_context && Object.keys(res.graph_context).length > 0)) && (
                                                                <div className="mt-3 pt-3 border-t border-gray-100">
                                                                    <ContextAccordion context={res.used_context} graph={res.graph_context} />
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {/* Context & Graph Accordion */}
                                    {msg.type === 'bot' && (msg.context || msg.graph) && (
                                        <ContextAccordion context={msg.context} graph={msg.graph} />
                                    )}
                                </div>
                            </div>
                        ))}

                        {loading && (
                            <div className="flex gap-6 animate-pulse">
                                <div className={clsx(
                                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white mt-1 opacity-50",
                                    activeSession === 'Nexus Council' ? "bg-gradient-to-tr from-purple-600 to-amber-500" : "bg-gradient-to-tr from-blue-500 to-red-500"
                                )}>
                                    {activeSession === 'Nexus Council' ? <Users className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
                                </div>
                                <div className="flex items-center gap-1 mt-3">
                                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></span>
                                    <span className="w-2 h-2 bg-red-400 rounded-full animate-bounce delay-75"></span>
                                    <span className="w-2 h-2 bg-yellow-400 rounded-full animate-bounce delay-150"></span>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Input Area (Bottom Fixed) */}
            <div className="absolute bottom-0 left-0 w-full p-6 bg-gradient-to-t from-white via-white to-transparent pt-20 z-30">

                {/* Council Member Selector (Visible only in Council Mode) */}
                {activeSession === 'Nexus Council' && (
                    <div className="max-w-3xl mx-auto mb-4 animate-in slide-in-from-bottom-2 fade-in">
                        <div
                            className="bg-white/90 backdrop-blur-md border border-purple-100 rounded-2xl p-4 shadow-lg ring-1 ring-purple-500/10 cursor-pointer"
                            onClick={() => setShowCouncilSelector(!showCouncilSelector)}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-amber-600 uppercase tracking-widest flex items-center gap-2">
                                    <Users className="w-3 h-3 text-purple-600" />
                                    Aktive Ratsmitglieder
                                </span>
                                <span className="text-xs text-gray-400 font-medium">
                                    {selectedMembers.length} Ausgewählt
                                    <ChevronDown className={clsx("w-3 h-3 inline ml-1 transition-transform", showCouncilSelector && "rotate-180")} />
                                </span>
                            </div>

                            {/* Preview or Expanded Selector */}
                            {showCouncilSelector ? (
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3 animate-in fade-in">
                                    {COUNCIL_MEMBERS_LIST.map((member) => (
                                        <div
                                            key={member.id}
                                            onClick={(e) => { e.stopPropagation(); toggleMember(member.id); }}
                                            className={clsx(
                                                "flex items-center gap-2 p-2 rounded-lg border transition-all cursor-pointer select-none",
                                                selectedMembers.includes(member.id)
                                                    ? "bg-purple-50 border-purple-300 shadow-sm"
                                                    : "bg-white border-gray-200 opacity-60 hover:opacity-100"
                                            )}
                                        >
                                            <div className="text-lg">{member.icon}</div>
                                            <div>
                                                <div className={clsx("text-xs font-bold", selectedMembers.includes(member.id) ? "text-purple-900" : "text-gray-600")}>
                                                    {member.name}
                                                </div>
                                                <div className="text-[10px] text-gray-400 truncate w-24">
                                                    {member.role}
                                                </div>
                                            </div>
                                            {selectedMembers.includes(member.id) && <Check className="w-3 h-3 text-purple-600 ml-auto" />}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                // Minimized view (avatars)
                                <div className="flex gap-2 overflow-x-auto pb-1 mt-1">
                                    {selectedMembers.length === 0 ? (
                                        <span className="text-sm text-gray-400 italic">No members selected. Tap to assemble council.</span>
                                    ) : (
                                        selectedMembers.map(mid => {
                                            const m = COUNCIL_MEMBERS_LIST.find(x => x.id === mid);
                                            return (
                                                <div key={mid} className="flex items-center gap-1.5 px-3 py-1 bg-purple-50 rounded-full border border-purple-200">
                                                    <span className="text-sm">{m?.icon}</span>
                                                    <span className="text-xs font-medium text-purple-900">{m?.name}</span>
                                                </div>
                                            )
                                        })
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <div className="max-w-3xl mx-auto relative bg-gray-100 rounded-full flex items-center px-4 py-3 hover:shadow-md transition-shadow focus-within:bg-white focus-within:shadow-lg focus-within:ring-1 focus-within:ring-gray-200">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
                        placeholder={`Fragen Sie ${activeSession}...`}
                        className="flex-1 bg-transparent border-none outline-none px-4 text-gray-800 placeholder-gray-500 h-full"
                    />

                    <div className="flex items-center gap-1 pr-2">
                        {(query.trim()) && (
                            <button
                                onClick={() => handleQuery()}
                                className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-full transition-colors animate-in zoom-in duration-200"
                            >
                                <Send className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </div>
                <div className="text-center mt-3">
                    <p className="text-xs text-gray-400">Nexus may display inaccurate info, including about people, so double-check its responses.</p>
                </div>
            </div>
        </div>
    );
}

function ContextAccordion({ context, graph }: { context?: SearchResult[], graph?: any }) {
    const [isOpen, setIsOpen] = useState(false);

    if ((!context || context.length === 0) && (!graph || Object.keys(graph).length === 0)) return null;

    return (
        <div className="mt-4 relative z-10">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-blue-600 transition-colors bg-white border border-gray-200 px-3 py-1.5 rounded-full shadow-sm hover:shadow cursor-pointer select-none active:scale-95 transition-transform"
            >
                <Sparkles className="w-3 h-3" />
                {isOpen ? "Quellen verbergen" : "Quellen anzeigen"}
            </button>

            {isOpen && (
                <div className="mt-4 p-4 pr-6 bg-gray-50 rounded-2xl border border-gray-200 space-y-4 animate-in fade-in slide-in-from-top-1 duration-200 w-full box-border overflow-hidden">
                    {/* Vector Context */}
                    {context && context.length > 0 && (
                        <div>
                            <h4 className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase mb-3 select-none">
                                <FileText className="w-3 h-3" /> Retrieved Documents
                            </h4>
                            <div className="grid gap-2">
                                {context.map((ctx, i) => (
                                    <ContextItem key={i} ctx={ctx} />
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Graph Context */}
                    {graph && graph.summary && (
                        <div>
                            <h4 className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase mb-3 select-none">
                                <Network className="w-3 h-3" /> Knowledge Graph
                            </h4>
                            <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm text-gray-800">
                                {graph.summary}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function ContextItem({ ctx }: { ctx: SearchResult }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="bg-white p-3 rounded-xl border border-gray-200 hover:border-blue-300 transition-colors shadow-sm min-w-0 max-w-full">
            <div
                onClick={() => setExpanded(!expanded)}
                className={clsx(
                    "text-sm text-gray-600 cursor-pointer font-serif leading-relaxed break-all overflow-hidden",
                    !expanded && "line-clamp-2"
                )}
            >
                "{ctx.text}"
            </div>

            <div className="mt-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium select-none">
                        {ctx.score.toFixed(2)}
                    </span>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="text-[10px] text-gray-400 hover:text-gray-600 font-medium select-none"
                    >
                        {expanded ? "Weniger anzeigen" : "Mehr anzeigen"}
                    </button>
                </div>

                {ctx.metadata?.source_url ? (
                    <a
                        href={ctx.metadata.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-blue-500 hover:underline truncate max-w-[150px]"
                    >
                        {ctx.metadata?.filename || 'Quelle öffnen'}
                    </a>
                ) : (
                    <span className="text-[10px] text-gray-400 truncate max-w-[150px]">
                        {ctx.metadata?.filename || ctx.metadata?.source || 'Unbekannte Quelle'}
                    </span>
                )}
            </div>
        </div>
    );
}
