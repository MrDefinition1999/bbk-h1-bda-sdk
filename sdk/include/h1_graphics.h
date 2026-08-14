#ifndef H1_GRAPHICS_H
#define H1_GRAPHICS_H

#include "h1_runtime.h"

#define H1_SCREEN_WIDTH  480
#define H1_SCREEN_HEIGHT 272

#define H1_GUI_PRESENT_REGION_OFFSET 0x070u
#define H1_GUI_READ_RGB565_OFFSET    0x3F8u
#define H1_GUI_BLIT_RGB565_OFFSET    0x400u

typedef int (*h1_rgb565_pixels_fn)(
    int x,
    int y,
    int width,
    int height,
    h1_u16 *pixels
);

typedef int (*h1_present_region_fn)(int x1, int y1, int x2, int y2);

static inline int h1_blit_rgb565(
    int x,
    int y,
    int width,
    int height,
    const h1_u16 *pixels
)
{
    h1_rgb565_pixels_fn function = (h1_rgb565_pixels_fn)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_BLIT_RGB565_OFFSET
    );
    return function(x, y, width, height, (h1_u16 *)pixels);
}

static inline int h1_read_rgb565(
    int x,
    int y,
    int width,
    int height,
    h1_u16 *pixels
)
{
    h1_rgb565_pixels_fn function = (h1_rgb565_pixels_fn)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_READ_RGB565_OFFSET
    );
    return function(x, y, width, height, pixels);
}

static inline int h1_present_region(int x1, int y1, int x2, int y2)
{
    h1_present_region_fn function = (h1_present_region_fn)h1_runtime_entry(
        h1_runtime_table(H1_RUNTIME_GUI_TABLE_SLOT),
        H1_GUI_PRESENT_REGION_OFFSET
    );
    return function(x1, y1, x2, y2);
}

static inline int h1_present_full_screen(void)
{
    return h1_present_region(0, 0, 0, 0);
}

#endif
