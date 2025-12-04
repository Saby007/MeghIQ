# ArchMate UI - Angular Frontend

Modern, corporate-themed Angular application for interacting with the ArchMate architecture diagram generator.

## Features

✨ **Modern UI**: Built with Angular 18 and Material Design  
💬 **Real-time Chat**: Conversational interface for architecture requirements  
📊 **Live Diagram Preview**: View generated DrawIO diagrams directly in the browser  
⬇️ **Download Support**: Export diagrams as .drawio files  
🔄 **Session Management**: Reset and restart conversations  
🎨 **Corporate Theme**: Professional Azure-inspired color scheme  
📱 **Responsive Design**: Works on desktop and tablet devices

## Technology Stack

- **Angular**: 18.2.11
- **Angular Material**: 20.2.14
- **TypeScript**: Latest
- **SCSS**: For styling
- **RxJS**: For reactive programming

## Getting Started

### Prerequisites

- Node.js 18+ (Note: Node 24 is unsupported by Angular)
- npm or yarn
- Backend server running on `http://localhost:8000`

### Installation

1. Navigate to the frontend directory:
```bash
cd Frontend/archmate-ui
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
ng serve
```

4. Open your browser and navigate to:
```
http://localhost:4200
```

## Project Structure

```
archmate-ui/
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   └── chat/              # Main chat component
│   │   │       ├── chat.component.ts
│   │   │       ├── chat.component.html
│   │   │       └── chat.component.scss
│   │   ├── services/
│   │   │   └── chat.service.ts    # API communication service
│   │   ├── app.ts                 # Root component
│   │   ├── app.config.ts          # App configuration
│   │   └── app.routes.ts          # Routing configuration
│   ├── styles.scss                # Global styles
│   └── index.html                 # Main HTML file
└── package.json
```

## Usage

### Starting a Conversation

1. Type your architecture requirements in the message input
2. Press Enter or click Send
3. The AI assistant will ask clarifying questions
4. Once confirmed, the diagram will be generated

### Example Prompts

- "Create a multi-region web application with frontend, backend, and SQL database"
- "Design a secure architecture with Key Vault and private endpoints"
- "Generate a microservices architecture with API Management and Azure OpenAI"

### Viewing Diagrams

- Generated diagrams appear in the right panel
- Diagrams are rendered using the DrawIO viewer
- Interactive zoom and pan controls available

### Downloading Diagrams

1. Click the "Download" button in the diagram panel
2. File will be saved as `architecture-{timestamp}.drawio`
3. Open with DrawIO desktop or web app for editing

### Resetting Session

- Click the refresh icon in the top toolbar
- Clears conversation history and session ID
- Starts a fresh conversation

## Configuration

### API Endpoint

Update the API URL in `src/app/services/chat.service.ts`:

```typescript
private apiUrl = 'http://localhost:8000';
```

### Theme Customization

Modify colors in `src/styles.scss` and component SCSS files.

## Development

### Generate Components

```bash
ng generate component components/my-component
```

### Generate Services

```bash
ng generate service services/my-service
```

### Build for Production

```bash
ng build --configuration production
```

Output will be in `dist/archmate-ui/browser/`

## Features Breakdown

### Chat Interface

- **Message History**: Scrollable conversation view
- **Auto-scroll**: Automatically scrolls to latest message
- **Loading States**: Shows spinner during API calls
- **Error Handling**: Displays friendly error messages
- **Timestamps**: Shows when each message was sent

### Diagram Viewer

- **Embedded DrawIO**: Uses official DrawIO viewer
- **Interactive**: Zoom, pan, and navigate layers
- **Responsive**: Adapts to panel size
- **No External Dependencies**: Works offline once loaded

### Session Management

- **Persistent Session**: Maintains session across messages
- **Session ID Display**: Shows current session in toolbar
- **Easy Reset**: One-click session restart
- **State Management**: Uses RxJS for reactive state

## Troubleshooting

### CORS Errors

Ensure backend has CORS enabled for `http://localhost:4200`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Port Already in Use

Change the port:
```bash
ng serve --port 4201
```

### Node Version Warning

Angular 18 officially supports Node 18-20. If using Node 24, consider downgrading or ignore the warning.

## Browser Support

- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- IE11: ❌ Not supported

## Future Enhancements

- [ ] Dark mode toggle
- [ ] Export to PNG/SVG
- [ ] Diagram comparison view
- [ ] Architecture templates library
- [ ] Cost estimation display
- [ ] Multi-language support
- [ ] Keyboard shortcuts

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## License

Internal use only - Microsoft SfMC Project
