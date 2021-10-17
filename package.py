import json, os, re, socket, sublime, sublime_plugin, threading
from .src import bencode

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

    def send(self, msg):
        print(">>>", msg)
        self.socket.sendall(bencode.encode(msg).encode())

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

class SocketIO:
    def __init__(self, socket):
        self.socket = socket
        self.buffer = None
        self.pos = -1

    def read(self, n):
        if not self.buffer or self.pos >= len(self.buffer):
            self.buffer = self.socket.recv(4096)
            # print("<<<", self.buffer.decode())
            self.pos = 0
        begin = self.pos
        end = min(begin + n, len(self.buffer))
        self.pos = end
        return self.buffer[begin:end]

def handle_msg(msg):
    print("<<<", msg)
    if "value" in msg:
        value = msg["value"]
        view = sublime.active_window().active_view()
        # view.show_popup(value, sublime.HIDE_ON_CHARACTER_EVENT)
        view.add_regions('clojure-repl', view.sel(), 'region.greenish', '',  sublime.DRAW_NO_FILL, [value], '#7CCE9B')
        # view.erase_phantoms("clojure-repl")
        # region = sublime.Region(view.sel()[0].end(), view.sel()[0].end())
        # view.add_phantom("clojure-repl", region, f"<dic class='success'>{value}</div>", sublime.LAYOUT_INLINE)
    elif "sublime.clojure.repl/root-ex-class" in msg and "sublime.clojure.repl/root-ex-msg" in msg:
        text = msg["sublime.clojure.repl/root-ex-class"] + ": " + msg["sublime.clojure.repl/root-ex-msg"]
        if "sublime.clojure.repl/root-ex-data" in msg:
            text += " " + msg["sublime.clojure.repl/root-ex-data"]
        view = sublime.active_window().active_view()
        view.add_regions('clojure-repl', view.sel(), 'region.redish', '',  sublime.DRAW_NO_FILL, [text], '#DD1730')
    elif "root-ex" in msg:
        text = msg["root-ex"]
        view = sublime.active_window().active_view()
        view.add_regions('clojure-repl', view.sel(), 'region.redish', '',  sublime.DRAW_NO_FILL, [text], '#DD1730')
    elif "out" in msg or "err" in msg:
        text = msg.get("out") or msg.get("err")
        print(text, end="")
    else:
        pass
        # print("Unknown message:", msg)

def read_loop(read_stream):
    try:
        for msg in read_stream:
            handle_msg(msg)
    except OSError:
        pass
    disconnect()

def connect(host, port):
    conn.host = host
    conn.port = port
    try:
        conn.socket = socket.create_connection((host, port))
        read_stream = bencode.decode_file(SocketIO(conn.socket))

        with open(os.path.join(sublime.packages_path(), "sublime-clojure-repl", "src", "middlewares.clj"), "r") as file:
            middlewares = file.read()

        conn.send({"op": "clone", "id": 1})
        resp = next(read_stream)
        print("<<<", resp)
        session = resp["new-session"]

        conn.send({"op": "load-file",
                   "session": session,
                   "file": middlewares,
                   "id": 2})
        print("<<<", next(read_stream))
        print("<<<", next(read_stream))

        conn.send({"op": "add-middleware",
                   "middleware": ["sublime.clojure.repl/wrap-errors"],
                   "extra-namespaces": ["sublime.clojure.repl"],
                   "session": session,
                   "id": 3})
        print("<<<", next(read_stream))

        # conn.send({"op": "ls-middleware",
        #            "session": session,
        #            "id": 4})
        # resp = next(read_stream)
        # print("<<<", resp)
        # for m in resp["middleware"]:
        #     print("  ", m)

        conn.reader = threading.Thread(daemon=True, target=read_loop, args=(read_stream,))
        conn.reader.start()
        
        if sublime.active_window() and sublime.active_window().active_view():
            conn.update_status(sublime.active_window().active_view())
        sublime.status_message(f"🔌 Just connected to {host}:{port}")
    except Exception as e:
        print(e)
        conn.socket = None
        sublime.status_message(f"❌ Failed to connect to {host}:{port}")

class ConnectCommand(sublime_plugin.ApplicationCommand):
    def run(self, host_port):
        host, port = host_port.strip().split(':')
        port = int(port)
        connect(host, port)

    def input(self, args):
        return HostPortInputHandler()

    def is_enabled(self):
        return conn.socket == None

def disconnect():
    if conn.socket:
        socket = conn.socket
        conn.socket = None
        conn.reader = None
        socket.close()
        if sublime.active_window() and sublime.active_window().active_view():
            conn.update_status(sublime.active_window().active_view())
        sublime.status_message(f"🙅 Disconnected from {conn.host}:{conn.port}")    

class DisconnectCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        disconnect()

    def is_enabled(self):
        return conn.socket != None

class EvalSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        code = self.view.substr(self.view.sel()[0])
        conn.send({"op": "eval",
                   "code": code,
                   # "nrepl.middleware.caught/caught": "sublime.clojure.repl/print-throwable",
                   # "nrepl.middleware.caught/print?": "true",
                   "nrepl.middleware.print/quota": 100})

    def is_enabled(self):
        return conn.socket != None

class EventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        conn.update_status(view)

def plugin_loaded():
    connect('localhost', 5555)
    pass

def plugin_unloaded():
    disconnect()
