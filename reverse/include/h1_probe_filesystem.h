#ifndef H1_PROBE_FILESYSTEM_H
#define H1_PROBE_FILESYSTEM_H

#include "h1_probe_runtime.h"

typedef void h1_probe_file;

#define H1_FS_FOPEN_OFFSET  0x000u
#define H1_FS_FCLOSE_OFFSET 0x004u
#define H1_FS_FREAD_OFFSET  0x008u
#define H1_FS_FWRITE_OFFSET 0x00Cu
#define H1_FS_FSEEK_OFFSET  0x010u
#define H1_FS_FTELL_OFFSET  0x014u
#define H1_FS_REMOVE_OFFSET 0x024u
#define H1_FS_MKDIR_OFFSET  0x030u

#define H1_SEEK_SET 0
#define H1_SEEK_CUR 1
#define H1_SEEK_END 2

static inline h1_probe_file *h1_probe_fopen(const char *path, const char *mode)
{
    typedef h1_probe_file *(*function_type)(const char *, const char *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FOPEN_OFFSET
    );
    return function(path, mode);
}

static inline int h1_probe_fclose(h1_probe_file *file)
{
    typedef int (*function_type)(h1_probe_file *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FCLOSE_OFFSET
    );
    return function(file);
}

static inline h1_u32 h1_probe_fread(
    void *buffer, h1_u32 size, h1_u32 count, h1_probe_file *file
)
{
    typedef h1_u32 (*function_type)(void *, h1_u32, h1_u32, h1_probe_file *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FREAD_OFFSET
    );
    return function(buffer, size, count, file);
}

static inline h1_u32 h1_probe_fwrite(
    const void *buffer, h1_u32 size, h1_u32 count, h1_probe_file *file
)
{
    typedef h1_u32 (*function_type)(const void *, h1_u32, h1_u32, h1_probe_file *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FWRITE_OFFSET
    );
    return function(buffer, size, count, file);
}

static inline int h1_probe_fseek(h1_probe_file *file, int offset, int whence)
{
    /* H1 returns the resulting absolute position, or -1 on failure. */
    typedef int (*function_type)(h1_probe_file *, int, int);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FSEEK_OFFSET
    );
    return function(file, offset, whence);
}

static inline int h1_probe_ftell(h1_probe_file *file)
{
    typedef int (*function_type)(h1_probe_file *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_FTELL_OFFSET
    );
    return function(file);
}

static inline int h1_probe_remove(const char *path)
{
    typedef int (*function_type)(const char *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_REMOVE_OFFSET
    );
    return function(path);
}

static inline int h1_probe_mkdir(const char *path)
{
    typedef int (*function_type)(const char *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_FS_TABLE_SLOT), H1_FS_MKDIR_OFFSET
    );
    return function(path);
}

#endif
