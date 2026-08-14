#ifndef H1_MEMORY_H
#define H1_MEMORY_H

#include "h1_runtime.h"

#define H1_MEM_ALLOC_OFFSET   0x008u
#define H1_MEM_FREE_OFFSET    0x00Cu
#define H1_MEM_CALLOC_OFFSET  0x010u
#define H1_MEM_REALLOC_OFFSET 0x014u

typedef h1_u32 h1_memory_alias_u32 __attribute__((__may_alias__));

static inline void *h1_memset(void *destination, int value, h1_size_t size)
{
    h1_u8 *output = (h1_u8 *)destination;
    h1_u8 byte = (h1_u8)value;
    h1_u32 word = (h1_u32)byte * 0x01010101u;

    while (size != 0u && ((h1_u32)output & 3u) != 0u) {
        *output++ = byte;
        --size;
    }
    if (size >= 4u) {
        h1_memory_alias_u32 *words = (h1_memory_alias_u32 *)output;
        while (size >= 32u) {
            words[0] = word;
            words[1] = word;
            words[2] = word;
            words[3] = word;
            words[4] = word;
            words[5] = word;
            words[6] = word;
            words[7] = word;
            words += 8;
            size -= 32u;
        }
        while (size >= 4u) {
            *words++ = word;
            size -= 4u;
        }
        output = (h1_u8 *)words;
    }
    while (size-- != 0u) {
        *output++ = byte;
    }
    return destination;
}

static inline void *h1_memcpy(
    void *destination,
    const void *source,
    h1_size_t size
)
{
    h1_u8 *output = (h1_u8 *)destination;
    const h1_u8 *input = (const h1_u8 *)source;

    if ((((h1_u32)output ^ (h1_u32)input) & 3u) == 0u) {
        while (size != 0u && ((h1_u32)output & 3u) != 0u) {
            *output++ = *input++;
            --size;
        }
        if (size >= 4u) {
            h1_memory_alias_u32 *output_words =
                (h1_memory_alias_u32 *)output;
            const h1_memory_alias_u32 *input_words =
                (const h1_memory_alias_u32 *)input;
            while (size >= 32u) {
                output_words[0] = input_words[0];
                output_words[1] = input_words[1];
                output_words[2] = input_words[2];
                output_words[3] = input_words[3];
                output_words[4] = input_words[4];
                output_words[5] = input_words[5];
                output_words[6] = input_words[6];
                output_words[7] = input_words[7];
                output_words += 8;
                input_words += 8;
                size -= 32u;
            }
            while (size >= 4u) {
                *output_words++ = *input_words++;
                size -= 4u;
            }
            output = (h1_u8 *)output_words;
            input = (const h1_u8 *)input_words;
        }
    }
    while (size-- != 0u) {
        *output++ = *input++;
    }
    return destination;
}

static inline void *h1_alloc(h1_size_t size)
{
    typedef void *(*function_type)(h1_size_t);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_MEM_TABLE_SLOT),
        H1_MEM_ALLOC_OFFSET
    );
    return function(size);
}

static inline void h1_free(void *pointer)
{
    typedef void (*function_type)(void *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_MEM_TABLE_SLOT),
        H1_MEM_FREE_OFFSET
    );
    function(pointer);
}

static inline void *h1_calloc(h1_size_t count, h1_size_t size)
{
    typedef void *(*function_type)(h1_size_t, h1_size_t);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_MEM_TABLE_SLOT),
        H1_MEM_CALLOC_OFFSET
    );
    return function(count, size);
}

static inline void *h1_realloc(void *pointer, h1_size_t size)
{
    typedef void *(*function_type)(void *, h1_size_t);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_MEM_TABLE_SLOT),
        H1_MEM_REALLOC_OFFSET
    );
    return function(pointer, size);
}

#endif
