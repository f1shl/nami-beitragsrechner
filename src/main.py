import sys
import platform
import tkinter
import tkinter as tk
from tkinter import ttk, filedialog, IntVar
import sv_ttk
import logging
import LoggingHandlerFrame as loggingFrame
import version
from accounting import NamiAccounting
from threading import Thread
from nami import Nami
from tools import Config, BookingHalfYear, MembershipFees, SepaWrapper
import platformdirs
from pathlib import Path

print = logging.info
import datetime as dt
from tkcalendar import DateEntry
from sepa import Sepa
from schwifty import IBAN
from os import path


class RunAccounting(Thread):
    def __init__(self, config_path: str, config: Config, memberTree, nami: Nami, sepa: Sepa):
        super().__init__()
        self.m = NamiAccounting(config_path, config, memberTree, nami, sepa)

    def run(self):
        self.m.process()


class App(ttk.Frame):
    def __init__(self, parent, root_path: str):
        ttk.Frame.__init__(self, parent)
        self._parent = parent
        self._root_path = root_path

        # App and Authorname
        appname = "NamiBeitragsrechner"
        authorname = "DPSG"

        # Init
        self._nami = None
        self._sepa = None

        parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Bind shortcuts
        self._parent.bind('<Control-s>', self.save)

        # Read Config
        self._config_root_path = platformdirs.user_data_dir(appname=appname, appauthor=authorname)
        #if getattr(sys, 'frozen', False):
        #    self._config_root_path = path.dirname(sys.executable)
        
        config_path = path.join(self._config_root_path, 'config.ini')
        self._config = Config(config_path)

        # Read some stuff from the theme (colors and font)
        self._color_foreground = '#fafafa'
        self._color_background = '1c1c1c'
        self._color_disabled_foreground = '#a0a0a0'
        self._color_selected_foreground = '#ffffff'
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
        self.frame_login.grid(row=0, column=0, sticky="nsew", padx=(10, 0),
                              pady=(1, 0))  # Pad one pixel to align it with the TreeView widget
        self.frame_login.grid_columnconfigure(0, weight=1)
        self.frame_login.grid_rowconfigure(0, weight=0)

        # self.frame_config = ttk.LabelFrame(self, text="Konfiguration", padding=(10,10))
        # self.frame_config.grid(row=1, column=0, sticky="nsew", padx=(10,0), pady=(0,10))
        # self.frame_config.grid_columnconfigure(0, weight=1)
        # self.frame_config.grid_rowconfigure(0, weight=0)
        self.configNotebook = ttk.Notebook(self)

        self.accountingFrame = ttk.Frame(master=self.configNotebook, padding=(10, 10))
        self.feesFrame = ttk.Frame(master=self.configNotebook, padding=(10, 10))
        self.creditorFrame = ttk.Frame(master=self.configNotebook, padding=(10, 10))
        self.configNotebook.add(self.accountingFrame, text='Buchung')
        self.configNotebook.add(self.feesFrame, text='Beiträge')
        self.configNotebook.add(self.creditorFrame, text='Gläubiger ID')
        self.configNotebook.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(10, 10))

        self.frame_logging = loggingFrame.LoggingHandlerFrame(self, text="Info", padding=(10, 10))
        self.frame_logging.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(10, 0), pady=(0, 10))

        self.loggingScrollbar = ttk.Scrollbar(master=self, orient=tk.VERTICAL, command=self.frame_logging.text.yview)
        self.frame_logging.text.configure(yscroll=self.loggingScrollbar.set)
        self.loggingScrollbar.grid(row=1, column=2, rowspan=2, padx=(0, 10), pady=(10, 10), sticky='ns')

        # ============ frame_login ============

        # configure grid layout (1x11)

        # self.label_1 = customtkinter.CTkLabel(master=self.frame_left,
        #                                      text="Konfiguration",
        #                                      text_font=("Roboto Medium", -16))  # font name and size in px
        # self.label_1.grid(row=1, column=0)
        vcmd = (self.register(self.validate_int))
        self.usernameLabel = ttk.Label(master=self.frame_login, text="Nami Nummer", anchor="w")
        self.usernameLabel.grid(row=0, column=0, padx=0, pady=(5, 0), sticky="nsew")

        self.usernameEntry = ttk.Entry(master=self.frame_login, validate='all', validatecommand=(vcmd, '%P'))
        self.usernameEntry.grid(row=1, column=0, padx=0, pady=5, sticky="nsew")
        self.usernameEntry.insert(tk.END, self._config.get_nami_username())

        self.passwordLabel = ttk.Label(master=self.frame_login, text="Passwort", anchor="w")
        self.passwordLabel.grid(row=2, column=0, padx=0, pady=(5, 0), sticky="nsew")

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
            pathToDpsgLogo = path.join(self._root_path, 'img/dpsg_logo.png')
            # Set the dpsg logo
            self.dpsgImage = tk.PhotoImage(file=pathToDpsgLogo)
            self.dpsgImageLabel = ttk.Label(master=self.frame_login, image=self.dpsgImage, anchor="w")
        except:
            self.dpsgImageLabel = ttk.Label(master=self.frame_login, text='', anchor="w")

        self.dpsgImageLabel.grid(row=5, column=0, padx=0, pady=(5, 0))

        # ============ accountingFrame ============
        self.bookingYearLabel = ttk.Label(master=self.accountingFrame, text="Buchungsjahr", anchor="w")
        self.bookingYearLabel.grid(row=0, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        year_now = dt.date.today().year
        choices = list(range(year_now - 5, year_now + 1))
        self.yearOptionVar = tk.StringVar(self)
        self.yearOptionMenu = ttk.OptionMenu(self.accountingFrame, self.yearOptionVar,
                                             self._config.get_accounting_year(), *choices,
                                             command=self.year_option_changed)
        self.yearOptionMenu.grid(row=1, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")

        self.bookingPeriodLabel = ttk.Label(master=self.accountingFrame, text="Buchungsturnus", anchor="w")
        self.bookingPeriodLabel.grid(row=2, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.bookingPeriodOptionVar = tk.StringVar(self)
        self.bookingPeriodOptions = ['Erstes Halbjahr', 'Zweites Halbjahr', 'Beide']
        idx = int(self._config.get_accounting_halfyear()) - 1
        self.bookingPeriodOptionMenu = ttk.OptionMenu(self.accountingFrame, self.bookingPeriodOptionVar,
                                                      self.bookingPeriodOptions[idx], *self.bookingPeriodOptions,
                                                      command=self.booking_period_option_changed)
        self.bookingPeriodOptionMenu.grid(row=3, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")

        self.bookingDateLabel = ttk.Label(master=self.accountingFrame, text="Fälligkeitsdatum", anchor="w")
        self.bookingDateLabel.grid(row=4, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.bookingDateCalendar = DateEntry(self.accountingFrame, selectmode='none', date_pattern='dd.mm.yyyy',
                                             font='SunValleyBodyFont', foreground=self._color_foreground,
                                             background=self._color_background,
                                             disabledforeground=self._color_disabled_foreground,
                                             selectedforeground=self._color_selected_foreground)
        self.bookingDateCalendar.set_date(self._config.get_accounting_date())
        self.bookingDateCalendar.grid(row=5, column=0, columnspan=2, padx=0, pady=5, sticky="nsew")
        #Mandate folder
        self.mandatePathLabel = ttk.Label(master=self.accountingFrame, text="Mandate Pfad", anchor="w")
        self.mandatePathLabel.grid(row=6, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.mandatePathVar = tk.StringVar(self)
        self.mandatePathVar.set(self._config.get_position_file())
        self.mandatePathEntry = ttk.Entry(master=self.accountingFrame, textvariable=self.mandatePathVar)
        self.mandatePathEntry.grid(row=7, column=0, padx=0, pady=5)
        self.mandatePathButton = ttk.Button(master=self.accountingFrame, text="Öffnen",
                                            command=self.position_path_open_dialog)
        self.mandatePathButton.grid(row=7, column=1, padx=0, pady=5)
        # Output folder
        self.savePathLabel = ttk.Label(master=self.accountingFrame, text="Speicher Pfad", anchor="w")
        self.savePathLabel.grid(row=8, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.savePathVar = tk.StringVar(self)
        self.savePathVar.set(self._config.get_save_path())
        self.savePathEntry = ttk.Entry(master=self.accountingFrame, textvariable=self.savePathVar)
        self.savePathEntry.grid(row=9, column=0, padx=0, pady=5)
        self.savePathButton = ttk.Button(master=self.accountingFrame, text="Öffnen",
                                            command=self.save_path_open_dialog)
        self.savePathButton.grid(row=9, column=1, padx=0, pady=5)

        self.generateLabel = ttk.Label(master=self.accountingFrame, text="Generierung", anchor="w")
        self.generateLabel.grid(row=10, column=0, columnspan=2, padx=0, pady=(5, 0), sticky="nsew")
        self.sepaVar = IntVar()
        self.sepaVar.set(0)
        self.sepaCheckbox = ttk.Checkbutton(master=self.accountingFrame, text="SEPA XML", onvalue=1, offvalue=0,
                                            variable=self.sepaVar)
        self.sepaCheckbox.grid(row=11, column=0, padx=0, pady=5)

        self.startButton = ttk.Button(master=self, style="Accent.TButton",
                                      text="Start",
                                      command=self.start)
        self.startButton.grid(row=2, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")

        # ============ feesFrame ================
        self.feeDescriptionLabel = tk.Text(master=self.feesFrame, height=6, width=40, bd=0, wrap=tk.WORD)
        self.feeDescriptionLabel.grid(row=0, column=0, columnspan=2, padx=0, pady=(5, 5), sticky="nsew")
        self.feeDescriptionLabel.insert(tk.END, "Der Mitgliedsbeitrag bezieht sich auf den Jahresbeitrag"
                                                " und setzt sich aus dem DPSG Beitrag + dem Stammesbeitrag zusammen."
                                                " Bitte hier die Summe angeben. Für den sozialermäßigten "
                                                "Beitrag ist kein eigener Stammesbeitrag vorgesehen.")
        self.feeDescriptionLabel.config(state='disabled')

        self.feeSeparator = ttk.Separator(master=self.feesFrame, orient='horizontal')
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
        self.creditorNameLabel.grid(row=0, column=0, padx=0, pady=(5, 0), sticky="nsew")
        self.creditorNameEntry = ttk.Entry(master=self.creditorFrame, width=30)
        self.creditorNameEntry.grid(row=1, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorNameEntry.insert(tk.END, sepa.name)

        self.creditorIbanLabel = ttk.Label(master=self.creditorFrame, text="IBAN", anchor="w")
        self.creditorIbanLabel.grid(row=2, column=0, padx=0, pady=(5, 0), sticky="nsew")
        self.creditorIbanEntry = ttk.Entry(master=self.creditorFrame)
        self.creditorIbanEntry.grid(row=3, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorIbanEntry.insert(tk.END, sepa.iban)

        self.creditorIbanEntry.bind('<FocusOut>', self.validate_iban)
        self.creditorIbanEntry.bind('<FocusIn>', self.validate_iban)
        self.creditorIbanEntry.bind('<KeyRelease>', self.validate_iban)

        self.creditorBicLabel = ttk.Label(master=self.creditorFrame, text="BIC", anchor="w")
        self.creditorBicLabel.grid(row=4, column=0, padx=0, pady=(5, 0), sticky="nsew")
        self.creditorBicEntry = ttk.Entry(master=self.creditorFrame, state='disabled')
        self.creditorBicEntry.grid(row=5, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorBicEntry.insert(tk.END, sepa.bic)

        self.creditorIdLabel = ttk.Label(master=self.creditorFrame, text="Gläubiger ID", anchor="w")
        self.creditorIdLabel.grid(row=6, column=0, padx=0, pady=(5, 0), sticky="nsew")
        self.creditorIdEntry = ttk.Entry(master=self.creditorFrame)
        self.creditorIdEntry.grid(row=7, column=0, padx=0, pady=5, sticky="nsew")
        self.creditorIdEntry.insert(tk.END, sepa.id)

        self.validate_iban()

        # ============ frame_members ============
        columns = ('member_number', 'first_name', 'last_name', 'start_date', 'iban', 'fee')
        self.memberTree = ttk.Treeview(master=self, columns=columns, show='headings')
        self.memberTree.heading('member_number', text='Mitgliedsnummer', command=lambda _col='member_number': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.heading('first_name', text='Vorname', command=lambda _col='first_name': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.heading('last_name', text='Nachname', command=lambda _col='last_name': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.heading('start_date', text='Eintrittsdatum', command=lambda _col='start_date': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.heading('iban', text='IBAN', command=lambda _col='iban': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.heading('fee', text='Beitrag', command=lambda _col='fee': \
            self.treeview_sort_column(self.memberTree, _col, False))
        self.memberTree.column("member_number", stretch="no", width=120)
        self.memberTree.column("first_name", stretch="yes", minwidth=120)
        self.memberTree.column("last_name", stretch="yes", minwidth=150)
        self.memberTree.column("start_date", stretch="no", width=100)
        self.memberTree.column("iban", stretch="no", width=170)
        self.memberTree.column("fee", stretch="no", width=80)
        self.memberTree.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))

        # add a scrollbar
        self.memberScrollbar = ttk.Scrollbar(master=self, orient=tk.VERTICAL, command=self.memberTree.yview)
        self.memberTree.configure(yscroll=self.memberScrollbar.set)
        self.memberScrollbar.grid(row=0, column=2, padx=(0, 10), pady=(10, 0), sticky='ns')

        # ============ frame_logging ============
        # Logging configuration
        logging.basicConfig(filename=path.join(self._config_root_path, 'log.log'), level=logging.DEBUG)
        # Add the handler to logger
        logger = logging.getLogger()
        logger.addHandler(self.frame_logging.logging_handler)

    def nami_login(self):
        username = self.usernameEntry.get()
        password = self.passwordEntry.get()
        self.config(cursor="watch")
        self.update()
        nami = Nami(username, password)
        self._nami = None
        if nami.check_login():
            self._nami = nami
        self.config(cursor="")
        
    def position_path_open_dialog(self):
        filetypes = (('csv files', '*.csv'),)
        filepath = filedialog.askopenfilename(title='VR-Networld Mandate Pfad', filetypes=filetypes)
        if filepath != "":
            self._config.set_position_file(filepath)
            self.mandatePathVar.set(filepath)

    def save_path_open_dialog(self):
        filetypes = (('csv files', '*.csv'),)
        filepath = filedialog.askdirectory(title='Speicherpfad')
        if filepath != "":
            self._config.set_save_path(filepath)
            self.savePathVar.set(filepath)

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

            process = RunAccounting(self._config_root_path, self._config, self.memberTree, self._nami, self._sepa)
            process.start()
            self.monitor(process)

            # Write SEPA XML file
            if self.sepaVar.get() == 1:
                filepath = str(Path(self._config.get_save_path()) / Path('sepa_' + str(self._config.get_accounting_year()) +
                                                                     '_' + str(int(self._config.get_accounting_halfyear())) + '.xml'))
                if Path(filepath).exists():
                    ans = tkinter.messagebox.askquestion("Datei überschreiben?",
                                                         f"{filepath} existiert bereits. Überschreiben?")
                    if ans == 'no':
                        i = 1
                        while Path(filepath).exists():
                            filepath = str(Path(self._config.get_save_path()) / Path('sepa_' + str(self._config.get_accounting_year()) +
                                                                         '_' + str(int(self._config.get_accounting_halfyear())) + f' ({i}).xml'))
                            i = i + 1
                success = self._sepa.export(filepath)
                if success is False:
                    logging.error(
                        'SEPA Xml Generierung schlug fehl. Bitte die Gläubiger Identifikation nochmal überprüfen.')

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
        sepa = SepaWrapper(self.creditorNameEntry.get(), self.creditorIbanEntry.get(), self.creditorBicEntry.get(),
                           self.creditorIdEntry.get())
        self._config.set_creditor_id(sepa)
        self._config.save()
        logging.debug('Konfiguration gespeichert')

    def monitor(self, thread):
        while thread.is_alive():
            # check the thread every 100ms
            self._parent.update()

    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        l.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # reverse sort next time
        tv.heading(col, command=lambda _col=col: \
            self.treeview_sort_column(tv, _col, not reverse))

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


def main():
    root = tk.Tk()
    root.title("Nami Beitragsrechner Version " + version.__version__)

    # Get the root path of the executable or main.py script
    # Get the absolute path of the temp directory
    root_path = path.abspath(path.join(path.dirname(__file__), '../'))
    # Different folder, if application got build
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        root_path = path.abspath(path.dirname(__file__))
        
    try:
        # Get the absolute path of the temp directory
        if platform.system() == "Windows":
            pathToDpsgIcon = path.join(root_path, 'img/favicon.ico')
        else:
            pathToDpsgIcon = path.join(root_path, 'img/favicon.icns')

        # Set the DPSG Logo as icon
        root.iconbitmap(pathToDpsgIcon)
    except:
        pass

    sv_ttk.set_theme("light")

    app = App(root, root_path)
    app.pack(fill="both", expand=True)

    root.update_idletasks()  # Make sure every screen redrawing is done

    width, height = root.winfo_width(), root.winfo_height()
    width = 1110
    height = 800
    x = int((root.winfo_screenwidth() / 2) - (width / 2))
    y = int((root.winfo_screenheight() / 2) - (height / 2))

    # Set a minsize for the window, and place it in the middle
    root.minsize(width, height)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
