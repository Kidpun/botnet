import os
from typing import List, Optional, Tuple, Any

try:
    import socks
except ImportError:
    socks = None

PROXY_FILE = "proxy.txt"

def _parse_proxy_line(line: str) -> Optional[Tuple[Any, ...]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    try:
        if "://" in line:
            if line.startswith("socks5://"):
                rest = line[9:].strip()
                proxy_type = socks.SOCKS5 if socks else None
            elif line.startswith("http://") or line.startswith("https://"):
                rest = (line.split("://", 1)[1]).strip()
                proxy_type = socks.HTTP if socks else None
            else:
                return None
            if not proxy_type:
                return None
            if "@" in rest:
                auth, hostport = rest.rsplit("@", 1)
                user, _, password = auth.partition(":")
                host, _, port = hostport.rpartition(":")
                port = int(port) if port else (1080 if proxy_type == socks.SOCKS5 else 8080)
                return (proxy_type, host.strip(), port, True, user.strip(), password.strip())
            else:
                host, _, port = rest.rpartition(":")
                port = int(port) if port else (1080 if proxy_type == socks.SOCKS5 else 8080)
                return (proxy_type, host.strip(), port)
        return None
    except Exception:
        return None

def load_proxies(base_dir: Optional[str] = None) -> List[Tuple[Any, ...]]:
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, PROXY_FILE)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = _parse_proxy_line(line)
            if p:
                out.append(p)
    return out

def get_proxy_for_index(proxies: List[Tuple], index: int):
    if not proxies:
        return None
    return proxies[index % len(proxies)]
