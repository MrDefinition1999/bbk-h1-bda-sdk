#ifndef H1_PROBE_DIALOGS_H
#define H1_PROBE_DIALOGS_H

#include "h1_probe_runtime.h"

/* Historical probe wrapper. New applications should include h1_dialogs.h. */
static inline int h1_probe_message_box(
    h1_u32 parent,
    const char *message,
    const char *title,
    h1_u32 style
)
{
    return h1_probe_call4(
        h1_probe_table(H1_GUI_TABLE_SLOT),
        0x2B8u,
        parent,
        (h1_u32)message,
        (h1_u32)title,
        style
    );
}

#endif
