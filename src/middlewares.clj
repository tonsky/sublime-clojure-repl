(ns sublime.clojure.repl
  (:require
   [clojure.main :as main]
   [nrepl.middleware :as middleware]
   [nrepl.middleware.print :as print]
   [nrepl.middleware.caught :as caught]
   [nrepl.transport :as transport])
  (:import
   [nrepl.transport Transport]))

(defn- caught-transport
  [{:keys [transport] :as msg}]
  (reify Transport
    (recv [this]
      (transport/recv transport))
    (recv [this timeout]
      (transport/recv transport timeout))
    (send [this {throwable ::caught/throwable :as resp}]
      (let [root  (some-> throwable main/root-cause)
            data  (ex-data root)
            resp' (cond-> resp
                    root (assoc
                           ::root-ex-msg   (.getMessage root)
                           ::root-ex-class (.getSimpleName (class root)))
                    data (update ::print/keys (fnil conj []) ::root-ex-data)
                    data (assoc ::root-ex-data data))]
        (transport/send transport resp'))
      this)))

(defn wrap-errors [handler]
  (fn [msg]
    (handler (assoc msg :transport (caught-transport msg)))))

(middleware/set-descriptor!
  #'wrap-errors
  {:requires #{#'caught/wrap-caught}
   :expects #{}
   :handles {}})