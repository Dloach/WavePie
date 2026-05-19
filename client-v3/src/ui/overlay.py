"""WavePie Overlay v3 — 窗口 + 准星 + 圆环菜单。"""
import math, time, tkinter as tk
from typing import Callable, Optional

SIGHT_INNER = "#FFFFFF"
SIGHT_OUTER = "#6688EE"
SIGHT_LINE  = "#AABBFF"
MENU_RATIO  = 0.40
DEAD_RATIO  = 0.40

class OverlayUI:
    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config; self._on_execute = on_execute
        self._vx,self._vy,self._vw,self._vh = self._get_virtual_screen()
        self.root = tk.Tk()
        self.root.title("WavePie")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.attributes("-transparentcolor", "black")
        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.root.bind("<Escape>", lambda e: self.deactivate())
        self._state = "idle"
        self._cx=self._cy=self._menu_r=self._dead_r=0
        self._sx=self._sy=0; self._ids={}; self._n=6
        self._snap_start=0.0; self._snap_from=(0.0,0.0); self._snap_to=(0.0,0.0); self._snapping=False
        self._idle_geom()

    @staticmethod
    def _get_virtual_screen():
        try: import ctypes; u=ctypes.windll.user32; return u.GetSystemMetrics(76),u.GetSystemMetrics(77),u.GetSystemMetrics(78),u.GetSystemMetrics(79)
        except: return 0,0,1920,1080

    def _get_monitor_bounds(self):
        try:
            import ctypes,struct; from ctypes import wintypes
            pt=wintypes.POINT(); ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            hMon=ctypes.windll.user32.MonitorFromPoint(pt,0)
            buf=ctypes.create_string_buffer(40); ctypes.memset(buf,0,40)
            ctypes.memmove(buf,ctypes.byref(ctypes.c_uint32(40)),4)
            if ctypes.windll.user32.GetMonitorInfoW(hMon,buf): return struct.unpack_from("<llll",buf,4)
        except: pass
        return 0,0,1920,1080

    def _idle_geom(self):
        self.root.geometry("1x1+0+0"); self.root.attributes("-alpha",0.01)

    def _show_geom(self):
        self.root.attributes("-alpha",0.85)
        self.root.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self.root.update_idletasks()
        self._canvas.configure(width=self._vw,height=self._vh)
        self._canvas.pack(); self.root.lift(); self.root.focus_force()

    @property
    def state(self): return self._state
    @property
    def selected_idx(self): return self._selected

    def activate(self, num_sectors=12, labels=None):
        if self._state!="idle": return
        self._state="menu_open"
        l,t,r,b=self._get_monitor_bounds()
        mh=b-t; self._menu_r=mh*MENU_RATIO; self._dead_r=self._menu_r*DEAD_RATIO
        cx,cy=(l+r)//2,(t+b)//2
        self._cx=cx-self._vx; self._cy=cy-self._vy
        self._sx=self._sy=0; self._selected=-1; self._n=max(2,min(12,num_sectors))
        self._menu_labels = labels or [str(i) for i in range(self._n)]
        self._show_geom()
        self._build_menu()
        self._build_sight()
        self.root.lift(); self.root.focus_force()

    def deactivate(self):
        if self._state=="idle": return
        self._state="idle"
        self._canvas.delete("all"); self._ids.clear()
        self._canvas.pack_forget(); self._idle_geom()

    def set_sight(self, rx:float, ry:float):
        if self._state!="menu_open": return
        sx=rx*self._menu_r; sy=ry*self._menu_r
        d=math.hypot(sx,sy)
        if d>self._menu_r: s=self._menu_r/d; sx*=s; sy*=s
        # 实际光标位置
        self._rx, self._ry = sx, sy
        # 扇区检测
        sel = -1
        if d >= self._menu_r * 0.5:
            a = (-math.degrees(math.atan2(sy, sx)) + 360) % 360
            w = 360.0 / self._n
            for i in range(self._n):
                s = (90 - i*w + w/2) % 360
                e = -w
                end = (s + e + 360) % 360
                if end < s:
                    if a >= end and a <= s: sel = i; break
                else:
                    if a >= end or a <= s: sel = i; break
        self._selected = sel
        # 吸附
        snap_d = self._menu_r * 0.6
        in_snap = sel >= 0 and d >= snap_d
        if in_snap:
            ca = math.radians((90 - sel*w) % 360)
            cr = self._menu_r * 0.75
            sx_target = cr * math.cos(ca)
            sy_target = -cr * math.sin(ca)
            if not self._snapping:
                self._snapping = True
                self._snap_start = time.monotonic()
                self._snap_from = (self._sx, self._sy)
                self._snap_to = (sx_target, sy_target)
            elif (self._snap_to[0], self._snap_to[1]) != (sx_target, sy_target):
                self._snap_from = (self._sx, self._sy)
                self._snap_to = (sx_target, sy_target)
                self._snap_start = time.monotonic()
            t = min((time.monotonic() - self._snap_start) / 0.2, 1.0)
            t = t * t * (3 - 2 * t)
            fx, fy = self._snap_from
            tx, ty = self._snap_to
            self._sx = fx + (tx - fx) * t
            self._sy = fy + (ty - fy) * t
        else:
            self._snapping = False
            self._sx, self._sy = sx, sy
        self._update_highlight()
        self._redraw_sight()

    def _update_highlight(self):
        if "sec_fills" not in self._ids: return
        n,ox,oy,mr = self._n,self._cx,self._cy,self._menu_r
        for i in range(n):
            if i < len(self._ids["sec_fills"]):
                if i == self._selected:
                    self._canvas.coords(self._ids["sec_fills"][i],
                        ox-mr,oy-mr,ox+mr,oy+mr)
                else:
                    self._canvas.coords(self._ids["sec_fills"][i],0,0,1,1)

    def _rebuild_sectors(self):
        for key in ("sec_arcs","sec_seps","sec_labels","sec_fills","zero_mark","ring_hole"):
            if key in self._ids:
                if isinstance(self._ids[key], list):
                    for item in self._ids[key]: self._canvas.delete(item)
                else:
                    self._canvas.delete(self._ids[key])
                del self._ids[key]
        self._draw_sectors()
        # 重绘内圆在最上层
        ir=self._menu_r*0.5; ox,oy=self._cx,self._cy
        self._ids["ring_hole"]=self._canvas.create_oval(ox-ir,oy-ir,ox+ir,oy+ir,fill="black",outline="")

    def _draw_sectors(self):
        c,ox,oy,mr=self._canvas,self._cx,self._cy,self._menu_r
        n,ir=self._n,mr*0.5; w=360.0/n
        self._ids["sec_arcs"]=[]; self._ids["sec_seps"]=[]
        for i in range(n):
            s=(90-i*w+w/2)%360
            e=-(w-1)
            self._ids["sec_arcs"].append(c.create_arc(
                ox-mr,oy-mr,ox+mr,oy+mr,start=s,extent=e,
                style="arc",outline="#88BBFF",width=1))
            a0=math.radians(s)
            cs, sn = math.cos(a0), math.sin(a0)
            self._ids["sec_seps"].append(c.create_line(
                ox+ir*cs, oy-ir*sn, ox+mr*cs, oy-mr*sn,
                fill="#88BBFF",width=1))
        # 填充（必须先画，下面再画文字/标记在它之上）
        self._ids["sec_fills"]=[]
        for i in range(n):
            s=(90-i*w+w/2)%360; e=-w
            self._ids["sec_fills"].append(c.create_arc(
                ox-mr,oy-mr,ox+mr,oy+mr,start=s,extent=e,
                fill="#4488FF",outline="",stipple="gray50"))
            self._canvas.coords(self._ids["sec_fills"][i],0,0,1,1)
        # 文字标签（在填充之上）
        cr=(ir+mr)/2
        self._ids["sec_labels"]=[]
        for i in range(n):
            a=math.radians((90-i*w)%360)
            cs,sn=math.cos(a),math.sin(a)
            label = self._menu_labels[i] if i < len(self._menu_labels) else str(i)
            self._ids["sec_labels"].append(c.create_text(
                ox+cr*cs, oy-cr*sn,
                text=label[:8],fill="#FFFFFF",font=("Segoe UI",12,"bold"),anchor="center"))
        r2=mr+16
        self._ids["zero_mark"]=c.create_text(ox,oy-mr-r2,
            text="0",fill="#FFD700",font=("Consolas",10,"bold"),anchor="center")

    def _build_menu(self):
        c,ox,oy,mr=self._canvas,self._cx,self._cy,self._menu_r
        ir=mr*0.5
        self._ids["ring_fill"]=c.create_oval(ox-mr,oy-mr,ox+mr,oy+mr,fill="#0E0E24",outline="#4466DD",width=2)
        self._draw_sectors()
        # 内圆必须画在扇区之上，才能盖住填充块形成圆环效果
        self._ids["ring_hole"]=c.create_oval(ox-ir,oy-ir,ox+ir,oy+ir,fill="black",outline="")

    def _build_sight(self):
        self._ids["dot"]=self._canvas.create_oval(0,0,1,1,fill=SIGHT_INNER,outline="")
        self._ids["ring"]=self._canvas.create_oval(0,0,1,1,fill="",outline=SIGHT_OUTER,width=1.5)
        self._ids["cross"]=[self._canvas.create_line(0,0,1,1,fill=SIGHT_LINE,width=1) for _ in range(4)]

    def _redraw_sight(self):
        if"dot"not in self._ids: return
        sx=self._cx+self._sx; sy=self._cy+self._sy
        r,ro,cl=5,15,12
        self._canvas.coords(self._ids["dot"],sx-r,sy-r,sx+r,sy+r)
        self._canvas.coords(self._ids["ring"],sx-ro,sy-ro,sx+ro,sy+ro)
        for i,(dx,dy)in enumerate([(-1,0),(1,0),(0,-1),(0,1)]):
            self._canvas.coords(self._ids["cross"][i],sx+dx*cl,sy+dy*cl,sx+dx*ro,sy+dy*ro)
