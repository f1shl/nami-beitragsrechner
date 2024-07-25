import sys
import logging
import configparser
from enum import IntEnum
import datetime


def print_error(text):
    logging.error(text)


def print_info(text):
    logging.info(text)


def replace_umlaute_and_s(s : str) -> str:
    s = s.replace('ä', 'ae')
    s = s.replace('ö', 'oe')
    s = s.replace('ü', 'ue')
    s = s.replace('ß', 'ss')
    return s


class BookingHalfYear(IntEnum):
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

    def get_fee_full_annual(self):
        return self._feeFull

    def get_fee_family(self):
        if self._bookingHalfYear == BookingHalfYear.BOTH:
            return self._feeFamily
        else:
            return self._feeFamily / 2

    def get_fee_family_annual(self):
        return self._feeFamily

    def get_fee_social(self):
        if self._bookingHalfYear == BookingHalfYear.BOTH:
            return self._feeSocial
        else:
            return self._feeSocial / 2

    def get_fee_social_annual(self):
        return self._feeSocial


class SepaWrapper:
    def __init__(self, name, iban, bic, id):
        self.name = name
        self.iban = iban
        self.bic = bic
        self.id = id


class Config:
    def __init__(self, configPath):
        self._config_path = configPath
        self._config = configparser.ConfigParser()
        self._config.read(configPath)
        # Update ensures that all necessary fields are avialable in the config ini file
        self.update_config()

    def save(self):
        with open(self._config_path, 'w') as configfile:
            self._config.write(configfile)

    def get_nami_username(self):
        return self._config['Nami Login']['Username']

    def get_nami_password(self):
        return self._config['Nami Login']['Password']

    def set_nami_username(self, username):
        self._config['Nami Login']['Username'] = username

    def set_nami_password(self, password):
        self._config['Nami Login']['Password'] = password

    def get_accounting_year(self):
        return int(self._config['General']['Accounting Year'])        # Jahr für das die Beiträge eingezogen werden sollen

    def set_accounting_year(self, year):
        self._config['General']['Accounting Year'] = str(year)

    def get_accounting_date(self) -> datetime:
        return datetime.datetime.strptime(self._config['General']['Booking Date'], '%d.%m.%Y')                # Format in TT.MM.JJJJ. Termin zur SEPA Lastschriftausführung

    def get_accounting_date_str(self) -> str:
        return self._config['General']['Booking Date']               # Format in TT.MM.JJJJ. Termin zur SEPA Lastschriftausführung

    def set_accounting_date(self, date:datetime):
        self._config['General']['Booking Date'] = date.strftime('%d.%m.%Y')              # Format in TT.MM.JJJJ. Termin zur SEPA Lastschriftausführung

    def get_accounting_halfyear(self) -> BookingHalfYear:
        return BookingHalfYear(int(self._config['General']['Accounting Half-Year']))

    def set_accounting_halfyear(self, period:BookingHalfYear):
        self._config['General']['Accounting Half-Year'] = str(period)

    def get_position_file(self) -> str:
        return self._config['General']['Mandate Path']

    def set_position_file(self, path:str):
        self._config['General']['Mandate Path'] = path

    def get_membership_fees(self) -> MembershipFees:
        return MembershipFees(self.get_accounting_halfyear(), float(self._config['Membership Fee']['Full']),
                              float(self._config['Membership Fee']['Family']),
                              float(self._config['Membership Fee']['Social']))

    def set_membership_fees(self, fees: MembershipFees):
        self._config['Membership Fee']['Full'] = str(fees.get_fee_full_annual())
        self._config['Membership Fee']['Family'] = str(fees.get_fee_family_annual())
        self._config['Membership Fee']['Social'] = str(fees.get_fee_social_annual())

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

    def get_datetime_format(self) -> str:
        if (self._config.has_option('General', 'Datetime format')) is True:
            return self._config['General']['Datetime format']

    def set_datetime_format(self, datetimeFormat:str):
        if (self._config.has_option('General', 'Datetime format')) is False:
            self._config.set('General', 'Datetime format')
        datetimeFormat = datetimeFormat.replace('%', '%%') # Use double percent char to escape the basic inteprolation method of ConfigParser
        self._config['General']['Datetime format'] = datetimeFormat

    def get_creditor_id(self) -> SepaWrapper:
        return SepaWrapper(self._config['Creditor ID']['name'], self._config['Creditor ID']['iban'],
                           self._config['Creditor ID']['bic'], self._config['Creditor ID']['id'])

    def set_creditor_id(self, sepa:SepaWrapper):
        self._config['Creditor ID']['name'] = sepa.name
        self._config['Creditor ID']['iban'] = sepa.iban
        self._config['Creditor ID']['bic'] = sepa.bic
        self._config['Creditor ID']['id'] = sepa.id


    def update_config(self):
        if (self._config.has_section('Nami Login')) is False:
            self._config.add_section('Nami Login')
        if (self._config.has_section('General')) is False:
            self._config.add_section('General')
        if (self._config.has_section('Key Dates')) is False:
            self._config.add_section('Key Dates')
        if (self._config.has_section('Membership Fee')) is False:
            self._config.add_section('Membership Fee')
        if (self._config.has_section('Creditor ID')) is False:
            self._config.add_section('Creditor ID')

        if (self._config.has_option('Nami Login', 'username')) is False:
            self._config.set('Nami Login', 'username', '')
        if (self._config.has_option('Nami Login', 'password')) is False:
            self._config.set('Nami Login', 'password', '')

        if (self._config.has_option('General', 'accounting year')) is False:
            self._config.set('General', 'accounting year', str(datetime.date.today().year))
        if (self._config.has_option('General', 'accounting half-year')) is False:
            self._config.set('General', 'accounting half-year', '1')
        if (self._config.has_option('General', 'booking date')) is False:
            self._config.set('General', 'booking date', datetime.date.today().strftime('%d.%m.%Y'))
        if (self._config.has_option('General', 'mandate path')) is False:
            self._config.set('General', 'mandate path', '')
        if (self._config.has_option('General', 'datetime format')) is False:
            self._config.set('General', 'datetime format', '%%d.%%m.%%Y')

        if (self._config.has_option('Key Dates', 'first half-year')) is False:
            self._config.set('Key Dates', 'first half-year', '30.06')
        if (self._config.has_option('Key Dates', 'second half-year')) is False:
            self._config.set('Key Dates', 'second half-year', '31.12')
        if (self._config.has_option('Key Dates', 'schnupper weeks')) is False:
            self._config.set('Key Dates', 'schnupper weeks', '8')

        if (self._config.has_option('Membership Fee', 'full')) is False:
            self._config.set('Membership Fee', 'full', '0')
        if (self._config.has_option('Membership Fee', 'family')) is False:
            self._config.set('Membership Fee', 'family', '0')
        if (self._config.has_option('Membership Fee', 'social')) is False:
            self._config.set('Membership Fee', 'social', '0')

        if (self._config.has_option('Creditor ID', 'name')) is False:
            self._config.set('Creditor ID', 'name', '')
        if (self._config.has_option('Creditor ID', 'iban')) is False:
            self._config.set('Creditor ID', 'iban', '')
        if (self._config.has_option('Creditor ID', 'bic')) is False:
            self._config.set('Creditor ID', 'bic', '')
        if (self._config.has_option('Creditor ID', 'id')) is False:
            self._config.set('Creditor ID', 'id', '')
