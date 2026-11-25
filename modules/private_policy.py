"""Fail-closed separation of public output and password-protected source paths."""
import json
import hashlib
import re
import shutil
from pathlib import Path, PurePosixPath


def private_dirs(config):
    cfg = config.get('private_space', {})
    if not cfg.get('enabled', False):
        return ()
    result = []
    for value in cfg.get('source_dirs', []):
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
            raise ValueError('Private Space source directories must be relative note paths')
        result.append(path.as_posix().rstrip('/'))
    if not result:
        raise ValueError('Private Space requires source_dirs')
    return tuple(result)


def is_private(rel_path, config):
    rel = str(rel_path).replace('\\', '/').strip('/')
    return any(rel == directory or rel.startswith(directory + '/')
               for directory in private_dirs(config))


def public_paths(root, config):
    root = Path(root)
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*.md')
                  if not is_private(p.relative_to(root).as_posix(), config))


def _private_cache_key(key, config):
    prefix = config.get('source', {}).get('notes_subdir', '').strip('/')
    value = key[len(prefix) + 1:] if prefix and key.startswith(prefix + '/') else key
    return is_private(value, config)


def clean_public_outputs(config):
    """Remove previously published private trees and cache entries before any processing."""
    directories = private_dirs(config)
    if not directories:
        return
    content = Path(config.get('output', {}).get('content_dir', 'content'))
    static = Path(config.get('processing', {}).get('image_handling', {}).get('target_static_dir', 'static'))
    for directory in directories:
        for root in (content, static / 'images'):
            target = root.joinpath(*PurePosixPath(directory).parts)
            if not target.resolve().is_relative_to(root.resolve()) or target.resolve() == root.resolve():
                raise ValueError('Unsafe private output cleanup path')
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    processing = config.get('processing', {})
    for name in (processing.get('cache_file', '.hash_cache.json'),
                 processing.get('deepseek_cache_file', '.deepseek_cache.json'), '.file_times.json'):
        path = Path(name)
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        data = {key: value for key, value in data.items() if not _private_cache_key(key, config)}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def clear_rendered_output(config):
    """Hugo must never retain old private HTML/search/assets from an earlier build."""
    target = Path(config.get('validation', {}).get('public_dir', 'public')).resolve()
    root = Path.cwd().resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError('Rendered output must be a dedicated project subdirectory')
    if target.is_dir():
        shutil.rmtree(target)


def validate_public_output(config):
    """Fail deployment if a configured private source tree escaped encryption."""
    root = Path(config.get('validation', {}).get('public_dir', 'public'))
    for directory in private_dirs(config):
        if (root / directory.lower()).exists() or (root / 'images' / directory).exists():
            raise RuntimeError('Private Space plaintext output detected')
    processing = config.get('processing', {})
    for cache in (processing.get('cache_file', '.hash_cache.json'),
                  processing.get('deepseek_cache_file', '.deepseek_cache.json'), '.file_times.json'):
        path = Path(cache)
        if path.is_file() and any(_private_cache_key(key, config) for key in json.loads(path.read_text())):
            raise RuntimeError('Private Space metadata detected in public cache')
    for file in root.rglob('*'):
        if file.suffix in ('.html', '.json', '.xml', '.txt') and file.is_file():
            text = file.read_text(encoding='utf-8')
            for directory in private_dirs(config):
                if re.search(r'(?:href|src)=["\'][^"\']*/' + re.escape(directory.lower()) + '/', text, re.I):
                    raise RuntimeError('Public output links to a private source tree')
    # Catch copies of private attachments under an unrelated public filename.
    private_hashes = {hashlib.sha256(Path(p).read_bytes()).digest()
                      for p in config.get('_private_asset_paths', set())}
    if private_hashes:
        for file in root.rglob('*'):
            if file.is_file() and file.suffix not in ('.html', '.json', '.xml', '.txt'):
                if hashlib.sha256(file.read_bytes()).digest() in private_hashes:
                    raise RuntimeError('Private attachment plaintext detected in public output')
