#include "h1_sdk.h"

static int bytes_are_zero(const h1_u8 *data, h1_size_t size)
{
    h1_size_t index;

    for (index = 0; index < size; ++index) {
        if (data[index] != 0u) {
            return 0;
        }
    }
    return 1;
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char title[] = "H1 Memory Demo";
    static const char passed[] =
        "PASS\n"
        "alloc/free\n"
        "calloc zero fill\n"
        "realloc preserves bytes";
    static const char failed[] = "FAIL: heap operation";
    h1_u8 *block;
    h1_u8 *resized;
    h1_size_t index;

    block = (h1_u8 *)h1_calloc(32u, 1u);
    if (block == 0 || !bytes_are_zero(block, 32u)) {
        if (block != 0) {
            h1_free(block);
        }
        return h1_message_box(0, failed, title, 0);
    }

    for (index = 0; index < 32u; ++index) {
        block[index] = (h1_u8)(index ^ 0x5Au);
    }
    resized = (h1_u8 *)h1_realloc(block, 96u);
    if (resized == 0) {
        h1_free(block);
        return h1_message_box(0, failed, title, 0);
    }
    for (index = 0; index < 32u; ++index) {
        if (resized[index] != (h1_u8)(index ^ 0x5Au)) {
            h1_free(resized);
            return h1_message_box(0, failed, title, 0);
        }
    }
    h1_free(resized);

    block = (h1_u8 *)h1_alloc(17u);
    if (block == 0) {
        return h1_message_box(0, failed, title, 0);
    }
    h1_free(block);
    return h1_message_box(0, passed, title, 0);
}
