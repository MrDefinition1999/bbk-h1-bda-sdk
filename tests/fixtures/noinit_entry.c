__attribute__((section(".h1_noinit")))
static volatile unsigned char arena[2 * 1024 * 1024];

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    arena[0] = 0x12;
    arena[sizeof(arena) - 1] = 0x34;
    return arena[0] + arena[sizeof(arena) - 1];
}
