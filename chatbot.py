import json
import re
import html
import threading
import urllib.request
import urllib.error
from collections import deque

import tkinter as tk
from tkinter import font as tkfont

_LANG_EN = "en"
_LANG_PT = "pt"

_OLLAMA_URL   = "http://localhost:11434/api/chat"
_OLLAMA_MODEL = "llama3.2:1b"

_SYSTEM_PROMPTS = {
    _LANG_EN: (
        "You are a warm, witty, and genuinely helpful assistant named Nova. "
        "You speak exactly like a thoughtful human friend — casually, naturally, "
        "never robotically. You use contractions, light humour when appropriate, "
        "and short punchy sentences. Never use bullet points or markdown. "
        "Never start a reply with 'I' or your own name. "
        "Keep responses concise unless the user clearly wants depth. "
        "If you don't know something, admit it naturally. "
        "Never reveal that you are an AI model unless directly asked."
    ),
    _LANG_PT: (
        "Você é um assistente chamado Nova — caloroso, espirituoso e genuinamente útil. "
        "Fale exatamente como um amigo humano pensativo: casual, natural, nunca robótico. "
        "Use contrações, humor leve quando apropriado e frases curtas e diretas. "
        "Nunca use listas com marcadores nem markdown. "
        "Nunca comece uma resposta com 'Eu' ou com o seu próprio nome. "
        "Mantenha as respostas concisas, a menos que o usuário queira profundidade. "
        "Se não souber algo, admita de forma natural. "
        "Nunca revele que você é um modelo de IA, a menos que perguntado diretamente."
    ),
}

_FAREWELL_PATTERNS = {
    _LANG_EN: re.compile(
        r"\b(bye|goodbye|see you|farewell|cya|later|quit|exit)\b", re.IGNORECASE
    ),
    _LANG_PT: re.compile(
        r"\b(tchau|adeus|até mais|até logo|xau|falou|sair|fechar)\b", re.IGNORECASE
    ),
}

_FAREWELL_MSG = {
    _LANG_EN: "Take care! It was a genuine pleasure chatting with you. 👋",
    _LANG_PT: "Até mais! Foi um prazer genuíno conversar com você. 👋",
}

_LANG_DETECT_EN = re.compile(
    r"\b(english|en|yes|yeah|sure|i speak english)\b", re.IGNORECASE
)
_LANG_DETECT_PT = re.compile(
    r"\b(português|portugues|pt|sim|claro|brasileiro|falo português|falo portugues)\b",
    re.IGNORECASE,
)

_GREETING_MSG = {
    _LANG_EN: (
        "Hey! Great to meet you. I'm Nova, feel free to ask me anything. "
        "What's on your mind?"
    ),
    _LANG_PT: (
        "Olá! Que bom te conhecer. Sou o Nova, pode me perguntar qualquer coisa. "
        "O que está pensando?"
    ),
}

_THINKING_FRAMES = ["Nova  ·", "Nova · ·", "Nova · · ·"]

_P = {
    "bg":         "#0f1117",
    "surface":    "#1a1d27",
    "accent":     "#7c6af7",
    "accent2":    "#a78bfa",
    "text":       "#e2e8f0",
    "subtext":    "#64748b",
    "border":     "#2e3347",
    "entry_bg":   "#1e2235",
    "btn_bg":     "#7c6af7",
    "btn_active": "#6d5ce6",
    "success":    "#34d399",
}

_MAX_HISTORY = 20


def _sanitise(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"#{1,6}\s?", "", text)
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_language(text: str):
    if _LANG_DETECT_PT.search(text):
        return _LANG_PT
    if _LANG_DETECT_EN.search(text):
        return _LANG_EN
    return None


class ConversationMemory:
    def __init__(self, maxlen: int = _MAX_HISTORY):
        self._turns: deque = deque(maxlen=maxlen)

    def add(self, role: str, content: str):
        self._turns.append({"role": role, "content": content})

    def as_messages(self, lang: str) -> list:
        msgs = [{"role": "system", "content": _SYSTEM_PROMPTS[lang]}]
        msgs.extend(list(self._turns))
        return msgs

    def clear(self):
        self._turns.clear()


class OllamaClient:
    @staticmethod
    def chat(messages: list, timeout: int = 120) -> str:
        payload = json.dumps({
            "model":    _OLLAMA_MODEL,
            "messages": messages,
            "stream":   False,
            "options": {
                "temperature":    0.75,
                "num_predict":    512,
                "repeat_penalty": 1.15,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            _OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        return _sanitise(body["message"]["content"])


class ChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self._lang: str | None = None
        self._memory         = ConversationMemory()
        self._client         = OllamaClient()
        self._busy           = False
        self._think_frame    = 0
        self._think_after_id = None
        self._think_mark: str | None = None

        self.title("Nova Chat")
        self.geometry("800x640")
        self.minsize(540, 480)
        self.configure(bg=_P["bg"])
        self.resizable(True, True)

        self._define_fonts()
        self._build_ui()
        self._post_welcome()

    def _define_fonts(self):
        self._f_body   = tkfont.Font(family="Helvetica", size=11)
        self._f_name   = tkfont.Font(family="Helvetica", size=9,  weight="bold")
        self._f_header = tkfont.Font(family="Georgia",   size=14, weight="bold")
        self._f_sub    = tkfont.Font(family="Helvetica", size=9)
        self._f_status = tkfont.Font(family="Helvetica", size=8)
        self._f_btn    = tkfont.Font(family="Helvetica", size=10, weight="bold")
        self._f_system = tkfont.Font(family="Helvetica", size=9,  slant="italic")

    def _build_ui(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build_header()
        self._build_chat_area()
        self._build_input_bar()
        self._build_status_bar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=_P["surface"], height=58)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        tk.Label(
            hdr, text="◉", fg=_P["success"],
            bg=_P["surface"], font=self._f_header,
        ).grid(row=0, column=0, rowspan=2, padx=(18, 10), pady=8, sticky="ns")

        tk.Label(
            hdr, text="Nova", fg=_P["accent2"],
            bg=_P["surface"], font=self._f_header,
        ).grid(row=0, column=1, sticky="sw", pady=(10, 0))

        tk.Label(
            hdr, text="Llama 3.2 · Local · Offline",
            fg=_P["subtext"], bg=_P["surface"], font=self._f_sub,
        ).grid(row=1, column=1, sticky="nw", pady=(0, 8))

        tk.Frame(self, bg=_P["border"], height=1).grid(
            row=0, column=0, sticky="sew"
        )

    def _build_chat_area(self):
        wrapper = tk.Frame(self, bg=_P["bg"])
        wrapper.grid(row=1, column=0, sticky="nsew")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        self._chat = tk.Text(
            wrapper,
            state="disabled",
            wrap="word",
            font=self._f_body,
            bg=_P["bg"],
            fg=_P["text"],
            relief="flat",
            borderwidth=0,
            padx=20,
            pady=14,
            cursor="arrow",
            spacing1=2,
            spacing3=2,
        )
        self._chat.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(
            wrapper, orient="vertical",
            command=self._chat.yview,
            bg=_P["border"],
            troughcolor=_P["bg"],
            borderwidth=0,
            width=6,
        )
        sb.grid(row=0, column=1, sticky="ns")
        self._chat.configure(yscrollcommand=sb.set)

        self._chat.tag_configure(
            "user_name", foreground=_P["accent2"],
            font=self._f_name, spacing1=16,
        )
        self._chat.tag_configure(
            "user_msg", foreground=_P["text"],
            font=self._f_body,
            lmargin1=14, lmargin2=14, rmargin=80, spacing3=4,
        )
        self._chat.tag_configure(
            "bot_name", foreground=_P["accent"],
            font=self._f_name, spacing1=16,
        )
        self._chat.tag_configure(
            "bot_msg", foreground=_P["text"],
            font=self._f_body,
            lmargin1=14, lmargin2=14, rmargin=80, spacing3=4,
        )
        self._chat.tag_configure(
            "system_msg", foreground=_P["subtext"],
            font=self._f_system, justify="center",
            spacing1=10, spacing3=10,
        )
        self._chat.tag_configure(
            "thinking", foreground=_P["accent"],
            font=self._f_system, spacing1=12, spacing3=4,
        )

    def _build_input_bar(self):
        bar = tk.Frame(self, bg=_P["bg"])
        bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 12))
        bar.columnconfigure(0, weight=1)

        ef = tk.Frame(
            bar, bg=_P["entry_bg"],
            highlightbackground=_P["border"],
            highlightthickness=1,
        )
        ef.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ef.columnconfigure(0, weight=1)

        self._input_var = tk.StringVar()
        self._entry = tk.Entry(
            ef,
            textvariable=self._input_var,
            font=self._f_body,
            bg=_P["entry_bg"],
            fg=_P["text"],
            insertbackground=_P["accent2"],
            relief="flat",
            borderwidth=0,
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=12, pady=9)
        self._entry.bind("<Return>",   self._on_send)
        self._entry.bind("<KP_Enter>", self._on_send)

        self._send_btn = tk.Button(
            bar,
            text="Send",
            font=self._f_btn,
            bg=_P["btn_bg"],
            fg="#ffffff",
            activebackground=_P["btn_active"],
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._on_send,
        )
        self._send_btn.grid(row=0, column=1)
        self._send_btn.bind(
            "<Enter>", lambda e: self._send_btn.configure(bg=_P["btn_active"])
        )
        self._send_btn.bind(
            "<Leave>", lambda e: self._send_btn.configure(bg=_P["btn_bg"])
        )

    def _build_status_bar(self):
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self,
            textvariable=self._status_var,
            bg=_P["bg"], fg=_P["subtext"],
            font=self._f_status, anchor="w",
        ).grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 6))

    def _write(self, text: str, *tags):
        self._chat.configure(state="normal")
        self._chat.insert("end", text, tags)
        self._chat.configure(state="disabled")
        self._chat.see("end")

    def _append_user(self, msg: str):
        label = "You" if self._lang == _LANG_EN else "Você"
        self._write(f"\n{label}\n", "user_name")
        self._write(f"{msg}\n",     "user_msg")

    def _append_bot(self, msg: str):
        self._write("\nNova\n",  "bot_name")
        self._write(f"{msg}\n", "bot_msg")

    def _append_system(self, msg: str):
        self._write(f"\n{msg}\n", "system_msg")

    def _start_thinking(self):
        self._think_frame = 0
        self._chat.configure(state="normal")
        self._chat.insert("end", "\n", "bot_name")
        self._think_mark = self._chat.index("end - 1 char")
        self._chat.insert("end", _THINKING_FRAMES[0] + "\n", "thinking")
        self._chat.configure(state="disabled")
        self._chat.see("end")
        self._tick_thinking()

    def _tick_thinking(self):
        if not self._busy:
            return
        self._think_frame = (self._think_frame + 1) % len(_THINKING_FRAMES)
        self._chat.configure(state="normal")
        s = self._think_mark
        e = self._chat.index(f"{s} lineend + 1 char")
        self._chat.delete(s, e)
        self._chat.insert(s, _THINKING_FRAMES[self._think_frame] + "\n", "thinking")
        self._chat.configure(state="disabled")
        self._chat.see("end")
        self._think_after_id = self.after(450, self._tick_thinking)

    def _stop_thinking(self):
        if self._think_after_id:
            self.after_cancel(self._think_after_id)
            self._think_after_id = None
        if self._think_mark:
            self._chat.configure(state="normal")
            s    = self._think_mark
            e    = self._chat.index(f"{s} lineend + 1 char")
            prev = self._chat.index(f"{s} - 1 char")
            self._chat.delete(prev, e)
            self._chat.configure(state="disabled")
            self._think_mark = None

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self._entry.configure(state=state)
        self._send_btn.configure(state=state)

    def _post_welcome(self):
        self._append_system("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self._append_bot(
            "Hey there! Quick question before we dive in do you prefer to chat in "
            "English or Portuguese? / Oi! Uma pergunta rápida antes de começarmos — "
            "você prefere conversar em Inglês ou Português?"
        )
        self._entry.focus_set()

    def _on_send(self, _event=None):
        raw = self._input_var.get().strip()
        if not raw or self._busy:
            return

        user_input = html.unescape(raw[:2000])
        self._input_var.set("")

        if self._lang is None:
            detected = _detect_language(user_input)
            if detected is None:
                self._append_bot(
                    "Just to confirm, English or Português? / "
                    "Só para confirmar, Inglês ou Português?"
                )
                return
            self._lang = detected
            self._append_user(user_input)
            self._memory.add("user", user_input)
            greeting = _GREETING_MSG[self._lang]
            self._memory.add("assistant", greeting)
            self._append_bot(greeting)
            return

        self._append_user(user_input)

        if _FAREWELL_PATTERNS[self._lang].search(user_input):
            farewell = _FAREWELL_MSG[self._lang]
            self._memory.add("user", user_input)
            self._memory.add("assistant", farewell)
            self._append_bot(farewell)
            self._append_system("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self.after(2200, self.destroy)
            return

        label = "Thinking" if self._lang == _LANG_EN else "Pensando"
        self._status_var.set(f"{label}...")
        self._set_busy(True)
        self._start_thinking()

        threading.Thread(
            target=self._generate,
            args=(user_input,),
            daemon=True,
        ).start()

    def _generate(self, user_input: str):
        try:
            self._memory.add("user", user_input)
            messages = self._memory.as_messages(self._lang)
            response = self._client.chat(messages)
            self._memory.add("assistant", response)
            self.after(0, self._deliver, response)
        except urllib.error.URLError:
            err = (
                "Can't reach Ollama — make sure it's running "
                "(ollama serve) and try again."
                if self._lang == _LANG_EN
                else "Não consigo alcançar o Ollama, certifique-se de que está "
                     "em execução (ollama serve) e tente novamente."
            )
            self.after(0, self._deliver, err)
        except Exception as exc:
            err = (
                f"Something went wrong — {exc}"
                if self._lang == _LANG_EN
                else f"Algo deu errado — {exc}"
            )
            self.after(0, self._deliver, err)

    def _deliver(self, response: str):
        self._stop_thinking()
        self._append_bot(response)
        self._status_var.set("")
        self._set_busy(False)
        self._entry.focus_set()

if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
