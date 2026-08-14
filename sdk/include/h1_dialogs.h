#ifndef H1_DIALOGS_H
#define H1_DIALOGS_H

#include "h1_runtime.h"

#define H1_GUI_MESSAGE_BOX_OFFSET 0x2B8u

typedef int (*h1_message_box_fn)(
    h1_u32 parent,
    const char *message,
    const char *title,
    h1_u32 flags
);

static inline int h1_message_box(
    h1_u32 parent,
    const char *message,
    const char *title,
    h1_u32 flags
)
{
    h1_message_box_fn function = (h1_message_box_fn)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_MESSAGE_BOX_OFFSET
    );
    return function(parent, message, title, flags);
}

#endif
