import '@testing-library/jest-dom'
import { TextEncoder, TextDecoder } from 'util'
import React from 'react'

Object.assign(global, { TextDecoder, TextEncoder })

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn()

// Mock react-markdown to avoid ESM issues
jest.mock('react-markdown', () => ({
    __esModule: true,
    default: ({ children }: { children: React.ReactNode }) => {
        return React.createElement('div', { 'data-testid': 'markdown-content' }, children)
    },
}))

// Mock lucide-react icons if needed (optional but safe)
jest.mock('lucide-react', () => ({
    Upload: () => React.createElement('svg', { 'data-testid': 'icon-upload' }),
    Link: () => React.createElement('svg', { 'data-testid': 'icon-link' }),
    FileText: () => React.createElement('svg', { 'data-testid': 'icon-file-text' }),
    Loader2: () => React.createElement('svg', { 'data-testid': 'icon-loader' }),
    CheckCircle: () => React.createElement('svg', { 'data-testid': 'icon-check' }),
    AlertCircle: () => React.createElement('svg', { 'data-testid': 'icon-alert' }),
    RefreshCw: () => React.createElement('svg', { 'data-testid': 'icon-refresh' }),
    MessageSquare: () => React.createElement('svg', { 'data-testid': 'icon-message' }),
    Menu: () => React.createElement('svg', { 'data-testid': 'icon-menu' }),
    Settings: () => React.createElement('svg', { 'data-testid': 'icon-settings' }),
    Send: () => React.createElement('svg', { 'data-testid': 'icon-send' }),
    User: () => React.createElement('svg', { 'data-testid': 'icon-user' }),
    Sparkles: () => React.createElement('svg', { 'data-testid': 'icon-sparkles' }),
    Users: () => React.createElement('svg', { 'data-testid': 'icon-users' }),
    Check: () => React.createElement('svg', { 'data-testid': 'icon-check' }),
    ChevronDown: () => React.createElement('svg', { 'data-testid': 'icon-chevron-down' }),
    Search: () => React.createElement('svg', { 'data-testid': 'icon-search' }),
    X: () => React.createElement('svg', { 'data-testid': 'icon-x' }),
    Play: () => React.createElement('svg', { 'data-testid': 'icon-play' }),
    Clock: () => React.createElement('svg', { 'data-testid': 'icon-clock' }),
    Database: () => React.createElement('svg', { 'data-testid': 'icon-database' }),
    Sprout: () => React.createElement('svg', { 'data-testid': 'icon-sprout' }),
    FlaskConical: () => React.createElement('svg', { 'data-testid': 'icon-flask' }),
    Activity: () => React.createElement('svg', { 'data-testid': 'icon-activity' }),
    Scale: () => React.createElement('svg', { 'data-testid': 'icon-scale' }),
}))
