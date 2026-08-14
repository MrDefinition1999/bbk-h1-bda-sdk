__attribute__((section(".h1_noinit.a320_stack"), used))
unsigned char guest_stack[0x80000];

__attribute__((section(".h1_noinit.a320_arena"), aligned(0x10000), used))
unsigned char guest_arena[0x10000];

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    return guest_stack[0] + guest_arena[0];
}
