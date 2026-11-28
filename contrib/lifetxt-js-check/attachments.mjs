import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { open, opendir, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { MAX_DIAGNOSTICS, splitAttachmentValue } from './parser.mjs';

// Match the Python checker's default attachment settings.
const DIRECTORY_IGNORES = new Set([
    '.git', '.hg', '.svn', '.venv', 'venv', '__pycache__', 'node_modules',
    '.mypy_cache', '.pytest_cache', '.DS_Store', 'Thumbs.db',
]);
const MAX_DIRECTORY_FILES = 2000;
const MAX_DIRECTORY_BYTES = 200 * 1024 * 1024;

class DirectoryHashLimit extends Error {}

function directoryByteLimit() {
    return new DirectoryHashLimit(`More than ${MAX_DIRECTORY_BYTES} bytes`);
}

async function hashFile(path, budget) {
    const file = await open(path, constants.O_RDONLY | (constants.O_NONBLOCK ?? 0));
    try {
        if (!(await file.stat()).isFile()) throw new Error('Expected a regular file');
        const hash = createHash('sha256');
        const chunk = Buffer.alloc(65536);
        while (true) {
            const { bytesRead } = await file.read(chunk, 0, chunk.length);
            if (!bytesRead) return hash.digest('hex');
            if (budget) {
                budget.remaining -= bytesRead;
                if (budget.remaining < 0) throw directoryByteLimit();
            }
            hash.update(chunk.subarray(0, bytesRead));
        }
    } finally {
        await file.close();
    }
}

async function hashDirectory(root) {
    const pending = [{ full: root, relative: '' }];
    const entries = [];
    let totalBytes = 0;
    while (pending.length) {
        const { full, relative } = pending.pop();
        const directory = await opendir(full);
        for await (const entry of directory) {
            if (DIRECTORY_IGNORES.has(entry.name)) continue;
            const child = join(full, entry.name);
            const name = relative ? `${relative}/${entry.name}` : entry.name;
            if (entry.isDirectory()) {
                pending.push({ full: child, relative: name });
                continue;
            }
            const info = await stat(child);
            // Python's walk does not recurse into symlinks to directories.
            if (entry.isSymbolicLink() && info.isDirectory()) continue;
            if (!info.isFile()) throw new Error('Expected a regular file');
            if (entries.length >= MAX_DIRECTORY_FILES) {
                throw new DirectoryHashLimit(`More than ${MAX_DIRECTORY_FILES} files`);
            }
            totalBytes += info.size;
            if (totalBytes > MAX_DIRECTORY_BYTES) throw directoryByteLimit();
            entries.push({ full: child, name: Buffer.from(name, 'utf8') });
        }
    }
    // UTF-8 byte ordering matches Core's Unicode code-point ordering.
    entries.sort((a, b) => Buffer.compare(a.name, b.name));
    const hash = createHash('sha256');
    const budget = { remaining: MAX_DIRECTORY_BYTES };
    for (const { full, name } of entries) {
        hash.update(name);
        hash.update('\0');
        hash.update(await hashFile(full, budget));
        hash.update('\n');
    }
    return hash.digest('hex');
}

async function attachmentProblem(value, key, source, verify) {
    const parsed = splitAttachmentValue(value);
    if (parsed === null) return { code: 'attachment-invalid-value' };
    const { path, digest } = parsed;

    let resolved;
    if (path === '~' || path.startsWith('~/')) {
        resolved = resolve(homedir(), path === '~' ? '.' : `.${path.slice(1)}`);
    } else {
        if (process.platform !== 'win32' && /^[A-Za-z]:\//.test(path)) return { code: 'attachment-missing' };
        resolved = resolve(dirname(source), path);
    }
    let info;
    try {
        info = await stat(resolved);
    } catch (error) {
        const code = error.code === 'ENOENT' || error.code === 'ENOTDIR'
            ? 'attachment-missing'
            : 'attachment-unreadable';
        return { code };
    }
    if (info.isDirectory() !== (key === 'dir')) return { code: 'attachment-wrong-type' };
    if (!verify || !digest) return;
    if (!info.isDirectory() && !info.isFile()) return { code: 'attachment-unreadable' };
    try {
        const hash = info.isDirectory() ? await hashDirectory(resolved) : await hashFile(resolved);
        const actual = hash.slice(0, digest.length);
        if (actual !== digest) return { code: 'attachment-hash-changed', part: `SHA-256 ${actual}` };
    } catch (error) {
        if (error instanceof DirectoryHashLimit) {
            return { code: 'attachment-directory-limit', part: error.message };
        }
        return { code: 'attachment-unreadable' };
    }
}

export async function checkAttachments(result, defaultSource, verify) {
    for (const { details, line, source } of result.items) {
        for (const key of ['file', 'dir']) {
            const values = details.find(([name]) => name === key)?.[1] ?? [];
            for (const value of values) {
                if (typeof value !== 'string') continue;
                const problem = await attachmentProblem(value, key, source ?? defaultSource, verify);
                if (!problem) continue;
                result.diagnosticCount++;
                if (result.diagnostics.length < MAX_DIAGNOSTICS) {
                    result.diagnostics.push({ severity: 'warning', ...problem, line, source, key, value });
                }
            }
        }
    }
}
