import tkinter as tk
from tkinter import ttk, filedialog, IntVar
import sv_ttk
import logging
import LoggingHandlerFrame as loggingFrame
from accounting import NamiAccounting
from threading import Thread
from nami import Nami
from tools import Config, BookingHalfYear, MembershipFees, SepaWrapper
print = logging.info
import datetime as dt
from tkcalendar import Calendar, DateEntry
from sepa import Sepa
from schwifty import IBAN, BIC
from os import path
from treeViewEdit import TableEdit
from vr_import import VRImport, VRMandat

class RunAccounting(Thread):
    def __init__(self, config:Config, memberTree, nami: Nami, sepa: Sepa):
        super().__init__()
        self.m = NamiAccounting(config, memberTree, nami, sepa)

    def run(self):
        self.m.process()


class MenuBar(tk.Menu):
    def __init__(self, master):
        super().__init__(master=master)
        self._filemenu = tk.Menu(self)
        self._filemenu.add_command(label="Importiere Mandate", command=master.importMandate)
        self._filemenu.add_command(label="Speichern")
        self.add_cascade(label="Datei", menu=self._filemenu)


class App(ttk.Frame):
    def __init__(self, parent):
        ttk.Frame.__init__(self, parent)
        self._parent = parent
        # Init
        self._nami = None
        self._sepa = None

        # Create the menu bar
        self._menuBar = MenuBar(self)
        parent.config(menu=self._menuBar)

        parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Bind shortcuts
        self._parent.bind('<Control-s>', self.save)

        # Read Config
        self._config = Config('config.ini')

        # Set the global datetime format
        self._config.set_datetime_format('%d.%m.%Y')
        # ============ create two frames ============

        # configure grid layout (2x1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self.frame_login = ttk.LabelFrame(self, text="Login", padding=(10, 10))
        self.frame_login.grid(row=0, column=0, sticky="nsew", padx=(10,0), pady=(1,0)) # Pad one pixel to align it with the TreeView widget
        self.frame_login.grid_columnconfigure(0, weight=1)
        self.frame_login.grid_rowconfigure(0, weight=0)

        #self.frame_config = ttk.LabelFrame(self, text="Konfiguration", padding=(10,10))
        #self.frame_config.grid(row=1, column=0, sticky="nsew", padx=(10,0), pady=(0,10))
        #self.frame_config.grid_columnconfigure(0, weight=1)
        #self.frame_config.grid_rowconfigure(0, weight=0)
        self.configNotebook = ttk.Notebook(self)

        self.accountingFrame = ttk.Frame(master=self.configNotebook, padding=(10,10))
        self.feesFrame = ttk.Frame(master=self.configNotebook, padding=(10,10))
        self.creditorFrame = ttk.Frame(master=self.configNotebook, padding=(10, 10))
        self.configNotebook.add(self.accountingFrame, text='Buchung')
        self.configNotebook.add(self.feesFrame, text='Beiträge')
        self.configNotebook.add(self.creditorFrame, text='Gläubiger ID')
        self.configNotebook.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(10, 10))

        self.frame_logging = loggingFrame.LoggingHandlerFrame(self, text="Info", padding=(10, 10))
        self.frame_logging.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(10,0), pady=(0,10))

        self.loggingScrollbar = ttk.Scrollbar(master=self, orient=tk.VERTICAL, command=self.frame_logging.text.yview)
        self.frame_logging.text.configure(yscroll=self.loggingScrollbar.set)
        self.loggingScrollbar.grid(row=1, column=2, rowspan=2, padx=(0,10), pady=(10,10), sticky='ns')

        # ============ frame_login ============

        # configure grid layout (1x11)

        #self.label_1 = customtkinter.CTkLabel(master=self.frame_left,
        #                                      text="Konfiguration",
        #                                      text_font=("Roboto Medium", -16))  # font name and size in px
        #self.label_1.grid(row=1, column=0)
        vcmd = (self.register(self.validate_int))
        self.usernameLabel = ttk.Label(master=self.frame_login, text="Nami Nummer", anchor="w")
        self.usernameLabel.grid(row=0, column=0, padx=0, pady=(5,0), sticky="nsew")

        self.usernameEntry = ttk.Entry(master=self.frame_login, validate='all', validatecommand=(vcmd, '%P'))
        self.usernameEntry.grid(row=1, column=0, padx=0, pady=5, sticky="nsew")
        self.usernameEntry.insert(tk.END, self._config.get_nami_username())

        self.passwordLabel = ttk.Label(master=self.frame_login, text="Passwort", anchor="w")
        self.passwordLabel.grid(row=2, column=0, padx=0, pady=(5,0), sticky="nsew")

        self.passwordEntry = ttk.Entry(master=self.frame_login, show='*')
        self.passwordEntry.grid(row=3, column=0, padx=0, pady=5, sticky="nsew")
        self.passwordEntry.insert(tk.END, self._config.get_nami_password())

        self.loginButton = ttk.Button(master=self.frame_login, style="Accent.TButton",
                                                text="Login",
                                                command=self.nami_login)
        self.loginButton.grid(row=4, column=0, padx=0, pady=5, sticky="nsew")

        # get path to image. Do it this way to allow the correct image path search with pyinstaller
        try:
            # Get the absolute path of the temp directory
            pathToDpsgLogo = path.abspath(path.join(path.dirname(__file__), 'img/dpsg_logo.png'))
            # Set the dpsg logo
            self.dpsgImage = tk.PhotoImage(file=pathToDpsgLogo)
            self.dpsgImageLabel = ttk.Label(master=self.frame_login, image=self.dpsgImage, anchor="w")
        except:
            self.dpsgImageLabel = ttk.Label(master=self.frame_login, text='', anchor="w")

        self.dpsgImageLabel.grid(row=5, column=0, padx=0, pady=(5,0))

        # ============ accountingFrame ============
        self.bookingYearLabel = ttk.Label(master=self.accountingFrame, text="Buchungsjahr", anchor="w")
        self.bookingYearLabel.grid(row=0, column=0, columnspan=2, padx=0, pady=(5,0), sticky="nsew")
        year_now = dt.date.today().year
        choices = list(range(year_now - 5, year_now + 1))
        self.yearOptionVar = tk.StringVar(self)
        self.yearOptionMenu = ttk.OptionMenu(self.accountingFrame, self.yearOptionVar, self._config.get_accounting_year(), *choices, command=self.year_option_changed)
        self.yearOptionMenu.grid(row=1, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")

        self.bookingPeriodLabel = ttk.Label(master=self.accountingFrame, text="Buchungsturnus", anchor="w")
        self.bookingPeriodLabel.grid(row=2, column=0, columnspan=2, padx=0, pady=(5,0), sticky="nsew")
        self.bookingPeriodOptionVar = tk.StringVar(self)
        self.bookingPeriodOptions = ['Erstes Halbjahr', 'Zweites Halbjahr', 'Beide']
        idx = int(self._config.get_accounting_halfyear()) - 1
        self.bookingPeriodOptionMenu = ttk.OptionMenu(self.accountingFrame, self.bookingPeriodOptionVar, self.bookingPeriodOptions[idx], *self.bookingPeriodOptions,
                                                      command=self.booking_period_option_changed)
        self.bookingPeriodOptionMenu.grid(row=3, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")

        self.bookingDateLabel = ttk.Label(master=self.accountingFrame, text="Fälligkeitsdatum", anchor="w")
        self.bookingDateLabel.grid(row=4, column=0, columnspan=2, padx=0, pady=(5,0), sticky="nsew")
        self.bookingDateCalendar = DateEntry(self.accountingFrame, selectmode='none', date_pattern='dd.mm.yyyy')
        self.bookingDateCalendar.set_date(self._config.get_accounting_date())
        self.bookingDateCalendar.grid(row=5, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")

        self.mandatePathLabel = ttk.Label(master=self.accountingFrame, text="Mandate Pfad", anchor="w")
        self.mandatePathLabel.grid(row=6, column=0, columnspan=2, padx=0, pady=(5,0), sticky="nsew")
        self.mandatePathVar = tk.StringVar(self)
        self.mandatePathVar.set(self._config.get_position_file())
        self.mandatePathEntry = ttk.Entry(master=self.accountingFrame, textvariable=self.mandatePathVar)
        self.mandatePathEntry.grid(row=7, column=0, padx=0, pady=5)
        self.mandatePathButton = ttk.Button(master=self.accountingFrame, text="Öffnen", command=self.position_path_open_dialog)
        self.mandatePathButton.grid(row=7, column=1, padx=0, pady=5)
        self.generateLabel = ttk.Label(master=self.accountingFrame, text="Generierung", anchor="w")
        self.generateLabel.grid(row=8, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.sepaVar = IntVar()
        self.sepaVar.set(0)
        self.sepaCheckbox = ttk.Checkbutton(master=self.accountingFrame, text="SEPA XML", onvalue=1, offvalue=0, variable=self.sepaVar)
        self.sepaCheckbox.grid(row=9, column=0, padx=0, pady=5)

        self.startButton = ttk.Button(master=self, style="Accent.TButton",
                                                text="Start",
                                                command=self.start)
        self.startButton.grid(row=2, column=0, padx=(10,0), pady=(0,10), sticky="nsew")

        # ============ feesFrame ================
        self.feeDescriptionLabel = tk.Text(master=self.feesFrame, height=6, width=40, bd=0, wrap=tk.WORD)
        self.feeDescriptionLabel.grid(row=0, column=0, columnspan=2, padx=0, pady=(5, 5), sticky="nsew")
        self.feeDescriptionLabel.insert(tk.END, "Der Mitgliedsbeitrag bezieht sich auf den Jahresbeitrag"
                                                " und setzt sich aus dem DPSG Beitrag + dem Stammesbeitrag zusammen."
                                                " Bitte hier die Summe angeben. Für den sozialermäßigten "
                                                "Beitrag ist kein eigener Stammesbeitrag vorgesehen.")
        self.feeDescriptionLabel.config(state='disabled')

        self.feeSeparator = ttk.Separator(master=self.feesFrame,orient='horizontal')
        self.feeSeparator.grid(row=1, column=0, columnspan=2, padx=0, pady=(0, 0), sticky="nsew")

        vcmd = (self.register(self.validate_float))
        self.fullFeeLabel = ttk.Label(master=self.feesFrame, text="Voller Beitrag", anchor="w")
        self.fullFeeLabel.grid(row=2, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.fullFeeEntry = ttk.Entry(master=self.feesFrame, validate='all', validatecommand=(vcmd, '%P'))
        fees = self._config.get_membership_fees()
        self.fullFeeEntry.insert(tk.END, str(fees.get_fee_full_annual()))
        self.fullFeeEntry.grid(row=3, column=0, padx=0, pady=5)
        self.fullFeeCurrencyLabel = ttk.Label(master=self.feesFrame, text="€", anchor="w")
        self.fullFeeCurrencyLabel.grid(row=3, column=1, padx=(5, 0), pady=(5, 0), sticky="nsew")

        self.familyFeeLabel = ttk.Label(master=self.feesFrame, text="Familienermäßigt", anchor="w")
        self.familyFeeLabel.grid(row=4, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.familyFeeEntry = ttk.Entry(master=self.feesFrame, validate='all', validatecommand=(vcmd, '%P'))
        fees = self._config.get_membership_fees()
        self.familyFeeEntry.insert(tk.END, str(fees.get_fee_family_annual()))
        self.familyFeeEntry.grid(row=5, column=0, padx=0, pady=5)
        self.familyFeeCurrencyLabel = ttk.Label(master=self.feesFrame, text="€", anchor="w")
        self.familyFeeCurrencyLabel.grid(row=5, column=1, padx=(5, 0), pady=(5, 0), sticky="nsew")

        self.socialFeeLabel = ttk.Label(master=self.feesFrame, text="Sozialermäßigt", anchor="w")
        self.socialFeeLabel.grid(row=6, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.socialFeeEntry = ttk.Entry(master=self.feesFrame, validate='all', validatecommand=(vcmd, '%P'))
        fees = self._config.get_membership_fees()
        self.socialFeeEntry.insert(tk.END, str(fees.get_fee_social_annual()))
        self.socialFeeEntry.grid(row=7, column=0, padx=0, pady=5)
        self.socialFeeCurrencyLabel = ttk.Label(master=self.feesFrame, text="€", anchor="w")
        self.socialFeeCurrencyLabel.grid(row=7, column=1, padx=(5, 0), pady=(5, 0), sticky="nsew")

        # ============ creditorFrame ================
        sepa = self._config.get_creditor_id()
        self.creditorNameLabel = ttk.Label(master=self.creditorFrame, text="Name", anchor="w")
        self.creditorNameLabel.grid(row=0, column=0, padx=0, pady=(5,0), sticky="nsew")
        self.creditorNameEntry = ttk.Entry(master=self.creditorFrame, width=30)
        self.creditorNameEntry.grid(row=1, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorNameEntry.insert(tk.END, sepa.name)

        self.creditorIbanLabel = ttk.Label(master=self.creditorFrame, text="IBAN", anchor="w")
        self.creditorIbanLabel.grid(row=2, column=0, padx=0, pady=(5,0), sticky="nsew")
        self.creditorIbanEntry = ttk.Entry(master=self.creditorFrame)
        self.creditorIbanEntry.grid(row=3, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorIbanEntry.insert(tk.END, sepa.iban)

        self.creditorIbanEntry.bind('<FocusOut>', self.validate_iban)
        self.creditorIbanEntry.bind('<FocusIn>', self.validate_iban)
        self.creditorIbanEntry.bind('<KeyRelease>', self.validate_iban)

        self.creditorBicLabel = ttk.Label(master=self.creditorFrame, text="BIC", anchor="w")
        self.creditorBicLabel.grid(row=4, column=0, padx=0, pady=(5,0), sticky="nsew")
        self.creditorBicEntry = ttk.Entry(master=self.creditorFrame, state='disabled')
        self.creditorBicEntry.grid(row=5, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorBicEntry.insert(tk.END, sepa.bic)

        self.creditorIdLabel = ttk.Label(master=self.creditorFrame, text="Gläubiger ID", anchor="w")
        self.creditorIdLabel.grid(row=6, column=0, padx=0, pady=(5,0), sticky="nsew")
        self.creditorIdEntry = ttk.Entry(master=self.creditorFrame)
        self.creditorIdEntry.grid(row=7, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorIdEntry.insert(tk.END, sepa.id)

        self.validate_iban()

        # ============ frame_members ============
        self.memberNotebook = ttk.Notebook(self)
        self.memberNotebook.bind("<<NotebookTabChanged>>", self.enableCorrectScrollbar)
        self.memberNotebook.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))

        columns = ('member_number', 'first_name', 'last_name', 'start_date', 'iban', 'fee')
        readableNames = ('Mitgliedsnummer', 'Vorname', 'Nachname', 'Eintrittsdatum', 'IBAN', 'Beitrag')
        self.memberTree = TableEdit(master=self.memberNotebook, columns=columns, readableNames=readableNames, editable=False)

        self.memberTree.column("member_number", stretch="no", width=120)
        self.memberTree.column("first_name", stretch="yes", minwidth=120)
        self.memberTree.column("last_name", stretch="yes", minwidth=150)
        self.memberTree.column("start_date", stretch="no", width=100)
        self.memberTree.column("iban", stretch="no", width=170)
        self.memberTree.column("fee", stretch="no", width=80)
        self.memberNotebook.add(self.memberTree, text='Mitglieder')
        # add a scrollbar
        self.memberScrollbar = ttk.Scrollbar(master=self, orient=tk.VERTICAL, command=self.memberTree.yview)
        self.memberTree.configure(yscroll=self.memberScrollbar.set)
        self.memberScrollbar.grid(row=0, column=2, padx=(0, 10), pady=(51, 0), sticky='ns')


        # ============= frame_mandate ===========
        columns = ('member_number', 'mandat_reference', 'name', 'date', 'bank', 'bic', 'iban')
        readableNames = ('Mitgliedsnummer', 'Mandatsreferenz', 'Name', 'Austellungsdatum', 'Kreditinstitut', 'BIC', 'IBAN')
        self.mandateTree = TableEdit(master=self.memberNotebook, columns=columns, readableNames=readableNames, editable=True)
        self.memberNotebook.add(self.mandateTree, text='Mandate')
        # add a scrollbar
        self.mandateScrollbar = ttk.Scrollbar(master=self, orient=tk.VERTICAL, command=self.mandateTree.yview)
        self.mandateTree.configure(yscroll=self.mandateScrollbar.set)
        self.mandateScrollbar.grid(row=0, column=2, padx=(0,10), pady=(51,0), sticky='ns')

        # ============ frame_logging ============
        # Logging configuration
        logging.basicConfig(filename='test.log',level=logging.DEBUG)
        # Add the handler to logger
        logger = logging.getLogger()
        logger.addHandler(self.frame_logging.logging_handler)

    def enableCorrectScrollbar(self, event):
        if self.memberNotebook.index(self.memberNotebook.select()) == 0:
            self.memberScrollbar.grid()
            self.mandateScrollbar.grid_remove()
            self.memberScrollbar.tkraise()
        elif self.memberNotebook.index(self.memberNotebook.select()) == 1:
            self.mandateScrollbar.grid()
            self.memberScrollbar.grid_remove()
            self.mandateScrollbar.tkraise()

    def nami_login(self):
        username = self.usernameEntry.get()
        password = self.passwordEntry.get()
        nami = Nami(username, password)
        self._nami = None
        if nami.check_login():
            self._nami = nami

    def position_path_open_dialog(self):
        filetypes = (('csv files', '*.csv'),)
        filePath = filedialog.askopenfilename(title='VR-Networld Mandate Pfad', filetypes=filetypes)
        self._config.set_position_file(filePath)
        self.mandatePathVar.set(filePath)

    def year_option_changed(self, *args):
        self._config.set_accounting_year(self.yearOptionVar.get())

    def booking_period_option_changed(self, *args):
        if self.bookingPeriodOptionVar.get() == self.bookingPeriodOptions[0]:
            self._config.set_accounting_halfyear(int(BookingHalfYear.FIRST))
        elif self.bookingPeriodOptionVar.get() == self.bookingPeriodOptions[1]:
            self._config.set_accounting_halfyear(int(BookingHalfYear.SECOND))
        elif self.bookingPeriodOptionVar.get() == self.bookingPeriodOptions[2]:
            self._config.set_accounting_halfyear(int(BookingHalfYear.BOTH))

    def set_membership_fees(self):
        full = float(self.fullFeeEntry.get())
        family = float(self.familyFeeEntry.get())
        social = float(self.socialFeeEntry.get())

        fees = MembershipFees(BookingHalfYear.BOTH, full, family, social)
        self._config.set_membership_fees(fees)

    def start(self):
        # Clear log and Member tree
        self.frame_logging.clear()
        self.memberTree.delete(*self.memberTree.get_children())
        self.save()
        if self._nami is None:
            self.nami_login()
        if self._nami is not None:
            self._sepa = None
            s = self._config.get_creditor_id()
            self._sepa = Sepa(s.name, s.iban, s.bic, s.id)
            if self._sepa.check_config() is False:
                logging.error('Gläubiger Identifikation inkorrekt. Bitte nochmal die Daten überprüfen.')
                return

            process = RunAccounting(self._config, self.memberTree, self._nami, self._sepa)
            process.start()
            self.monitor(process)

            # Write SEPA XML file
            if self.sepaVar.get() == 1:
                success = self._sepa.export('sepa_' + str(self._config.get_accounting_year()) + '.xml')
                if success is False:
                    logging.error('SEPA Xml Generierung schlug fehl. Bitte die Gläubiger Identifikation nochmal überprüfen.')

    def on_closing(self, event=0):
        del self._nami
        self.save()
        self._parent.destroy()

    def save(self, event=0):
        self.set_membership_fees()
        self._config.set_nami_username(self.usernameEntry.get())
        self._config.set_nami_password(self.passwordEntry.get())
        self._config.set_accounting_date(self.bookingDateCalendar.get_date())
        self._config.set_position_file(self.mandatePathEntry.get())
        sepa = SepaWrapper(self.creditorNameEntry.get(), self.creditorIbanEntry.get(), self.creditorBicEntry.get(), self.creditorIdEntry.get())
        self._config.set_creditor_id(sepa)
        self._config.save()
        logging.debug('Konfiguration gespeichert')

    def monitor(self, thread):
        while thread.is_alive():
            # check the thread every 100ms
            self._parent.update()

    def validate_iban(self, event=0):
        pass
        try:
            iban = IBAN(self.creditorIbanEntry.get())
            self.creditorIbanEntry.state(['!invalid'])
            self.creditorBicEntry.configure(state='enable')
            self.creditorBicEntry.delete(0, tk.END)
            self.creditorBicEntry.insert(tk.END, iban.bic)
            self.creditorBicEntry.configure(state='disable')
        except ValueError:
            self.creditorIbanEntry.state(['invalid'])
            self.creditorBicEntry.configure(state='enable')
            self.creditorBicEntry.delete(0, tk.END)
            self.creditorBicEntry.configure(state='disable')

    def validate_float(self, P):
        try:
            float(P)
            return True
        except:
            return False

    def validate_int(self, P):
        try:
            int(P)
            return True
        except:
            return False

    def importMandate(self):
        v = VRImport(self.mandatePathEntry.get())

        self.memberNotebook.select(1)
        self.enableCorrectScrollbar(0)
        for m in v.mandate:
            self.mandateTree.insert('', tk.END, values=m.get_for_treeview())

        logging.debug(str(v.get_nof_mandate()) + ' Mandate erfolgreich aus der CSV Datei importiert.')


def main():
    root = tk.Tk()
    root.title("Nami Beitragsrechner Version 0.1")

    try:
        # Get the absolute path of the temp directory
        pathToDpsgIcon = path.abspath(path.join(path.dirname(__file__), 'img/favicon.ico'))
        # Set the DPSG Logo as icon
        root.iconbitmap(pathToDpsgIcon)
    except:
        pass

    sv_ttk.set_theme("light")

    app = App(root)
    app.pack(fill="both", expand=True)

    root.update_idletasks()  # Make sure every screen redrawing is done

    width, height = root.winfo_width(), root.winfo_height()
    width = 1110
    height = 785
    x = int((root.winfo_screenwidth() / 2) - (width / 2))
    y = int((root.winfo_screenheight() / 2) - (height / 2))

    # Set a minsize for the window, and place it in the middle
    root.minsize(width, height)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
