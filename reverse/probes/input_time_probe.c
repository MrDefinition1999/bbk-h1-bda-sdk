#include "h1_probe_dialogs.h"
#include "h1_probe_filesystem.h"
#include "h1_probe_input_time.h"

#define H1_INPUT_TIME_MAGIC   0x54493148u
#define H1_INPUT_TIME_VERSION 1u
#define H1_INPUT_TIME_EVENTS    128u
#define H1_INPUT_TIME_CAPTURE_MS 12000u
#define H1_INPUT_TIME_GUARD      100000000u
#define H1_INPUT_TIME_REPORT_VA  0x83C10000u

struct h1_input_time_event {
    h1_u32 raw_tick;
    h1_u32 timer_count;
    int code;
    int value;
};

struct h1_input_time_report {
    h1_u32 magic;
    h1_u32 version;
    h1_u32 size;
    int timer_start_result;
    int timer_stop_result;
    h1_u32 raw_tick_start;
    h1_u32 raw_tick_end;
    h1_u32 timer_start;
    h1_u32 timer_end;
    h1_u32 loop_count;
    h1_u32 event_count;
    struct h1_input_time_event events[H1_INPUT_TIME_EVENTS];
};

#define report (*(volatile struct h1_input_time_report *)H1_INPUT_TIME_REPORT_VA)

static void drain_old_events(void)
{
    int code;
    int value;
    h1_u32 count;

    for (count = 0; count < 64u; ++count) {
        h1_probe_event_fetch(&code, &value);
        if (code == -1 && value == -1) {
            break;
        }
    }
}

static void capture_event(void)
{
    int code;
    int value;
    h1_u32 count;

    for (count = 0; count < 8u; ++count) {
        h1_probe_event_fetch(&code, &value);
        if (code == -1 && value == -1) {
            return;
        }
        /* The H1 queue emits a 1 ms housekeeping event while this timer runs. */
        if (code == 3 && value == 0) {
            continue;
        }
        if (report.event_count < H1_INPUT_TIME_EVENTS) {
            volatile struct h1_input_time_event *event =
                &report.events[report.event_count++];
            event->raw_tick = h1_probe_raw_tick();
            event->timer_count = h1_probe_timer_read();
            event->code = code;
            event->value = value;
        }
    }
}

static int save_report(void)
{
    static const char path[] = "A:\\H1INPT.BIN";
    static const char mode[] = "wb";
    h1_probe_file *file;
    h1_u32 written;

    h1_probe_remove(path);
    file = h1_probe_fopen(path, mode);
    if (!file) {
        return 0;
    }
    written = h1_probe_fwrite((const void *)&report, 1, sizeof(report), file);
    if (h1_probe_fclose(file) != 0) {
        return 0;
    }
    return written == sizeof(report);
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char title[] = "H1 Input/Time Probe";
    static const char passed[] =
        "PASS: capture saved\n"
        "A:\\H1INPT.BIN";
    static const char failed[] = "FAIL: cannot save capture";
    h1_u32 loop;

    report.magic = H1_INPUT_TIME_MAGIC;
    report.version = H1_INPUT_TIME_VERSION;
    report.size = sizeof(report);
    report.event_count = 0;
    report.loop_count = 0;

    drain_old_events();
    report.timer_start_result = h1_probe_timer_start();
    report.raw_tick_start = h1_probe_raw_tick();
    report.timer_start = h1_probe_timer_read();

    for (loop = 0; loop < H1_INPUT_TIME_GUARD; ++loop) {
        capture_event();
        if ((h1_u32)(h1_probe_timer_read() - report.timer_start)
            >= H1_INPUT_TIME_CAPTURE_MS) {
            break;
        }
        h1_probe_busy_delay(1u);
    }

    capture_event();
    report.loop_count = loop;
    report.raw_tick_end = h1_probe_raw_tick();
    report.timer_end = h1_probe_timer_read();
    report.timer_stop_result = h1_probe_timer_stop();

    return h1_probe_message_box(
        0,
        save_report() ? passed : failed,
        title,
        0
    );
}
