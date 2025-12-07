'use client';

import { clsx } from 'clsx';
import { MessageSquare, Upload, Menu, Settings, ScanEye } from 'lucide-react';
import { useState } from 'react';

type View = 'chat' | 'ingest' | 'vision';

interface SidebarProps {
    activeView: View;
    onViewChange: (view: View) => void;
}

export default function Sidebar({ activeView, onViewChange }: SidebarProps) {
    const [collapsed, setCollapsed] = useState(false);

    return (
        <div className={clsx(
            "h-full bg-gray-50 flex flex-col transition-all duration-300 border-r border-gray-200",
            collapsed ? "w-20 items-center py-4" : "w-64 p-4"
        )}>
            {/* Header / Menu Toggle */}
            <div className={clsx("mb-8 flex items-center", collapsed ? "justify-center" : "gap-3 px-2")}>
                <button
                    onClick={() => setCollapsed(!collapsed)}
                    className="p-2 hover:bg-gray-200/50 rounded-full transition-colors text-gray-500 hover:text-gray-700"
                >
                    <Menu className="w-5 h-5" />
                </button>
                {!collapsed && (
                    <span className="font-semibold text-gray-800 text-lg tracking-tight">Nexus</span>
                )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 flex flex-col gap-2">
                <NavItem
                    icon={MessageSquare}
                    label="Chat"
                    isActive={activeView === 'chat'}
                    isCollapsed={collapsed}
                    onClick={() => onViewChange('chat')}
                />
                <NavItem
                    icon={Upload}
                    label="Inhalte aufnehmen"
                    isActive={activeView === 'ingest'}
                    isCollapsed={collapsed}
                    onClick={() => onViewChange('ingest')}
                />
                <NavItem
                    icon={ScanEye}
                    label="Nexus Grow Vision"
                    isActive={activeView === 'vision'}
                    isCollapsed={collapsed}
                    onClick={() => onViewChange('vision')}
                />
            </nav>

            {/* Footer / Settings */}
            <div className="mt-auto">
                <NavItem
                    icon={Settings}
                    label="Einstellungen"
                    isActive={false}
                    isCollapsed={collapsed}
                    onClick={() => { }} // Placeholder
                />
            </div>
        </div>
    );
}

function NavItem({ icon: Icon, label, isActive, isCollapsed, onClick }: any) {
    return (
        <button
            onClick={onClick}
            className={clsx(
                "flex items-center gap-3 p-3 rounded-full transition-all group",
                isActive
                    ? "bg-blue-100/50 text-blue-800 font-medium"
                    : "text-gray-600 hover:bg-gray-100 font-medium",
                isCollapsed && "justify-center px-0 w-10 h-10 mx-auto"
            )}
            title={isCollapsed ? label : undefined}
        >
            <Icon className={clsx("w-5 h-5", isActive ? "text-blue-600" : "text-gray-500 group-hover:text-gray-900")} />
            {!isCollapsed && <span>{label}</span>}
        </button>
    );
}
