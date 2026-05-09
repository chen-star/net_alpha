"""Render the macOS sandbox-exec profile that wraps the service process.

The filesystem rules are the meaningful security boundary:
  - Read everywhere (so CSV imports from ~/Downloads keep working)
  - Write only inside ~/.net_alpha
  - Bind only loopback on the pinned port
  - Outbound HTTPS is intentionally permissive (Yahoo Finance is CDN-fronted
    and tight pinning would intermittently break — see the v2 spec §9 OQ#2).
"""

from __future__ import annotations

_TEMPLATE = """(version 1)
(deny default)

;; ----------------------------------------------------------------------
;; Process / signaling — needed for launchctl + child process management.
;; ----------------------------------------------------------------------
(allow process-fork)
(allow process-exec)
(allow signal (target self))
(allow sysctl-read)
(allow mach-lookup)
(allow ipc-posix-shm)

;; ----------------------------------------------------------------------
;; Filesystem
;; ----------------------------------------------------------------------
(allow file-read*)                                            ;; read anywhere (CSV imports etc.)

(allow file-write*
    (subpath "{net_alpha_home}")                              ;; the only writable location
    (subpath "/private/var/folders")                          ;; Python tempfile
    (subpath "/private/tmp"))

;; ----------------------------------------------------------------------
;; Network
;;   Inbound: loopback only, on the pinned port.
;;   Outbound: HTTPS to anywhere. Tight pinning to yfinance hosts was
;;   considered and rejected — Yahoo's CDN rotates and macOS sandbox-exec
;;   resolves hostnames at rule-load time only. The filesystem sandbox is
;;   the real security boundary; this is belt-and-suspenders.
;; ----------------------------------------------------------------------
(allow network-bind (local ip "localhost:{port}"))
(allow network-outbound (remote tcp "*:443"))
(allow network-outbound (remote tcp "*:80"))                  ;; redirect chains
(allow network-outbound (remote unix-socket))                 ;; DNS, log
"""


def render(*, net_alpha_home: str, port: int) -> str:
    """Return the sandbox-exec profile text."""
    return _TEMPLATE.format(net_alpha_home=net_alpha_home, port=port)
