from pynami.nami import NaMi
from pynami.tools import tabulate2x
import csv
from schwifty import IBAN, BIC
from vr_import import VRImport, VRMandat
from colorama import init
import tools
from termcolor import colored
import datetime
from marshmallow import exceptions
import configparser
from enum import Enum
from pdf_converter import PdfConverter, PdfMember, PdfMemberList
from pathlib import Path


class BookingHalfYear(Enum):
    FIRST = 1
    SECOND = 2
    BOTH = 3


class MembershipFees:
    def __init__(self, bookingHalfYear, feeFull, feeFamily, feeSocial):
        self._feeFull = feeFull
        self._feeFamily = feeFamily
        self._feeSocial = feeSocial
        self._bookingHalfYear = bookingHalfYear

    def get_fee_full(self):
        if self._bookingHalfYear == BookingHalfYear.BOTH:
            return self._feeFull
        else:
            return self._feeFull / 2

    def get_fee_family(self):
        if self._bookingHalfYear == BookingHalfYear.BOTH:
            return self._feeFamily
        else:
            return self._feeFamily / 2

    def get_fee_social(self):
        if self._bookingHalfYear == BookingHalfYear.BOTH:
            return self._feeSocial
        else:
            return self._feeSocial / 2


class ConfigReader:
    def __init__(self, configPath):
        self._config = configparser.ConfigParser()
        self._config.read(configPath)

    def get_nami_username(self):
        return self._config['Nami Login']['Username']

    def get_nami_password(self):
        return self._config['Nami Login']['Password']

    def get_accounting_year(self):
        return int(self._config['General']['Accounting Year'])        # Jahr für das die Beiträge eingezogen werden sollen

    def get_accounting_date(self):
        return self._config['General']['Booking Date']                # Format in TT.MM.JJJJ. Termin zur SEPA Lastschriftausführung

    def get_accounting_halfyear(self) -> BookingHalfYear:
        return BookingHalfYear(int(self._config['General']['Accounting Half-Year']))

    def get_position_file(self) -> str:
        return self._config['General']['Mandate Path']

    def get_membership_fees(self) -> MembershipFees:
        return MembershipFees(self.get_accounting_halfyear(), float(self._config['Membership Fee']['Full']),
                              float(self._config['Membership Fee']['Family']),
                              float(self._config['Membership Fee']['Social']))

    def get_key_date_frist_half(self) -> datetime.date:
        # Get the accounting year first
        year = self.get_accounting_year()
        s = self._config['Key Dates']['First Half-Year'] + '.' + str(year)
        return datetime.datetime.strptime(s, '%d.%m.%Y').date()

    def get_key_date_second_half(self) -> datetime.date:
        # Get the accounting year first
        year = self.get_accounting_year()
        s = self._config['Key Dates']['Second Half-Year'] + '.' + str(year)
        return datetime.datetime.strptime(s, '%d.%m.%Y').date()

    def get_schnupper_weeks(self) -> datetime.timedelta:
        weeks = int(self._config['Key Dates']['Schnupper Weeks'])
        return datetime.timedelta(weeks = weeks)


class CsvWriter:
    # CSV header
    _header = ['Mitgliedsnummer', 'Nachname', 'Vorname', 'Zahler/Zahlungsempfänger',
               'IBAN Zielkonto', 'BIC Zielkonto', 'Betrag in EUR', 'Mandatsreferenz',
               'Mandatsdatum', 'Termin', 'SEPA-Lastschriftsequenz', 'Verwendungszweck']

    def __init__(self, year):
        self._filename = 'MitgliederAbrechnung_' + str(year) + '.csv'
        # Do this to truncate existing content
        with open(self._filename, 'w', newline='') as f:
            pass
        self.writerow(self._header)

    def writerow(self, row):
        with open(self._filename, 'a', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(row)


class DesignatedUse:
    def get_designated_use(self, accounting_year, bookingHalfYear:BookingHalfYear, beitragsart, name):
        if bookingHalfYear == BookingHalfYear.FIRST:
            year_str = '1/' + str(accounting_year)
        elif bookingHalfYear == BookingHalfYear.SECOND:
            year_str = '2/' + str(accounting_year)
        else:
            year_str = '1/' + str(accounting_year) + ' + 2/' + str(accounting_year)

        return 'Mitgliedsbeitrag ' + year_str + ', ' + beitragsart + '. Mitglied ' + name


class NamiAccounting:

    def __init__(self, configPath):
        self._config = ConfigReader(configPath)
        # use Colorama to make Termcolor work on Windows too
        init()


    def process(self):
        vrImport = VRImport(self._config.get_position_file())
        # Downloads all invoices from DPSG for the given year and removes all entries which are not needed
        # e.g. Removes first half year entries if second half year shall be booked
        dpsg_members = self.download_invoices()
        nof_dpsg_members = dpsg_members.get_nof_unique_members()

        print('Herunterladen aller aktiven Mitglieder aus der Nami...')
        with NaMi(username=self._config.get_nami_username(), password=self._config.get_nami_password()) as nami:

            # Suchmaske für alle aktiven Mitglieder. Hier werden keine inaktiven, noch die Schnuppermitglieder gefunden
            # Die Nami muss also zuvor gepflegt werden, bevor der Export geschehen kann
            search = {
                'mglStatusId': 'AKTIV',
                'mglTypeId': 'MITGLIED'
            }
            result = nami.search(**search)
            print(tabulate2x(result))

            # Error variables
            list_of_missing_mandat = []
            list_of_corrupt_activities = []
            list_of_members_second_half_of_year = []
            list_of_members_in_new_year = []  # Liste von Mitgliedern die erst im neuen Jahr dazu gekommen sind.
            list_of_members_booked_here_but_not_by_dpsg = []
            # Wenn für 2021 abgebucht wird, so darf kein Mitglied von 2022 gebucht werden
            list_of_members_this_year_schnupper = []
            nof_claimed_members = 0  # Zähler, wieviele Mitglieder gebucht werden
            booking_value = 0
            # Create CsvWriter
            writer = CsvWriter(self._config.get_accounting_year())

            # Loop through all members
            for r in result:
                row = []
                member = r.get_mitglied(nami)
                print(r.tabulate())
                combinedName = member.vorname + ' ' + member.nachname
                member.correct_eintrittsdatum = member.eintrittsdatum

                # If member entered the claimed year, check for Schnuppermitgliedschaft to extract the correct entry date
                if member.eintrittsdatum >= datetime.date(self._config.get_accounting_year(), 1, 1):
                    try:
                        activities = nami.mgl_activities(member.id)
                    except exceptions.ValidationError as e:
                        tools.print_error(
                            'Mitglied ' + combinedName + ': Enddatum scheint für die Schnuppermitgliedschaft nicht zu stimmen. ' + str(
                                e))
                        list_of_corrupt_activities.append(member)
                        continue
                    # Last activity in list is the oldest one
                    if 'Schnupper' in activities[-1].taetigkeit:
                        member.correct_eintrittsdatum = member.eintrittsdatum + self._config.get_schnupper_weeks()
                        list_of_members_this_year_schnupper.append(member)

                # Check for correct IBAN and BIC. The following object instantiations raising a ValueError, if BIC or IBAN is wrong
                try:
                    IBAN(member.kontoverbindung.iban)
                except ValueError as e:
                    tools.print_error('IBAN nicht korrekt für Mitglied ' + combinedName + ' Error: ' + str(e))
                    raise ValueError('IBAN nicht korrekt für Mitglied ' + combinedName + ' Error: ' + str(e))

                try:
                    BIC(member.kontoverbindung.bic)
                except ValueError as e:
                    tools.print_error('BIC nicht korrekt für Mitglied ' + combinedName + ' Error: ' + str(e))
                    raise ValueError('BIC nicht korrekt für Mitglied ' + combinedName + ' Error: ' + str(e))

                row.append(member.mitgliedsNummer)
                row.append(member.nachname)
                row.append(member.vorname)
                row.append(member.kontoverbindung.kontoinhaber)
                row.append(member.kontoverbindung.iban)
                row.append(member.kontoverbindung.bic)

                # Create Verwendungszweck
                if 'Voller Beitrag' in member.beitragsart:
                    beitragsart = 'Voller Beitrag'
                    beitragsatz = self._config.get_membership_fees().get_fee_full()
                elif 'Familienermäßigt' in member.beitragsart:
                    beitragsart = 'Familienermaeßigt'
                    beitragsatz = self._config.get_membership_fees().get_fee_family()
                elif 'Sozialermäßigt' in member.beitragsart:
                    beitragsart = 'Sozialermaeßigt'
                    beitragsatz = self._config.get_membership_fees().get_fee_social()
                else:
                    tools.print_error(
                        'Beitragsart ' + member.beitragsart + ' von Mitglied ' + combinedName + ' unbekannt.')
                    raise ValueError(
                        'Beitragsart ' + member.beitragsart + ' von Mitglied ' + combinedName + ' unbekannt.')

                # Check if the member entry date was after the stichtag. If so, only half of the membership fee is claimed
                b = self._config.get_accounting_halfyear()
                if b == BookingHalfYear.FIRST:
                    if member.correct_eintrittsdatum > self._config.get_key_date_frist_half():
                        continue
                    elif member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                       member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                        list_of_members_second_half_of_year.append(member)
                    # Check if member entered in the following year. If so, no claiming should be done
                    elif member.correct_eintrittsdatum > self._config.get_key_date_second_half():
                        list_of_members_in_new_year.append(member)
                        continue
                elif b == BookingHalfYear.SECOND:
                    if member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                       member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                        list_of_members_second_half_of_year.append(member)
                    # Check if member entered in the following year. If so, no claiming should be done
                    elif member.correct_eintrittsdatum > self._config.get_key_date_second_half():
                        list_of_members_in_new_year.append(member)
                        continue
                else:
                    if member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                       member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                        beitragsatz = beitragsatz / 2
                        list_of_members_second_half_of_year.append(member)
                        b = BookingHalfYear.SECOND
                    # Check if member entered in the following year. If so, no claiming should be done
                    elif member.correct_eintrittsdatum > self._config.get_key_date_second_half():
                        list_of_members_in_new_year.append(member)
                        continue

                # Now compare with DPSG invoice and remove from list
                tmp = len(dpsg_members)
                dpsg_members = [x for x in dpsg_members if not x.compare(member)]
                # Check if entries got removed
                if tmp == len(dpsg_members):
                    # Member wasn't booked by DPSG but here
                    list_of_members_booked_here_but_not_by_dpsg.append(member)

                # Zu zahlender Beitrag
                row.append(str(beitragsatz).replace('.', ','))

                # Now search for the correct Mandat in Mandatenliste
                mandat = vrImport.find_correct_mandat(member)
                if mandat == None:
                    list_of_missing_mandat.append(member)
                    continue

                row.append(mandat.mandatsreferenz)
                row.append(mandat.mandatsdatum)
                row.append(self._config.get_accounting_date())

                if mandat.is_first_lastschrift():
                    row.append('erstmalig')
                else:
                    row.append('wiederkehrend')

                # Create Verwendungszweck
                d = DesignatedUse()
                verwendungszweck = d.get_designated_use(self._config.get_accounting_year(), b, beitragsart, combinedName)
                row.append(verwendungszweck)
                # Write to CSV file
                writer.writerow(row)
                nof_claimed_members = nof_claimed_members + 1

                booking_value = booking_value + beitragsatz

            # Info printing
            used = vrImport.get_nof_used_mandate()
            overall = vrImport.get_nof_mandate()
            not_used = overall - used

            print()
            print(colored('--------------------- Abbrechnungsjahr: ' + str(self._config.get_accounting_year()) + ' ---------------------------',
                          'green'))
            tools.print_info('Verarbeitete Mitglieder:      ' + str(len(result)))
            tools.print_info('Fehlerhafte  Mitglieder:      ' + str(
                len(list_of_missing_mandat) + len(list_of_corrupt_activities)) + '/' + str(len(result)))
            tools.print_info('Abzubuchende Mitglieder:      ' + str(nof_claimed_members) + '/' + str(len(result)))
            tools.print_info('Eintritt im zweiten Halbjahr: ' + str(len(list_of_members_second_half_of_year)) + '/' + str(
                    len(result)))
            tools.print_info('Eintritt im neuen Jahr  ' + str(self._config.get_accounting_year() + 1) + ': ' + str(
                len(list_of_members_in_new_year)) + '/' + str(len(result)))
            tools.print_info('Mitglieder von DPSG gebucht:  ' + str(nof_dpsg_members))
            print()
            tools.print_info('Verarbeitete Mandate:         ' + str(overall))
            tools.print_info('Benutzte     Mandate:         ' + str(used) + '/' + str(overall))
            tools.print_info('Gesamtsumme: ' + str(booking_value) + ' EUR')
            print()
            if not_used == 0:
                tools.print_info('Alle SEPA-Mandate wurden erfolgreich verwendet.')
            else:
                tools.print_error(
                    'Nicht alle SEPA-Mandate wurden verwendet. Nochmal die Mandate überprüfen und ggf. bereinigen.')
            print(colored('------------------------------------------------------------------------', 'green'))
            print()

            self.print_member_entry_this_year_as_schnupper(list_of_members_this_year_schnupper)
            #self.print_member_entry_second_half(list_of_members_second_half_of_year)
            self.print_member_entry_new_year(list_of_members_in_new_year)

            # Error printing
            self.print_missing_mandate_members(list_of_missing_mandat)
            list_of_not_used_mandate = vrImport.get_not_used_mandate()
            self.print_not_used_mandate(list_of_not_used_mandate)
            self.print_member_booked_by_dpsg_but_not_here(dpsg_members)
            self.print_member_not_booked_by_dpsg(list_of_members_booked_here_but_not_by_dpsg)

    def print_missing_mandate_members(self, members):

        if len(members) == 0:
            return

        print(colored('--------------------------- Fehlende Mandate ---------------------------', 'red'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_error('Mitgliedsnummer: ' + str(m.mitgliedsNummer) + ' Name: ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'red'))
        print(colored('Bitte die fehlenden Mandate in VR Networld für die Mitglieder anlegen.', 'red'))
        print()

    def print_not_used_mandate(self, mandate: VRMandat):

        if len(mandate) == 0:
            return

        print(colored('----------------------- Nicht verwendete Mandate -----------------------', 'red'))
        for m in mandate:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_error('Mandatsreferenz: ' + m.mandatsreferenz + ' Name: ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'red'))
        print(colored('Bitte nochmal die DPSG Nami und VR-Networld überprüfen und die nicht verwendenten Mandate entfernen.', 'red'))
        print()

    def print_member_entry_this_year_as_schnupper(self, members):
        if len(members) == 0:
            return

        print(colored('-------------- Schnuppermitglieder Jahr ' + str(self._config.get_accounting_year()) + ' --------------', 'green'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                             ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                             ' Mitglied ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'green'))
        print()

    def print_member_entry_second_half(self, members):
        if len(members) == 0:
            return

        print(colored('----------------- Mitglieder zweite Jahreshälfte ' + str(self._config.get_accounting_year()) + ' ------------------', 'green'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                             ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                             ' Mitglied ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'green'))
        print()


    def print_member_entry_new_year(self, members):
        if len(members) == 0:
            return

        print(colored('--------------------- Mitglieder im neuen Jahr ' + str(self._config.get_accounting_year()+1) + ' --------------------', 'green'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                             ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                             ' Mitglied ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'green'))
        print()

    def print_member_booked_by_dpsg_but_not_here(self, members):
        if len(members) == 0:
            return

        print(colored('-------- Mitglieder die von DPSG gebucht wurden aber nicht hier --------', 'green'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Rechnungsdatum: ' + str(m.datumVon) +
                             ' - ' + str(m.datumBis) +
                             ' Mitglied ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'green'))
        print()

    def print_member_not_booked_by_dpsg(self, members):
        if len(members) == 0:
            return

        print(colored('------ Mitglieder die hier gebucht wurden aber nicht von der DPSG ------', 'green'))
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                             ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                             ' Mitglied ' + combinedName)
        print(colored('------------------------------------------------------------------------', 'green'))
        print()

    def download_invoices(self) -> PdfMemberList:
        print('Herunterladen aller Rechnungen aus der Nami...')
        year_start_date = datetime.date(self._config.get_accounting_year(), 1,1)
        billing_sum = 0
        members_overall = []
        Path('./invoices/').mkdir(parents=True, exist_ok=True)

        with NaMi(username=self._config.get_nami_username(), password=self._config.get_nami_password()) as nami:
            groupId = nami.grpId
            invoices = nami.invoices(groupId)
            # Now filter for the relevant invoices
            for n in invoices:
                if n.reDatum >= year_start_date:
                    billing_sum = billing_sum + float(n.reNetto[:-4].replace(',', '.'))
                    invoice = nami.invoice(groupId, n.id)
                    filename = './invoices/' + str(n.id)+'.pdf'
                    nami.download_invoice(n.id, open_file=False, save_file=True, filename=filename)
                    members = PdfConverter.convert(pdfpath=filename)
                    members_overall.extend(members)

        members_overall = self.remove_unused_members(members_overall, self._config.get_accounting_halfyear())
        return members_overall

    def remove_unused_members(self, members : list, bookingPeriod : BookingHalfYear) -> PdfMemberList:
        # Removes all members from the DPSG invoice PDF's which are not used for this booking period
        members_new = PdfMemberList()
        for m in members:
            if m.datumVon >= datetime.date(self._config.get_accounting_year(), 1, 1):
                if bookingPeriod == BookingHalfYear.FIRST and \
                   m.datumBis <= self._config.get_key_date_frist_half():
                    members_new.append(m)
                elif bookingPeriod == BookingHalfYear.SECOND and \
                     m.datumVon > self._config.get_key_date_frist_half() and \
                     m.datumBis <= self._config.get_key_date_second_half():
                    members_new.append(m)
                elif bookingPeriod == BookingHalfYear.BOTH and \
                     m.datumBis <= self._config.get_key_date_second_half():
                    members_new.append(m)
        return members_new


if __name__ == "__main__":
    m = NamiAccounting('config.ini')
    m.process()