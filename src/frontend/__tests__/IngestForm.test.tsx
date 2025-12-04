import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import IngestForm from '../components/IngestForm';
import { api } from '../utils/api';

// Mock the API module
jest.mock('../utils/api', () => ({
    api: {
        post: jest.fn(),
    },
}));

describe('IngestForm', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders correctly with default Text tab', () => {
        render(<IngestForm />);
        expect(screen.getByPlaceholderText('Paste text content here...')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /Ingest Content/i })).toBeInTheDocument();
    });

    it('switches tabs correctly', () => {
        render(<IngestForm />);

        // Switch to URL tab
        fireEvent.click(screen.getByText('URL'));
        expect(screen.getByPlaceholderText('https://example.com')).toBeInTheDocument();

        // Switch to File tab
        fireEvent.click(screen.getByText('File'));
        expect(screen.getByText(/Click to upload/i)).toBeInTheDocument();
    });

    it('submits text ingestion successfully', async () => {
        (api.post as jest.Mock).mockResolvedValueOnce({
            data: { status: 'success', message: 'Ingested successfully' }
        });

        render(<IngestForm />);

        const textarea = screen.getByPlaceholderText('Paste text content here...');
        fireEvent.change(textarea, { target: { value: 'Test content' } });

        const button = screen.getByRole('button', { name: /Ingest Content/i });
        fireEvent.click(button);

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith('/ingest', {
                text: 'Test content',
                metadata: { source: 'manual' }
            });
            expect(screen.getByText('Ingested successfully')).toBeInTheDocument();
        });
    });

    it('handles ingestion error', async () => {
        (api.post as jest.Mock).mockRejectedValueOnce({
            response: { data: { detail: 'API Error' } }
        });

        render(<IngestForm />);

        const textarea = screen.getByPlaceholderText('Paste text content here...');
        fireEvent.change(textarea, { target: { value: 'Test content' } });

        fireEvent.click(screen.getByRole('button', { name: /Ingest Content/i }));

        await waitFor(() => {
            expect(screen.getByText('API Error')).toBeInTheDocument();
        });
    });
});
