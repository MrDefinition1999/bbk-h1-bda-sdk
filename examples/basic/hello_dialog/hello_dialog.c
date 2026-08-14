#include "h1_sdk.h"

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char title[] = "H1 SDK Test";
    static const char message[] =
        "Native BDA is running.\n"
        "Press OK to return.";

    return h1_message_box(0, message, title, 0);
}
