import IngestForm from '../components/IngestForm';
import ChatInterface from '../components/ChatInterface';
import { Database, LayoutDashboard } from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 p-8 font-[family-name:var(--font-geist-sans)]">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-600/20">
              <Database className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">RAG Knowledge Base</h1>
              <p className="text-sm text-gray-500">Vector Search + Knowledge Graph</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500 bg-white px-3 py-1.5 rounded-full border border-gray-200 shadow-sm">
            <LayoutDashboard className="w-4 h-4" />
            v0.1.0
          </div>
        </header>

        {/* Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          {/* Left Column: Ingestion (4 cols) */}
          <div className="lg:col-span-4 space-y-6">
            <IngestForm />

            {/* Stats Card (Placeholder) */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <h3 className="font-semibold text-gray-900 mb-4">System Status</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Backend</span>
                  <span className="text-green-600 font-medium flex items-center gap-1">
                    <span className="w-2 h-2 bg-green-500 rounded-full"></span> Online
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Vector DB</span>
                  <span className="text-green-600 font-medium flex items-center gap-1">
                    <span className="w-2 h-2 bg-green-500 rounded-full"></span> Connected
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
