

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import IngestForm from '../components/IngestForm';

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
        expect(screen.getByText(/Verarbeitungs-Pipeline/i)).toBeInTheDocument();
    });

    it('adds item to queue and processes pipeline', async () => {
        // Mock successful stream response
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            ok: true,
            body: {
                getReader: () => ({
                    read: jest.fn()
                        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(JSON.stringify({ step: 'complete', message: 'Ingestion complete', progress: 1.0 }) + '\n') })
                        .mockResolvedValueOnce({ done: true })
                })
            }
        });

        render(<IngestForm />);

        // ENTER TEXT
        const textarea = screen.getByPlaceholderText('Textinhalt hier einfügen...');
        fireEvent.change(textarea, { target: { value: 'Test pipeline content' } });

        // ADD TO PIPELINE
        const addButton = screen.getByRole('button', { name: /Zur Pipeline hinzufügen/i });
        fireEvent.click(addButton);

        // CHECK QUEUE
        expect(screen.getByText('Test pipeline content')).toBeInTheDocument();
        // Wait for Start button to be enabled/visible
        const startButton = screen.getByRole('button', { name: /Starten/i });
        expect(startButton).toBeInTheDocument();

        // START PIPELINE
        fireEvent.click(startButton);

        // VERIFY FETCH CALL
        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/ingest'),
                expect.objectContaining({
                    method: 'POST',
                    body: expect.any(String) // or check json content
                })
            );
            // Check for success indicator (CheckCircle logic in component updates status to 'completed')
            // Using testid for icons in setup would be cleaner, but we can check for logic side effects or classNames if strictly needed.
            // For now, let's verify fetch called.
        });
    });
});
