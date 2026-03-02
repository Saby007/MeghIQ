import { Component, ViewChild, ElementRef, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, ChatResponse } from '../../services/chat.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sqlQuery?: string;
  rawData?: { columns: string[]; rows: string[][]; row_count: number };
  timestamp: Date;
  loading?: boolean;
}

@Component({
  selector: 'app-chat',
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
})
export class ChatComponent {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;
  @ViewChild('messageInput') private messageInput!: ElementRef;

  messages = signal<ChatMessage[]>([]);
  userInput = '';
  isLoading = signal(false);
  sessionId = 'session-' + Date.now();
  showSqlFor = signal<number | null>(null);

  constructor(private chatService: ChatService) {}

  sendMessage(): void {
    const message = this.userInput.trim();
    if (!message || this.isLoading()) return;

    // Add user message
    this.messages.update((msgs) => [
      ...msgs,
      { role: 'user', content: message, timestamp: new Date() },
    ]);
    this.userInput = '';
    this.isLoading.set(true);

    // Add loading placeholder
    this.messages.update((msgs) => [
      ...msgs,
      { role: 'assistant', content: '', timestamp: new Date(), loading: true },
    ]);

    this.scrollToBottom();

    this.chatService.sendMessage(message, this.sessionId).subscribe({
      next: (response: ChatResponse) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: response.answer,
            sqlQuery: response.sql_query || undefined,
            rawData: response.raw_data || undefined,
            timestamp: new Date(),
            loading: false,
          };
          return updated;
        });
        this.isLoading.set(false);
        this.scrollToBottom();
      },
      error: (err) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: 'Sorry, something went wrong. Please try again.',
            timestamp: new Date(),
            loading: false,
          };
          return updated;
        });
        this.isLoading.set(false);
        console.error('Chat error:', err);
      },
    });
  }

  toggleSql(index: number): void {
    this.showSqlFor.update((current) => (current === index ? null : index));
  }

  clearChat(): void {
    this.chatService.clearSession(this.sessionId).subscribe({
      next: () => {
        this.messages.set([]);
        this.sessionId = 'session-' + Date.now();
      },
      error: (err) => console.error('Clear error:', err),
    });
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      if (this.messagesContainer) {
        const el = this.messagesContainer.nativeElement;
        el.scrollTop = el.scrollHeight;
      }
    }, 100);
  }
}
