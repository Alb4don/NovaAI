
  ![novafrontend](https://github.com/user-attachments/assets/d3eaa898-15eb-4d76-8b32-462aca57b692)


# Conversation flow

            User keystroke (Return or Send button)
              │
              ▼
              
        _on_send()              ← runs on main thread
              │
              ├─ Language detection (first message only)
              ├─ Farewell pattern match → graceful exit after 2.2 s delay
              └─ Normal turn:
                     │
                     ├─ _memory.add("user", ...)
                     ├─ _start_thinking()          ← animated indicator
                     └─ threading.Thread(_generate)
                                │
                                ▼
                                
                        OllamaClient.chat()         ← blocks on network I/O
                                │
                                ▼
                                
                        self.after(0, _deliver)     ← back on main thread
                                │
                                ├─ _stop_thinking()
                                ├─ _append_bot(response)
                                └─ _memory.add("assistant", ...)


# Requirements

- Python 3.10+
- Ollama ≥ 0.1.x
- llama3.2:1b model
- Linux or Windows
  
No virtual environment is necessary.

# Setup

On Linux:

      curl -fsSL https://ollama.com/install.sh | sh

- On Windows, download the installer from [ollama](ollama.com/download) and run it.

# Pull the model

      ollama pull llama3.2:1b

- You can confirm it loaded correctly by running a quick smoke test:

      ollama run llama3.2:1b "Answer in one sentence."

# Run the chatbot

      python chatbot.py

- Ollama must be reachable at ***http://localhost:11434*** before you start a session. If it isn't running, Nova will display a descriptive error in the chat area (in the active language) without crashing.

# Troubleshooting

- Connection refused when sending a message, Ollama is not running. Start it with ollama serve in a separate terminal, then send again. Nova recovers, you do not need to restart the application.
- Slow responses On CPU, a 1B parameter model typically takes between 5 and 20 seconds depending on the hardware. This is normal.
- Model not found. Run ollama list to confirm the model name exactly as stored, then update *_OLLAMA_MODEL* to match. Model identifiers are case-sensitive.
- No module named 'tkinter'. Some minimal Linux distributions strip Tkinter from the Python package, install it with sudo *apt install python3-tk* on Debian/Ubuntu or the equivalent for your distribution.

# Extending the project

- Switching to a larger model requires only changing ***_OLLAMA_MODEL*** and pulling the new model with ollama pull. Prompts and memory logic are model-agnostic.
- Adding a third language involves three steps: adding a compiled regex to ***_LANG_DETECT_***, writing a new system prompt entry in ***_SYSTEM_PROMPTS***, and adding the appropriate keys to ***_FAREWELL_PATTERNS***, ***_FAREWELL_MSG***, and ***_GREETING_MSG***.
- Persisting conversation history across sessions can be achieved by serialising ***ConversationMemory._turns*** to JSON on window close and deserialising on startup. The deque structure maps directly to a JSON array of ***{"role": ..., "content": ...} objects.***
- Streaming responses are supported by Ollama's ***/api/chat endpoint when "stream": true is set.*** Adapting OllamaClient.chat to consume the newline-delimited JSON stream and write tokens progressively to the tk.Text widget would require iterating over resp line by line and scheduling each chunk with self.after(0, ...).
