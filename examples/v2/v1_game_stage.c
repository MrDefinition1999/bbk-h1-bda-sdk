typedef unsigned char h1_u8;
typedef unsigned int h1_u32;

#ifndef H1_GAME_SIZE
#error H1_GAME_SIZE must be supplied by the V2 compatibility builder
#endif

#define H1_PREFIX ((volatile h1_u32 *)0x83C00000u)
#define H1_GAME_ENTRY ((int (*)(void))0x83C00020u)
#define H1_COMPAT_GUI ((volatile h1_u32 *)0x83E00000u)
#define H1_COMPAT_RES ((volatile h1_u32 *)0x83E01000u)
#define H1_COMPAT_SYS ((volatile h1_u32 *)0x83E02000u)
#define H1_COMPAT_FS ((volatile h1_u32 *)0x83E03000u)
#define H1_STAGE_DATA ((volatile h1_u32 *)0x83F10000u)
#define H1_STAGE_TRACE ((volatile h1_u32 *)0xA3F10F00u)

/* The probe trace lives in reserved SDRAM and never enters a release archive. */
#define H1_TRACE_MAGIC 0x56545231u
#define H1_TRACE_HEADER_WORDS 8u
#define H1_TRACE_RECORD_WORDS 6u
#define H1_TRACE_RECORD_COUNT 64u

#define TRACE_STAGE_START 0x53544730u
#define TRACE_STAGE_TABLES 0x53544731u
#define TRACE_GAME_START 0x47315331u
#define TRACE_GAME_RETURN 0x47315231u
#define TRACE_GUI_BASE 0x10000000u
#define TRACE_RES_BASE 0x20000000u
#define TRACE_SYS_BASE 0x30000000u
#define TRACE_FS_BASE 0x40000000u

static volatile h1_u32 compat_game_mode;
static volatile h1_u32 compat_license_depth;
static volatile h1_u32 compat_rtc_ticks;
static volatile h1_u32 compat_rtc_flag;
static volatile h1_u32 compat_legacy_handle;
static volatile h1_u32 *compat_v2_gui_table;
static volatile h1_u32 compat_game_mode_stop;
static const h1_u8 compat_game_name[] = "V1Game";

static void trace_reset(void)
{
    h1_u32 index;

    for (index = 0u; index < H1_TRACE_HEADER_WORDS +
        H1_TRACE_RECORD_WORDS * H1_TRACE_RECORD_COUNT; ++index) {
        H1_STAGE_TRACE[index] = 0u;
    }
    H1_STAGE_TRACE[0] = H1_TRACE_MAGIC;
    H1_STAGE_TRACE[1] = 1u;
}

static void trace_event(
    h1_u32 event,
    h1_u32 a0,
    h1_u32 a1,
    h1_u32 a2,
    h1_u32 a3,
    h1_u32 result)
{
    h1_u32 index = H1_STAGE_TRACE[2] % H1_TRACE_RECORD_COUNT;
    volatile h1_u32 *record = H1_STAGE_TRACE + H1_TRACE_HEADER_WORDS +
        index * H1_TRACE_RECORD_WORDS;

    record[0] = event;
    record[1] = a0;
    record[2] = a1;
    record[3] = a2;
    record[4] = a3;
    record[5] = result;
    H1_STAGE_TRACE[2] = (index + 1u) % H1_TRACE_RECORD_COUNT;
    H1_STAGE_TRACE[3] += 1u;
    __asm__ volatile ("sync" ::: "memory");
}

static void copy_words(
    volatile h1_u32 *destination,
    const volatile h1_u32 *source,
    h1_u32 words)
{
    while (words != 0u) {
        *destination++ = *source++;
        --words;
    }
}

static void copy_bytes_forward(
    volatile h1_u8 *destination,
    const volatile h1_u8 *source,
    h1_u32 size)
{
    while (size != 0u) {
        *destination++ = *source++;
        --size;
    }
}

static void flush_cache(const volatile h1_u8 *start, h1_u32 size)
{
    h1_u32 address = (h1_u32)start & ~15u;
    h1_u32 end = ((h1_u32)start + size + 15u) & ~15u;

    __asm__ volatile ("sync" ::: "memory");
    while (address < end) {
        __asm__ volatile ("cache 0x15, 0(%0)" :: "r"(address) : "memory");
        __asm__ volatile ("cache 0x10, 0(%0)" :: "r"(address) : "memory");
        address += 16u;
    }
    __asm__ volatile ("sync" ::: "memory");
}

static int compat_return_zero(
    h1_u32 a0,
    h1_u32 a1,
    h1_u32 a2,
    h1_u32 a3)
{
    (void)a0;
    (void)a1;
    (void)a2;
    (void)a3;
    trace_event(TRACE_RES_BASE | 0x00000094u, a0, a1, a2, a3, 0u);
    return 0;
}

/*
 * V1 FS+0x048 reports block-device geometry.  V2's table has no compatible
 * implementation at this slot, but Mission only needs a stable geometry
 * during its startup capacity check.  Keep the values within the virtual
 * storage scale while satisfying the original >0x7FFFF byte threshold.
 */
static int compat_fs_get_info(
    h1_u32 device,
    volatile h1_u32 *info)
{
    (void)device;
    if (info == (volatile h1_u32 *)0) {
        trace_event(TRACE_FS_BASE | 0x00000048u, device, 0u, 0u, 0u,
            (h1_u32)-1);
        return -1;
    }
    info[0] = 0x00010000u;
    info[1] = 0x00010000u;
    info[2] = 1u;
    info[3] = 512u;
    trace_event(TRACE_FS_BASE | 0x00000048u, device, info[0], info[1],
        info[2], 0u);
    return 0;
}

typedef int (*compat_event_callback_type)(h1_u32, h1_u32, h1_u32, h1_u32);
typedef int (*compat_gui_init_type)(void);
typedef int (*compat_gui_create_type)(volatile h1_u32 *);
typedef int (*compat_gui_get_message_type)(volatile h1_u8 *, h1_u32);
typedef void (*compat_gui_message_type)(volatile h1_u8 *);
typedef int (*compat_gui_close_type)(h1_u32);

/*
 * V1's GUI+0x6A8 callback is part of the V1 system image and cannot be
 * called after the game has switched its prefix to V2 tables.  The V2
 * default event handler is ABI-compatible with the callback signature, so
 * retain V2's input/desktop handling and only add the V1 close boundary.
 */
static int compat_game_callback(
    h1_u32 app,
    h1_u32 type,
    h1_u32 a3,
    h1_u32 a4)
{
    compat_event_callback_type default_callback;
    h1_u32 result;

    trace_event(TRACE_GUI_BASE | 0x00000084u, app, type, a3, a4, 0u);
    if (type == 102u || type == 2116u) {
        compat_game_mode_stop = 1u;
        trace_event(TRACE_GUI_BASE | 0x000006A9u, type, 0u, 0u, 0u, 0u);
        return 0;
    }
    if (compat_v2_gui_table == (volatile h1_u32 *)0) {
        return 0;
    }
    result = compat_v2_gui_table[0x084u >> 2];
    if (result == 0u) {
        return 0;
    }
    default_callback = (compat_event_callback_type)result;
    return default_callback(app, type, a3, a4);
}

/* V1 uses this as a non-blocking gate before its own game loop starts. */
static int compat_game_mode_open(h1_u32 mode)
{
    compat_game_mode = mode;
    compat_game_mode_stop = 0u;
    trace_event(TRACE_GUI_BASE | 0x000006A8u, mode, 0u, 0u, 0u, 1u);
    return 1;
}

/*
 * V1 enters a game with one GUI context already established by the launcher.
 * V2's equivalent slot performs lazy initialization and returns zero on the
 * successful first call, so repeat it once to obtain V1's boolean contract.
 */
static int compat_game_gui_init(void)
{
    compat_gui_init_type initialize;
    h1_u32 pointer;
    int result;

    trace_event(TRACE_GUI_BASE | 0x0000084Cu, 0u, 0u, 0u, 0u, 0u);
    if (compat_v2_gui_table == (volatile h1_u32 *)0) {
        return 0;
    }
    pointer = compat_v2_gui_table[0x738u >> 2];
    if (pointer == 0u) {
        return 0;
    }
    initialize = (compat_gui_init_type)pointer;
    result = initialize();
    if (result == 0) {
        result = initialize();
    }
    trace_event(TRACE_GUI_BASE | 0x0000084Cu, 0u, 0u, 0u, 0u,
        (h1_u32)result);
    return result != 0;
}

static int compat_gui_get_display(h1_u32 buffer)
{
    volatile unsigned short *values = (volatile unsigned short *)buffer;

    /* V1 expects the current 480x272 LCD geometry and four zero margins. */
    if (values != (volatile unsigned short *)0) {
        values[0] = 480u;
        values[1] = 272u;
        values[2] = 0u;
        values[3] = 0u;
        values[4] = 480u;
        values[5] = 272u;
        values[6] = 0u;
        values[7] = 0u;
    }
    trace_event(TRACE_GUI_BASE | 0x00000884u, buffer, 0u, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_init(void)
{
    trace_event(TRACE_GUI_BASE | 0x00000888u, 0u, 0u, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_set_volume(h1_u32 a0, h1_u32 a1, h1_u32 a2)
{
    trace_event(TRACE_GUI_BASE | 0x00000890u, a0, a1, a2, 0u, 1u);
    return 1;
}

static int compat_gui_audio_send(h1_u32 a0)
{
    trace_event(TRACE_GUI_BASE | 0x00000894u, a0, 0u, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_audio_open(void)
{
    trace_event(TRACE_GUI_BASE | 0x00000898u, 0u, 0u, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_color_a(h1_u32 color, h1_u32 target)
{
    trace_event(TRACE_GUI_BASE | 0x000008FCu, color, target, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_color_b(h1_u32 color, h1_u32 target)
{
    trace_event(TRACE_GUI_BASE | 0x00000900u, color, target, 0u, 0u, 1u);
    return 1;
}

static int compat_gui_color_format(h1_u32 format, h1_u32 value)
{
    trace_event(TRACE_GUI_BASE | 0x00000908u, format, value, 0u, 0u, 1u);
    return 1;
}

/* V1's coin/trial service has no V2 equivalent. Permit play without charging. */
static int compat_license_allow(
    h1_u32 a0,
    h1_u32 a1,
    h1_u32 a2,
    h1_u32 a3)
{
    (void)a0;
    (void)a1;
    (void)a2;
    (void)a3;
    trace_event(TRACE_GUI_BASE | 0x00000AA4u, a0, a1, a2, a3, 1u);
    return 1;
}

static int compat_license_scope_begin(void)
{
    compat_license_depth = 2u;
    trace_event(TRACE_GUI_BASE | 0x000006E4u, 0u, 0u, 0u, 0u, 0u);
    return 0;
}

static int compat_license_scope_end(void)
{
    compat_license_depth = 0u;
    trace_event(TRACE_GUI_BASE | 0x000006E8u, 0u, 0u, 0u, 0u, 0u);
    return 0;
}

static int compat_rtc_set_ticks(h1_u32 ticks)
{
    compat_rtc_ticks = 40u * ticks;
    trace_event(TRACE_GUI_BASE | 0x000006FCu, ticks, compat_rtc_ticks, 0u, 0u,
        compat_rtc_ticks);
    return (int)compat_rtc_ticks;
}

static int compat_rtc_set_flag(h1_u32 flag)
{
    compat_rtc_flag = flag & 0xFFu;
    trace_event(TRACE_GUI_BASE | 0x00000700u, flag, compat_rtc_flag, 0u, 0u,
        0u);
    return 0;
}

static int compat_legacy_handle_cleanup(void)
{
    compat_legacy_handle = 0u;
    trace_event(TRACE_SYS_BASE | 0x0000008Cu, 0u, 0u, 0u, 0u, 0u);
    return 0;
}

static volatile h1_u32 *compat_legacy_handle_address(void)
{
    trace_event(TRACE_SYS_BASE | 0x00000090u, 0u, 0u, 0u, 0u,
        (h1_u32)&compat_legacy_handle);
    return &compat_legacy_handle;
}

static void map_gui(
    volatile h1_u32 *compat,
    const volatile h1_u32 *v2,
    h1_u32 v1_offset,
    h1_u32 v2_offset)
{
    compat[v1_offset >> 2] = v2[v2_offset >> 2];
}

static void install_gui_compatibility(
    volatile h1_u32 *compat,
    const volatile h1_u32 *v2)
{
    h1_u32 offset;

    copy_words(compat, v2, 0xB00u >> 2);

    compat[0x884u >> 2] = (h1_u32)compat_gui_get_display;
    compat[0x888u >> 2] = (h1_u32)compat_gui_init;
    compat[0x890u >> 2] = (h1_u32)compat_gui_set_volume;
    compat[0x894u >> 2] = (h1_u32)compat_gui_audio_send;
    compat[0x898u >> 2] = (h1_u32)compat_gui_audio_open;
    compat[0x8FCu >> 2] = (h1_u32)compat_gui_color_a;
    compat[0x900u >> 2] = (h1_u32)compat_gui_color_b;
    compat[0x908u >> 2] = (h1_u32)compat_gui_color_format;

    map_gui(compat, v2, 0x2B8u, 0x2B0u);
    map_gui(compat, v2, 0x300u, 0x2F8u);
    map_gui(compat, v2, 0x3F8u, 0x3F0u);
    map_gui(compat, v2, 0x400u, 0x3F8u);

    compat[0x6A8u >> 2] = (h1_u32)compat_game_mode_open;
    map_gui(compat, v2, 0x6E0u, 0x9E4u);
    compat[0x6E4u >> 2] = (h1_u32)compat_license_scope_begin;
    compat[0x6E8u >> 2] = (h1_u32)compat_license_scope_end;
    compat[0x6F4u >> 2] = (h1_u32)compat_return_zero;
    compat[0x6FCu >> 2] = (h1_u32)compat_rtc_set_ticks;
    compat[0x700u >> 2] = (h1_u32)compat_rtc_set_flag;
    map_gui(compat, v2, 0x72Cu, 0x688u);

    compat[0x84Cu >> 2] = (h1_u32)compat_game_gui_init;
    for (offset = 0x850u; offset <= 0x9F8u; offset += 4u) {
        map_gui(compat, v2, offset, offset - 0x114u);
    }
    map_gui(compat, v2, 0xA38u, 0x924u);
    map_gui(compat, v2, 0xA70u, 0x938u);
    map_gui(compat, v2, 0xA7Cu, 0x6A4u);
    map_gui(compat, v2, 0xA80u, 0x6A8u);
    map_gui(compat, v2, 0xA84u, 0x940u);
    map_gui(compat, v2, 0xA88u, 0x944u);
    map_gui(compat, v2, 0xA8Cu, 0x948u);
    map_gui(compat, v2, 0xA90u, 0x94Cu);
    compat[0xAA4u >> 2] = (h1_u32)compat_license_allow;
    compat[0xAA8u >> 2] = (h1_u32)compat_license_allow;
    map_gui(compat, v2, 0xAD8u, 0x95Cu);
    map_gui(compat, v2, 0xADCu, 0x960u);
}

static void install_fs_compatibility(
    volatile h1_u32 *compat,
    const volatile h1_u32 *v2)
{
    copy_words(compat, v2, 0x100u >> 2);
    compat[0x048u >> 2] = (h1_u32)compat_fs_get_info;
}

static int load_external_game(const char *path, h1_u32 fs_table)
{
    typedef void *(*fopen_type)(const char *, const char *);
    typedef h1_u32 (*fread_type)(void *, h1_u32, h1_u32, void *);
    typedef int (*fclose_type)(void *);
    volatile h1_u32 *table = (volatile h1_u32 *)fs_table;
    fopen_type open_file = (fopen_type)table[0x000u >> 2];
    fclose_type close_file = (fclose_type)table[0x004u >> 2];
    fread_type read_file = (fread_type)table[0x008u >> 2];
    static const char mode[] = "rb";
    void *file;
    h1_u32 read;

    trace_event(TRACE_SYS_BASE | 0x00000000u, (h1_u32)path, 0u, 0u, 0u, 0u);
    file = open_file(path, mode);
    if (file == (void *)0) {
        return 0;
    }
    trace_event(TRACE_SYS_BASE | 0x00000008u, (h1_u32)file, 0u, 0u, 0u, 0u);
    read = read_file((void *)0x83C00020u, 1u, H1_GAME_SIZE, file);
    close_file(file);
    trace_event(TRACE_SYS_BASE | 0x0000000Cu, read, H1_GAME_SIZE, 0u, 0u,
        read == H1_GAME_SIZE);
    return read == H1_GAME_SIZE;
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(const h1_u8 *game_source, h1_u32 game_size)
{
    volatile h1_u32 *saved = H1_STAGE_DATA;
    volatile h1_u32 *v2_gui;
    volatile h1_u32 *v2_fs;
    volatile h1_u32 *v2_res;
    volatile h1_u32 *v2_sys;
    h1_u32 result;

    trace_reset();
    trace_event(TRACE_STAGE_START, game_size, (h1_u32)game_source, 0u, 0u, 0u);
    copy_words(saved, H1_PREFIX, 16u);
    v2_gui = (volatile h1_u32 *)saved[1];
    v2_fs = (volatile h1_u32 *)saved[2];
    v2_sys = (volatile h1_u32 *)saved[3];
    v2_res = (volatile h1_u32 *)saved[5];

    compat_game_mode = 0u;
    compat_v2_gui_table = v2_gui;
    compat_game_mode_stop = 0u;
    compat_license_depth = 0u;
    compat_rtc_ticks = 0u;
    compat_rtc_flag = 0u;
    compat_legacy_handle = 0u;

    install_gui_compatibility(H1_COMPAT_GUI, v2_gui);
    install_fs_compatibility(H1_COMPAT_FS, v2_fs);
    copy_words(H1_COMPAT_RES, v2_res, 0x100u >> 2);
    copy_words(H1_COMPAT_SYS, v2_sys, 0x100u >> 2);
    H1_COMPAT_RES[0x094u >> 2] = (h1_u32)compat_return_zero;
    H1_COMPAT_SYS[0x08Cu >> 2] = (h1_u32)compat_legacy_handle_cleanup;
    H1_COMPAT_SYS[0x090u >> 2] = (h1_u32)compat_legacy_handle_address;

    H1_PREFIX[0] = saved[0];
    H1_PREFIX[1] = (h1_u32)H1_COMPAT_GUI;
    H1_PREFIX[2] = (h1_u32)H1_COMPAT_FS;
    H1_PREFIX[3] = (h1_u32)H1_COMPAT_SYS;
    H1_PREFIX[4] = saved[4];
    H1_PREFIX[5] = (h1_u32)H1_COMPAT_RES;
    H1_PREFIX[6] = saved[6];
    H1_PREFIX[7] = saved[7];

    if (game_size == 0u) {
        if (!load_external_game((const char *)game_source, saved[2])) {
            copy_words(H1_PREFIX, saved, 16u);
            return -1;
        }
        game_size = H1_GAME_SIZE;
    } else {
        copy_bytes_forward((volatile h1_u8 *)0x83C00020u, game_source, game_size);
    }

    flush_cache((const volatile h1_u8 *)0x83C00020u, game_size);
    trace_event(TRACE_STAGE_TABLES, (h1_u32)v2_gui, (h1_u32)v2_res,
        (h1_u32)v2_sys, game_size, 0u);
    trace_event(TRACE_GAME_START, (h1_u32)H1_GAME_ENTRY, game_size, 0u, 0u, 0u);
    result = H1_GAME_ENTRY();
    trace_event(TRACE_GAME_RETURN, (h1_u32)H1_GAME_ENTRY, game_size, 0u, 0u,
        (h1_u32)result);

    copy_words(H1_PREFIX, saved, 16u);
    flush_cache((const volatile h1_u8 *)0x83C00000u, 0x40u);
    return (int)result;
}
