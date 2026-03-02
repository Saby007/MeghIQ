import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  answer: string;
  sql_query?: string;
  raw_data?: {
    columns: string[];
    rows: string[][];
    row_count: number;
  };
  session_id: string;
}

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private readonly apiUrl = 'http://localhost:8000/api';

  constructor(private http: HttpClient) {}

  sendMessage(message: string, sessionId: string = 'default'): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.apiUrl}/chat`, {
      message,
      session_id: sessionId,
    });
  }

  clearSession(sessionId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/chat/${sessionId}`);
  }

  healthCheck(): Observable<any> {
    return this.http.get(`${this.apiUrl}/health`);
  }
}
