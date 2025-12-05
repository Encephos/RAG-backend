import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'secret-api-key';

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
    },
});

export interface IngestResponse {
    status: string;
    message: string;
    filename?: string;
    num_chunks?: number;
    pages_processed?: number;
}

export interface QueryResponse {
    answer: string;
    context: SearchResult[];
    graph_context: any;
    council_results?: {
        member_id: string;
        role: string;
        task: string;
        answer: string;
    }[];
}

export interface SearchResult {
    text: string;
    score: number;
    metadata: any;
}
