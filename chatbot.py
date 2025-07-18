
import customtkinter as ctk
from groq import Groq
import threading
import time
from queue import Queue
import re

class GroqChatApp:
    def __init__(self, root):
        self.root = root
        self.client = Groq(api_key='insert_api_key_here')
        self.stop_stream = False
        self.message_queue = Queue()
        self.is_bot_responding = False
        self.bold_pattern = re.compile(r'\*\*(.*?)\*\*')
        self.setup_ui()
        self.check_queue()
        self.username = ""
        self.get_username()

    def setup_ui(self):
        self.root.title("Groq Chatbot")
        self.root.geometry("1000x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.chat_frame = ctk.CTkFrame(self.main_frame)
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=(5, 0))
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_frame.grid_rowconfigure(0, weight=1)

        self.chat_display = ctk.CTkTextbox(
            self.chat_frame,
            wrap="word",
            state="disabled",
            activate_scrollbars=True
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew")

        input_frame = ctk.CTkFrame(self.main_frame)
        input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.user_input = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type your message here..."
        )
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.user_input.bind("<Return>", lambda e: self.send_message())

        button_frame = ctk.CTkFrame(input_frame)
        button_frame.pack(side="left")

        self.send_button = ctk.CTkButton(
            button_frame,
            text="Send",
            command=self.send_message,
            width=80
        )
        self.send_button.pack(side="left", padx=(0, 5))

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Stop",
            command=self.stop_generation,
            fg_color="#d9534f",
            hover_color="#c9302c",
            state="disabled",
            width=80
        )
        self.stop_button.pack(side="left")

        self.status_bar = ctk.CTkLabel(
            self.main_frame,
            text="Ready",
            anchor="w"
        )
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.init_text_tags()

    def init_text_tags(self):
        self.chat_display.tag_config("user_username", foreground="#4fc3f7")
        self.chat_display.tag_config("bot_username", foreground="#81c784")
        self.chat_display.tag_config("system_username", foreground="#ba68c8")
        self.chat_display.tag_config("normal_text", foreground="#e0e0e0")
        self.chat_display.tag_config("bold_text", foreground="#ffffff")


    def get_username(self):
        dialog = ctk.CTkInputDialog(title="Username", text="Enter your username:")
        username = dialog.get_input()
        while not username or not username.strip():
            dialog = ctk.CTkInputDialog(title="Username", text="Please enter a valid username:")
            username = dialog.get_input()
        self.username = username
        self.add_to_chat("System", f"Chat session started with {self.username}. Type 'quit' to exit")
        self.update_status("Ready")

    def send_message(self):
        if self.is_bot_responding:
            return
        message = self.user_input.get().strip()
        if not message:
            return
        self.user_input.delete(0, "end")
        self.add_to_chat(self.username, message)

        if message.lower() in ['quit', 'exit', 'bye']:
            self.add_to_chat("Bot", f"Goodbye, {self.username}! Have a great day!")
            self.root.after(2000, self.root.destroy)
            return

        self.is_bot_responding = True
        self.send_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.update_status("Generating response...")

        threading.Thread(
            target=self.generate_response,
            args=(message,),
            daemon=True
        ).start()

    def generate_response(self, prompt):
        self.stop_stream = False
        try:
            stream = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192",
                temperature=0.7,
                stream=True
            )

            self.message_queue.put(("bot_prefix",))

            formatting = None
            buffer = ""

            for chunk in stream:
                if self.stop_stream:
                    self.message_queue.put(("add_text", "\n[Response stopped]"))
                    break

                content = chunk.choices[0].delta.content
                if not content:
                    continue

                for char in content:
                    buffer += char

                    # Detect ** toggle
                    if buffer.endswith("**"):
                        if formatting == "bold_text":
                            formatting = None
                        else:
                            formatting = "bold_text"
                        buffer = buffer[:-2]
                        if buffer:
                            self.message_queue.put(("add_text" if formatting is None else "add_bold_text", buffer))
                            buffer = ""
                        continue

                    # Flush buffer at word boundaries
                    if char in [' ', '\n', '.', ',', '!', '?', ';', ':']:
                        self.message_queue.put(("add_text" if formatting is None else "add_bold_text", buffer))
                        buffer = ""

                    time.sleep(0.01)

            if buffer:
                self.message_queue.put(("add_text" if formatting is None else "add_bold_text", buffer))

        except Exception as e:
            self.message_queue.put(("add_text", f"\nError: {str(e)}"))

        self.message_queue.put(("end_response",))

    def stop_generation(self):
        self.stop_stream = True
        self.stop_button.configure(state="disabled")
        self.update_status("Stopping generation...")

    def add_to_chat(self, sender, message):
        self.chat_display.configure(state="normal")
        if sender == "Bot":
            self.chat_display.insert("end", "Bot: ", "bot_username")
        elif sender == "System":
            self.chat_display.insert("end", "System: ", "system_username")
        else:
            self.chat_display.insert("end", f"{sender}: ", "user_username")

        parts = self.bold_pattern.split(message)
        for i, part in enumerate(parts):
            tag = "bold_text" if i % 2 == 1 else "normal_text"
            self.chat_display.insert("end", part, tag)

        self.chat_display.insert("end", "\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def update_status(self, message):
        self.status_bar.configure(text=message)

    def check_queue(self):
        while not self.message_queue.empty():
            item = self.message_queue.get()

            if item[0] == "bot_prefix":
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", "Bot: ", "bot_username")
                self.chat_display.configure(state="disabled")
                self.chat_display.see("end")

            elif item[0] == "add_text":
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", item[1], "normal_text")
                self.chat_display.configure(state="disabled")
                self.chat_display.see("end")

            elif item[0] == "add_bold_text":
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", item[1], "bold_text")
                self.chat_display.configure(state="disabled")
                self.chat_display.see("end")

            elif item[0] == "end_response":
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", "\n\n")
                self.chat_display.configure(state="disabled")
                self.chat_display.see("end")
                self.is_bot_responding = False
                self.send_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.update_status("Ready")

        self.root.after(50, self.check_queue)

if __name__ == "__main__":
    root = ctk.CTk()
    app = GroqChatApp(root)
    root.mainloop()
