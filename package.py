import html, json, os, re, socket, sublime, sublime_plugin, threading
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
        self.pending_id = None
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
        extended_region = view.line(region)
        for id, eval in list(self.evals.items()):
            regions = eval.view.get_regions(eval.key)
            if regions and len(regions) >= 1 and extended_region.intersects(regions[0]):
                eval.view.erase_regions(eval.key)
                del self.evals[id]

    def add_eval(self, id, view, region, scope, text, color):
        if region:
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

def format_lookup(info):
    ns = info.get('ns')
    name = info['name']
    file = info.get('file')
    arglists = info.get('arglists')
    forms = info.get('forms')
    doc = info.get('doc')

    body = """<body>
              <style>
                body { padding: 0; margin: 0; }
                a { text-decoration: none; }
                p { margin: 0; padding: .25rem .5rem; }
                .arglists { color: color(var(--foreground) alpha(0.5)); }
              </style>"""

    body += "<p>"
    if file:
        body += f"<a href='{file}'>"
    if ns:
        body += html.escape(ns) + "/"
    body += html.escape(name)
    if file:
        body += f"</a>"
    body += "</p>"

    if arglists:
        body += f'<p class="arglists">{html.escape(arglists.strip("()"))}</p>'

    if forms:
        def format_form(form):
            if isinstance(form, str):
                return form
            else:
                return "(" + " ".join([format_form(x) for x in form]) + ")"
        body += '<p class="arglists">'
        body += html.escape(" ".join([format_form(form) for form in forms]))
        body += "</p>"

    if doc:
        body += "<p>" + html.escape(doc).replace("\n", "<br/>") + "</p>"

    body += "</body>"
    return body

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

    if id and id == conn.pending_id and "status" in msg and "done" in msg["status"]:
        conn.pending_id = None

    if msg.get("id") == 1 and "new-session" in msg:
        conn.session = msg["new-session"]
        with open(os.path.join(sublime.packages_path(), "sublime-clojure-repl", "src", "middleware.clj"), "r") as file:
            conn.send({"op": "load-file",
                       "session": conn.session,
                       "file": file.read(),
                       "id": 2})
        conn.set_status("🌓 Uploading middlewares")
        conn.pending_id = None

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

    elif "info" in msg:
        info = msg["info"]
        view = sublime.active_window().active_view() if sublime.active_window() else None
        if view:
            if info:
                view.show_popup(format_lookup(info), max_width=1024)
            else:
                view.show_popup("Not found")

    elif "status" in msg and "namespace-not-found" in msg["status"]:
        conn.add_eval(id, view, region, 'region.redish', f'Namespace not found: {msg["ns"]}', '#DD1730')

    else:
        pass

def read_loop():
    try:
        conn.pending_id = 1
        conn.send({"op": "clone", "id": conn.pending_id})
        conn.set_status(f"🌒 Cloning session")
        for msg in bencode.decode_file(SocketIO(conn.socket)):
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

def namespace(view, point):
    ns = None
    for region in view.find_by_selector("entity.name"):
        if region.end() <= point:
            begin = region.begin()
            while begin > 0 and view.match_selector(begin - 1, 'meta.parens'):
                begin -= 1
            if re.match(r"\([\s,]*ns[\s,]", view.substr(sublime.Region(begin, region.begin()))):
                ns = view.substr(region)
        else:
            break
    return ns

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

def eval(view, region):
    conn.pending_id = conn.next_id
    conn.next_id += 1
    code = view.substr(region)
    (line, column) = view.rowcol_utf16(region.begin())
    msg = {"op":      "eval",
           "code":    code,
           "ns":      namespace(view, region.begin()) or 'user',
           "line":    line + 1,
           "column":  column + 1,
           "session": conn.session,
           "id":      conn.pending_id,
           "nrepl.middleware.caught/caught":"sublime-clojure-repl.middleware/print-root-trace",
           "nrepl.middleware.print/quota": 300}
    if view.file_name():
        msg["file"] = view.file_name()
    conn.send(msg)
    conn.clear_evals_intersecting(view, region)
    conn.add_eval(conn.pending_id, view, region, 'region.bluish', '...', '#7C9BCE')

def topmost_form(view, point):
    scope = view.scope_name(point)
    if 'source.clojurec ' == scope and point > 0:
        point = point - 1
        scope = view.scope_name(point)
    if 'source.clojurec ' != scope:
        begin = point
        while begin > 0 and view.scope_name(begin - 1) != 'source.clojurec ':
            begin -= 1
        end = point
        while end < view.size() and view.scope_name(end) != 'source.clojurec ':
            end += 1
        return sublime.Region(begin, end)

class EvalTopmostFormCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        point = self.view.sel()[0].begin()
        region = topmost_form(self.view, point)
        if region:
            eval(self.view, region)

    def is_enabled(self):
        return conn.socket != None \
            and conn.session != None \
            and conn.pending_id == None \
            and len(self.view.sel()) == 1

class EvalSelectionCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        region = self.view.sel()[0]
        eval(self.view, region)
        
    def is_enabled(self):
        return conn.socket != None \
            and conn.session != None \
            and conn.pending_id == None \
            and len(self.view.sel()) == 1 \
            and not self.view.sel()[0].empty()

class EvalBufferCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        region = sublime.Region(0, view.size())
        conn.pending_id = conn.next_id
        conn.next_id += 1
        msg = {"op":      "load-file",
               "file":    view.substr(region),
               "session": conn.session,
               "id":      conn.pending_id,
               "nrepl.middleware.caught/caught":"sublime-clojure-repl.middleware/print-root-trace",
               "nrepl.middleware.print/quota": 300}
        if view.file_name():
            path, name = os.path.split(view.file_name())
            msg["file-path"] = path
            msg["file-name"] = name
        else:
            msg["file-name"] = "NO_SOURCE_FILE.cljc"
        conn.send(msg)
        conn.clear_evals_intersecting(view, region)
        conn.add_eval(conn.pending_id, view, region, 'region.bluish', '...', '#7C9BCE')
        
    def is_enabled(self):
        return conn.socket != None \
            and conn.session != None \
            and conn.pending_id == None

class ClearEvalsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        conn.clear_evals_in_view(self.view)

class InterruptEvalCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        conn.send({"op":           "interrupt",
                   "session":      conn.session,
                   "interrupt-id": conn.pending_id})

    def is_enabled(self):
        return conn.socket != None \
            and conn.session != None \
            and conn.pending_id != None

class LookupSymbolCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        region = self.view.sel()[0]
        if region.empty():
            point = region.begin()
            if view.match_selector(point, 'source.symbol.clojure'):
                region = self.view.extract_scope(point)
            elif point > 0 and view.match_selector(point - 1, 'source.symbol.clojure'):
                region = self.view.extract_scope(point - 1)
        if not region.empty():
            conn.send({"op":      "lookup",
                       "sym":     view.substr(region),
                       "session": conn.session,
                       "id":      conn.next_id,
                       "ns":      namespace(view, region.begin()) or 'user'})
            conn.next_id += 1

    def is_enabled(self):
        if conn.socket == None or conn.session == None:
            return False
        view = self.view
        if len(view.sel()) > 1:
            return False
        region = view.sel()[0]
        if not region.empty():
            return True
        point = region.begin()
        if view.match_selector(point, 'source.symbol.clojure'):
            return True
        if point > 0 and view.match_selector(point - 1, 'source.symbol.clojure'):
            return True
        return False

class EventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        conn.refresh_status()

def plugin_loaded():
    connect('localhost', 5555) # FIXME
    # pass

def plugin_unloaded():
    conn.disconnect()
