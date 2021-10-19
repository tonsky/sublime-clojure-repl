import json, os, re, socket, sublime, sublime_plugin, threading
from collections import defaultdict
from dataclasses import dataclass
from .src import bencode

ns = 'sublime-clojure-repl'

@dataclass(eq=True, frozen=True)
class Region:
    id: int
    begin: int
    end: int

class Connection:
    def __init__(self):
        self.host = 'localhost'
        self.port = 5555
        self.regions: dict[sublime.View, list[Region]] = defaultdict(list)
        self.reset()

    def set_status(self, status):
        self.status = status
        self.refresh_status()

    def refresh_status(self):
        if sublime.active_window():
            view = sublime.active_window().active_view()
            if view:
                view.set_status(ns, self.status)

    def send(self, msg):
        print(">>>", msg)
        self.socket.sendall(bencode.encode(msg).encode())

    def reset(self):
        self.socket = None
        self.reader = None
        # TODO remove regions
        self.next_id = 10
        self.session = None
        self.set_status('🌑 Offline')

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.reset()            

conn = Connection()

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
    if msg.get("id") == 1 and "new-session" in msg:
        conn.session = msg["new-session"]
        with open(os.path.join(sublime.packages_path(), "sublime-clojure-repl", "src", "middleware.clj"), "r") as file:
            conn.send({"op": "load-file",
                       "session": conn.session,
                       "file": file.read(),
                       "id": 2})
        conn.set_status("🌓 Uploading middlewares")
    elif msg.get("id") == 2 and msg.get("status") == ["done"]:
        conn.send({"op":               "add-middleware",
                   "middleware":       ["sublime-clojure-repl.middleware/wrap-errors",
                                        "sublime-clojure-repl.middleware/wrap-output"],
                   "extra-namespaces": ["sublime-clojure-repl.middleware"],
                   "session":          conn.session,
                   "id":               3})
        conn.set_status("🌔 Adding middlewares")
    elif msg.get("id") == 3 and msg.get("status") == ["done"]:
        # conn.send({"op": "ls-middleware",
        #            "session": session,
        #            "id": 4})
        conn.set_status(f"🌕 {conn.host}:{conn.port}")

    elif "value" in msg:
        value = msg["value"]
        view = sublime.active_window().active_view()
        # view.show_popup(value, sublime.HIDE_ON_CHARACTER_EVENT)
        view.add_regions('clojure-repl', view.sel(), 'region.greenish', '',  sublime.DRAW_NO_FILL, [value], '#7CCE9B')
        # view.erase_phantoms("clojure-repl")
        # region = sublime.Region(view.sel()[0].end(), view.sel()[0].end())
        # view.add_phantom("clojure-repl", region, f"<dic class='success'>{value}</div>", sublime.LAYOUT_INLINE)
    elif "sublime-clojure-repl.middleware/root-ex-class" in msg and "sublime-clojure-repl.middleware/root-ex-msg" in msg:
        text = msg["sublime-clojure-repl.middleware/root-ex-class"] + ": " + msg["sublime-clojure-repl.middleware/root-ex-msg"]
        if "sublime-clojure-repl.middleware/root-ex-data" in msg:
            text += " " + msg["sublime-clojure-repl.middleware/root-ex-data"]
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

def read_loop():
    try:
        conn.send({"op": "clone", "id": 1})
        conn.set_status(f"🌒 Cloning session")

        read_stream = bencode.decode_file(SocketIO(conn.socket))
        for msg in read_stream:
            handle_msg(msg)
    except OSError:
        pass
    conn.disconnect()

def connect(host, port):
    conn.host = host
    conn.port = port
    try:
        conn.socket = socket.create_connection((host, port))
        conn.reader = threading.Thread(daemon=True, target=read_loop)
        conn.reader.start()
    except Exception as e:
        print(e)
        conn.socket = None
        conn.set_status(f"🌑 {host}:{port}")

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

class ConnectCommand(sublime_plugin.ApplicationCommand):
    def run(self, host_port):
        host, port = host_port.strip().split(':')
        port = int(port)
        connect(host, port)

    def input(self, args):
        return HostPortInputHandler()

    def is_enabled(self):
        return conn.socket == None

class DisconnectCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        conn.disconnect()

    def is_enabled(self):
        return conn.socket != None

class EvalSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        code = self.view.substr(self.view.sel()[0])
        conn.send({"op": "eval",
                   "code": code,
                   "nrepl.middleware.caught/caught":"sublime-clojure-repl.middleware/print-root-trace",
                   "nrepl.middleware.print/quota": 100})

    def is_enabled(self):
        return conn.socket != None

class EventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        conn.refresh_status()

def plugin_loaded():
    connect('localhost', 5555)
    pass

def plugin_unloaded():
    conn.disconnect()
