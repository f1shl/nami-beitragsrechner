from pynami.nami import NaMi, NamiResponseSuccessError
import logging


class Nami:
    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._nami = None
        self._loginSuccessful = False

    def __del__(self):
        if self._nami is not None:
            self._nami.logout()

    def check_login(self) -> bool:
        successful = False
        if self._nami is not None:
            self._nami.logout()

        try:
            nami = NaMi()
            if not self._username or not self._password:
                raise NamiResponseSuccessError
            nami.auth(username=self._username, password=self._password)
            logging.debug('Verbindung zur Nami erfolgreich.')
            self._loginSuccessful = True
            self._nami = nami
        except NamiResponseSuccessError:
            logging.debug('Nami Mitgliedsnummer, oder Passwort falsch')
            self._loginSuccessful = False
            self._nami = None

        return self._loginSuccessful

    def get_active_members(self):
        # Suchmaske für alle aktiven Mitglieder. Hier werden keine inaktiven, noch die Schnuppermitglieder gefunden
        # Die Nami muss also zuvor gepflegt werden, bevor der Export geschehen kann
        search = {
            'mglStatusId': 'AKTIV',
            'mglTypeId': 'MITGLIED'
        }
        return self._nami.search(**search)
    def get_schnupper_members(self):
        # Suchmaske für alle aktiven Mitglieder. Hier werden keine inaktiven, noch die Schnuppermitglieder gefunden
        # Die Nami muss also zuvor gepflegt werden, bevor der Export geschehen kann
        search = {
            'mglStatusId': 'AKTIV',
            'mglTypeId': 'SCHNUPPER_MITGLIED'
        }
        return self._nami.search(**search)

    def get_nami_interface(self) -> NaMi:
        return self._nami