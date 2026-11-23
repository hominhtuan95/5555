"""Chẩn đoán giao diện ngoại tuyến. Không dùng Windows API, không quét cửa sổ, không gửi phím/chuột."""
import json
import math
from datetime import datetime
from tkinter import filedialog
import sys
import threading
import random
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
CONFIG = Path.home() / 'AutoTrainMil4NV_MoPhong_config.json'
PATTERNS=['BB DD CC AA','DD CC DD CC','EE DD BB HH','AA BB DD CC','HH DD EE CC','GG AA FF BB','BB HH DD EE','CC GG AA FF','FF BB HH DD','EE CC GG AA','DD EE CC GG','AA FF BB HH','HH BB FF AA','CC EE DD HH','GG CC EE DD','BB DD EE CC','FF AA GG CC','DD HH BB FF','EE GG CC AA','AA CC DD BB']
SKILLS=[f'Skill {i}' for i in range(1,6)]
TIMED=SKILLS+['Bay chỗ khác (8)','Bơm Máu (9)','Bơm Mana (0)']

class Character:
    def __init__(self, app, index, parent, saved):
        self.app=app; self.index=index; self.running=threading.Event(); self.thread=None
        self.hwnds={}; self.checks={}; self.intervals={}
        self.sim=None; self.timer=None
        self.route_view=tk.StringVar(value='Lộ trình: —')
        # Toàn bộ tùy chọn nằm ngay trong ô nhân vật, không mở cửa sổ phụ.
        self.frame=tk.LabelFrame(parent,text=f'NHÂN VẬT {index}',font=('Segoe UI',8,'bold'),
                                 bg='white',fg='#075bb7',padx=3,pady=1,bd=2,relief='groove',highlightthickness=2,highlightbackground='#00a72c')
        self.frame.grid(row=(index-1)//2,column=(index-1)%2,sticky='nsew',padx=2,pady=1)
        # Nút BẬT/TẮT AUTO luôn ở vị trí đầu tiên trong mỗi ô nhân vật.
        self.button=tk.Button(self.frame,text='▶ MÔ PHỎNG',command=self.toggle,bg='#078d28',fg='white',
                              activebackground='#0b9e34',activeforeground='white',font=('Segoe UI',9,'bold'),height=1)
        self.button.pack(fill='x',pady=(0,2))
        self.window=tk.StringVar(value=saved.get('window',''))
        self.combo=ttk.Combobox(self.frame,textvariable=self.window,state='readonly',width=15,
                                font=('Segoe UI',8))
        self.combo.pack(fill='x',pady=(0,1))
        for label,key in [('Bật lùa quái Cự Thú, Thiên Ngoại Ảo','move'),
                          ('Tìm Quái và Đi Cổ Mộ','find')]:
            self.checks[key]=tk.BooleanVar(value=saved.get(key,False))
        for label in ['Nhặt Đồ']+TIMED:
            self.checks[label]=tk.BooleanVar(value=saved.get('enabled',{}).get(label,label=='Nhặt Đồ'))
            if label in TIMED:
                default='180' if label.startswith('Bay') else '2'
                self.intervals[label]=tk.StringVar(value=str(saved.get('intervals',{}).get(label,default)))
        for label,key in [('Lùa quái Cự Thú / Thiên Ngoại Ảo','move'),
                          ('Tìm quái / Cổ Mộ','find')]:
            tk.Checkbutton(self.frame,text=label,variable=self.checks[key],bg='white',
                           fg='#9d2921',font=('Segoe UI',7,'bold'),anchor='w',
                           padx=0,pady=0).pack(fill='x')
        tk.Frame(self.frame,height=1,bg='#c4ddf4').pack(fill='x',pady=1)
        skills=tk.Frame(self.frame,bg='white');skills.pack(fill='x')
        skills.columnconfigure(0,weight=1)
        tk.Label(skills,text='Tính năng',bg='white',fg='#43698e',font=('Segoe UI',7,'bold')).grid(row=0,column=0,sticky='w')
        tk.Label(skills,text='Giây',bg='white',fg='#43698e',font=('Segoe UI',7,'bold')).grid(row=0,column=1)
        for ri,label in enumerate(['Nhặt Đồ']+TIMED,1):
            tk.Checkbutton(skills,text=label,variable=self.checks[label],bg='white',
                           font=('Segoe UI',7),anchor='w',padx=0,pady=0).grid(row=ri,column=0,sticky='w',pady=0)
            if label in TIMED:
                tk.Entry(skills,textvariable=self.intervals[label],width=6,
                         font=('Segoe UI',7),justify='center',relief='solid',bd=1).grid(row=ri,column=1,sticky='e',padx=(2,1),pady=0)
        tk.Label(self.frame,textvariable=self.route_view,bg='white',fg='#17632c',font=('Segoe UI',7,'bold'),anchor='w').pack(fill='x')
        self.status=tk.StringVar(value='Sẵn sàng (ngoại tuyến)')
        tk.Label(self.frame,textvariable=self.status,bg='white',fg='#44617a',
                 font=('Segoe UI',7,'bold'),wraplength=230,anchor='w').pack(fill='x',pady=(1,0))

    def refresh(self, options=None):
        self.hwnds = {}
        self.combo['values'] = ['Chế độ xem giao diện']
        self.window.set('Chế độ xem giao diện')

    def settings(self):
        return {'window':self.window.get(),'move':self.checks['move'].get(),
                'find':self.checks['find'].get(),
                'enabled':{k:v.get() for k,v in self.checks.items() if k not in ('move','find')},
                'intervals':{k:v.get() for k,v in self.intervals.items()}}

    def toggle(self):
        if self.sim is not None:
            self.stop()
            return
        try:
            intervals = {name: float(v.get().replace(',', '.')) for name, v in self.intervals.items()}
            if any(not math.isfinite(x) or not (0.1 <= x <= 10800) for x in intervals.values()):
                raise ValueError()
        except ValueError:
            messagebox.showwarning('Thời gian không hợp lệ', 'Nhập thời gian từ 0,1 đến 10800 giây.')
            return
        self.app.save()
        self.app.log(self.index, 'Bắt đầu mô phỏng')
        self.app.lab_event(self.index, 'start')
        flags = {name: v.get() for name, v in self.checks.items()}
        self.sim = {'flags': flags, 'intervals': intervals, 'route': '', 'i': 0,
                    'phase': 'moving' if flags['move'] else 'idle',
                    'start': time.monotonic(), 'next': time.monotonic(),
                    'fight_start': 0, 'f1': 0, 'return_at': time.monotonic()+300,
                    'return_step': 0, 'return_until': 0,
                    'last_skill': {}, 'count': 0}
        self._new_route()
        self.button.config(text='■ DỪNG MÔ PHỎNG', bg='#d44444')
        self._tick()

    def _new_route(self):
        if self.sim is None: return
        self.sim['route'] = ''.join(t[0]*2 for t in random.choice(PATTERNS).split()[:3])
        self.sim['i'] = 0
        self.route_view.set('Lộ trình: ' + ' → '.join(self.sim['route'][i] for i in (0,2,4)))
        self.app.log(self.index, 'Chọn lộ trình ' + self.sim['route'])
        self.app.lab_event(self.index, 'route', self.sim['route'])

    def _tick(self):
        s = self.sim
        if s is None: return
        now = time.monotonic()
        if s['flags']['move'] and now >= s['return_at'] and s['phase'] not in ('return_click', 'return_wait', 'return_escape', 'return_pause'):
            s['phase']='return_click'; s['return_step']=0; s['next']=now
            self.status.set('Mô phỏng Alt+D (không gửi phím)')
            self.app.log(self.index, 'Bắt đầu chu kỳ về trung tâm: Alt+D giả lập')
            self.app.lab_event(self.index, 'return')
        phase=s['phase']
        if phase == 'return_click' and now >= s['next']:
            s['return_step']+=1
            self.status.set(f'Mô phỏng nhấp trung tâm {s["return_step"]}/10')
            s['next']=now+0.25
            if s['return_step']>=10:
                s['phase']='return_wait'; s['return_until']=now+30
                self.app.log(self.index, 'Hoàn tất 10 nhấp giả lập, chờ 30 giây')
        elif phase == 'return_wait':
            self.status.set(f'Mô phỏng chờ trung tâm: {max(0,int(s["return_until"]-now))}s')
            if now>=s['return_until']:
                s['phase']='return_escape'; s['return_step']=0; s['next']=now
        elif phase == 'return_escape' and now>=s['next']:
            s['return_step']+=1
            self.status.set(f'Mô phỏng Esc {s["return_step"]}/2')
            s['next']=now+0.25
            if s['return_step']>=2:
                s['phase']='return_pause'; s['return_until']=now+2
                self.app.log(self.index, 'Hoàn tất 2 Esc giả lập, chờ 2 giây')
        elif phase == 'return_pause' and now>=s['return_until']:
            self._new_route(); s['phase']='moving'; s['next']=now; s['return_at']=now+300
        elif phase == 'moving' and now>=s['next']:
            letter=s['route'][s['i']]; s['i']+=1; s['count']+=1
            self.status.set(f'Mô phỏng điểm {letter}: {s["i"]}/6 • lượt {s["count"]}')
            self.app.log(self.index, f'Điểm {letter} ({s["i"]}/6), tổng {s["count"]}')
            self.app.lab_event(self.index, 'point', letter)
            s['next']=now+random.choice((2,2.5,3))
            if s['i']>=len(s['route']):
                s['phase']='fighting'; s['fight_start']=now; s['f1']=0
                self.app.log(self.index, 'Đứng đánh giả lập 15 giây')
        elif phase == 'fighting':
            elapsed=now-s['fight_start']
            if elapsed>=15:
                self._new_route(); s['phase']='moving'; s['next']=now
            elif s['f1']<6 and elapsed>=3+2*s['f1']:
                s['f1']+=1
                self.status.set(f'Mô phỏng F1 {s["f1"]}/6 • đứng 15s')
                self.app.log(self.index, f'F1 giả lập {s["f1"]}/6')
                self.app.lab_event(self.index, 'skill', 'F1')
        elif phase == 'idle':
            self.status.set('Mô phỏng đang chạy • không chọn lùa quái')
        # Only show simulated events, never send OS input or inspect processes/windows.
        if s['phase'] not in ('return_click','return_wait','return_escape','return_pause'):
            for name, enabled in s['flags'].items():
                if not enabled or name in ('move','find','Nhặt Đồ'): continue
                period=s['intervals'].get(name, 2)
                if now-s['last_skill'].get(name, s['start']) >= period:
                    s['last_skill'][name]=now
                    self.app.log(self.index, f'{name} giả lập (chu kỳ {period:g}s)')
                    self.app.lab_event(self.index, 'skill', name)
        self.timer=self.app.root.after(100, self._tick)

    def stop(self):
        if self.sim is not None:
            self.app.log(self.index, 'Dừng mô phỏng')
        self.sim=None
        self.app.lab_event(self.index, 'stop')
        if self.timer is not None:
            try: self.app.root.after_cancel(self.timer)
            except tk.TclError: pass
            self.timer=None
        self.running.clear()
        self.button.config(text='▶ MÔ PHỎNG',bg='#078d28')
        self.status.set('Đã dừng mô phỏng')

    def report(self,msg):
        try:self.app.root.after(0,lambda:self.status.set(msg))
        except RuntimeError:pass

    def _ended(self):
        self.button.config(text='▶ MÔ PHỎNG',bg='#078d28')
        self.status.set('Đã dừng')

class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Auto Train Mil và Cổ Mộ — Mô phỏng ngoại tuyến 4 NV')
        # Cố định tỷ lệ 9:16, 540x960px; không có cuộn dọc.
        # Skill 1-5, giao diện thu gọn.
        self.root.geometry('540x960')
        self.root.resizable(False,False)
        self.root.configure(bg='#e7f3ff')
        self.data={}
        try:self.data=json.loads(CONFIG.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        self.characters=[]
        self.events=[]
        self.log_window=None
        self.lab=None
        self.build()
        self.root.protocol('WM_DELETE_WINDOW',self.close)

    def build(self):
        # Nền cây xanh hoạt hình phủ toàn bộ cửa sổ, bao quanh bốn bảng chức năng.
        self.canvas=tk.Canvas(self.root,bg='#bdf5df',highlightthickness=0,bd=0)
        self.canvas.pack(side='left',fill='both',expand=True)
        bg_file=ROOT/'forest_background.png'
        self.bg_original=Image.open(bg_file).convert('RGB') if bg_file.exists() else None
        self.bg_photo=None
        self.bg_id=self.canvas.create_image(0,0,anchor='nw') if self.bg_original else None
        self.content=tk.Frame(self.canvas,bg='#d8f6e7')
        self.content_id=self.canvas.create_window(15,8,window=self.content,anchor='nw')
        self.canvas.bind('<Configure>',self._resize_background)

        # Banner hai nhân vật tràn toàn bộ bề ngang phần nội dung.
        banner=ROOT/'header.png'
        if banner.exists():
            im=Image.open(banner).convert('RGB')
            # Ảnh banner gốc đã có chữ vàng nổi, Zalo và hai nhân vật.
            # Không vẽ thêm chữ trắng che lên ảnh.
            self.banner_source=im
            self.banner_width=0
            b=tk.Canvas(self.content,width=535,height=112,highlightthickness=0,bd=0)
            b.pack(fill='x',padx=0,pady=(0,1))
            self.banner_canvas=b
            self.banner_image_id=b.create_image(0,0,anchor='nw')
            b.bind('<Configure>',self._resize_banner)
        else:
            tk.Label(self.content,text='Auto Train Mil và Cổ Mộ',font=('Segoe UI',14,'bold'),
                     bg='#0875d4',fg='white').pack(fill='x',ipady=6)
        toolbar=tk.Frame(self.content,bg='#d8f6e7');toolbar.pack(fill='x',padx=6,pady=(1,1))
        ttk.Button(toolbar,text='⟳ Làm mới',command=self.refresh_all).pack(side='left')
        ttk.Button(toolbar,text='Nhật ký',command=self.show_log).pack(side='left',padx=3)
        ttk.Button(toolbar,text='Lộ trình',command=self.show_routes).pack(side='left')
        ttk.Button(toolbar,text='Phòng thử',command=self.open_lab).pack(side='left',padx=3)
        tk.Label(toolbar,text='Zalo: TuanHo – 0398438721',font=('Segoe UI',8,'bold'),
                 bg='#d8f6e7',fg='#064d9b').pack(side='right',padx=3)
        grid=tk.Frame(self.content,bg='#d8f6e7');grid.pack(fill='both',expand=True,padx=3,pady=1)
        for c in range(2):grid.columnconfigure(c,weight=1,uniform='characters')
        for r in range(2):grid.rowconfigure(r,weight=1,uniform='characters')
        saved=self.data.get('characters',[{}]*4)
        for i in range(4):
            self.characters.append(Character(self,i+1,grid,saved[i] if i<len(saved) else {}))
        self.refresh_all()
        self.sync=tk.BooleanVar(value=False)


    def _resize_banner(self,event):
        width=max(1,event.width)
        if width==self.banner_width:return
        self.banner_width=width
        height=112  # Thu gọn banner để cả 4 trạng thái Sẵn sàng hiển thị
        self.banner_canvas.configure(height=height)
        self.banner=ImageTk.PhotoImage(self.banner_source.resize((width,height),Image.Resampling.LANCZOS))
        self.banner_canvas.itemconfigure(self.banner_image_id,image=self.banner)

    def _resize_background(self,event):
        if self.bg_original is not None:
            im=self.bg_original.resize((max(1,event.width),max(1,event.height)),Image.Resampling.LANCZOS)
            self.bg_photo=ImageTk.PhotoImage(im)
            self.canvas.itemconfig(self.bg_id,image=self.bg_photo)
            self.canvas.tag_lower(self.bg_id)
        # Giữ lá cây tràn viền, chừa 15px ở hai cạnh.
        self.canvas.itemconfig(self.content_id,width=max(480,event.width-20))

    def open_lab(self):
        if self.lab is not None and self.lab.alive():
            self.lab.window.lift()
            return
        self.lab=TestLab(self.root)
        for c in self.characters:
            if c.sim is not None:
                self.lab.handle(c.index, 'start')
                self.lab.handle(c.index, 'route', c.sim['route'])

    def lab_event(self, index, event, value=None):
        if self.lab is not None and self.lab.alive():
            self.lab.handle(index, event, value)

    def log(self, index, message):
        entry=f'{datetime.now():%H:%M:%S} | NV{index} | {message}'
        self.events.append(entry)
        if len(self.events)>3000: self.events=self.events[-3000:]
        if self.log_window is not None and self.log_window.winfo_exists():
            widget=self.log_text
            widget.configure(state='normal')
            widget.insert('end',entry+'\n')
            widget.see('end')
            widget.configure(state='disabled')

    def show_log(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.lift(); return
        w=tk.Toplevel(self.root); w.title('Nhật ký mô phỏng (ngoại tuyến)')
        w.geometry('690x480'); self.log_window=w
        bar=tk.Frame(w);bar.pack(fill='x')
        tk.Button(bar,text='Xuất nhật ký .txt',command=self.export_log).pack(side='left',padx=6,pady=4)
        tk.Button(bar,text='Xóa nhật ký',command=self.clear_log).pack(side='left')
        frame=tk.Frame(w);frame.pack(fill='both',expand=True)
        scroll=tk.Scrollbar(frame);scroll.pack(side='right',fill='y')
        self.log_text=tk.Text(frame,wrap='none',font=('Consolas',10),yscrollcommand=scroll.set)
        self.log_text.pack(fill='both',expand=True);scroll.config(command=self.log_text.yview)
        self.log_text.insert('end','\n'.join(self.events)+'\n');self.log_text.configure(state='disabled')

    def clear_log(self):
        self.events.clear()
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_text.configure(state='normal');self.log_text.delete('1.0','end');self.log_text.configure(state='disabled')

    def export_log(self):
        filename=filedialog.asksaveasfilename(parent=self.log_window,defaultextension='.txt',filetypes=[('Text','*.txt')],initialfile='NhatKyMoPhong.txt')
        if filename:
            try: Path(filename).write_text('\n'.join(self.events)+'\n',encoding='utf-8')
            except OSError as exc: messagebox.showerror('Không lưu được',str(exc),parent=self.log_window)

    def show_routes(self):
        w=tk.Toplevel(self.root);w.title('20 lộ trình mô phỏng')
        w.geometry('430x530')
        tk.Label(w,text='Mỗi lộ trình lấy 3 điểm đầu; mỗi điểm 2 lần',font=('Segoe UI',10,'bold')).pack(pady=8)
        body=tk.Text(w,font=('Consolas',11),width=44)
        body.pack(fill='both',expand=True,padx=8,pady=4)
        for i,p in enumerate(PATTERNS,1):
            route=' → '.join(t[0] for t in p.split()[:3])
            body.insert('end',f'{i:02d}. {route}  (6 lần nhấp giả lập)\n')
        body.configure(state='disabled')

    def refresh_all(self):
        for c in self.characters:c.refresh()

    def sync_settings(self):
        if not self.sync.get():return
        src=self.characters[0]
        for dst in self.characters[1:]:
            for name,var in src.checks.items():dst.checks[name].set(var.get())
            for name,var in src.intervals.items():dst.intervals[name].set(var.get())
        self.save()

    def start_all(self):
        for c in self.characters:
            if not c.running.is_set():c.toggle()

    def stop_all(self):
        for c in self.characters:c.stop()

    def save(self):
        data={'characters':[c.settings() for c in self.characters], 'sync':self.sync.get() if hasattr(self,'sync') else False}
        try:CONFIG.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError as exc: self.log(0, f'Lỗi lưu cấu hình: {exc}')

    def close(self):
        self.stop_all();self.save();self.root.destroy()


class TestLab:
    """Offline visual target: never enumerate windows or send OS-level input."""
    POS={'A':(0.13,0.18),'B':(0.87,0.18),'C':(0.16,0.82),'D':(0.86,0.82),
         'E':(0.53,0.83),'F':(0.50,0.18),'G':(0.13,0.50),'H':(0.87,0.50)}
    def __init__(self, parent):
        self.window=tk.Toplevel(parent)
        self.window.title('PHÒNG THỬ NGOẠI TUYẾN — 4 nhân vật')
        self.window.geometry('760x650')
        self.window.configure(bg='#e8f5e9')
        tk.Label(self.window,text='PHÒNG THỬ 4 NHÂN VẬT — KHÔNG KẾT NỐI GAME',
                 bg='#166534',fg='white',font=('Segoe UI',13,'bold'),pady=9).pack(fill='x')
        tk.Label(self.window,text='Nhấn MÔ PHỎNG ở giao diện chính để điều khiển nhân vật trong bản đồ thử nghiệm này.',
                 bg='#e8f5e9',fg='#334155',font=('Segoe UI',9)).pack(pady=6)
        grid=tk.Frame(self.window,bg='#e8f5e9');grid.pack(fill='both',expand=True,padx=10,pady=8)
        for x in range(2):grid.columnconfigure(x,weight=1)
        for y in range(2):grid.rowconfigure(y,weight=1)
        self.views={}
        for i in range(1,5):
            panel=tk.LabelFrame(grid,text=f'NHÂN VẬT {i}',bg='white',fg='#14532d',font=('Segoe UI',10,'bold'))
            panel.grid(row=(i-1)//2,column=(i-1)%2,sticky='nsew',padx=5,pady=5)
            canvas=tk.Canvas(panel,width=330,height=210,bg='#f0fdf4',highlightthickness=1,highlightbackground='#86efac')
            canvas.pack(fill='both',expand=True,padx=5,pady=4)
            status=tk.StringVar(value='Chờ bắt đầu')
            tk.Label(panel,textvariable=status,bg='white',font=('Segoe UI',9),fg='#334155').pack(pady=(0,4))
            self.views[i]={'canvas':canvas,'status':status,'point':None,'skills':0,'route':''}
            canvas.bind('<Configure>',lambda ev,idx=i:self.draw(idx))

    def alive(self):
        return bool(self.window.winfo_exists())

    def draw(self, index):
        v=self.views[index]; c=v['canvas']; c.delete('all')
        w=max(c.winfo_width(),10);h=max(c.winfo_height(),10)
        c.create_rectangle(8,8,w-8,h-8,outline='#86efac',width=2)
        for letter,(x,y) in self.POS.items():
            px,py=x*w,y*h
            c.create_oval(px-11,py-11,px+11,py+11,fill='#dbeafe',outline='#2563eb')
            c.create_text(px,py,text=letter,font=('Segoe UI',9,'bold'),fill='#1e40af')
        if v['point'] in self.POS:
            x,y=self.POS[v['point']];px,py=x*w,y*h
            c.create_oval(px-15,py-15,px+15,py+15,outline='#dc2626',width=3)
        c.create_text(w/2,h/2,text='NHÂN VẬT '+str(index),fill='#166534',font=('Segoe UI',10,'bold'))
        c.create_text(w/2,h/2+17,text='Skill đã dùng: '+str(v['skills']),fill='#475569',font=('Segoe UI',9))

    def handle(self, index, event, value=None):
        v=self.views[index]
        if event=='start':
            v['skills']=0;v['point']=None;v['status'].set('Đang mô phỏng')
        elif event=='route':
            v['route']=value or '';v['status'].set('Lộ trình: '+ ' → '.join(v['route'][j] for j in (0,2,4)))
        elif event=='point':
            v['point']=value;v['status'].set(f'Đang đến điểm {value} | Skill: {v["skills"]}')
        elif event=='skill':
            v['skills']+=1;v['status'].set(f'{value} (mô phỏng) | Tổng: {v["skills"]}')
        elif event=='return':
            v['point']=None;v['status'].set('Đang mô phỏng về trung tâm')
        elif event=='stop':
            v['status'].set('Đã dừng')
        self.draw(index)

if __name__=='__main__':
    App().root.mainloop()
