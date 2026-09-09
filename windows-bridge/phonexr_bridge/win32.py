"""Checked Win32 touch injection; explicit mouse compatibility mode."""
import ctypes as C
import os
import logging

U32, I32, U64 = C.c_uint32, C.c_int32, C.c_uint64

class POINT(C.Structure):
    _fields_ = [('x', I32), ('y', I32)]

class RECT(C.Structure):
    _fields_ = [('left', I32), ('top', I32), ('right', I32), ('bottom', I32)]

class POINTER_INFO(C.Structure):
    _fields_ = [('pointerType', U32), ('pointerId', U32), ('frameId', U32), ('pointerFlags', U32), ('sourceDevice', C.c_void_p), ('hwndTarget', C.c_void_p), ('ptPixelLocation', POINT), ('ptHimetricLocation', POINT), ('ptPixelLocationRaw', POINT), ('ptHimetricLocationRaw', POINT), ('dwTime', U32), ('historyCount', U32), ('InputData', I32), ('dwKeyStates', U32), ('PerformanceCount', U64), ('ButtonChangeType', U32)]

class TOUCH(C.Structure):
    _fields_ = [('pointerInfo', POINTER_INFO), ('touchFlags', U32), ('touchMask', U32), ('rcContact', RECT), ('rcContactRaw', RECT), ('orientation', U32), ('pressure', U32)]

class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', I32), ('dy', I32), ('mouseData', U32), ('dwFlags', U32), ('time', U32), ('dwExtraInfo', C.c_size_t)]

class INPUTUNION(C.Union):
    _fields_ = [('mi', MOUSEINPUT), ('padding', C.c_byte * C.sizeof(MOUSEINPUT))]

class INPUT(C.Structure):
    _fields_ = [('type', U32), ('data', INPUTUNION)]

class WindowsSink:
    def __init__(self, mouse=False):
        if os.name != 'nt':
            raise RuntimeError('Input bridge requires Windows 10/11')
        self.api = C.WinDLL('user32', use_last_error=True)
        self.mouse = mouse
        self.api.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
        self.api.SetProcessDpiAwarenessContext(C.c_void_p(-4))
        self.api.InitializeTouchInjection.argtypes = [U32, U32]
        self.api.InjectTouchInput.argtypes = [U32, C.POINTER(TOUCH)]
        self.api.SendInput.argtypes = [U32, C.POINTER(INPUT), I32]
        self.api.SendInput.restype = U32
        self.api.IsWindow.argtypes = [C.c_void_p]
        self.api.IsWindowVisible.argtypes = [C.c_void_p]
        self.api.GetWindowRect.argtypes = [C.c_void_p, C.POINTER(RECT)]
        self.api.WindowFromPoint.argtypes = [POINT]
        self.api.WindowFromPoint.restype = C.c_void_p
        self.api.GetAncestor.argtypes = [C.c_void_p, U32]
        self.api.GetAncestor.restype = C.c_void_p
        if not mouse and not self.api.InitializeTouchInjection(1, 3):
            raise C.WinError(C.get_last_error())

    def valid(self, panel, xy):
        x,y = xy
        vx,vy,vw,vh = [self.api.GetSystemMetrics(i) for i in (76,77,78,79)]
        if not vx <= x < vx+vw or not vy <= y < vy+vh:
            return False
        hwnd = int(panel['hwnd'])
        if hwnd:
            rect = RECT()
            if not self.api.IsWindow(hwnd) or not self.api.IsWindowVisible(hwnd) or not self.api.GetWindowRect(hwnd, C.byref(rect)):
                return False
            if not rect.left <= x < rect.right or not rect.top <= y < rect.bottom:
                return False
            actual = self.api.WindowFromPoint(POINT(x,y))
            if self.api.GetAncestor(actual, 2) != self.api.GetAncestor(hwnd, 2):
                return False
        return True

    def emit(self, phase, xy):
        x,y = xy
        if self.mouse:
            vx,vy,vw,vh = [self.api.GetSystemMetrics(i) for i in (76,77,78,79)]
            event = INPUT()
            event.type = 0
            event.data.mi = MOUSEINPUT(round((x-vx)*65535/max(1,vw-1)), round((y-vy)*65535/max(1,vh-1)), 0, 0x8000|0x4000|1|{'down':2,'update':0,'up':4}[phase], 0, 0)
            ok = self.api.SendInput(1, C.byref(event), C.sizeof(event)) == 1
        else:
            event = TOUCH()
            event.pointerInfo.pointerType = 2
            event.pointerInfo.pointerId = 1
            event.pointerInfo.pointerFlags = {'down':0x10000|2|4, 'update':0x20000|2|4, 'up':0x40000}[phase]
            event.pointerInfo.ptPixelLocation = POINT(x,y)
            event.touchMask = 1|2|4
            event.rcContact = RECT(x-2,y-2,x+2,y+2)
            event.orientation, event.pressure = 90, 512
            ok = bool(self.api.InjectTouchInput(1, C.byref(event)))
        if not ok:
            logging.error('Input %s failed: Win32 error %d', phase, C.get_last_error())
        return ok
