#include "h1_probe_dialogs.h"
#include "h1_probe_graphics.h"

#define TEST_X 160
#define TEST_Y 72
#define TEST_WIDTH 160
#define TEST_HEIGHT 112

static h1_u16 pixels[TEST_WIDTH * TEST_HEIGHT];
static h1_u16 readback[TEST_WIDTH * TEST_HEIGHT];

static h1_u16 test_pixel(int x, int y)
{
    if (x < TEST_WIDTH / 2 && y < TEST_HEIGHT / 2) {
        return 0xF800u;
    }
    if (x >= TEST_WIDTH / 2 && y < TEST_HEIGHT / 2) {
        return 0x07E0u;
    }
    if (x < TEST_WIDTH / 2) {
        return 0x001Fu;
    }
    if (((x / 8) ^ (y / 8)) & 1) {
        return 0xFFFFu;
    }
    return 0x0000u;
}

static int buffers_equal(void)
{
    int index;
    for (index = 0; index < TEST_WIDTH * TEST_HEIGHT; ++index) {
        if (pixels[index] != readback[index]) {
            return 0;
        }
    }
    return 1;
}

__attribute__((section(".text.h1_bda_entry"), used))
int h1_bda_main(void)
{
    static const char title[] = "H1 Graphics Probe";
    static const char passed[] =
        "PASS\n"
        "RGB565 blit/readback\n"
        "480x272 present path";
    static const char failed[] = "FAIL: RGB565 readback mismatch";
    int x;
    int y;

    for (y = 0; y < TEST_HEIGHT; ++y) {
        for (x = 0; x < TEST_WIDTH; ++x) {
            pixels[y * TEST_WIDTH + x] = test_pixel(x, y);
        }
    }

    h1_probe_blit_rgb565(TEST_X, TEST_Y, TEST_WIDTH, TEST_HEIGHT, pixels);
    h1_probe_present_region(
        TEST_X,
        TEST_Y,
        TEST_X + TEST_WIDTH - 1,
        TEST_Y + TEST_HEIGHT - 1
    );
    h1_probe_read_rgb565(
        TEST_X,
        TEST_Y,
        TEST_WIDTH,
        TEST_HEIGHT,
        readback
    );

    return h1_probe_message_box(
        0,
        buffers_equal() ? passed : failed,
        title,
        0
    );
}
