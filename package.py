import re, socket, sublime, sublime_plugin, threading
from .src import edn

class Connection:
    def __init__(self):
        self.socket = None
        self.host = 'localhost'
        self.port = 5555
        self.reader = None

    def __str__(self):
        if self.socket:
            return f'Connected to {self.host}:{self.port}'
        else:
            return f'Not connected, last {self.host}:{self.port}'

    def update_status(self, view):
        if view:
            if self.socket:
                view.set_status('clojure-repl', f"🔌 {self.host}:{self.port}")
            else:
                view.erase_status('clojure-repl')

conn = Connection()

class HostPortInputHandler(sublime_plugin.TextInputHandler):
    def placeholder(self):
        return "host:port"

    def initial_text(self):
        if conn.host and conn.port:
            return f'{conn.host}:{conn.port}'

    def preview(self, text):
        if not self.validate(text):
            return "Invalid, expected <host>:<port>"

    def validate(self, text):
        text = text.strip()
        if not re.fullmatch(r'[a-zA-Z0-9\.]+:\d{1,5}', text):
            return False
        host, port = text.split(':')
        port = int(port)
        return 0 <= port and port <= 65536

class PortInputHandler(sublime_plugin.TextInputHandler):
    def placeholder(self):
        return "e.g. 55555"

    def initial_text(self):
        if conn.port:
            return str(conn.port)

    def preview(self, text):
        if not self.validate(text):
            return "Invalid port, expected 0..65536"

    def validate(self, text):
        text = text.strip()
        if not re.fullmatch(r'\d+', text):
            return False
        port = int(text)
        return 0 <= port and port <= 65536

# class SocketIO:
#     def __init__(self, socket):
#         self.socket = socket

def read_loop(socket):
    try:
        while msg := socket.recv(4096):
            parsed = edn.read(msg.decode())
            tag = parsed[edn.Keyword("tag")]
            if tag == edn.Keyword("ret"):
                val = parsed[edn.Keyword("val")]
                print(val)
                view = sublime.active_window().active_view()
                # view.show_popup(val, sublime.HIDE_ON_CHARACTER_EVENT)
                view.add_regions('clojure-repl', view.sel(), 'region.greenish', '',  sublime.DRAW_NO_FILL, [val], '#7CCE9B')
            elif tag == edn.Keyword("out"):
                val = parsed[edn.Keyword("val")]
                print(val, end='')
            else:
                print("Unknown tag:", tag, "in", msg)
    finally:
        print("Socket closed")

class ConnectCommand(sublime_plugin.ApplicationCommand):
    def run(self, host_port):
        host_port = host_port.strip()
        host, port = host_port.split(':')
        port = int(port)
        conn.host = host
        conn.port = port
        # sublime.status_message(f"⏳ Connecting to {host}:{port}")
        try:
            conn.socket = socket.create_connection((host, port))
            if sublime.active_window() and sublime.active_window().active_view():
                conn.update_status(sublime.active_window().active_view())
        except OSError as msg:
            conn.socket = None
            sublime.status_message(f"❌ Failed to connect to {host}:{port}")

        conn.reader = threading.Thread(daemon=True, target=read_loop, args=(conn.socket,))
        conn.reader.start()

    def input(self, args):
        return HostPortInputHandler()

    def is_enabled(self):
        return conn.socket == None

class ConnectLocalhostCommand(sublime_plugin.ApplicationCommand):
    def run(self, port):
        sublime.run_command('connect', {'host_port': f'localhost:{port}'})

    def input(self, args):
        return PortInputHandler()

    def is_enabled(self):
        return conn.socket == None

class DisconnectCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        conn.socket.close()
        conn.socket = None
        conn.reader = None
        if sublime.active_window() and sublime.active_window().active_view():
            conn.update_status(sublime.active_window().active_view())
        # sublime.status_message(f"🙅 Disconnected from {conn.host}:{conn.port}")    

    def is_enabled(self):
        return conn.socket != None

class EvalSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        text = self.view.substr(self.view.sel()[0])
        conn.socket.sendall(text.encode())

    def is_enabled(self):
        return conn.socket != None

class EventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        conn.update_status(view)

# (+ 1 2)
# (println "123")
# sublime.run_command('connect_localhost', {'port': f'5555'})