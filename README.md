# Basic Clojure REPL for Sublime Text

Goals:

- Decomplected: just REPL, nothing more
- Compact: Display code evaluation results inline
- Connect over network: no requirements on project structure

## Status

In development.

- [x] Command: Connect to nREPL
- [x] Parse bencode
- [x] Command: Disconnect
- [x] Command: Reconnect
- [x] Detect socket close
- [x] Redirect stdout & stderr to System.out / System.err
- [x] Middleware for error info
- [x] Print stack trace to stderr
- [x] Use nREPL sessions & ids
- [x] Keep multiple annotations on screen
- [x] Command: Clear annotations
- [x] Pending evaluation annotation
- [x] Identify namespace of a file
- [x] Command: Interrupt evaluation
- [x] Send file name and position with eval
- [x] Command: Evaluate top-level form under cursor
- [x] Command: Evaluate buffer
- [x] Command: arglist and docstring for symbol under cursor
- [x] Remove results when region is modified
- [x] Display full stacktrace in editor
- [x] Detect and highlight error position when evaluating a buffer
- [x] Parallel evaluation
- [x] Handle eval comments
- [x] Allow conditional reads in eval_buffer
- [x] Eval top-level non-bracketed forms (strings, symbols, regexes)
- [x] Handle namespace-not-found
- [x] Handle nrepl.middleware.print/truncated-keys
- [ ] Use TextChangeListener to invalidate regions
- [ ] Handle multiple results returned from multiple forms at once
- [x] Eval second topmost form inside (comment)
- [x] Clear previous evals on the same line
- [ ] Clean up formatting of Clojure docstrings
- [ ] Better formatter for exceptions
- [ ] Animated progress indicator
- [ ] Option to choose between Phantoms and Region Annotations
- [ ] Option to clone session before eval
- [ ] Match editor line height in lookup popup

Issues:

- [ ] When evaling form, source file name gets lost in stacktraces
- [ ] Eval top-level custom reader tags and stuff with meta
- [x] Clean up evals on view close
- [ ] Line numbers in stacktrace seems to be 0-based

Productize:

- [ ] Include syntax highlighting into the package
- [ ] Move colors into color scheme
- [ ] Figure out minimal Sublime Text version
- [ ] Design icon
- [ ] Update Readme
- [ ] Publish a package
- [ ] Blog post

## Motivation

### Differences from Tutkain

- Can eval non well-formed forms (e.g. `(+ 1 2`)
- Can eval infinite sequences
- Does not have separate REPL panel
- Redirects all `*out*`/`*err*` to `System.out`/`System.err`
- Can keep multiple eval results on a screen simultaneously

### Clients

*Command-line*:

- Con: needs terminal window
- Con: not machine-friendly

*SublimeREPL*:

- Just a terminal opened in a Sublime tab
- Con: Requires local lein project

*Tutkain*:

- Pro: Relies on Socket REPL
- Pro: Network-friendly
- Pro: Can interrupt evaluation
- Pro: Very full-featured
- Pro: Can display results inline
- Con: Requires separate tab
- Con: Requires custom Clojure syntax
- Con: Can’t eval if other evaluation pending
- Con: Autocompletes brackets, indents your code

### Servers

*Socket Server* (clojure.core.server/repl):

- Pro: comes bundled with Clojure
- Pro: can be run through env option, without modifying app code
- Con: not machine-friendly

*prerp*:

- Pro: comes bundled with Clojure
- Pro: can be run through Socket Server
- Pro: machine-friendly output
- Con: input is streaming, no way to send incomplete form
- Con: output is EDN, needs parser
- Con: exception serialization is terrible
- Con: can’t run two things in parallel/background
- Con: no way to interrupt evaluation

*unrepl*:

- Pro: can self-upgrade from Socket Server
- Pro: can be run through Socket Server
- Pro: machine-readable format
- Pro: interruption built-in
- Pro: crops long responses
- Con: still fundamentally streaming/human interaction-based
- Con: output is EDN, needs parser
- Con: requires separate socket for control

*nREPL*:

- Pro: real machine-oriented
- Pro: serialization (bencode) is very simple
- Pro: message-based input, not streaming-based. Can send not well-formed forms
- Pro: interruption built-in
- Pro: can evaluate in parallel
- Pro: extendable through middlewares
- Pro: load-file (w/ file name and line numbers)
- Pro: mature, huge ecosystem (CLJS, ...)
- Pro: cool logo
- Con: no upgrade path from Socket Server
- Con: error reporting lacks exception message and ex-data
- Con: middlewares are global

## Credits

Made by [Niki Tonsky](https://twitter.com/nikitonsky).

## License

[MIT License](./LICENSE.txt)
