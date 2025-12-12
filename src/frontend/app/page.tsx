'use client';

import { useState } from 'react';
import ChatInterface from '../components/ChatInterface';
import IngestForm from '../components/IngestForm';
import Sidebar from '../components/Sidebar';
import GrowVision from '../components/GrowVision';
import GenealogyExplorer from '../components/GenealogyExplorer';

export default function Home() {
  const [activeView, setActiveView] = useState<'chat' | 'ingest' | 'vision' | 'genealogy'>('chat');

  return (
    <div className="flex h-screen w-full bg-white text-gray-900 font-sans selection:bg-blue-100 selection:text-blue-900">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

      <main className="flex-1 h-full overflow-hidden flex flex-col relative bg-white">
        {activeView === 'chat' && (
          <ChatInterface />
        )}

        {activeView === 'ingest' && (
          <div className="flex-1 overflow-y-auto w-full">
            <div className="p-8 max-w-3xl mx-auto w-full pt-16 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="mb-8 text-center">
                <h1 className="text-3xl font-medium tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-red-500 bg-clip-text text-transparent">
                  Wissens Import
                </h1>
                <p className="text-gray-500 mt-2">Füge Dokumente und URLs zur Wissensbasis hinzu</p>
              </div>
              <IngestForm />
            </div>
          </div>
        )}

        {activeView === 'vision' && (
          <GrowVision />
        )}

        {activeView === 'genealogy' && (
          <GenealogyExplorer />
        )}
      </main>
    </div>
  );
}
