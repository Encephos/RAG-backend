import IngestForm from '../components/IngestForm';
import ChatInterface from '../components/ChatInterface';
import { Database, LayoutDashboard } from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-violet-500/30">
              <Database className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight">RAG Knowledge Base</h1>
              <p className="text-sm text-gray-400">Vector Search + Knowledge Graph</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-medium text-gray-400 glass-panel px-4 py-2 rounded-full">
            <LayoutDashboard className="w-4 h-4 text-violet-400" />
            v2.0.0
          </div>
        </header>

        {/* Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* Left Column: Ingestion (4 cols) */}
          <div className="lg:col-span-4 space-y-6">
            <IngestForm />

            {/* Stats Card */}
            <div className="glass-panel p-6 rounded-2xl">
              <h3 className="font-semibold text-gray-200 mb-4 flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-400"></div>
                System Status
              </h3>
              <div className="space-y-4">
                <div className="flex justify-between text-sm py-2 border-b border-gray-700/50">
                  <span className="text-gray-400">Backend API</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    Online
                  </span>
                </div>
                <div className="flex justify-between text-sm py-2">
                  <span className="text-gray-400">Vector Database</span>
                  <span className="text-emerald-400 font-medium flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                    Connected
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Chat (8 cols) */}
          <div className="lg:col-span-8">
            <ChatInterface />
          </div>
        </div>
      </div>
    </main>
  );
}
