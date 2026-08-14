#ifndef H1_PROBE_RUNTIME_H
#define H1_PROBE_RUNTIME_H

typedef unsigned char h1_u8;
typedef unsigned int h1_u32;
typedef int (*h1_probe_fn4)(h1_u32, h1_u32, h1_u32, h1_u32);

#define H1_GUI_TABLE_SLOT 0x83C00004u
#define H1_FS_TABLE_SLOT  0x83C00008u
#define H1_SYS_TABLE_SLOT 0x83C0000Cu
#define H1_MEM_TABLE_SLOT 0x83C00010u
#define H1_RES_TABLE_SLOT 0x83C00014u

static inline void *h1_probe_table(h1_u32 slot)
{
    return *(void * volatile *)slot;
}

static inline void *h1_probe_entry(void *table, h1_u32 offset)
{
    return *(void **)((h1_u8 *)table + offset);
}

static inline int h1_probe_call4(
    void *table,
    h1_u32 offset,
    h1_u32 a0,
    h1_u32 a1,
    h1_u32 a2,
    h1_u32 a3
)
{
    h1_probe_fn4 fn = *(h1_probe_fn4 *)((unsigned char *)table + offset);
    return fn(a0, a1, a2, a3);
}

#endif
