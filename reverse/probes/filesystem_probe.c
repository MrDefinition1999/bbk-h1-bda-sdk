#include "h1_probe_dialogs.h"
#include "h1_probe_filesystem.h"

static int bytes_equal(const h1_u8 *left, const h1_u8 *right, h1_u32 size)
{
    h1_u32 index;
    for (index = 0; index < size; ++index) {
        if (left[index] != right[index]) {
            return 0;
        }
    }
    return 1;
}

static int fail(const char *message)
{
    static const char title[] = "H1 Filesystem Probe";
    return h1_probe_message_box(0, message, title, 0);
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char path[] = "A:\\H1SDK.TMP";
    static const char write_mode[] = "wb";
    static const char read_mode[] = "rb";
    static const h1_u8 pattern[16] = {
        0x48, 0x31, 0x46, 0x53, 0x00, 0x7F, 0x80, 0xFF,
        0x19, 0x97, 0x20, 0x26, 0xDE, 0xAD, 0xBE, 0xEF
    };
    static const char passed[] =
        "PASS\n"
        "write/read round trip\n"
        "seek/tell\n"
        "remove";
    static const char fail_open_write[] = "FAIL: fopen wb";
    static const char fail_write[] = "FAIL: fwrite or ftell";
    static const char fail_seek_write[] = "FAIL: seek on writer";
    static const char fail_close_write[] = "FAIL: fclose writer";
    static const char fail_open_read[] = "FAIL: fopen rb";
    static const char fail_read[] = "FAIL: fread or bytes";
    static const char fail_seek_read[] = "FAIL: seek/tell from end";
    static const char fail_tail[] = "FAIL: tail fread";
    static const char fail_close_read[] = "FAIL: fclose reader";
    static const char fail_remove[] = "FAIL: remove";
    static const char fail_still_exists[] = "FAIL: removed file opens";
    h1_u8 buffer[16];
    h1_probe_file *file;

    h1_probe_remove(path);
    file = h1_probe_fopen(path, write_mode);
    if (!file) {
        return fail(fail_open_write);
    }
    if (h1_probe_fwrite(pattern, 1, sizeof(pattern), file) != sizeof(pattern)
        || h1_probe_ftell(file) != (int)sizeof(pattern)) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_write);
    }
    if (h1_probe_fseek(file, 4, H1_SEEK_SET) != 4 || h1_probe_ftell(file) != 4) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_seek_write);
    }
    if (h1_probe_fclose(file) != 0) {
        h1_probe_remove(path);
        return fail(fail_close_write);
    }

    file = h1_probe_fopen(path, read_mode);
    if (!file) {
        h1_probe_remove(path);
        return fail(fail_open_read);
    }
    if (h1_probe_fread(buffer, 1, sizeof(buffer), file) != sizeof(buffer)
        || !bytes_equal(buffer, pattern, sizeof(buffer))) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_read);
    }
    if (h1_probe_fseek(file, -4, H1_SEEK_END) != 12 || h1_probe_ftell(file) != 12) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_seek_read);
    }
    if (h1_probe_fread(buffer, 1, 4, file) != 4
        || !bytes_equal(buffer, pattern + 12, 4)) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_tail);
    }
    if (h1_probe_fclose(file) != 0) {
        h1_probe_remove(path);
        return fail(fail_close_read);
    }
    if (h1_probe_remove(path) != 0) {
        return fail(fail_remove);
    }
    file = h1_probe_fopen(path, read_mode);
    if (file) {
        h1_probe_fclose(file);
        h1_probe_remove(path);
        return fail(fail_still_exists);
    }
    return fail(passed);
}
