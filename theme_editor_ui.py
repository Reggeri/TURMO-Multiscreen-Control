"""Theme editor: selectable widgets, drag to position, save to per-screen settings."""
import copy
import tkinter as tk
from tkinter import ttk,colorchooser,filedialog,messagebox
from PIL import ImageTk
from editor import FIELDS,default_layout,render,load_background
from theme_packages import import_theme, export_theme, ThemePackageError

class ThemeEditor(tk.Toplevel):
    def __init__(self,root,config,save,values):
        super().__init__(root)
        self.title('TURMO / THEME EDITOR v0.20');self.geometry('850x760');self.configure(bg='#111b2c')
        self.config_data=copy.deepcopy(config or default_layout())
        self.save_cb=save;self.values=values;self.selection=0;self.photo=None
        self.video=None
        self.protocol('WM_DELETE_WINDOW',self.close)
        top=tk.Frame(self,bg='#111b2c');top.pack(fill='x',padx=14,pady=12)
        tk.Button(top,text='BACKGROUND COLOR',command=self.color_background).pack(side='left',padx=3)
        tk.Button(top,text='IMAGE / MP4',command=self.pick_media).pack(side='left',padx=3)
        tk.Button(top,text='CLEAR MEDIA',command=self.clear_media).pack(side='left',padx=3)
        tk.Button(top,text='IMPORT .TURMO',command=self.import_package,bg='#425c77',fg='white').pack(side='left',padx=3)
        tk.Button(top,text='EXPORT .TURMO',command=self.export_package,bg='#425c77',fg='white').pack(side='left',padx=3)
        tk.Button(top,text='SAVE THEME',command=self.save,bg='#52c9e5').pack(side='right',padx=3)
        body=tk.Frame(self,bg='#111b2c');body.pack(fill='both',expand=True,padx=12)
        self.canvas=tk.Canvas(body,width=480,height=320,bg='black',highlightthickness=1,highlightbackground='#61748e')
        self.canvas.pack(side='left',anchor='n')
        self.canvas.bind('<Button-1>',self.pick_on_canvas)
        self.canvas.bind('<B1-Motion>',self.drag)
        side=tk.Frame(body,bg='#18273b');side.pack(side='left',fill='y',padx=12)
        tk.Label(side,text='DATA WIDGETS',fg='white',bg='#18273b').pack(pady=6)
        self.widgets=tk.Listbox(side,height=7,width=31,exportselection=False)
        self.widgets.pack(padx=10);self.widgets.bind('<<ListboxSelect>>',self.selected)
        tk.Button(side,text='+ ADD',command=self.add).pack(fill='x',padx=10,pady=3)
        tk.Button(side,text='REMOVE',command=self.remove).pack(fill='x',padx=10,pady=3)
        self.key=tk.StringVar(value='cpu')
        ttk.Combobox(side,textvariable=self.key,values=FIELDS,state='readonly').pack(padx=10,pady=5)
        tk.Label(side,text='Label',bg='#18273b',fg='white').pack()
        self.labelvar=tk.StringVar();entry=tk.Entry(side,textvariable=self.labelvar);entry.pack(padx=10)
        entry.bind('<KeyRelease>',lambda e:self.apply())
        tk.Label(side,text='Font size',bg='#18273b',fg='white').pack()
        self.size=tk.IntVar(value=28)
        tk.Scale(side,from_=12,to=60,variable=self.size,orient='horizontal',command=lambda v:self.apply(),bg='#18273b',fg='white',highlightthickness=0).pack(fill='x',padx=10)
        tk.Label(side,text='Font family',bg='#18273b',fg='white').pack()
        self.fontvar=tk.StringVar(value='Segoe UI')
        ttk.Combobox(side,textvariable=self.fontvar,values=['Segoe UI','Arial','Consolas','Verdana','Tahoma'],state='readonly',width=22).pack(padx=10,pady=4)
        self.fontvar.trace_add('write',lambda *_:self.apply())
        tk.Label(side,text='Label size',bg='#18273b',fg='white').pack()
        self.labelsize=tk.IntVar(value=13)
        tk.Scale(side,from_=8,to=30,variable=self.labelsize,orient='horizontal',command=lambda v:self.apply(),bg='#18273b',fg='white',highlightthickness=0).pack(fill='x',padx=10)
        tk.Button(side,text='TEXT COLOR',command=self.color_text).pack(pady=6)
        self.key.trace_add('write',lambda *_:self.apply())
        self.info=tk.Label(self,text='MP4 WARNING: High CPU usage (30–40% or more). Eco mode: 2 FPS video. Drag metrics to edit.',fg='#b8d5e8',bg='#111b2c')
        self.info.pack(pady=10)
        self.refresh_list();self.refresh()
        self.after(2000,self.tick)
    def tick(self):
        if not self.winfo_exists():return
        if self.video is not None:self.refresh()
        self.after(2000,self.tick)
    def refresh_list(self):
        self.widgets.delete(0,'end')
        for w in self.config_data['widgets']:self.widgets.insert('end',w.get('label',w['key'])+'  ['+w['key']+']')
        if self.config_data['widgets']:
            self.selection=min(self.selection,len(self.config_data['widgets'])-1)
            self.widgets.selection_set(self.selection)
            self.load_selected()
    def load_selected(self):
        if not self.config_data['widgets']:return
        w=self.config_data['widgets'][self.selection]
        self.key.set(w['key']);self.labelvar.set(w.get('label',''));self.size.set(w.get('size',28));self.fontvar.set(w.get('font','Segoe UI'));self.labelsize.set(w.get('label_size',13))
    def selected(self,event=None):
        sel=self.widgets.curselection()
        if sel:self.selection=sel[0];self.load_selected();self.refresh()
    def apply(self):
        if not self.config_data['widgets']:return
        w=self.config_data['widgets'][self.selection]
        w['key']=self.key.get();w['label']=self.labelvar.get();w['size']=self.size.get();w['font']=self.fontvar.get();w['label_size']=self.labelsize.get()
        self.refresh()
    def add(self):
        self.config_data['widgets'].append({'key':'cpu','x':25,'y':25,'size':28,'color':'#ffffff','label':'CPU','font':'Segoe UI','label_size':13})
        self.selection=len(self.config_data['widgets'])-1;self.refresh_list();self.refresh()
    def remove(self):
        if self.config_data['widgets']:self.config_data['widgets'].pop(self.selection)
        self.refresh_list();self.refresh()
    def pick_on_canvas(self,event):
        if not self.config_data['widgets']:return
        self.selection=min(range(len(self.config_data['widgets'])),key=lambda i:
            (self.config_data['widgets'][i]['x']-event.x)**2+(self.config_data['widgets'][i]['y']-event.y)**2)
        self.widgets.selection_clear(0,'end');self.widgets.selection_set(self.selection);self.load_selected();self.refresh()
    def drag(self,event):
        if not self.config_data['widgets']:return
        w=self.config_data['widgets'][self.selection]
        w['x']=max(0,min(440,event.x));w['y']=max(0,min(275,event.y));self.refresh()
    def color_background(self):
        col=colorchooser.askcolor(color=self.config_data.get('background','#101827'),parent=self)[1]
        if col:self.config_data['background']=col;self.refresh()
    def color_text(self):
        if not self.config_data['widgets']:return
        col=colorchooser.askcolor(parent=self)[1]
        if col:self.config_data['widgets'][self.selection]['color']=col;self.refresh()
    def pick_media(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[('Media','*.mp4 *.png *.jpg *.jpeg *.bmp *.webp'),('All files','*.*')])
        if p:self.config_data['media']=p;self.open_video();self.refresh()
    def clear_media(self):
        self.config_data['media']='';self.open_video();self.refresh()
    def open_video(self):
        if self.video:self.video.close();self.video=None
        if self.config_data.get('media','').lower().endswith('.mp4'):
            from media import VideoSource
            self.video=VideoSource(self.config_data['media'],min(2,self.config_data.get('fps',2)))
    def refresh(self):
        values=self.values() or {}
        bg=self.video.get() if self.video else load_background(self.config_data)
        img=render(self.config_data,values,bg)
        self.photo=ImageTk.PhotoImage(img)
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        if self.config_data['widgets']:
            w=self.config_data['widgets'][self.selection]
            self.canvas.create_rectangle(w['x']-2,w['y']-2,w['x']+115,w['y']+56,outline='#f1b84d',dash=(4,3))
    def import_package(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('TURMO theme','*.turmo')])
        if not path:return
        try:
            new_config=import_theme(path)
            self.config_data=new_config
            self.selection=0
            self.open_video()
            self.refresh_list()
            self.refresh()
            messagebox.showinfo('TURMO','Theme imported. Click SAVE THEME to keep it.',parent=self)
        except (ThemePackageError,OSError) as exc:
            messagebox.showerror('Import failed',str(exc),parent=self)

    def export_package(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.turmo',
                filetypes=[('TURMO theme','*.turmo')],initialfile='my-theme.turmo')
        if not path:return
        try:
            result=export_theme(self.config_data,path)
            messagebox.showinfo('TURMO','Theme exported to:\n'+str(result),parent=self)
        except (ThemePackageError,OSError) as exc:
            messagebox.showerror('Export failed',str(exc),parent=self)

    def save(self):
        self.save_cb(copy.deepcopy(self.config_data))
        messagebox.showinfo('TURMO','Theme saved. Restart both displays to apply changes.',parent=self)
    def close(self):
        if self.video:self.video.close()
        self.destroy()
