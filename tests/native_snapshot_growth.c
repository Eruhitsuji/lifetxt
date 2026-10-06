/* Deterministic syscall fault injection in a test executable only. */
#define read injected_read
#define main snapshot_main
#include "../native/resource_snapshot.c"
#undef main
#undef read

ssize_t injected_read(int fd, void *buffer, size_t count) {
    static int changed = 0;
    if (!changed) {
        char own[64];
        struct stat s;
        if (!fstat(fd, &s) && S_ISREG(s.st_mode)) {
            snprintf(own, sizeof(own), "/proc/self/fd/%d", fd);
            int writer = open(own, O_WRONLY | O_CLOEXEC);
            if (writer >= 0) {
                /* Append after native inspection, before its first byte read. */
                if (lseek(writer, 0, SEEK_END) >= 0) {
                    ssize_t n = write(writer, "B", 1);
                    (void)n;
                }
                close(writer);
            }
            changed = 1;
        }
    }
    return syscall(SYS_read, fd, buffer, count);
}

int main(int argc, char **argv) { return snapshot_main(argc, argv); }
