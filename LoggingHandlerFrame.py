import logging
from tkinter import END, Text, ttk

class LoggingHandlerFrame(ttk.LabelFrame):

    class Handler(logging.Handler):
        def __init__(self, widget):
            logging.Handler.__init__(self)
            self.setFormatter(logging.Formatter("%(message)s"))
            self.widget = widget
            self.widget.config(state='disabled')
            self.widget.tag_config("DEBUG", foreground="black")
            self.widget.tag_config("INFO", foreground="green")
            self.widget.tag_config("WARNING", foreground="orange")
            self.widget.tag_config("ERROR", foreground="red")
            self.widget.tag_config("CRITICAL", foreground="red", underline=1)

        def emit(self, record):
            self.widget.config(state='normal')
            self.widget.insert(END, self.format(record) + "\n", record.levelname)
            self.widget.see(END)
            self.widget.config(state='disabled')
            self.widget.update()  # Refresh the widget

    def __init__(self, *args, **kwargs):
        ttk.LabelFrame.__init__(self, *args, **kwargs)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        self.text = Text(self, bd=0, selectbackground=f'#F0F0F0')
        self.text.grid(row=0, column=0, sticky="nsew")

        self.logging_handler = LoggingHandlerFrame.Handler(self.text)

    def clear(self):
        self.text.config(state='normal')
        self.text.delete('1.0', END)
        self.text.config(state='disabled')