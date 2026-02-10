
import { User } from '../types';

const API_BASE_URL = 'http://localhost:8000';

export const apiService = {
    async register(name: string, email: string, password: string): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, role: 'student' })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        return response.json();
    },

    async login(email: string, password: string): Promise<{access_token: string, token_type: string}> {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        localStorage.setItem('nuesa_token', data.access_token);
        return data;
    },

    async getUsers(): Promise<User[]> {
        const token = localStorage.getItem('nuesa_token');
        const response = await fetch(`${API_BASE_URL}/admin/users`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) throw new Error("Unauthorized Admin Access");
        return response.json();
    },

    async getTrendingOpportunities(): Promise<any[]> {
        const response = await fetch(`${API_BASE_URL}/opportunities/trending`);
        if (!response.ok) return [];
        return response.json();
    },

    logout() {
        localStorage.removeItem('nuesa_token');
    }
};
