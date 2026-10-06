/* Private Linux snapshot worker, protocol LTXS1. No caller-selected executable.
 * Build with the target's headers; never guess syscall numbers. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <linux/magic.h>
#include <linux/openat2.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/vfs.h>
#include <unistd.h>

enum { UNSUPPORTED = 2, DENIED = 3, LIMIT = 4, STALE = 5 };

static int confined(int root, const char *path) {
#ifdef SYS_openat2
    struct open_how how = {0};
    how.flags = O_PATH | O_CLOEXEC;
    how.resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS |
                  RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV;
    return (int)syscall(SYS_openat2, root, path, &how, sizeof(how));
#else
    (void)root; (void)path; errno = ENOSYS; return -1;
#endif
}

static int local_fs(int fd) {
    struct statfs fs;
    if (fstatfs(fd, &fs)) return 0;
    /* Admission policy, not evidence that every filesystem/deployment passes. */
    return fs.f_type == EXT4_SUPER_MAGIC || fs.f_type == XFS_SUPER_MAGIC ||
           fs.f_type == BTRFS_SUPER_MAGIC || fs.f_type == TMPFS_MAGIC ||
           fs.f_type == OVERLAYFS_SUPER_MAGIC;
}

static int owned(const struct stat *s) {
    return (s->st_uid == geteuid() || s->st_uid == 0) && !(s->st_mode & 0022);
}

static int same(const struct stat *a, const struct stat *b) {
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
           a->st_size == b->st_size && a->st_nlink == b->st_nlink &&
           a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
           a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
           a->st_ctim.tv_sec == b->st_ctim.tv_sec &&
           a->st_ctim.tv_nsec == b->st_ctim.tv_nsec &&
           a->st_mode == b->st_mode && a->st_uid == b->st_uid;
}

static int unsupported_errno(void) {
    return errno == ENOSYS || errno == EINVAL || errno == EPERM;
}

int main(int argc, char **argv) {
    int result = DENIED, inspected = -1, readable = -1, current = -1, proc = -1;
    char header[128], path[4096], proc_path[64], extra;
    char *end = NULL;
    uint64_t cap;
    unsigned int path_size;
    unsigned char *bytes = NULL;
    size_t count = 0, allocated = 0;
    struct stat root, first, last, fresh;
    struct statfs proc_fs;
    if (argc != 2) return DENIED;
    errno = 0;
    long root_number = strtol(argv[1], &end, 10);
    if (errno || !end || *end || root_number < 0 || root_number > INT_MAX)
        return DENIED;
    int rootfd = (int)root_number;
    if (fstat(rootfd, &root) || !S_ISDIR(root.st_mode) || !owned(&root))
        return DENIED;
    if (!local_fs(rootfd)) return UNSUPPORTED;
    if (!fgets(header, sizeof(header), stdin) || !strchr(header, '\n') ||
        sscanf(header, "LTXS1 %" SCNu64 " %u%c", &cap, &path_size, &extra) != 3 ||
        extra != '\n' || !path_size || path_size >= sizeof(path) ||
        cap >= SIZE_MAX) return DENIED;
    if (fread(path, 1, path_size, stdin) != path_size ||
        memchr(path, 0, path_size)) return DENIED;
    path[path_size] = 0;
    if (path[0] == '/') return DENIED;
    /* Reject traversal even if a particular '..' would stay beneath root. */
    char *p = path;
    while (*p) {
        char *q = strchr(p, '/');
        size_t n = q ? (size_t)(q - p) : strlen(p);
        if (n == 2 && p[0] == '.' && p[1] == '.') return DENIED;
        if (!q) break;
        p = q + 1;
    }
    inspected = confined(rootfd, path);
    if (inspected < 0) { result = unsupported_errno() ? UNSUPPORTED : DENIED; goto done; }
    if (fstat(inspected, &first) || !S_ISREG(first.st_mode) ||
        first.st_nlink != 1 || !owned(&first) || first.st_size < 0) goto done;
    if ((uint64_t)first.st_size > cap) { result = LIMIT; goto done; }
    proc = open("/proc", O_PATH | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (proc < 0 || fstatfs(proc, &proc_fs) || proc_fs.f_type != PROC_SUPER_MAGIC) {
        result = UNSUPPORTED; goto done;
    }
    snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", inspected);
    /* This is only our own pinned FD, not a caller-supplied magic-link path. */
    readable = open(proc_path, O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (readable < 0) { result = UNSUPPORTED; goto done; }
    if (fstat(readable, &last) || !same(&first, &last) || !S_ISREG(last.st_mode)) {
        result = STALE; goto done;
    }
    allocated = (size_t)first.st_size + 1;
    if (allocated > 65536) allocated = 65536;
    bytes = malloc(allocated);
    if (!bytes) { result = LIMIT; goto done; }
    for (;;) {
        if (count == allocated) {
            size_t next = allocated > SIZE_MAX / 2 ? SIZE_MAX : allocated * 2;
            if ((uint64_t)next > cap + 1) next = (size_t)cap + 1;
            if (next <= allocated) { result = LIMIT; goto done; }
            unsigned char *grown = realloc(bytes, next);
            if (!grown) { result = LIMIT; goto done; }
            bytes = grown; allocated = next;
        }
        ssize_t n = read(readable, bytes + count, allocated - count);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) goto done;
        if (!n) break;
        count += (size_t)n;
        if ((uint64_t)count > cap) { result = LIMIT; goto done; }
    }
    if (fstat(readable, &last) || !same(&first, &last) ||
        (uint64_t)last.st_size != count) { result = STALE; goto done; }
    current = confined(rootfd, path);
    if (current < 0 || fstat(current, &fresh) || !same(&first, &fresh)) {
        result = STALE; goto done;
    }
    if (printf("LTXS1 %zu %ju %ju %ju %ju %jd %ld %jd %ld\n", count,
               (uintmax_t)root.st_dev, (uintmax_t)root.st_ino,
               (uintmax_t)last.st_dev, (uintmax_t)last.st_ino,
               (intmax_t)last.st_mtim.tv_sec, last.st_mtim.tv_nsec,
               (intmax_t)last.st_ctim.tv_sec, last.st_ctim.tv_nsec) < 0 ||
        fwrite(bytes, 1, count, stdout) != count || fflush(stdout)) goto done;
    result = 0;
done:
    free(bytes);
    if (current >= 0) close(current);
    if (readable >= 0) close(readable);
    if (inspected >= 0) close(inspected);
    if (proc >= 0) close(proc);
    close(rootfd);
    return result;
}
