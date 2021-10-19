import json, os, re, socket, sublime, sublime_plugin, threading
from collections import defaultdict
from dataclasses import dataclass
from .src import bencode

ns = 'sublime-clojure-repl'

@dataclass(eq=True, frozen=True)
class Eval:
    key: str
    view: sublime.View
    scope: str

class Connection:
    def __init__(self):
        self.host = 'localhost'
        self.port = 5555
        self.evals: dict[int, Eval] = {}
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
        self.next_id = 10
        self.session = None
        self.set_status('🌑 Offline')
        self.clear_evals()

    def clear_evals(self):
        for id, eval in self.evals.items():
            eval.view.erase_regions(eval.key)
        self.evals.clear()

    def clear_evals_in_view(self, view):
        for id, eval in list(self.evals.items()):
            if eval.view == view and eval.scope != 'region.bluish':
                eval.view.erase_regions(eval.key)
                del self.evals[id]

    def clear_evals_intersecting(self, view, region):
        for id, eval in list(self.evals.items()):
            regions = eval.view.get_regions(eval.key)
            if regions and len(regions) >= 1 and region.intersects(regions[0]):
                eval.view.erase_regions(eval.key)
                del self.evals[id]

    def add_eval(self, id, view, region, scope, text, color):
        key = f"{ns}.eval-{id}"
        view.add_regions(key, [region], scope, '', sublime.DRAW_NO_FILL, [text], color)
        self.evals[id] = Eval(key, view, scope)

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

    id = None
    view = None
    region = None
    if "id" in msg:
        id = msg["id"]
        if id in conn.evals:
            eval = conn.evals[id]
            view = eval.view
            regions = view.get_regions(eval.key)
            if regions and len(regions) >= 1:
                region = regions[0]

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

    elif "value" in msg and id and view and region:
        value = msg["value"]
        conn.add_eval(id, view, region, 'region.greenish', value, '#7CCE9B')

    elif "sublime-clojure-repl.middleware/root-ex-class" in msg and "sublime-clojure-repl.middleware/root-ex-msg" in msg:
        text = msg["sublime-clojure-repl.middleware/root-ex-class"] + ": " + msg["sublime-clojure-repl.middleware/root-ex-msg"]
        if "sublime-clojure-repl.middleware/root-ex-data" in msg:
            text += " " + msg["sublime-clojure-repl.middleware/root-ex-data"]
        conn.add_eval(id, view, region, 'region.redish', text, '#DD1730')

    elif "root-ex" in msg:
        conn.add_eval(id, view, region, 'region.redish', msg["root-ex"], '#DD1730')

    else:
        pass

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
        view = self.view
        id = conn.next_id
        conn.next_id += 1
        region = view.sel()[0]
        code = view.substr(region) # TODO multiple selections?
        conn.send({"op":      "eval",
                   "code":    code,
                   "session": conn.session,
                   "id":      id,
                   "nrepl.middleware.caught/caught":"sublime-clojure-repl.middleware/print-root-trace",
                   "nrepl.middleware.print/quota": 100})
        conn.clear_evals_intersecting(view, region)
        conn.add_eval(id, view, region, 'region.bluish', '...', '#7C9BCE')
        
    def is_enabled(self):
        return conn.socket != None and conn.session != None

class ClearEvalsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        conn.clear_evals_in_view(self.view)

class EventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        conn.refresh_status()

def plugin_loaded():
    connect('localhost', 5555)
    pass

def plugin_unloaded():
    conn.disconnect()
