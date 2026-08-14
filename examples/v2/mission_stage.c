typedef unsigned char h1_u8;
typedef unsigned int h1_u32;

#define H1_PREFIX ((volatile h1_u32 *)0x83C00000u)
#define H1_COMPAT_GUI ((volatile h1_u32 *)0x83E00000u)
#define H1_COMPAT_RES ((volatile h1_u32 *)0x83E01000u)
#define H1_STAGE_DATA ((volatile h1_u32 *)0x83F10000u)
#define H1_STAGE_TRACE ((volatile h1_u32 *)0xA3F10F00u)
#define H1_MISSION_ENTRY ((int (*)(void))0x83C00020u)
#define H1_MISSION_SIZE 0x79374u

static void copy_words(volatile h1_u32 *destination, const volatile h1_u32 *source, h1_u32 words)
{
    while (words != 0u) {
        *destination++ = *source++;
        --words;
    }
}

static void copy_bytes_forward(volatile h1_u8 *destination, const volatile h1_u8 *source, h1_u32 size)
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

static int mission_res_return_zero(h1_u32 a0, h1_u32 a1, h1_u32 a2, h1_u32 a3)
{
    (void)a0;
    (void)a1;
    (void)a2;
    (void)a3;
    return 0;
}

/* V1 calls these only while entering/leaving its game display mode. */
static int mission_game_open(h1_u32 a0, h1_u32 a1, h1_u32 a2, h1_u32 a3)
{
    (void)a0;
    (void)a1;
    (void)a2;
    (void)a3;
    return 1;
}

static int mission_game_close(h1_u32 a0, h1_u32 a1, h1_u32 a2, h1_u32 a3)
{
    (void)a0;
    (void)a1;
    (void)a2;
    (void)a3;
    return 1;
}

static void map_gui(volatile h1_u32 *compat, const volatile h1_u32 *v2, h1_u32 v1_offset, h1_u32 v2_offset)
{
    compat[v1_offset >> 2] = v2[v2_offset >> 2];
}

static int load_external_mission(const char *path, h1_u32 fs_table)
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

    H1_STAGE_TRACE[0] = 0x46534F50u;
    H1_STAGE_TRACE[1] = fs_table;
    H1_STAGE_TRACE[2] = (h1_u32)open_file;
    H1_STAGE_TRACE[3] = (h1_u32)close_file;
    H1_STAGE_TRACE[4] = (h1_u32)read_file;
    H1_STAGE_TRACE[5] = (h1_u32)path;
    file = open_file(path, mode);
    H1_STAGE_TRACE[0] = 0x46534F4Bu;
    H1_STAGE_TRACE[6] = (h1_u32)file;

    if (file == (void *)0) {
        return 0;
    }
    H1_STAGE_TRACE[0] = 0x46535244u;
    read = read_file((void *)0x83C00020u, 1u, H1_MISSION_SIZE, file);
    H1_STAGE_TRACE[0] = 0x4653524Bu;
    H1_STAGE_TRACE[7] = read;
    close_file(file);
    H1_STAGE_TRACE[0] = 0x4653434Cu;
    return read == H1_MISSION_SIZE;
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(const h1_u8 *mission_source, h1_u32 mission_size)
{
    volatile h1_u32 *saved = H1_STAGE_DATA;
    volatile h1_u32 *v2_gui;
    volatile h1_u32 *v2_res;
    h1_u32 result;

    H1_STAGE_TRACE[0] = 0x53544730u;

    /* Preserve every V2 prefix word before installing the V1 view. */
    copy_words(saved, H1_PREFIX, 16u);
    v2_gui = (volatile h1_u32 *)saved[1];
    v2_res = (volatile h1_u32 *)saved[5];
    copy_words(H1_COMPAT_GUI, v2_gui, 0xB00u >> 2);
    copy_words(H1_COMPAT_RES, v2_res, 0x100u >> 2);

    map_gui(H1_COMPAT_GUI, v2_gui, 0x2B8u, 0x2B0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x6A8u, 0x6A8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x6E0u, 0x6E0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0xAD8u, 0x95Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0xADCu, 0x960u);

    /* V1's large graphics block is a stable -0x114 table rebase. */
    map_gui(H1_COMPAT_GUI, v2_gui, 0x84Cu, 0x738u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x850u, 0x73Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x854u, 0x740u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x858u, 0x744u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x85Cu, 0x748u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x860u, 0x74Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x864u, 0x750u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x87Cu, 0x768u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x880u, 0x76Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x884u, 0x770u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x888u, 0x774u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x88Cu, 0x778u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x890u, 0x77Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x894u, 0x780u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x898u, 0x784u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x89Cu, 0x788u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8A0u, 0x78Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8A8u, 0x794u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8BCu, 0x7A8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8C0u, 0x7ACu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8C4u, 0x7B0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8C8u, 0x7B4u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8DCu, 0x7C8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8E0u, 0x7CCu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8E4u, 0x7D0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8F4u, 0x7E0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8F8u, 0x7E4u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x8FCu, 0x7E8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x900u, 0x7ECu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x908u, 0x7F4u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x910u, 0x7FCu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x914u, 0x800u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x91Cu, 0x808u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x924u, 0x810u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x934u, 0x820u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x940u, 0x82Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x944u, 0x830u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x94Cu, 0x838u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x98Cu, 0x878u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x990u, 0x87Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x994u, 0x880u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x998u, 0x884u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x99Cu, 0x888u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9A0u, 0x88Cu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9A4u, 0x890u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9BCu, 0x8A8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9C0u, 0x8ACu);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9C4u, 0x8B0u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9D8u, 0x8C4u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9DCu, 0x8C8u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9E8u, 0x8D4u);
    map_gui(H1_COMPAT_GUI, v2_gui, 0x9F4u, 0x8E0u);

    H1_COMPAT_GUI[0xAA4u >> 2] = (h1_u32)mission_game_open;
    H1_COMPAT_GUI[0xAA8u >> 2] = (h1_u32)mission_game_close;
    H1_COMPAT_RES[0x094u >> 2] = (h1_u32)mission_res_return_zero;

    H1_PREFIX[0] = saved[0];
    H1_PREFIX[1] = (h1_u32)H1_COMPAT_GUI;
    H1_PREFIX[2] = saved[2];
    H1_PREFIX[3] = saved[3];
    H1_PREFIX[4] = saved[4];
    H1_PREFIX[5] = (h1_u32)H1_COMPAT_RES;
    H1_PREFIX[6] = saved[6];
    H1_PREFIX[7] = saved[7];

    if (mission_size == 0u) {
        if (!load_external_mission((const char *)mission_source, saved[2])) {
            copy_words(H1_PREFIX, saved, 16u);
            return -1;
        }
        mission_size = H1_MISSION_SIZE;
    } else {
        /* The destination overlaps the entry BDA but is below its source. */
        copy_bytes_forward((volatile h1_u8 *)0x83C00020u, mission_source, mission_size);
    }
    flush_cache((const volatile h1_u8 *)0x83C00020u, mission_size);
    H1_STAGE_TRACE[0] = 0x4D495331u;
    result = H1_MISSION_ENTRY();
    H1_STAGE_TRACE[0] = 0x4D495352u;

    copy_words(H1_PREFIX, saved, 16u);
    flush_cache((const volatile h1_u8 *)0x83C00000u, 0x40u);
    return (int)result;
}
