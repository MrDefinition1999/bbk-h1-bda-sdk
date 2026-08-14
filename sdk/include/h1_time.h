#ifndef H1_TIME_H
#define H1_TIME_H

#include "h1_runtime.h"

#define H1_GUI_RAW_TICK_OFFSET    0x6D8u
#define H1_GUI_TIMER_START_OFFSET 0x714u
#define H1_GUI_TIMER_STOP_OFFSET  0x718u
#define H1_GUI_TIMER_READ_OFFSET  0x71Cu

static inline h1_u32 h1_raw_tick_80hz(void)
{
    typedef h1_u32 (*function_type)(void);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_RAW_TICK_OFFSET
    );
    return function();
}

static inline void h1_timer_start(void)
{
    typedef void (*function_type)(void);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_TIMER_START_OFFSET
    );
    function();
}

static inline void h1_timer_stop(void)
{
    typedef void (*function_type)(void);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_TIMER_STOP_OFFSET
    );
    function();
}

static inline h1_u32 h1_timer_read_ms(void)
{
    typedef h1_u32 (*function_type)(void);
    function_type function = (function_type)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_TIMER_READ_OFFSET
    );
    return function();
}

#endif
