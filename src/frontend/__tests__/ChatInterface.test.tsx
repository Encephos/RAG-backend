import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatInterface from '../components/ChatInterface';
import { api } from '../utils/api';

jest.mock('../utils/api', () => ({
    api: {
        post: jest.fn(),
    },
}));

describe('ChatInterface', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders correctly', () => {
        render(<ChatInterface />);
        expect(screen.getByText('Hallo, Mensch')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Fragen Sie Nexus...')).toBeInTheDocument();
    });

    it('sends query and displays response', async () => {
        (api.post as jest.Mock).mockResolvedValueOnce({
            data: {
                answer: 'Das ist die Antwort.',
                context: [{ text: 'Context chunk', score: 0.9, metadata: {} }],
                graph_context: { summary: 'Graph info' },
                council_results: []
            }
        });

        render(<ChatInterface />);

        const input = screen.getByPlaceholderText('Fragen Sie Nexus...');
        fireEvent.change(input, { target: { value: 'Was ist RAG?' } });

        // Find send button via icon testid (there are multiple, the input one is last)
        const sendIcons = screen.getAllByTestId('icon-send');
        const sendButton = sendIcons[sendIcons.length - 1].closest('button');
        if (sendButton) fireEvent.click(sendButton);

        // Check user message
        expect(screen.getByText('Was ist RAG?')).toBeInTheDocument();

        // Check bot response
        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/query', expect.objectContaining({ query: 'Was ist RAG?' }));
            expect(screen.getByText('Das ist die Antwort.')).toBeInTheDocument();
        });
    });
});
