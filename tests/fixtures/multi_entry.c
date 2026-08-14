extern int h1_multi_helper(int value);

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    return h1_multi_helper(40);
}
