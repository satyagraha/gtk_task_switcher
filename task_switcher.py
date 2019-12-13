#!/usr/bin/python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from pathlib import Path
import pickle
import re
import sys
import win_support

class Task:
    def __init__(self, wmctrl_line):
        fields = re.split(r'\s+', wmctrl_line, 4)
        self.hexId = fields[0]
        self.desktop = fields[1]
        self.program = fields[2]
        self.user = fields[3]
        self.title = fields[4]
        program_fields = self.program.split('.', 1)
        if len(program_fields) == 2:
            self.program_class = program_fields[0]
            self.program_name = program_fields[1]
        else:
            self.program_class = ""
            self.program_name = program_fields[0]

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def for_list_store(self):
        return (self.hexId, self.program_name, self.title)
    
    @staticmethod
    def from_win_info(win_info):
        return [Task(line) for line in win_info.list_windows()]

    history_path = Path.home() / ".task_switcher"

    @staticmethod
    def save(items):
        with Task.history_path.open("wb") as dst:
            pickle.dump(items, dst)

    @staticmethod
    def load():
        if Task.history_path.exists():
            with Task.history_path.open("rb") as src:
                return pickle.load(src)
        else:
            return []

    @staticmethod
    def merge(current, history):
        # print("current:", current)
        # print("history:", history)
        new = [x for x in current if x not in history]
        # print("new:", new)
        old = [x for x in history if x in current]
        # print("old:", old)
        return new + old

    @staticmethod
    def update(tasks, wmId):
        selected = [next(x for x in tasks if x.hexId == wmId)]
        unselected = [x for x in tasks if x.hexId != wmId]
        Task.save(selected + unselected)

class Icons:
    location = { 
        "Firefox-esr": "/usr/share/firefox-esr/browser/chrome/icons/default/default32.png",
        "Geany": "/usr/share/icons/hicolor/32x32/apps/geany.png",
        "GitKraken": "/usr/share/pixmaps/gitkraken.png",
        "Gnome-terminal": "/usr/share/icons/Adwaita/32x32/apps/utilities-terminal.png",
        "Google-chrome": "/usr/share/icons/hicolor/32x32/apps/google-chrome.png",
        "jetbrains-idea": "~/Icons/idea.png",
        "jetbrains-pycharm-ce": "~/Icons/pycharm.png",
        "Slack": "/usr/share/pixmaps/slack.png",
        "Xfe": "/usr/share/icons/hicolor/32x32/apps/geany.png"
    }
    
class GtkKeyMap:
    ESCAPE = 65307
    DELETE = 65535

class MonitorInfo:
    def __init__(self):
        display = Gdk.Display.get_default()
        self.n_monitors = display.get_n_monitors()
        self.geometries = [display.get_monitor(m).get_geometry() for m in range(self.n_monitors)]
               
class TaskSwitcherWindow(Gtk.Window):
    name = "Task Switcher"

    def __init__(self, win_info: win_support.WinInfo, monitor_info, tasks, width, height, preferred_monitor):
        Gtk.Window.__init__(self, title = TaskSwitcherWindow.name)
        self.win_info = win_info
        self.tasks = tasks
        
        # get info about monitors for window placement
        x_offset = sum([geometry.width for geometry in monitor_info.geometries[0 : preferred_monitor]])
        target = monitor_info.geometries[preferred_monitor]
        
        self.set_size_request(width, height)
        self.move(x_offset + (target.width / 2) - (width / 2), (target.height / 2) - (height / 2))

        # create and populate list model
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str)
        icon_size = 16
        loaded_icons = {}
        for task in tasks:
            icon = loaded_icons.get(task.program_name)
            if not icon:
                icon_path = Icons.location.get(task.program_name)
                if icon_path:
                    try:
                        full_path = Path(icon_path).expanduser()
                        icon = GdkPixbuf.Pixbuf.new_from_file_at_size(str(full_path), icon_size, icon_size)
                    except GLib.Error as err:
                        print("Glib error:", err)
                    loaded_icons[icon_path] = icon
            self.store.append((icon,) + task.for_list_store())
            
        # create view and link to model
        self.list_view = Gtk.TreeView()
        self.list_view.set_model(self.store)
        
        icon_renderer = Gtk.CellRendererPixbuf()
        icon_column = Gtk.TreeViewColumn("Icon", icon_renderer, pixbuf = 0)
        self.list_view.append_column(icon_column)
        
        program_renderer = Gtk.CellRendererText()
        program_column = Gtk.TreeViewColumn("Program", program_renderer, text = 2)
        self.list_view.append_column(program_column)
        
        title_renderer = Gtk.CellRendererText()
        title_column = Gtk.TreeViewColumn("Title", title_renderer, text = 3)
        self.list_view.append_column(title_column)
        
        # set up keyboard event handlers
        self.list_view.connect("row-activated", self.activated)
        self.list_view.connect("key-press-event", self.key_press)
        self.add_events(Gdk.EventMask.FOCUS_CHANGE_MASK)
        self.connect("focus-out-event", self.focus_lost)
        
        # wrap list view in scrollable view
        self.list_view.set_headers_visible(False)
        self.scrollable_view = Gtk.ScrolledWindow()
        self.scrollable_view.set_vexpand(True)
        self.scrollable_view.add(self.list_view)

        # set up top-level windown
        self.add(self.scrollable_view)
        self.set_modal(True)
        self.set_decorated(False)
        self.set_border_width(10)
        self.show_all()
        
    # user picked a task
    def activated(self, tree_view, path, column):
        # print("activated:", path.get_indices())
        iter = tree_view.get_model().get_iter(path)
        wmId = tree_view.get_model().get_value(iter, 1)
        # print("wmId:", wmId)
        Task.update(self.tasks, wmId)
        self.win_info.switch_to(wmId)
        Gtk.main_quit()

    # user deletes a task
    def delete(self):
        (store, iter) = self.list_view.get_selection().get_selected()
        if not iter:
            return
        # print("iter:", iter)
        wmId = store.get_value(iter, 1)
        # print("wmId:", wmId)
        self.win_info.kill(wmId)
        store.remove(iter)

    # user pressed a key
    def key_press(self, widget, event):
        # print("key_press:", event.keyval)
        if event.keyval == GtkKeyMap.ESCAPE:
            Gtk.main_quit()
        if event.keyval == GtkKeyMap.DELETE:
            self.delete()
        return False

    # UI lost focus
    def focus_lost(self, widget, event):
        Gtk.main_quit()
        
###############################################################################

if __name__ == '__main__':
    # get the running task windows
    # win_info = win_support.WmFile("wmctrl_sample.txt")
    # win_info = win_support.WmCtrl()
    # win_info = win_support.WmEWMH()
    win_info = win_support.WmX()
    tasks = Task.merge(Task.from_win_info(win_info), Task.load())
    # for task in tasks: print(task.__dict__)

    # check if already running, if so select and quit
    existing = next((filter(lambda task: task.title == TaskSwitcherWindow.name, tasks)), None)
    if existing:
        win_info.switch_to(existing.hexId)
        sys.exit(0)

    # tweak the window sizes and selected monitor as desired
    monitor_info = MonitorInfo()
    if monitor_info.n_monitors == 3:
        preferred_monitor = 1
    else:
        preferred_monitor = 0

    window = TaskSwitcherWindow(win_info, monitor_info, tasks, 800, 600, preferred_monitor)
    window.show()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
