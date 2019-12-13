#!/usr/bin/python3

import abc
import subprocess
from ewmh import EWMH
from Xlib import display, protocol, X


# The abstract base class for desktop window management
class WinInfo(metaclass=abc.ABCMeta):

    # expected line format:
    # 0x0160008e  0 Navigator.Firefox-esr  user iso timezone converter - Google Search - Mozilla Firefox
    @abc.abstractmethod
    def list_windows(self) -> [str]:
        pass

    @abc.abstractmethod
    def switch_to(self, wm_id: str) -> None:
        pass

    @abc.abstractmethod
    def kill(self, wm_id: str) -> None:
        pass

    def _from_source(self, source) -> [str]:
        result = []
        for line in source:
            trimmed = line.rstrip()
            if trimmed:
                result.append(trimmed)
        return result


###############################################################################


# Provides window information via wmctrl executable
class Wmctrl(WinInfo):
    executable = "/usr/bin/wmctrl"

    def list_windows(self):
        with subprocess.Popen([Wmctrl.executable, "-x", "-l"], shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True) as proc:
            return self._from_source(proc.stdout)

    def kill(self, wm_id: str) -> None:
        pass # TODO

    def switch_to(self, wm_id):
        subprocess.run([Wmctrl.executable, "-i", "-a", wm_id], shell=False)


###############################################################################


# Provides window information from a file
class WmFile(WinInfo):
    def __init__(self, file_path):
        self.file_path = file_path

    def list_windows(self):
        with open(self.file_path, "r") as source:
            return self._from_source(source)

    def kill(self, wm_id: str) -> None:
        pass # TODO

    def switch_to(self, wm_id):
        subprocess.run([Wmctrl.executable, "-i", "-a", wm_id], shell=False)


###############################################################################


# Provides window information via ewmh library
class WmEWMH(WinInfo):
    ewmh = EWMH()
    wmclass = ewmh.display.get_atom("WM_CLASS")
    wmcm = ewmh.display.get_atom("WM_CLIENT_MACHINE")
    wmname = ewmh.display.get_atom("WM_NAME")

    def list_windows(self):
        wins = WmEWMH.ewmh.getClientListStacking()
        lines = []
        for win in wins:
            id = '0x' + hex(win.id)[2:].zfill(8)
            disp = win.display.default_screen
            wmcm = win.get_full_property(self.wmcm, X.AnyPropertyType)
            if wmcm:
                wmcm = wmcm.value.decode("utf-8", 'backslashreplace')
            else:
                wmcm = "N/A"
            itemb = win.get_full_property(WmEWMH.wmclass, X.AnyPropertyType).value
            cls = '.'.join(itemb.decode("utf-8").rstrip('\x00').split('\x00'))
            nameb = win.get_full_property(WmEWMH.wmname, X.AnyPropertyType).value
            name = nameb.decode("utf-8", 'backslashreplace')
            line = "%s %s %s %s %s" % (id, disp, cls, wmcm, name)
            lines.append(line)
        return lines

    def kill(self, wm_id: str) -> None:
        win_id = int(wm_id, 16)
        win = WmEWMH.ewmh._createWindow(win_id)
        WmEWMH.ewmh.setCloseWindow(win)
        WmEWMH.ewmh.display.flush()

    def switch_to(self, wm_id):
        win_id = int(wm_id, 16)
        win = WmEWMH.ewmh._createWindow(win_id)
        WmEWMH.ewmh.setActiveWindow(win)
        WmEWMH.ewmh.display.flush()


###############################################################################


# provides window information via Xlib library
class WmX(WinInfo):

    def __init__(self):
        self.display = display.Display()
        self.root = self.display.screen().root
        self.wmclass = self.display.get_atom("WM_CLASS")
        self.wmcm = self.display.get_atom("WM_CLIENT_MACHINE")
        self.wmname = self.display.get_atom("WM_NAME")
        self.stacking = self.display.get_atom('_NET_CLIENT_LIST_STACKING')
        self.active = self.display.get_atom('_NET_ACTIVE_WINDOW')
        self.close = self.display.get_atom('_NET_CLOSE_WINDOW')

    def _create_window(self, win_id):
        return self.display.create_resource_object('window', win_id)

    def list_windows(self):
        win_ids = self.root.get_full_property(self.stacking, X.AnyPropertyType).value
        wins = [self._create_window(win_id) for win_id in win_ids]
        lines = []
        for win in wins:
            id = '0x' + hex(win.id)[2:].zfill(8)
            disp = win.display.default_screen
            wmcm = win.get_full_property(self.wmcm, X.AnyPropertyType)
            if wmcm:
                wmcm = wmcm.value.decode("utf-8", 'backslashreplace')
            else:
                wmcm = "N/A"
            itemb = win.get_full_property(self.wmclass, X.AnyPropertyType).value
            cls = '.'.join(itemb.decode("utf-8").rstrip('\x00').split('\x00'))
            # name = win.get_wm_name()
            nameb = win.get_full_property(self.wmname, X.AnyPropertyType)
            # print("pt:", nameb.property_type)
            an = self.display.get_atom_name(nameb.property_type)
            # print("an:", an)
            # name = nameb.decode("utf-8", 'backslashreplace')
            name = nameb.value.decode("latin-1")
            if name.find("7.2") != -1:
                for b in nameb.value:
                    print("b:", hex(b), chr(b))
            # name = nameb.decode("windows-1252")
            print("name:", type(name), name)
            line = "%s %s %s %s %s" % (id, disp, cls, wmcm, name)
            lines.append(line)
        return lines

    def kill(self, wm_id: str) -> None:
        win_id = int(wm_id, 16)
        win = self._create_window(win_id)
        data = [1, X.CurrentTime, win.id, 0, 0]
        dataSize = 32
        ev = protocol.event.ClientMessage(window=win, client_type=self.close, data=(dataSize, data))
        mask = (X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.root.send_event(ev, event_mask=mask)
        self.display.flush()

    def switch_to(self, wm_id):
        win_id = int(wm_id, 16)
        win = self._create_window(win_id)
        data = [1, X.CurrentTime, win.id, 0, 0]
        dataSize = 32
        ev = protocol.event.ClientMessage(window=win, client_type=self.active, data=(dataSize, data))
        mask = (X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.root.send_event(ev, event_mask=mask)
        self.display.flush()


###############################################################################


if __name__ == '__main__':
    ewmh = EWMH()
    # props = ["WM_CLASS"] # ewmh.getReadableProperties()
    # props = []  # ewmh.getReadableProperties()
    # for prop in props:
    #     print("prop:", prop)

    # get every displayed windows
    wins = ewmh.getClientListStacking()

    # for win in wins:
    # 	print("win:", win, ewmh.getWmName(win))

    # for win in wins:
    #     print("win:", win)
    #     for prop in props:
    #         # value = ewmh.getProperty(prop, win)
    #         item = win.get_full_property(ewmh.display.get_atom(prop), X.AnyPropertyType)
    #         print("prop:", prop, item)
    # print("win:", win, ewmh.getWmPid(win), ewmh.getWmName(win))

    # win_info = WmEWMH()
    win_info_c = Wmctrl()
    win_info_x = WmX()

    windows_c = win_info_c.list_windows()
    windows_c.sort()
    for line in windows_c:
        print(line)
    print()
    windows_x = win_info_x.list_windows()
    windows_x.sort()
    for line in windows_x:
        print(line)
    # win_info.switch_to("0x01600036")
