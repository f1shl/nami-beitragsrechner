import csv
from vr_import import VRImport, VRMandat
import tools
import datetime
from marshmallow import exceptions
from pdf_converter import PdfConverter, PdfMemberList
from pathlib import Path
import logging
import tkinter as tk
from nami import Nami
from sepa import Sepa
from schwifty import IBAN, BIC

# Set the loglevel of pdfplumber to warning to avoid unnecessary log messages
logging.getLogger("urllib3").setLevel(logging.WARNING)

print = logging.debug


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
    def get_designated_use(self, accounting_year, bookingHalfYear:tools.BookingHalfYear, beitragsart, name):
        if bookingHalfYear == tools.BookingHalfYear.FIRST:
            year_str = '1/' + str(accounting_year)
        elif bookingHalfYear == tools.BookingHalfYear.SECOND:
            year_str = '2/' + str(accounting_year)
        else:
            year_str = '1/' + str(accounting_year) + ' + 2/' + str(accounting_year)

        return 'Mitgliedsbeitrag ' + year_str + ', ' + beitragsart + '. Mitglied ' + name


class NamiAccounting:
    def __init__(self, config:tools.Config, memberTree, nami:Nami, sepa:Sepa):
        self._config = config
        self._memberTree = memberTree
        self._nami = nami
        self._sepa = sepa

    def process(self):
        vrImport = VRImport(self._config.get_position_file())
        # Downloads all invoices from DPSG for the given year and removes all entries which are not needed
        # e.g. Removes first half year entries if second half year shall be booked
        dpsg_members = self.download_invoices()
        nof_dpsg_members = dpsg_members.get_nof_unique_members()

        print('Herunterladen aller aktiven Mitglieder aus der Nami...')
        result = self._nami.get_active_members()
        result_schnupper = self._nami.get_schnupper_members()
        result.extend(result_schnupper)
        #print(tabulate2x(result))

        # Error variables
        list_of_missing_mandat = []
        list_of_corrupt_activities = []
        list_of_members_second_half_of_year = []
        list_of_members_in_new_year = []  # Liste von Mitgliedern die erst im neuen Jahr dazu gekommen sind.
        list_of_members_booked_here_but_not_by_dpsg = []
        list_of_members_wrong_sepa = []
        # Wenn für 2021 abgebucht wird, so darf kein Mitglied von 2022 gebucht werden
        list_of_members_active_schnupper = []
        nof_claimed_members = 0  # Zähler, wieviele Mitglieder gebucht werden
        booking_value = 0
        # Create CsvWriter
        writer = CsvWriter(self._config.get_accounting_year())

        # Loop through all members
        for r in result:
            row = []
            member = r.get_mitglied(self._nami.get_nami_interface())
            combinedName = member.vorname + ' ' + member.nachname
            member.correct_eintrittsdatum = member.eintrittsdatum

            # If member entered the claimed year, check for Schnuppermitgliedschaft to extract the correct entry date
            if member.eintrittsdatum >= datetime.date(self._config.get_accounting_year(), 1, 1):
                try:
                    activities = self._nami.get_nami_interface().mgl_activities(member.id)
                except exceptions.ValidationError as e:
                    tools.print_error(
                        'Mitglied ' + combinedName + ': Enddatum scheint für die Schnuppermitgliedschaft nicht zu stimmen. ' + str(
                            e))
                    list_of_corrupt_activities.append(member)
                    continue
                # Last activity in list is the oldest one
                if 'Schnupper' in activities[0].taetigkeit:
                    member.correct_eintrittsdatum = member.eintrittsdatum + self._config.get_schnupper_weeks()
                    list_of_members_active_schnupper.append(member)

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

            if member.eintrittsdatum > self._config.get_key_date_second_half():
                list_of_members_in_new_year.append(member)

            # Check if member entered the following here. If so, ignore it.
            # Here the corrected Eintrittsdatum is decisive (Schnuppermitglieder must be handeled correctly)
            if member.correct_eintrittsdatum > self._config.get_key_date_second_half():
                continue
            # Check if the member entry date was after the stichtag. If so, only half of the membership fee is claimed
            b = self._config.get_accounting_halfyear()
            if b == tools.BookingHalfYear.FIRST:
                if member.correct_eintrittsdatum > self._config.get_key_date_frist_half():
                    continue
                elif member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                   member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                    list_of_members_second_half_of_year.append(member)
            elif b == tools.BookingHalfYear.SECOND:
                if member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                   member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                    list_of_members_second_half_of_year.append(member)
            else:
                if member.correct_eintrittsdatum > self._config.get_key_date_frist_half() and \
                   member.correct_eintrittsdatum <= self._config.get_key_date_second_half():
                    beitragsatz = beitragsatz / 2
                    list_of_members_second_half_of_year.append(member)
                    b = tools.BookingHalfYear.SECOND

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
            row.append(self._config.get_accounting_date_str())

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
            # Additional, write to the SEPA XML file
            b = self._sepa.add_member(member, beitragsatz, mandat, self._config.get_accounting_date_str(), verwendungszweck)
            if b is False:
                list_of_members_wrong_sepa.append(member)
                tools.print_error('Mitglied ' + member.vorname + ' ' + member.nachname + ': SEPA Generierung schlug fehl.')

            nof_claimed_members = nof_claimed_members + 1

            booking_value = booking_value + beitragsatz

            # Create additional tuple and add it ot the TreeView
            memberTuple = (member.mitgliedsNummer, member.vorname, member.nachname,
                           datetime.datetime.strftime(member.correct_eintrittsdatum, self._config.get_datetime_format()),
                           member.kontoverbindung.iban, str(beitragsatz) + ' €')
            self._memberTree.insert('', tk.END, values=memberTuple)


        # Info printing
        used = vrImport.get_nof_used_mandate()
        overall = vrImport.get_nof_mandate()
        not_used = overall - used

        #print("")
        if self._config.get_accounting_halfyear() == tools.BookingHalfYear.FIRST:
            booking_year_str = '1/' + str(self._config.get_accounting_year())
        elif self._config.get_accounting_halfyear() == tools.BookingHalfYear.SECOND:
            booking_year_str = '2/' + str(self._config.get_accounting_year())
        else:
            booking_year_str = ' ' + str(self._config.get_accounting_year()) + ' '

        tools.print_info('-------------------- Abbrechnungsjahr: ' + booking_year_str + ' --------------------------')
        tools.print_info('Verarbeitete Mitglieder:      ' + str(len(result)))
        tools.print_info('Fehlerhafte  Mitglieder:      ' + str(
            len(list_of_missing_mandat) + len(list_of_corrupt_activities)) + '/' + str(len(result)))
        tools.print_info('Abzubuchende Mitglieder:      ' + str(nof_claimed_members) + '/' + str(len(result)))
        tools.print_info('Eintritt im zweiten Halbjahr: ' + str(len(list_of_members_second_half_of_year)) + '/' + str(
                len(result)))
        tools.print_info('Eintritt im neuen Jahr  ' + str(self._config.get_accounting_year() + 1) + ': ' + str(
            len(list_of_members_in_new_year)) + '/' + str(len(result)))
        tools.print_info('Mitglieder von DPSG gebucht:  ' + str(nof_dpsg_members))
        print("")
        tools.print_info('Verarbeitete Mandate:         ' + str(overall))
        tools.print_info('Benutzte     Mandate:         ' + str(used) + '/' + str(overall))
        tools.print_info('Gesamtsumme: ' + str(booking_value) + ' EUR')
        print("")
        if not_used == 0:
            tools.print_info('Alle SEPA-Mandate wurden erfolgreich verwendet.')
        else:
            tools.print_error(
                'Nicht alle SEPA-Mandate wurden verwendet. Nochmal die Mandate überprüfen und ggf. bereinigen.')
        tools.print_info('-------------------------------------------------------------------------------')
        print("")

        self.print_member_entry_this_year_as_schnupper(list_of_members_active_schnupper)
        #self.print_member_entry_second_half(list_of_members_second_half_of_year)
        self.print_member_entry_new_year(list_of_members_in_new_year)

        # Error printing
        self.print_missing_mandate_members(list_of_missing_mandat)
        list_of_not_used_mandate = vrImport.get_not_used_mandate()
        self.print_not_used_mandate(list_of_not_used_mandate)
        self.print_member_booked_by_dpsg_but_not_here(dpsg_members)
        self.print_member_not_booked_by_dpsg(list_of_members_booked_here_but_not_by_dpsg)

    def print_missing_mandate_members(self, members):
        tools.print_error('--------------------------- Fehlende Mandate ---------------------------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_error('Mitgliedsnummer: ' + str(m.mitgliedsNummer) + ' Name: ' + combinedName)
        tools.print_error('-----------------------------------------------------------------------------')
        if len(members) != 0:
            tools.print_error('Bitte die fehlenden Mandate in VR Networld für die Mitglieder anlegen.')
        print("")

    def print_not_used_mandate(self, mandate: VRMandat):
        tools.print_error('----------------------- Nicht verwendete Mandate -----------------------')
        for m in mandate:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_error('Mandatsreferenz: ' + m.mandatsreferenz + ' Name: ' + combinedName)
        tools.print_error('-------------------------------------------------------------------------------')
        if len(mandate) != 0:
            tools.print_error('Bitte nochmal die DPSG Nami und VR-Networld überprüfen und die nicht verwendenten Mandate entfernen.')
        print("")

    def print_member_entry_this_year_as_schnupper(self, members):
        tools.print_info('-------------- Aktive Schnuppermitglieder Jahr --------------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + datetime.datetime.strftime(m.eintrittsdatum, self._config.get_datetime_format()) +
                             ' Abrechenbares Eintrittsdatum: ' + datetime.datetime.strftime(m.correct_eintrittsdatum, self._config.get_datetime_format()) +
                             ' Mitglied ' + combinedName)
        tools.print_info('-------------------------------------------------------------')
        print("")

    def print_member_entry_second_half(self, members):
        tools.print_info('----------------- Mitglieder zweite Jahreshälfte ' + str(self._config.get_accounting_year()) + ' ------------------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + datetime.datetime.strftime(m.eintrittsdatum, self._config.get_datetime_format()) +
                             ' Abrechenbares Eintrittsdatum: ' + datetime.datetime.strftime(m.correct_eintrittsdatum, self._config.get_datetime_format()) +
                             ' Mitglied ' + combinedName)
        tools.print_info('-----------------------------------------------------------------------------------------')
        print("")


    def print_member_entry_new_year(self, members):
        tools.print_info('--------------------- Mitglieder im neuen Jahr ' + str(self._config.get_accounting_year()+1) + ' --------------------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + datetime.datetime.strftime(m.eintrittsdatum, self._config.get_datetime_format()) +
                             ' Abrechenbares Eintrittsdatum: ' + datetime.datetime.strftime(m.correct_eintrittsdatum, self._config.get_datetime_format()) +
                             ' Mitglied ' + combinedName)
        tools.print_info('------------------------------------------------------------------------------')
        print("")

    def print_member_booked_by_dpsg_but_not_here(self, members):
        tools.print_info('-------- Mitglieder die von DPSG gebucht wurden aber nicht hier --------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Rechnungsdatum: ' + datetime.datetime.strftime(m.datumVon, self._config.get_datetime_format()) +
                             ' - ' + datetime.datetime.strftime(m.datumBis, self._config.get_datetime_format()) +
                             ' Mitglied ' + combinedName)
        tools.print_info('------------------------------------------------------------------------------------')
        print("")

    def print_member_not_booked_by_dpsg(self, members):
        tools.print_info('------ Mitglieder die hier gebucht wurden aber nicht von der DPSG ------')
        for m in members:
            combinedName = m.vorname + ' ' + m.nachname
            tools.print_info('Initiales Eintrittsdatum: ' + datetime.datetime.strftime(m.eintrittsdatum, self._config.get_datetime_format()) +
                             ' Abrechenbares Eintrittsdatum: ' + datetime.datetime.strftime(m.correct_eintrittsdatum, self._config.get_datetime_format()) +
                             ' Mitglied ' + combinedName)
        tools.print_info('------------------------------------------------------------------------------------')
        print("")

    def download_invoices(self) -> PdfMemberList:
        print('Herunterladen aller Rechnungen aus der Nami...')
        year_start_date = datetime.date(self._config.get_accounting_year(), 1,1)
        billing_sum = 0
        members_overall = []
        Path('./invoices/').mkdir(parents=True, exist_ok=True)

        nami = self._nami.get_nami_interface()
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

    def remove_unused_members(self, members : list, bookingPeriod : tools.BookingHalfYear) -> PdfMemberList:
        # Removes all members from the DPSG invoice PDF's which are not used for this booking period
        members_new = PdfMemberList()
        for m in members:
            if m.datumVon >= datetime.date(self._config.get_accounting_year(), 1, 1):
                if bookingPeriod == tools.BookingHalfYear.FIRST and \
                   m.datumBis <= self._config.get_key_date_frist_half():
                    members_new.append(m)
                elif bookingPeriod == tools.BookingHalfYear.SECOND and \
                     m.datumVon > self._config.get_key_date_frist_half() and \
                     m.datumBis <= self._config.get_key_date_second_half():
                    members_new.append(m)
                elif bookingPeriod == tools.BookingHalfYear.BOTH and \
                     m.datumBis <= self._config.get_key_date_second_half():
                    members_new.append(m)
        return members_new