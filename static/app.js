/** Hermes Web Interface - Application Logic */

let currentStreamAbort = null;
let currentMode = 'oneshot';

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    await checkHealth();
    setupInputHandlers();
});

// Health check
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        const footerHermes = document.getElementById('footer-hermes');
        
        if (data.status === 'healthy') {
            statusDot.className = 'status-dot healthy';
            statusText.textContent = 'Connected';
            footerHermes.textContent = `Hermes: ${data.hermes}`;
        } else {
            statusDot.className = 'status-dot unhealthy';
            statusText.textContent = 'Error';
        }
    } catch (error) {
        console.error('Health check failed:', error);
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        statusDot.className = 'status-dot unhealthy';
        statusText.textContent = 'Offline';
        footerHermes.textContent = 'Hermes: Offline';
    }
}

// Switch mode
function switchMode(mode) {
    currentMode = mode;
    
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    document.querySelectorAll('.mode-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`${mode}-mode`).classList.add('active');
    
    if (mode === 'info') {
        loadInfo();
    }
}

// One-shot execution
async function executeOneshot() {
    const prompt = document.getElementById('prompt-input').value.trim();
    if (!prompt) return;
    
    const outputEl = document.getElementById('oneshot-output');
    outputEl.innerHTML = '<div class="loading"></div>';
    
    try {
        const response = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });
        
        const data = await response.json();
        
        let html = '';
        if (data.stdout) {
            html += `<div class="msg-output">${escapeHtml(data.stdout)}</div>`;
        }
        if (data.stderr) {
            html += `<div class="msg-error">${escapeHtml(data.stderr)}</div>`;
        }
        html += `<div class="msg-info" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-color);">Exit code: ${data.exit_code} • Prompt: ${escapeHtml(data.prompt)}</div>`;
        
        outputEl.innerHTML = html;
    } catch (error) {
        outputEl.innerHTML = `<pre class="msg-error">Failed to execute: ${error.message}</pre>`;
    }
}

// Stream execution
async function executeStream() {
    const prompt = document.getElementById('stream-prompt').value.trim();
    if (!prompt) return;
    
    // Abort any existing stream
    if (currentStreamAbort) {
        currentStreamAbort.abort();
    }
    
    const outputEl = document.getElementById('stream-output');
    const streamBtn = document.getElementById('stream-btn');
    const stopBtn = document.getElementById('stop-stream-btn');
    const statusEl = document.getElementById('stream-status');
    
    outputEl.innerHTML = '';
    streamBtn.style.display = 'none';
    stopBtn.style.display = '';
    statusEl.textContent = 'Connecting...';
    statusEl.className = 'stream-status streaming';
    
    const controller = new AbortController();
    currentStreamAbort = controller;
    
    try {
        const response = await fetch('/api/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
            signal: controller.signal
        });
        
        statusEl.textContent = 'Streaming...';
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // Process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamMessage(data, outputEl);
                    } catch (e) {
                        // Skip malformed data
                    }
                }
            }
        }
        
        // Process remaining buffer
        if (buffer.startsWith('data: ')) {
            try {
                const data = JSON.parse(buffer.slice(6));
                handleStreamMessage(data, outputEl);
            } catch (e) {}
        }
        
        statusEl.textContent = 'Done';
        statusEl.className = 'stream-status done';
    } catch (error) {
        if (error.name === 'AbortError') {
            statusEl.textContent = 'Stopped';
            statusEl.className = 'stream-status stopped';
        } else {
            statusEl.textContent = 'Error';
            statusEl.className = 'stream-status error';
            appendOutput(outputEl, `<span class="msg-error">Stream error: ${escapeHtml(error.message)}</span>`);
        }
    } finally {
        streamBtn.style.display = '';
        stopBtn.style.display = 'none';
        currentStreamAbort = null;
    }
}

// Handle stream messages
function handleStreamMessage(data, outputEl) {
    switch (data.type) {
        case 'chunk':
            appendOutput(outputEl, `<span class="msg-output">${escapeHtml(data.data)}</span>`);
            break;
        case 'status':
            if (data.status === 'error') {
                appendOutput(outputEl, `<span class="msg-error">[Process exited with code ${data.exit_code}]</span>`);
            }
            break;
        case 'error':
            appendOutput(outputEl, `<span class="msg-error">${escapeHtml(data.message)}</span>`);
            break;
    }
}

// Stop stream
function stopStream() {
    if (currentStreamAbort) {
        currentStreamAbort.abort();
    }
}

// Load Hermes info
async function loadInfo() {
    const outputEl = document.getElementById('info-output');
    outputEl.innerHTML = '<div class="loading"></div>';
    
    try {
        const response = await fetch('/api/info');
        const data = await response.json();
        
        let html = '';
        
        if (data.version) {
            html += `<div class="msg-info"><strong>Version:</strong> ${escapeHtml(data.version)}</div>`;
        }
        if (data.commands && data.commands.length > 0) {
            html += `<div style="margin-top: 16px;"><strong>Available Commands:</strong></div>`;
            html += `<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;">`;
            for (const cmd of data.commands.slice(0, 50)) {
                html += `<span class="cmd-badge">${escapeHtml(cmd)}</span>`;
            }
            html += `</div>`;
        }
        
        if (!html) {
            html = '<div class="msg-error">No information available</div>';
        }
        
        outputEl.innerHTML = html;
    } catch (error) {
        outputEl.innerHTML = `<pre class="msg-error">Failed to load info: ${error.message}</pre>`;
    }
}

// Clear output
function clearOutput(elementId) {
    document.getElementById(elementId).innerHTML = '<div class="welcome-message"><p>Cleared</p></div>';
}

// Append to output
function appendOutput(element, html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    element.appendChild(div.firstElementChild);
    element.scrollTop = element.scrollHeight;
}

// Setup input handlers
function setupInputHandlers() {
    const oneshotInput = document.getElementById('prompt-input');
    const streamInput = document.getElementById('stream-prompt');
    
    // One-shot: Enter to submit (Shift+Enter for newline)
    oneshotInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeOneshot();
        }
    });
    
    // Stream: Enter to submit (Shift+Enter for newline)
    streamInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeStream();
        }
    });
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}