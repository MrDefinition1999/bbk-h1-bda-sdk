#ifndef H1_PROBE_MEMORY_H
#define H1_PROBE_MEMORY_H

#include "h1_probe_runtime.h"

#define H1_MEM_ALLOC_OFFSET   0x008u
#define H1_MEM_FREE_OFFSET    0x00Cu
#define H1_MEM_CALLOC_OFFSET  0x010u
#define H1_MEM_REALLOC_OFFSET 0x014u

static inline void *h1_probe_alloc(h1_u32 size)
{
    typedef void *(*function_type)(h1_u32);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_MEM_TABLE_SLOT),
        H1_MEM_ALLOC_OFFSET
    );
    return function(size);
}

static inline void h1_probe_free(void *pointer)
{
    typedef void (*function_type)(void *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_MEM_TABLE_SLOT),
        H1_MEM_FREE_OFFSET
    );
    function(pointer);
}

static inline void *h1_probe_calloc(h1_u32 count, h1_u32 size)
{
    typedef void *(*function_type)(h1_u32, h1_u32);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_MEM_TABLE_SLOT),
        H1_MEM_CALLOC_OFFSET
    );
    return function(count, size);
}

static inline void *h1_probe_realloc(void *pointer, h1_u32 size)
{
    typedef void *(*function_type)(void *, h1_u32);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_MEM_TABLE_SLOT),
        H1_MEM_REALLOC_OFFSET
    );
    return function(pointer, size);
}

#endif
