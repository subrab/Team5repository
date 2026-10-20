"""Tiny reader for the YAML subset our DSL uses (no packages needed). Uses PyYAML instead when installed."""
import re


def load(text):
    try:
        import yaml  # PyYAML, if present on the lab laptop
        return yaml.safe_load(text)
    except ImportError:
        return _parse(text)


def _scalar(s):
    s = s.strip()
    if s == "":
        return None
    if s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if s in ("true", "false"):
        return s == "true"
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    return s


def _parse(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if '"' not in raw and "'" not in raw:
            raw = re.sub(r"\s+#.*$", "", raw)
        lines.append([len(raw) - len(raw.lstrip()), raw.strip()])
    obj, _ = _block(lines, 0, lines[0][0]) if lines else ({}, 0)
    return obj


def _block(L, i, ind):
    if L[i][1].startswith("- "):
        out = []
        while i < len(L) and L[i][0] == ind and L[i][1].startswith("- "):
            content = L[i][1][2:]
            if re.match(r"^[\w\-]+:(\s|$)", content):
                L[i] = [ind + 2, content]
                item, i = _map(L, i, ind + 2)
                out.append(item)
            else:
                out.append(_scalar(content)); i += 1
        return out, i
    return _map(L, i, ind)


def _map(L, i, ind):
    out = {}
    while i < len(L) and L[i][0] == ind and not L[i][1].startswith("- "):
        k, _, v = L[i][1].partition(":")
        i += 1
        if v.strip():
            out[k.strip()] = _scalar(v)
        elif i < len(L) and (L[i][0] > ind or (L[i][0] == ind and L[i][1].startswith("- "))):
            out[k.strip()], i = _block(L, i, L[i][0])
        else:
            out[k.strip()] = None
    return out, i
