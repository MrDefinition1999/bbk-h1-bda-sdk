#ifndef H1_INPUT_H
#define H1_INPUT_H

#include "h1_runtime.h"

#define H1_GUI_EVENT_FETCH_OFFSET 0x750u

#define H1_EVENT_TIMER    3
#define H1_EVENT_KEY_DOWN 9
#define H1_EVENT_KEY_UP   10

/* H1 full-keyboard matrix values used by the emulator and native firmware. */
#define H1_KEY_Q       1
#define H1_KEY_W       2
#define H1_KEY_E       3
#define H1_KEY_R       4
#define H1_KEY_T       5
#define H1_KEY_Y       6
#define H1_KEY_U       7
#define H1_KEY_A       8
#define H1_KEY_S       9
#define H1_KEY_D       10
#define H1_KEY_F       11
#define H1_KEY_G       12
#define H1_KEY_H       13
#define H1_KEY_J       14
#define H1_KEY_PAGE_UP 15
#define H1_KEY_Z       16
#define H1_KEY_X       17
#define H1_KEY_C       18
#define H1_KEY_V       19
#define H1_KEY_B       20
#define H1_KEY_N       21
#define H1_KEY_PAGE_DOWN 22
#define H1_KEY_SPACE   23
#define H1_KEY_ESCAPE  24
#define H1_KEY_ENTER   25
#define H1_KEY_LEFT_ALT 26
#define H1_KEY_DOWN    27
#define H1_KEY_RIGHT_ALT 28
#define H1_KEY_I       29
#define H1_KEY_O       30
#define H1_KEY_P       31
#define H1_KEY_K       32
#define H1_KEY_L       33
#define H1_KEY_SYMBOL  34
#define H1_KEY_RIGHT   35
#define H1_KEY_M       36
#define H1_KEY_UP      37
#define H1_KEY_DELETE  38
#define H1_KEY_CONFIRM 39
#define H1_KEY_LEFT    40
#define H1_KEY_BACK    41
#define H1_KEY_SHIFT   42
#define H1_KEY_FN      43
#define H1_KEY_POWER   44

static inline int h1_event_fetch(int *code, int *value)
{
    typedef int (*function_type)(int *, int *);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_EVENT_FETCH_OFFSET
    );
    return function(code, value);
}

/* Returns 1 for one key transition, 0 when no key transition is available. */
static inline int h1_input_poll_key(int *pressed, int *key)
{
    int code;
    int value;
    int attempt;

    for (attempt = 0; attempt < 32; ++attempt) {
        h1_event_fetch(&code, &value);
        if (code == -1 && value == -1) {
            return 0;
        }
        if (code == H1_EVENT_KEY_DOWN || code == H1_EVENT_KEY_UP) {
            *pressed = code == H1_EVENT_KEY_DOWN;
            *key = value;
            return 1;
        }
    }
    return 0;
}

#endif
