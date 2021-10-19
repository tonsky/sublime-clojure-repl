# Basic Clojure REPL for Sublime Text

Goals:

- Decomplected: just REPL, nothing more
- Compact: Display code evaluation results inline
- Connect over network: no requirements on project structure

## Status

In development

- [x] Command: Connect to nREPL
- [x] Parse bencode
- [x] Command: Disconnect
- [x] Detect socket close
- [x] Redirect stdout & stderr to System.out / System.err
- [x] Middleware for error info
- [x] Print stack trace to stderr
- [x] Use nREPL sessions & ids
- [x] Keep multiple annotations on screen
- [x] Command: Clear annotations
- [x] Pending evaluation annotation
- [ ] Identify namespace of a file
- [x] Command: Interrupt evaluation
- [ ] Command: Evaluate top-level form under cursor
- [ ] Command: Evaluate file
- [ ] Send file name and position with eval
- [ ] Move colors into color scheme

## Motivation

### Clients

*Command-line*:

- Con: needs terminal window
- Con: not machine-friendly

*SublimeREPL*:

- Just a termnial opened in a Sublime tab
- Con: Requires local lein project

*Tutkain*:

- Pro: Relies on Socket REPL
- Pro: Network-friendly
- Pro: Can interrupt evaluation
- Pro: Very full-featured
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