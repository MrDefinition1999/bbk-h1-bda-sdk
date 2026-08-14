#include "h1_probe_dialogs.h"
#include "h1_probe_memory.h"

static int bytes_are_zero(const h1_u8 *data, h1_u32 size)
{
    h1_u32 index;
    for (index = 0; index < size; ++index) {
        if (data[index] != 0) {
            return 0;
        }
    }
    return 1;
}

static int bytes_keep_pattern(const h1_u8 *data, h1_u32 size)
{
    h1_u32 index;
    for (index = 0; index < size; ++index) {
        if (data[index] != (h1_u8)(index ^ 0x5Au)) {
            return 0;
        }
    }
    return 1;
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char title[] = "H1 Memory Probe";
    static const char passed[] =
        "PASS\n"
        "alloc/free\n"
        "calloc zero fill\n"
        "realloc preserves bytes";
    static const char failed_alloc[] = "FAIL: allocation returned NULL";
    static const char failed_zero[] = "FAIL: calloc did not clear bytes";
    static const char failed_realloc[] = "FAIL: realloc lost existing bytes";
    h1_u8 *block;
    h1_u8 *resized;
    h1_u32 index;

    block = (h1_u8 *)h1_probe_calloc(32, 1);
    if (!block) {
        return h1_probe_message_box(0, failed_alloc, title, 0);
    }
    if (!bytes_are_zero(block, 32)) {
        h1_probe_free(block);
        return h1_probe_message_box(0, failed_zero, title, 0);
    }
    for (index = 0; index < 32; ++index) {
        block[index] = (h1_u8)(index ^ 0x5Au);
    }

    resized = (h1_u8 *)h1_probe_realloc(block, 96);
    if (!resized) {
        h1_probe_free(block);
        return h1_probe_message_box(0, failed_alloc, title, 0);
    }
    if (!bytes_keep_pattern(resized, 32)) {
        h1_probe_free(resized);
        return h1_probe_message_box(0, failed_realloc, title, 0);
    }
    h1_probe_free(resized);

    block = (h1_u8 *)h1_probe_alloc(17);
    if (!block) {
        return h1_probe_message_box(0, failed_alloc, title, 0);
    }
    h1_probe_free(block);
    return h1_probe_message_box(0, passed, title, 0);
}
