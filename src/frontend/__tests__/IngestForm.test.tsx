import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import IngestForm from '../components/IngestForm';
// Note: IngestForm uses native fetch not the api utility wrapper for streaming, 
// so we should mock global.fetch instead of api.post for some tests, 
// OR check if IngestForm was updated to use api.post (it uses fetch in the viewed code).
// The original test mocked api.post, but the component uses fetch. 
// I will mock global.fetch here.

// Mock fetch
global.fetch = jest.fn();

describe('IngestForm', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders correctly with default Text tab', () => {
        render(<IngestForm />);
        expect(screen.getByPlaceholderText('Textinhalt hier einfügen...')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: /Inhalte aufnehmen/i })).toBeInTheDocument();
    });

    it('switches tabs correctly', () => {
        render(<IngestForm />);

        // Switch to URL tab
        fireEvent.click(screen.getByText('url')); // displayed as capitalized by CSS or text content? Code has {tab} inside span className="capitalize".
        // The dom text content will be "url" but capitalized visuals. Library getByText checks text node. "url" is text node.

        expect(screen.getByPlaceholderText('https://example.com')).toBeInTheDocument();

        // Switch to File tab
        fireEvent.click(screen.getByText('file'));
        expect(screen.getByText(/Klicken zum Hochladen/i)).toBeInTheDocument();
    });

    it('submits text ingestion successfully', async () => {
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            body: {
                getReader: () => ({
                    read: jest.fn()
                        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(JSON.stringify({ step: 'complete', message: 'Erfolgreich', progress: 1.0 }) + '\n') })
                        .mockResolvedValueOnce({ done: true })
                })
            }
        });

        render(<IngestForm />);

        const textarea = screen.getByPlaceholderText('Textinhalt hier einfügen...');
        fireEvent.change(textarea, { target: { value: 'Test content' } });

        const button = screen.getByRole('button', { name: /Inhalte aufnehmen/i });
        fireEvent.click(button);

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/ingest'),
                expect.objectContaining({
                    method: 'POST',
                    body: expect.any(String)
                })
            );
            expect(screen.getByText('Erfolgreich')).toBeInTheDocument();
        });
    });
});
