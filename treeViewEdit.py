import tkinter as tk
from tkinter import ttk
#from tkintertable import TableCanvase, TableModel

class TableEdit(ttk.Treeview):
    def __init__(self, master, columns, readableNames, editable = False):
        super().__init__(master=master, columns=columns, show='headings')

        self._columns = columns
        self._readableNames = readableNames

        if len(columns) != len(readableNames):
            raise ValueError('columns and readableNames have to be the same length')

        i = 0
        for col in columns:
            self.heading(col, text=readableNames[i], command=lambda _col=col: self.treeview_sort_column(self, _col, False))
            i = i+1

        if editable == True:
            self.bind("<Button-3>", self.popup)
            self.bind('<Double-Button-1>', self.onDoubleClick)

    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        l.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # reverse sort next time
        tv.heading(col, command=lambda _col=col: \
            self.treeview_sort_column(tv, _col, not reverse))

    def popup(self, event):
        """action in event of button 3 on tree view"""
        # select row under mouse
        iid = self.identify_row(event.y)
        popup = Popup(self, event, self._columns, self._readableNames)
        if iid:
            # mouse pointer over item
            self.selection_set(iid)
            popup.post(event.x_root, event.y_root)
        else:
            # mouse pointer not over item
            # occurs when items do not fill frame
            # no action required
            # mouse pointer over item
            popup.post(event.x_root, event.y_root)

    def onDoubleClick(self, event):
        m = EditMenu(event, self._columns, self._readableNames)
        m.show()

class Popup(tk.Menu):
    def __init__(self, master, event, columns, readableNames):
        tk.Menu.__init__(self, master, tearoff=0)
        self._event = event
        self._columns = columns
        self._readableNames = readableNames

        self.add_command(label="Bearbeiten", command=self.editMember)
        self.add_command(label="Hinzufügen", command=self.addMember)
        self.add_command(label="Löschen", command=self.deleteMember)

        iid = self._event.widget.identify_row(event.y)
        if '' == iid:
            self.entryconfig("Bearbeiten", state="disabled")
            self.entryconfig("Löschen", state="disabled")

    def editMember(self):
        m = EditMenu(self._event, self._columns, self._readableNames, False)

    def addMember(self):
        m = EditMenu(self._event, self._columns, self._readableNames, True)

    def deleteMember(self):
        w = WarningDelete(self._event)
        ok = w.show()
        if ok is True:
            curr = self._event.widget.focus()
            if '' == curr:
                return
            self._event.widget.delete(curr)


class EditMenu(tk.Toplevel):
    def __init__(self, event, columns, readableNames, new = False):
        super().__init__()
        # First check if a blank space was selected
        entryIndex = event.widget.focus()
        iid = event.widget.identify_row(event.y)
        if iid == '' or new is True:
            self._selection = False
            entryIndex = ''
        else:
            self._selection = True

        #if '' == entryIndex: return

        self._widget = event.widget

        # Set up window
        self.geometry("+%d+%d" % (event.x_root, event.y_root))
        self.title("Eintrag bearbeiten")
        self.attributes("-toolwindow", True)

        ####
        # Set up the window's other attributes and geometry
        ####

        # Pre initialize the values
        values = [''] * len(columns)
        # Grab the entry's values
        for child in self._widget.get_children():
            if child == entryIndex:
                values = self._widget.item(child)["values"]
                break

        i = 0
        k = 0
        self._entries = []
        self._labels = []
        for cal in columns:
            self._labels.append(ttk.Label(self, text=readableNames[i]))
            self._entries.append(ttk.Entry(self))
            self._entries[-1].insert(0, values[i])  # Default is column 1's current value
            self._labels[-1].grid(row=k, column=0, columnspan=2, padx=(10,10))
            self._entries[-1].grid(row=k + 1, column=0, columnspan=2, padx=(10,10))
            i = i + 1
            k = k + 2

        okButt = ttk.Button(self, text="Ok")
        okButt.bind("<Button-1>", lambda e: self.updateThenDestroy())
        okButt.grid(row=k, column=0, padx=(10,0))

        canButt = ttk.Button(self, text="Abbrechen")
        canButt.bind("<Button-1>", lambda c: self.destroy())
        canButt.grid(row=k, column=1, padx=(0,10), pady=(10,10))

    def show(self):
        self.grab_set()
        self.deiconify()
        self.wait_window()
        self.grab_release()

    def updateThenDestroy(self):
        valuesNew = []
        for entry in self._entries:
            valuesNew.append(entry.get())
        if all(val == '' for val in valuesNew) == True:
            self.destroy()
            return

        if self.confirmEntry(valuesNew):
            self.destroy()

    def confirmEntry(self, entries : list):
        ####
        # Whatever validation you need
        ####

        # Grab the current index in the tree
        currInd = self._widget.index(self._widget.focus())

        # Remove it from the tree
        self.deleteCurrentEntry()

        # Put it back in with the upated values
        if self._selection is True:
            self._widget.insert('', currInd, values=entries)
        else:
            self._widget.insert('', tk.END, values=entries)
        return True

    def deleteCurrentEntry(self):
        curr = self._widget.focus()

        if '' == curr or self._selection is False:
            return

        self._widget.delete(curr)


class WarningDelete(tk.Toplevel):
    def __init__(self, event):
        super().__init__()
        # Set up window
        self.geometry("+%d+%d" % (event.x_root, event.y_root))
        self.title("Eintrag entfernen")
        self.attributes("-toolwindow", True)

        self.label = ttk.Label(self, text='Eintrag sicher entfernen?')
        self.label.grid(row=0, column=0, columnspan=2, padx=(10,10))

        okButt = ttk.Button(self, text="Ok")
        okButt.bind("<Button-1>", lambda e: self.okThenDestroy())
        okButt.grid(row=1, column=0, padx=(10,0))

        canButt = ttk.Button(self, text="Abbrechen")
        canButt.bind("<Button-1>", lambda c: self.destroy())
        canButt.grid(row=1, column=1, padx=(0,10), pady=(10,10))
        self.ok = False

    def show(self):
        self.grab_set()
        self.deiconify()
        self.wait_window()
        self.grab_release()
        return self.ok

    def okThenDestroy(self):
        self.ok = True
        self.destroy()