;;; test.clj: a test file to check eval plugin

;; by Nikita Prokopov
;; October 2021

(ns ^{:doc "Hey!
Nice namespace"
:added ['asdas #"regexp"]
:author "Niki Tonsky"}
  sublime-clojure-repl.test
  (:require
   [clojure.string :as str]))

*ns*

(find-ns 'sublime-clojure-repl.test)

(str/join ", " (range 10))

(defn fun []
  *ns*)
