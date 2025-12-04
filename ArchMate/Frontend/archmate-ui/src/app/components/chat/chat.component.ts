import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ChatService, Message } from '../../services/chat.service';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatInputModule,
    MatFormFieldModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatToolbarModule,
    MatDividerModule,
    MatTooltipModule,
    MatSnackBarModule
  ],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messageContainer') private messageContainer!: ElementRef;
  @ViewChild('diagramViewer') private diagramViewer!: ElementRef;

  userMessage = '';
  messages: Message[] = [];
  isLoading = false;
  isEstimatingCost = false;
  diagramXml: string | null = null;
  showDiagram = false;
  sessionId: string | null = null;

  private shouldScrollToBottom = false;

  constructor(
    private chatService: ChatService,
    private snackBar: MatSnackBar,
    private sanitizer: DomSanitizer
  ) {}

  ngOnInit(): void {
    this.chatService.messages$.subscribe(messages => {
      this.messages = messages;
      this.shouldScrollToBottom = true;
    });

    this.sessionId = this.chatService.getSessionId();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  sendMessage(): void {
    if (!this.userMessage.trim() || this.isLoading) {
      return;
    }

    const userMsg: Message = {
      role: 'user',
      content: this.userMessage,
      timestamp: new Date()
    };

    this.chatService.addMessage(userMsg);
    const messageToSend = this.userMessage;
    this.userMessage = '';
    this.isLoading = true;

    this.chatService.sendMessage(messageToSend).subscribe({
      next: (response) => {
        console.log('Received response:', response);
        console.log('Response type:', response.type);
        this.isLoading = false;

        if (response.session_id) {
          this.sessionId = response.session_id;
          this.chatService.setSessionId(response.session_id);
        }

        if (response.type === 'message' && response.content) {
          const assistantMsg: Message = {
            role: 'assistant',
            content: response.content,
            timestamp: new Date()
          };
          this.chatService.addMessage(assistantMsg);
        } else if (response.type === 'diagram' && response.xml) {
          const assistantMsg: Message = {
            role: 'assistant',
            content: '✅ Architecture diagram generated successfully! You can view it in the diagram panel on the right.',
            timestamp: new Date()
          };
          this.chatService.addMessage(assistantMsg);
          this.diagramXml = response.xml;
          this.showDiagram = true;
          this.renderDiagram();
          
          // Reset session to allow new diagram generation
          this.chatService.resetSession();
          this.sessionId = null;
        } else if (response.type === 'error') {
          const errorMsg: Message = {
            role: 'assistant',
            content: `❌ Error: ${response.message || 'An unknown error occurred'}`,
            timestamp: new Date()
          };
          this.chatService.addMessage(errorMsg);
          this.showSnackbar('An error occurred. Please try again.', 'error');
        } else {
          console.warn('Unknown response type:', response);
          const unknownMsg: Message = {
            role: 'assistant',
            content: `Received response of type: ${response.type}. Full response logged to console.`,
            timestamp: new Date()
          };
          this.chatService.addMessage(unknownMsg);
        }
      },
      error: (error) => {
        this.isLoading = false;
        const errorMsg: Message = {
          role: 'assistant',
          content: `❌ Connection error: ${error.message}`,
          timestamp: new Date()
        };
        this.chatService.addMessage(errorMsg);
        this.showSnackbar('Failed to connect to the server.', 'error');
      }
    });
  }

  resetSession(): void {
    this.chatService.resetSession();
    this.diagramXml = null;
    this.showDiagram = false;
    this.sessionId = null;
    this.showSnackbar('Session reset successfully', 'success');
  }

  onFileUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) {
      return;
    }

    const file = input.files[0];
    if (!file.name.endsWith('.drawio') && !file.name.endsWith('.xml')) {
      this.showSnackbar('Please upload a .drawio or .xml file', 'warning');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (content) {
        this.diagramXml = content;
        this.showDiagram = true;
        this.renderDiagram();
        this.showSnackbar('Diagram uploaded successfully', 'success');
      }
    };
    reader.onerror = () => {
      this.showSnackbar('Failed to read file', 'error');
    };
    reader.readAsText(file);

    // Reset input so same file can be uploaded again
    input.value = '';
  }

  downloadDiagram(): void {
    if (!this.diagramXml) {
      this.showSnackbar('No diagram to download', 'warning');
      return;
    }

    const blob = new Blob([this.diagramXml], { type: 'application/xml' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `architecture-${new Date().getTime()}.drawio`;
    link.click();
    window.URL.revokeObjectURL(url);
    this.showSnackbar('Diagram downloaded successfully', 'success');
  }

  estimateCost(): void {
    if (!this.diagramXml) {
      this.showSnackbar('No diagram available for cost estimation', 'warning');
      return;
    }

    this.isEstimatingCost = true;

    this.chatService.estimateCost(this.diagramXml).subscribe({
      next: (response) => {
        this.isEstimatingCost = false;
        
        if (response.status === 'success' && response.estimation) {
          const estimation = response.estimation;
          
          // Format cost estimation as HTML table
          let costMessage = `💰 **Cost Estimation for Architecture**\n\n`;
          costMessage += `**Monthly Total:** $${estimation.monthly_total?.toFixed(2) || 'N/A'} | **Annual Total:** $${estimation.annual_total?.toFixed(2) || 'N/A'}\n\n`;
          
          // Category breakdown table
          if (estimation.breakdown_by_category) {
            costMessage += `**Cost Breakdown by Category:**\n\n`;
            costMessage += `| Category | Monthly Cost |\n`;
            costMessage += `|----------|-------------:|\n`;
            Object.entries(estimation.breakdown_by_category).forEach(([category, cost]: [string, any]) => {
              const categoryName = category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ');
              costMessage += `| ${categoryName} | $${cost.toFixed(2)} |\n`;
            });
            costMessage += `\n`;
          }
          
          // Service-level details table
          if (estimation.services && estimation.services.length > 0) {
            costMessage += `**Service-Level Details:**\n\n`;
            costMessage += `| Service | Type | Tier | Quantity | Monthly Cost | Pricing Source |\n`;
            costMessage += `|---------|------|------|----------|-------------:|---------------|\n`;
            
            let realPricingCount = 0;
            estimation.services.forEach((svc: any) => {
              const pricingSource = (svc.notes && (svc.notes.includes('Azure Retail Prices API') || svc.notes.includes('from API'))) 
                ? '✓ Azure API' 
                : 'Estimated';
              if (pricingSource === '✓ Azure API') realPricingCount++;
              
              costMessage += `| ${svc.name} | ${svc.type} | ${svc.tier} | ${svc.quantity} | $${svc.total_cost?.toFixed(2) || 'N/A'} | ${pricingSource} |\n`;
            });
            costMessage += `\n`;
            
            // Add summary of pricing data sources
            if (realPricingCount > 0) {
              costMessage += `_${realPricingCount} service(s) priced using official Azure Retail Prices API_\n\n`;
            }
          }
          
          // Regional breakdown table
          if (estimation.regions && estimation.regions.length > 0) {
            costMessage += `**Regional Breakdown:**\n\n`;
            costMessage += `| Region | Monthly Cost |\n`;
            costMessage += `|--------|-------------:|\n`;
            estimation.regions.forEach((region: any) => {
              costMessage += `| ${region.name} | $${region.monthly_cost?.toFixed(2) || 'N/A'} |\n`;
            });
            costMessage += `\n`;
          }
          
          // Data transfer costs table
          if (estimation.data_transfer) {
            costMessage += `**Data Transfer Costs:**\n\n`;
            costMessage += `| Type | Monthly Cost |\n`;
            costMessage += `|------|-------------:|\n`;
            if (estimation.data_transfer.inter_region) {
              costMessage += `| Inter-region | $${estimation.data_transfer.inter_region.toFixed(2)} |\n`;
            }
            if (estimation.data_transfer.egress) {
              costMessage += `| Egress to Internet | $${estimation.data_transfer.egress.toFixed(2)} |\n`;
            }
            costMessage += `\n`;
          }
          
          // Assumptions
          if (estimation.assumptions && estimation.assumptions.length > 0) {
            costMessage += `**Assumptions:**\n`;
            estimation.assumptions.forEach((assumption: string) => {
              costMessage += `- ${assumption}\n`;
            });
          }
          
          const costMsg: Message = {
            role: 'assistant',
            content: costMessage,
            timestamp: new Date()
          };
          this.chatService.addMessage(costMsg);
          this.showSnackbar('Cost estimation completed', 'success');
        } else {
          this.showSnackbar('Failed to estimate cost', 'error');
        }
      },
      error: (error) => {
        this.isEstimatingCost = false;
        console.error('Cost estimation error:', error);
        this.showSnackbar('Cost estimation failed', 'error');
      }
    });
  }

  private renderDiagram(): void {
    if (!this.diagramXml || !this.diagramViewer) {
      return;
    }

    setTimeout(() => {
      const viewer = this.diagramViewer.nativeElement;
      viewer.innerHTML = '';

      // Create iframe with DrawIO viewer using simple approach
      const iframe = document.createElement('iframe');
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      iframe.style.backgroundColor = '#ffffff';

      // Try the simplest possible approach - direct XML in data URI
      try {
        console.log('Diagram XML length:', this.diagramXml!.length);
        
        // Always use URL encoding (not base64) for viewer.diagrams.net
        // The viewer expects URL-encoded XML after #R parameter
        const encoded = encodeURIComponent(this.diagramXml!);
        
        console.log('Encoded URL length:', encoded.length);
        console.log('Loading diagram in viewer...');
        
        // Build URL with proper zoom parameters
        // chrome=0 removes toolbar, page-fit=1 fits to viewport, math=0 disables math rendering
        const baseUrl = 'https://viewer.diagrams.net/';
        const params = new URLSearchParams({
          'highlight': '0000ff',
          'edit': '_blank',
          'layers': '1',
          'nav': '1',
          'page-fit': '1',
          'zoom': '1',
          'title': 'Architecture.drawio'
        });
        
        iframe.src = `${baseUrl}?${params.toString()}#R${encoded}`;
        
        // After iframe loads, try to send a message to force fit
        iframe.onload = () => {
          console.log('Diagram iframe loaded');
          // Send postMessage to the iframe to ensure zoom is applied
          setTimeout(() => {
            try {
              iframe.contentWindow?.postMessage(JSON.stringify({
                action: 'fitWindow'
              }), 'https://viewer.diagrams.net');
            } catch (e) {
              console.log('Could not send fitWindow message:', e);
            }
          }, 500);
        };
        
        viewer.appendChild(iframe);
      } catch (error) {
        console.error('Error rendering diagram:', error);
        viewer.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: center; height: 100%; flex-direction: column; padding: 40px; text-align: center;">
            <div style="font-size: 48px; color: #f44336; margin-bottom: 16px;">⚠️</div>
            <h3 style="color: #333; margin-bottom: 12px;">Could not render diagram</h3>
            <p style="color: #666; margin-bottom: 20px;">Please use the Download button to save and view the diagram.</p>
          </div>
        `;
      }
    }, 100);
  }

  private scrollToBottom(): void {
    try {
      if (this.messageContainer) {
        this.messageContainer.nativeElement.scrollTop = this.messageContainer.nativeElement.scrollHeight;
      }
    } catch (err) {
      console.error('Scroll to bottom failed:', err);
    }
  }

  private showSnackbar(message: string, type: 'success' | 'error' | 'warning'): void {
    const panelClass = type === 'success' ? 'success-snackbar' : 
                       type === 'error' ? 'error-snackbar' : 'warning-snackbar';
    
    this.snackBar.open(message, 'Close', {
      duration: 3000,
      horizontalPosition: 'end',
      verticalPosition: 'top',
      panelClass: [panelClass]
    });
  }

  convertMarkdownToHtml(markdown: string): SafeHtml {
    if (!markdown) return '';
    
    let html = markdown;
    
    // Convert markdown tables to HTML tables
    const tableRegex = /\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)/g;
    html = html.replace(tableRegex, (match, header, body) => {
      const headers = header.split('|').map((h: string) => h.trim()).filter((h: string) => h);
      const rows = body.trim().split('\n').map((row: string) => 
        row.split('|').map((cell: string) => cell.trim()).filter((cell: string) => cell)
      );
      
      let table = '<table class="cost-table"><thead><tr>';
      headers.forEach((h: string) => {
        table += `<th>${h}</th>`;
      });
      table += '</tr></thead><tbody>';
      
      rows.forEach((row: string[]) => {
        table += '<tr>';
        row.forEach((cell: string) => {
          table += `<td>${cell}</td>`;
        });
        table += '</tr>';
      });
      
      table += '</tbody></table>';
      return table;
    });
    
    // Convert bold **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert italic *text*
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    // Convert bullet lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Convert line breaks
    html = html.replace(/\n/g, '<br>');
    
    return this.sanitizer.sanitize(1, html) || html;
  }

  onKeyPress(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}
