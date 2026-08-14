#ifndef H1_PROBE_INPUT_TIME_H
#define H1_PROBE_INPUT_TIME_H

#include "h1_probe_runtime.h"

#define H1_GUI_RAW_TICK_OFFSET       0x6D8u
#define H1_GUI_TIMER_START_OFFSET    0x714u
#define H1_GUI_TIMER_STOP_OFFSET     0x718u
#define H1_GUI_TIMER_READ_OFFSET     0x71Cu
#define H1_GUI_EVENT_FETCH_OFFSET    0x750u
#define H1_SYS_BUSY_DELAY_OFFSET     0x080u

static inline h1_u32 h1_probe_raw_tick(void)
{
    typedef h1_u32 (*function_type)(void);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_GUI_TABLE_SLOT), H1_GUI_RAW_TICK_OFFSET
    );
    return function();
}

static inline int h1_probe_timer_start(void)
{
    typedef int (*function_type)(void);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_GUI_TABLE_SLOT), H1_GUI_TIMER_START_OFFSET
    );
    return function();
}

static inline int h1_probe_timer_stop(void)
{
    typedef int (*function_type)(void);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_GUI_TABLE_SLOT), H1_GUI_TIMER_STOP_OFFSET
    );
    return function();
}

static inline h1_u32 h1_probe_timer_read(void)
{
    typedef h1_u32 (*function_type)(void);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_GUI_TABLE_SLOT), H1_GUI_TIMER_READ_OFFSET
    );
    return function();
}

static inline int h1_probe_event_fetch(int *code, int *value)
{
    typedef int (*function_type)(int *, int *);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_GUI_TABLE_SLOT), H1_GUI_EVENT_FETCH_OFFSET
    );
    return function(code, value);
}

static inline void h1_probe_busy_delay(h1_u32 duration)
{
    typedef void (*function_type)(h1_u32);
    function_type function = (function_type)h1_probe_entry(
        h1_probe_table(H1_SYS_TABLE_SLOT), H1_SYS_BUSY_DELAY_OFFSET
    );
    function(duration);
}

#endif
