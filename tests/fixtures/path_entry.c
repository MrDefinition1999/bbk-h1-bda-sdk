static const char source_path[] = __FILE__;
static const char *volatile retained_path = source_path;

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    return retained_path[0];
}
