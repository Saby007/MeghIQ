import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatResponse {
  type: 'message' | 'diagram' | 'error';
  content?: string;
  xml?: string;
  session_id?: string;
  message?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private apiUrl = environment.apiUrl;
  private sessionId: string | null = null;
  private messagesSubject = new BehaviorSubject<Message[]>([]);
  public messages$ = this.messagesSubject.asObservable();

  constructor(private http: HttpClient) {}

  sendMessage(message: string): Observable<ChatResponse> {
    const payload = {
      message: message,
      session_id: this.sessionId,
      history: this.getHistory()
    };

    // Don't save to file on server (UI will handle download)
    const params = new HttpParams().set('save_to_file', 'false');

    return this.http.post<ChatResponse>(
      `${this.apiUrl}/generate-architecture`,
      payload,
      { params }
    );
  }

  addMessage(message: Message): void {
    const currentMessages = this.messagesSubject.value;
    this.messagesSubject.next([...currentMessages, message]);
  }

  getMessages(): Message[] {
    return this.messagesSubject.value;
  }

  private getHistory(): { role: string; content: string }[] {
    return this.messagesSubject.value.map(msg => ({
      role: msg.role,
      content: msg.content
    }));
  }

  setSessionId(sessionId: string): void {
    this.sessionId = sessionId;
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  resetSession(): void {
    this.sessionId = null;
    this.messagesSubject.next([]);
  }

  estimateCost(diagramXml: string): Observable<any> {
    const payload = {
      xml: diagramXml
    };

    return this.http.post<any>(
      `${this.apiUrl}/estimate-cost`,
      payload
    );
  }
}
