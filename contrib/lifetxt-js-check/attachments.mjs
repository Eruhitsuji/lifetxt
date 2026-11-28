import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { open, opendir, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { basename, dirname, isAbsolute, join, posix, resolve } from 'node:path';
import { DIRECTORY_IGNORES, MAX_DIAGNOSTICS, MAX_DIRECTORY_BYTES, MAX_DIRECTORY_FILES, splitAttachmentValue } from './parser.mjs';

class DirectoryHashLimit extends Error {}

function positiveLimit(value, fallback) {
    const number = typeof value === 'string' && /^[+-]?\d(?:_?\d)*$/.test(value.trim())
        ? Number(value.trim().replaceAll('_', ''))
        : typeof value === 'number' || typeof value === 'boolean' ? Math.trunc(value) : NaN;
    return Number.isSafeInteger(number) && number > 0 ? number : fallback;
}

function attachmentSettings(config = {}) {
    const ignore = typeof config.ignore === 'string'
        ? config.ignore.split(',').map(name => name.trim()).filter(Boolean)
        : Array.isArray(config.ignore) ? config.ignore : [];
    return {
        ignores: new Set(ignore.length ? ignore : DIRECTORY_IGNORES),
        maxFiles: positiveLimit(config.max_files, MAX_DIRECTORY_FILES),
        maxBytes: positiveLimit(config.max_bytes, MAX_DIRECTORY_BYTES),
    };
}

function directoryByteLimit(maxBytes) {
    return new DirectoryHashLimit(`More than ${maxBytes} bytes`);
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
                if (budget.remaining < 0) throw directoryByteLimit(budget.maxBytes);
            }
            hash.update(chunk.subarray(0, bytesRead));
        }
    } finally {
        await file.close();
    }
}

async function hashDirectory(root, { ignores, maxFiles, maxBytes }) {
    const pending = [{ full: root, relative: '' }];
    const entries = [];
    let totalBytes = 0;
    while (pending.length) {
        const { full, relative } = pending.pop();
        const directory = await opendir(full);
        for await (const entry of directory) {
            if (ignores.has(entry.name)) continue;
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
            if (entries.length >= maxFiles) {
                throw new DirectoryHashLimit(`More than ${maxFiles} files`);
            }
            totalBytes += info.size;
            if (totalBytes > maxBytes) throw directoryByteLimit(maxBytes);
            entries.push({ full: child, name: Buffer.from(name, 'utf8') });
        }
    }
    // UTF-8 byte ordering matches Core's Unicode code-point ordering.
    entries.sort((a, b) => Buffer.compare(a.name, b.name));
    const hash = createHash('sha256');
    const budget = { remaining: maxBytes, maxBytes };
    for (const { full, name } of entries) {
        hash.update(name);
        hash.update('\0');
        hash.update(await hashFile(full, budget));
        hash.update('\n');
    }
    return hash.digest('hex');
}

const WINDOWS_DRIVE = /^[A-Za-z]:[\\/]/;

function* portabilityProblems(raw, normalized) {
    if (raw.includes('\\')) yield 'Use forward slashes';
    if (WINDOWS_DRIVE.test(raw)) yield 'Drive letters are machine-specific';
    else if (raw.startsWith('//') || raw.startsWith('\\\\')) yield 'UNC paths depend on a network share';
    else if (isAbsolute(raw)) yield 'Absolute paths are machine-specific';
    if (raw !== raw.normalize('NFC')) yield 'Path is not NFC-normalized';
    const name = posix.basename(posix.normalize(normalized));
    if (name !== '.' && name !== '..' && /[ .]$/.test(name)) yield 'Trailing spaces or dots are invalid on Windows';
}

async function caseMismatch(path) {
    const name = basename(path);
    if (!name) return;
    const lower = name.toLowerCase();
    try {
        const directory = await opendir(dirname(path));
        let match;
        for await (const entry of directory) {
            if (entry.name === name) return;
            if (match === undefined && entry.name.toLowerCase() === lower) match = entry.name;
        }
        if (match !== undefined) return `On-disk name is ${JSON.stringify(match)}`;
    } catch {
        // The path may be accessible even if the parent cannot be listed.
    }
}

async function inspectAttachment(resolved, key, digest, verify, settings) {
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
        const hash = info.isDirectory() ? await hashDirectory(resolved, settings) : await hashFile(resolved);
        const actual = hash.slice(0, digest.length);
        if (actual !== digest) return { code: 'attachment-hash-changed', part: `SHA-256 ${actual}` };
    } catch (error) {
        if (error instanceof DirectoryHashLimit) {
            return { code: 'attachment-directory-limit', part: error.message };
        }
        return { code: 'attachment-unreadable' };
    }
}

async function* attachmentProblems(value, key, source, verify, settings) {
    const parsed = splitAttachmentValue(value);
    if (parsed === null) {
        yield { code: 'attachment-invalid-value' };
        return;
    }
    const { path, rawPath, digest } = parsed;
    const foreignDrive = process.platform !== 'win32' && WINDOWS_DRIVE.test(path);
    const resolved = path === '~' || path.startsWith('~/')
        ? resolve(homedir(), path === '~' ? '.' : `.${path.slice(1)}`)
        : resolve(dirname(source), path);
    const problem = foreignDrive
        ? { code: 'attachment-missing' }
        : await inspectAttachment(resolved, key, digest, verify, settings);
    if (problem) yield problem;
    if (problem && problem.code !== 'attachment-missing' && problem.code !== 'attachment-hash-changed') return;
    for (const part of portabilityProblems(rawPath, path)) {
        yield { code: 'attachment-nonportable', part };
    }
    if (problem?.code !== 'attachment-missing') {
        const part = await caseMismatch(resolved);
        if (part !== undefined) yield { code: 'attachment-case-mismatch', part };
    }
}

export async function checkAttachments(result, defaultSource, verify, config) {
    const settings = attachmentSettings(config);
    for (const { details, line, source } of result.items) {
        for (const key of ['file', 'dir']) {
            const values = details.find(([name]) => name === key)?.[1] ?? [];
            for (const value of values) {
                if (typeof value !== 'string') continue;
                for await (const problem of attachmentProblems(value, key, source ?? defaultSource, verify, settings)) {
                    result.diagnosticCount++;
                    if (result.diagnostics.length < MAX_DIAGNOSTICS) {
                        result.diagnostics.push({ severity: 'warning', ...problem, line, source, key, value });
                    }
                }
            }
        }
    }
}
