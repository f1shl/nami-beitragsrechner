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

def main(username, password, year, ausführungstermin, mandatenliste, split_year):
    # use Colorama to make Termcolor work on Windows too
    init()

    lastschriftsequenz = 'wiederkehrend'                    # SEPA Lastschriftsequenz. Eigentlich immer wiederkehrend,
                                                            # das das SEPA Mandat immer bis zur Kündigung bestehen muss
                                                            # und die Abbuchung jährlich erfolgt
    # Alle Beiträge in Euro
    beitragvoll = 45                                        # Voller Beitrag in Euro der eingezogen werden soll
    beitragfamilienermäßigt = 31.5                          # Familienermäßigter Beitrag in Euro der eingezogen werden soll
    beitragsozialermäßigt = 13.8                            # Sozialermäßigter Beitrag in Euro der eingezogen werden soll
    stichtag_halbjahr = datetime.date(year, 6, 30)          # Stichtag definiert den Tag zwischen dem für beide Jahrehälften utnerschieden wird.
                                                            # Tritt jemand vor dem (einschließlich) 30.06 bei, so muss der volle Mitgliedsbeitrag entrichtet werden.
                                                            # Tritt jemand ab dem 01.07 bei, so muss nur der halbe Mitgliedsbeitrag entrichtet werden
    stichtag_neues_jahr = datetime.date(year+1, 1,1)        # Stichtag zum neuen Jahr. Tritt ein Mitglied erst im darauffgolenden Jahr ein
                                                            # (Buchung für 2021, Mitgliedseintritt in 2022), so darf das erstmal nciht abgebucht werden
    schnuppermitglied_weeks = datetime.timedelta(weeks = 8) # Anzahl der Wochen die ein Schnuppermitglied maximal bestehen kann (zzT. 8 Wochen).
                                                            # Wird benötigt um das korrekte Eintrittsdatum für die Beitragsberechnung festzusetzen.
                                                            # Wenn ein Mitglied zuerst Schnuppermitglied ist, so steht als eintrittsDatum dieses Datum fest.
                                                            # Für die Berechnung muss allerdings das Eintrittsdatum + maximale Schnuppermitgliedschaftslaufzeit
                                                            # verwendet werden. Nur so kann überprüft werden, ob das MItglied in diesem Jahr noch beitragspflichtig ist.

    # CSV header
    header = ['Mitgliedsnummer', 'Nachname', 'Vorname', 'Zahler/Zahlungsempfänger',
              'IBAN Zielkonto', 'BIC Zielkonto', 'Betrag in EUR', 'Mandatsreferenz',
              'Mandatsdatum', 'Termin', 'SEPA-Lastschriftsequenz', 'Verwendungszweck']

    vrImport = VRImport(mandatenliste)

    with NaMi(username=username, password=password) as nami:

        # Suchmaske für alle aktiven Mitglieder. Hier werden keine inaktiven, noch die Schnuppermitglieder gefunden
        # Die Nami muss also zuvor gepflegt werden, bevor der Export geschehen kann
        search = {
            'mglStatusId': 'AKTIV',
            'mglTypeId': 'MITGLIED'
        }
        result = nami.search(**search)
        print(tabulate2x(result))

        with open('mitglieder.csv', 'w', newline='') as f:
            writer = csv.writer(f, delimiter=';')

            # Write header to file
            writer.writerow(header)

            # Error variables
            list_of_missing_mandat = []
            list_of_corrupt_activities = []
            list_of_members_second_half_of_year = []
            list_of_members_in_new_year = []            # Liste von Mitgliedern die erst im neuen Jahr dazu gekommen sind.
                                                        # Wenn für 2021 abgebucht wird, so darf kein Mitglied von 2022 gebucht werden
            list_of_members_this_year_schnupper = []
            nof_claimed_members = 0                     # Zähler, wieviele Mitglieder gebucht werden

            # Loop through all members
            for r in result:
                row = []
                member = r.get_mitglied(nami)
                print(r.tabulate())
                combinedName = member.vorname + ' ' + member.nachname
                member.correct_eintrittsdatum = member.eintrittsdatum

                # If member entered the claimed year, check for Schnuppermitgliedschaft to extract the correct entry date
                if member.eintrittsdatum >= datetime.date(year,1,1):
                    try:
                        activities = nami.mgl_activities(member.id)
                    except exceptions.ValidationError as e:
                        tools.print_error('Mitglied ' + combinedName + ': Enddatum scheint für die Schnuppermitgliedschaft nicht zu stimmen. ' + str(e))
                        list_of_corrupt_activities.append(member)
                        continue
                    # Last activity in list is the oldest one
                    if 'Schnupper' in activities[-1].taetigkeit:
                        member.correct_eintrittsdatum = member.eintrittsdatum + schnuppermitglied_weeks
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
                    beitragsatz = beitragvoll
                elif 'Familienermäßigt' in member.beitragsart:
                    beitragsart = 'Familienermäßigt'
                    beitragsatz = beitragfamilienermäßigt
                elif 'Sozialermäßigt' in member.beitragsart:
                    beitragsart = 'Sozialermäßigt'
                    beitragsatz = beitragsozialermäßigt
                else:
                    tools.print_error('Beitragsart ' + member.beitragsart + ' von Mitglied ' + combinedName + ' unbekannt.')
                    raise ValueError('Beitragsart ' + member.beitragsart + ' von Mitglied ' + combinedName + ' unbekannt.')

                # Check if the member entry date was after the stichtag. If so, only half of the membership fee is claimed
                if member.correct_eintrittsdatum > stichtag_halbjahr and member.correct_eintrittsdatum < stichtag_neues_jahr:
                    if split_year:
                        beitragsatz = beitragsatz / 2
                        year_str = '2/' + str(year)             # Eintritt erst im zweiten Halbjahr des abgerechneten Jahres
                    list_of_members_second_half_of_year.append(member)
                # Check if member entered in the following year. If so, no caliming should be done
                elif member.correct_eintrittsdatum >= stichtag_neues_jahr:
                    list_of_members_in_new_year.append(member)
                    continue
                else:
                    year_str = '1/' + str(year) + ' + 2/' + str(year)

                if not split_year:
                    year_str = str(year)

                verwendungszweck = 'Mitgliedsbeitrag ' + year_str + ', ' + beitragsart + '. Mitglied ' + combinedName
                row.append(beitragsatz)
                # Now search for the correct Mandat in Mandatenliste
                mandat = vrImport.find_correct_mandat(member)
                if mandat == None:
                    list_of_missing_mandat.append(member)
                    continue

                row.append(mandat.mandatsreferenz)
                row.append(mandat.mandatsdatum)
                row.append(ausführungstermin)

                if mandat.is_first_lastschrift():
                    row.append('erstmalig')
                else:
                    row.append('wiederkehrend')

                row.append(verwendungszweck)
                # Write to CSV file
                writer.writerow(row)
                nof_claimed_members = nof_claimed_members + 1

            # Info printing
            used = vrImport.get_nof_used_mandate()
            overall = vrImport.get_nof_mandate()
            not_used = overall - used

            print()
            print(colored('--------------------- Abbrechnungsjahr: ' + str(year) + ' ---------------------------', 'green'))
            tools.print_info('Verarbeitete Mitglieder:      ' + str(len(result)))
            tools.print_info('Fehlerhafte  Mitglieder:      ' + str(len(list_of_missing_mandat) + len(list_of_corrupt_activities)) + '/' + str(len(result)))
            tools.print_info('Abzubuchende Mitglieder:      ' + str(nof_claimed_members)  + '/' + str(len(result)))
            tools.print_info('Eintritt im zweiten Halbjahr: ' + str(len(list_of_members_second_half_of_year)) + '/' + str(len(result)))
            tools.print_info('Eintritt im neuen Jahr ' + str(year+1) + ':  ' + str(len(list_of_members_in_new_year)) + '/' + str(len(result)))
            print()
            tools.print_info('Verarbeitete Mandate:         ' + str(overall))
            tools.print_info('Benutzte     Mandate:         ' + str(used) + '/' + str(overall))
            print()
            if not_used == 0:
                tools.print_info('Alle SEPA-Mandate wurden erfolgreich verwendet.')
            else:
                tools.print_error('Nicht alle SEPA-Mandate wurden verwendet. Nochmal die Mandate überprüfen und ggf. bereinigen.')
            print(colored('------------------------------------------------------------------------', 'green'))
            print()

            print_member_entry_this_year_as_schnupper(list_of_members_this_year_schnupper)
            print_member_entry_second_half(list_of_members_second_half_of_year)
            print_member_entry_new_year(list_of_members_in_new_year)

            # Error printing
            print_missing_mandate_members(list_of_missing_mandat)
            list_of_not_used_mandate = vrImport.get_not_used_mandate()
            print_not_used_mandate(list_of_not_used_mandate)


def print_missing_mandate_members(members):

    if len(members) == 0:
        return

    print(colored('--------------------------- Fehlende Mandate ---------------------------', 'red'))
    for m in members:
        combinedName = m.vorname + ' ' + m.nachname
        tools.print_error('Mitgliedsnummer: ' + str(m.mitgliedsNummer) + ' Name: ' + combinedName)
    print(colored('------------------------------------------------------------------------', 'red'))
    print(colored('Bitte die fehlenden Mandate in VR Networld für die Mitglieder anlegen.', 'red'))
    print()

def print_not_used_mandate(mandate: VRMandat):

    if len(mandate) == 0:
        return

    print(colored('----------------------- Nicht verwendete Mandate -----------------------', 'red'))
    for m in mandate:
        combinedName = m.vorname + ' ' + m.nachname
        tools.print_error('Mandatsreferenz: ' + m.mandatsreferenz + ' Name: ' + combinedName)
    print(colored('------------------------------------------------------------------------', 'red'))
    print(colored('Bitte nochmal die DPSG Nami und VR-Networld überprüfen und die nicht verwendenten Mandate entfernen.', 'red'))
    print()

def print_member_entry_this_year_as_schnupper(members):
    if len(members) == 0:
        return

    print(colored('-------------- Schnuppermitglieder Jahr ' + str(year) + ' --------------', 'green'))
    for m in members:
        combinedName = m.vorname + ' ' + m.nachname
        tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                         ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                         ' Mitglied ' + combinedName)
    print(colored('------------------------------------------------------------------------', 'green'))
    print()


def print_member_entry_second_half(members):
    if len(members) == 0:
        return

    print(colored('----------------- Mitglieder zweite Jahreshälfte ' + str(year) + ' ------------------', 'green'))
    for m in members:
        combinedName = m.vorname + ' ' + m.nachname
        tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                         ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                         ' Mitglied ' + combinedName)
    print(colored('------------------------------------------------------------------------', 'green'))
    print()


def print_member_entry_new_year(members):
    if len(members) == 0:
        return

    print(colored('--------------------- Mitglieder im neuen Jahr ' + str(year+1) + ' --------------------', 'green'))
    for m in members:
        combinedName = m.vorname + ' ' + m.nachname
        tools.print_info('Initiales Eintrittsdatum: ' + str(m.eintrittsdatum) +
                         ' Abrechenbares Eintrittsdatum: ' + str(m.correct_eintrittsdatum) +
                         ' Mitglied ' + combinedName)
    print(colored('------------------------------------------------------------------------', 'green'))
    print()


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('config.ini')
    username = config['Nami Login']['Username']
    password = config['Nami Login']['Password']

    year = int(config['General']['Accounting Year'])                        # Jahr für das die Beiträge eingezogen werden sollen
    termin = config['General']['Booking Date']                          # Format in TT.MM.JJJJ. Termin zur SEPA Lastschriftausführung
    biannual_accounting = bool(config['General']['Biannual Accounting'])     # Auf True Setzen, wenn die Beiträge pro Halbjahr berechnet werden sollen
                                                                        # Kündigt jemand halbjährlich, oder steigt halbjährlich ein, so
                                                                        # muss auch nur der halbe Beitrag geleistet werden. Stichtag ist der 30.06 und 31.12
    vr_networld_mandatenliste = 'VRExport_Aufträge_20220101_214611.csv'
    main(username, password, year=year, ausführungstermin=termin, mandatenliste=vr_networld_mandatenliste, split_year=biannual_accounting)

