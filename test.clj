; simple expr
(+ 1 2)

; long value
(range 100)

; infinite sequence
(range)

; print
(println "Hello, Sublime!")
(.println System/out "System.out.println")

; print to stderr
(binding [*out* *err*] (println "abc"))
(.println System/err "System.err.println")

; print in background
(doseq [i (range 0 1000)] (Thread/sleep 1000) (println i))

; throw exception
(throw (ex-info "abc" {:a 1}))
(throw (Exception. "ex with msg"))

; two exprs
(+ 1 2) (+ 3 4)

; malformed expr
(+ 1
(+ 1 2))
