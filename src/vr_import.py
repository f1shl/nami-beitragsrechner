import csv
import tools


class VRMandat:
    headerdict = {
        "Bezeichnung": 0,
        "Mandatsreferenz": 0,
        "Mandatsdatum": 0,
        "Lastschriftsequenz": 0,
        "Zahler Name": 0,
        "Zahler Vorname": 0,
        "Zahler IBAN": 0,
        "Zahler BIC": 0,
        "Mandatsstatus": 0
    }

    def __init__(self, header, csv_row):
        # Extract header
        try:
            self.headerdict["Bezeichnung"] = header.index("Bezeichnung")
            self.headerdict["Mandatsreferenz"] = header.index("Mandatsreferenz")
            self.headerdict["Mandatsdatum"] = header.index("Mandatsdatum")
            self.headerdict["Lastschriftsequenz"] = header.index("Lastschriftsequenz")
            self.headerdict["Zahler Name"] = header.index("Zahler Name")
            self.headerdict["Zahler Vorname"] = header.index("Zahler Vorname")
            self.headerdict["Zahler IBAN"] = header.index("Zahler IBAN")
            self.headerdict["Zahler BIC"] = header.index("Zahler BIC")
            self.headerdict["Mandatsstatus"] = header.index("Mandatsstatus")
        except Exception as e:
            raise ValueError('Benötigte Spalte fehlt in der exportierten Mandatenliste aus VR-Networld: ' + str(e))

        self.used = False  # Defines if the Mandat was used at least once. This is useful to find unused Mandate and for double check
        self.bezeichnung = csv_row[self.headerdict["Bezeichnung"]]
        self.mandatsreferenz = csv_row[self.headerdict["Mandatsreferenz"]]
        self.mandatsdatum = csv_row[self.headerdict["Mandatsdatum"]]
        self.lastschriftsequenz = csv_row[self.headerdict["Lastschriftsequenz"]]
        self.nachname = csv_row[self.headerdict["Zahler Name"]]
        # remove any colons
        self.nachname = self.nachname.replace(',', ' ')
        self.nachname = tools.replace_umlaute_and_s(self.nachname)
        self.vorname = csv_row[self.headerdict["Zahler Vorname"]]
        self.vorname = self.vorname.replace(',', ' ')
        self.vorname = tools.replace_umlaute_and_s(self.vorname)

        self.iban = csv_row[self.headerdict["Zahler IBAN"]]
        self.bic = csv_row[self.headerdict["Zahler BIC"]]
        self.mandatsstatus = csv_row[self.headerdict["Mandatsstatus"]]

    def check_name(self, name):
        combined_name = self.nachname + " " + self.vorname
        name_cleaned = tools.replace_umlaute_and_s(name)
        # Do the compare this way, as it is not ensured that the first name and the surname are in the same order
        # in both databases
        if sorted(combined_name.split()) == sorted(name_cleaned.split()):
            return True

        return False

    def check_iban(self, iban):
        if self.iban == iban:
            return True
        else:
            return False

    def is_first_lastschrift(self):
        if 'erstmalige' in self.lastschriftsequenz and \
                'vorbereitet' in self.mandatsstatus:
            return True
        else:
            return False


class VRImport:
    def __init__(self, csv_path):
        self.mandate = []
        with open(csv_path, 'r', newline='', encoding='iso-8859-1') as f:
            reader = csv.reader(f, delimiter=';')
            header = []
            # read each row and create VRMandat object from it
            first = True
            for row in reader:
                if first:
                    header = row
                    first = False
                else:
                    mandat = VRMandat(header, row)
                    self.mandate.append(mandat)
        if len(self.mandate) == 0:
            tools.print_error('VR-Networld Mandatenliste ' + csv_path + ' ist leer. Bitte nochmal überprüfen.')
            raise Exception('VR-Networld Mandatenliste ' + csv_path + ' ist leer. Bitte nochmal überprüfen.')

    def find_correct_mandat(self, member) -> VRMandat:
        # Try to find correct Mandate
        matched_mandate = []
        # Get all mandate which match the ID or the name and IBAN from the member
        for mandat in self.mandate:
            if mandat.bezeichnung == str(member.id) or \
                    (mandat.check_name(member.kontoverbindung.kontoinhaber) and mandat.check_iban(
                        member.kontoverbindung.iban)):
                matched_mandate.append(mandat)

        # First check: If ID is the same and the IBAN, use the Mandat
        for mandat in matched_mandate:
            if mandat.bezeichnung == str(member.id) and mandat.check_iban(member.kontoverbindung.iban):
                mandat.used = True
                return mandat

        # Second check: If Name and IBAN is the same, use the Mandat
        for mandat in matched_mandate:
            if mandat.check_name(member.kontoverbindung.kontoinhaber) and mandat.check_iban(
                    member.kontoverbindung.iban):
                mandat.used = True
                return mandat

        return None

    def get_nof_used_mandate(self):
        count = 0
        for mandat in self.mandate:
            if mandat.used:
                count = count + 1
        return count

    def get_not_used_mandate(self) -> VRMandat:
        mandate = []
        for mandat in self.mandate:
            if not mandat.used:
                mandate.append(mandat)
        return mandate

    def get_nof_mandate(self):
        return len(self.mandate)
