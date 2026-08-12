import glob
import os


def resolve_write_target(paths, explicit=None):
    """Resolve a write target without guessing across multiple inputs."""
    if explicit:
        return str(explicit)
    candidates = []
    seen = set()
    for path in paths or []:
        value = str(path)
        key = os.path.normcase(os.path.abspath(value))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(value)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError(
            "Multiple input sources require an explicit write target."
        )
    raise ValueError("No input source is available for writing.")


def expand_paths(paths, default=None, stdin_when_empty=False):
    if paths is None:
        paths = default
    if isinstance(paths, str):
        paths = [paths]
    paths = list(paths or [])
    if not paths:
        if default:
            paths = [default] if isinstance(default, str) else list(default)
        elif stdin_when_empty:
            return ["-"]

    expanded = []
    for path in paths:
        text = str(path)
        if not text:
            continue
        if text == "-":
            expanded.append(text)
            continue
        matches = _expand_one_path(text)
        expanded.extend(matches)
    return _dedupe_paths(expanded or (["-"] if stdin_when_empty else []))


def _expand_one_path(path):
    if _has_glob(path):
        matches = [
            match for match in glob.glob(path, recursive=True) if os.path.isfile(match)
        ]
        return sorted(matches) or [path]
    if os.path.isdir(path):
        return _directory_life_files(path) or [path]
    return [path]


def _directory_life_files(path):
    patterns = ("life.txt", "*.life.txt", "*_life.txt", "*.txt")
    matches = []
    seen = set()
    for pattern in patterns:
        for candidate in sorted(glob.glob(os.path.join(path, pattern))):
            if not os.path.isfile(candidate):
                continue
            key = os.path.abspath(candidate)
            if key in seen:
                continue
            seen.add(key)
            matches.append(candidate)
    return matches


def _has_glob(path):
    return any(char in path for char in ("*", "?", "["))


def _dedupe_paths(paths):
    result = []
    seen = set()
    for path in paths:
        key = path if path == "-" else os.path.abspath(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result
