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
        expect(screen.getByText('RAG Assistant')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Type your question...')).toBeInTheDocument();
    });

    it('sends query and displays response', async () => {
        (api.post as jest.Mock).mockResolvedValueOnce({
            data: {
                answer: 'This is the answer.',
                context: [{ text: 'Context chunk', score: 0.9, metadata: {} }],
                graph_context: { summary: 'Graph info' }
            }
        });

        render(<ChatInterface />);

        const input = screen.getByPlaceholderText('Type your question...');
        fireEvent.change(input, { target: { value: 'What is RAG?' } });

        const button = screen.getByRole('button'); // Send button
        fireEvent.click(button);

        // Check user message
        expect(screen.getByText('What is RAG?')).toBeInTheDocument();

        // Check bot response
        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/query', { query: 'What is RAG?', limit: 5 });
            expect(screen.getByText('This is the answer.')).toBeInTheDocument();
        });
    });
});
