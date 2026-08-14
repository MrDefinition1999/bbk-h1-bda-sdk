#ifndef H1_FILESYSTEM_H
#define H1_FILESYSTEM_H

#include "h1_runtime.h"

typedef void h1_file;

#define H1_FS_FOPEN_OFFSET  0x000u
#define H1_FS_FCLOSE_OFFSET 0x004u
#define H1_FS_FREAD_OFFSET  0x008u
#define H1_FS_FWRITE_OFFSET 0x00Cu
#define H1_FS_FSEEK_OFFSET  0x010u
#define H1_FS_FTELL_OFFSET  0x014u
#define H1_FS_REMOVE_OFFSET 0x024u

#define H1_SEEK_SET 0
#define H1_SEEK_CUR 1
#define H1_SEEK_END 2

static inline h1_file *h1_fopen(const char *path, const char *mode)
{
    typedef h1_file *(*function_type)(const char *, const char *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FOPEN_OFFSET
    );
    return function(path, mode);
}

static inline int h1_fclose(h1_file *file)
{
    typedef int (*function_type)(h1_file *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FCLOSE_OFFSET
    );
    return function(file);
}

static inline h1_size_t h1_fread(
    void *buffer, h1_size_t size, h1_size_t count, h1_file *file
)
{
    typedef h1_size_t (*function_type)(void *, h1_size_t, h1_size_t, h1_file *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FREAD_OFFSET
    );
    return function(buffer, size, count, file);
}

static inline h1_size_t h1_fwrite(
    const void *buffer, h1_size_t size, h1_size_t count, h1_file *file
)
{
    typedef h1_size_t (*function_type)(
        const void *, h1_size_t, h1_size_t, h1_file *
    );
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FWRITE_OFFSET
    );
    return function(buffer, size, count, file);
}

/* Success returns the resulting absolute offset; failure returns -1. */
static inline int h1_fseek(h1_file *file, int offset, int whence)
{
    typedef int (*function_type)(h1_file *, int, int);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FSEEK_OFFSET
    );
    return function(file, offset, whence);
}

static inline int h1_ftell(h1_file *file)
{
    typedef int (*function_type)(h1_file *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_FTELL_OFFSET
    );
    return function(file);
}

static inline int h1_remove(const char *path)
{
    typedef int (*function_type)(const char *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_FS_TABLE_SLOT), H1_FS_REMOVE_OFFSET
    );
    return function(path);
}

#endif
