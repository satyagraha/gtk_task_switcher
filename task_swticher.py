import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
from gi.repository import GdkPixbuf
import re

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
            
    def forListStore(self):
        return (self.hexId, self.program_name, self.title)
    
    @staticmethod
    def fromSource(source):
        result = []
        for line in source:
            trimmed = line.rstrip()
            if trimmed:
                result.append(Task(trimmed))
        return result

    @staticmethod
    def fromFile(filePath):
        with open(filePath, "r") as source:
            return Task.fromSource(source)

class Icons:
    location = { "Gnome-terminal": r"D:\software\msys64\usr\share\icons\hicolor\32x32\apps\mintty.png" }
    
class GtkKeyMap:
    ESCAPE = 65307
               
class TaskSwitcherWindow(Gtk.Window):

    def __init__(self, tasks, width, height, preferred_monitor):
        Gtk.Window.__init__(self, title="Task Switcher")
        
        # get info about monitors for window placement
        display = Gdk.Display.get_default()
        n_monitors = display.get_n_monitors()
        geometries = [display.get_monitor(m).get_geometry() for m in range(n_monitors)]
        x_offset = sum([geometry.width for geometry in geometries[0 : preferred_monitor]])
        target = geometries[preferred_monitor]
        
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
                    icon = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, icon_size, icon_size)
                    loaded_icons[icon_path] = icon
            self.store.append((icon,) + task.forListStore())
            
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
        value = tree_view.get_model().get_value(iter, 0)
        # print("value:", value)
        Gtk.main_quit()
        
    # user pressed a key
    def key_press(self, widget, event):
        # print("key_press:", event.keyval)
        if event.keyval == GtkKeyMap.ESCAPE:
            Gtk.main_quit()
        return False
        
tasks = Task.fromFile("wmctrl_sample.txt")
#for task in tasks: print(task.__dict__)

# tweak the window sizes and selected monitor as desired
window = TaskSwitcherWindow(tasks, 800, 400, 1)
window.show()
window.connect("destroy", Gtk.main_quit)
Gtk.main()
