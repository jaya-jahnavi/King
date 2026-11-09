"""Physical-pixel geometry for extended desktops, including negative origins."""
import ctypes
import math


def enable_dpi_awareness():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def bounds(monitor):
    return {key: int(monitor[key]) for key in ('left', 'top', 'width', 'height')}


def contains(monitor, region):
    return (region['width'] > 0 and region['height'] > 0
            and monitor['left'] <= region['left']
            and monitor['top'] <= region['top']
            and region['left']+region['width'] <= monitor['left']+monitor['width']
            and region['top']+region['height'] <= monitor['top']+monitor['height'])


def physical_selection(width, height, shown_width, shown_height, box):
    """Map the actual resized preview back to source pixels without DPI scaling."""
    x, y, w, h = box
    left = max(0, min(width, math.floor(x*width/shown_width)))
    top = max(0, min(height, math.floor(y*height/shown_height)))
    right = max(0, min(width, math.ceil((x+w)*width/shown_width)))
    bottom = max(0, min(height, math.ceil((y+h)*height/shown_height)))
    if right <= left or bottom <= top:
        raise ValueError('Select a nonempty area inside the screen')
    return left, top, right-left, bottom-top


def capture_region(monitor, box):
    x, y, w, h = box
    region = dict(left=monitor['left']+x, top=monitor['top']+y, width=w, height=h)
    if x < 0 or y < 0 or not contains(monitor, region):
        raise ValueError('Selected area is outside this display')
    return region
