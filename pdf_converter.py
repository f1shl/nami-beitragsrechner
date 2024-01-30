import os
import pdfplumber
import re
import datetime
import logging

# Set the loglevel of pdfplumber to warning to avoid unnecessary log messages
logging.getLogger("pdfminer").setLevel(logging.WARNING)


class PdfMember:
    def __init__(self, mglNo, mglId, vorname, nachname, datumVon, datumBis, beitrag):
        self.mglNo = mglNo
        self.mglId = mglId
        self.vorname = vorname
        self.nachname = nachname
        self.datumVon = datumVon
        self.datumBis = datumBis
        self.beitrag = beitrag

    def compare(self, rhs):
        if isinstance(rhs, PdfMember):
            return self.mglNo == rhs.mglNo
        else:
            # Check only Mitgliedsnummer. Alternatively, name could be changed, too, but this could lead to problems if
            # some name changed through marriage or so.
            # and self.vorname.strip() == rhs.vorname.strip() and self.nachname.strip() == rhs.nachname.strip()
            return self.mglNo == rhs.mitgliedsNummer


class PdfMemberList(list):
    def __init__(self):
        list.__init__(self)

    def get_nof_unique_members(self):
        unqiue_members = []
        for m in self:
            already_inserted = False
            for n in unqiue_members:
                if m.compare(n):
                    already_inserted = True

            if already_inserted == False:
                unqiue_members.append(m)

        return len(unqiue_members)

    def get_value_booked_by_dpsg(self) -> float:
        overall_value = 0
        for m in self:
            overall_value += m.beitrag

        return overall_value


class PdfConverter:

    def convert(pdfpath) -> list:
        # create file object variable
        # opening method will be rb
        pre, ext = os.path.splitext(pdfpath)
        # Load your PDF
        l = PdfMemberList()
        with pdfplumber.open(pdfpath) as pdf:
            overall_lines = []
            for p in range(1, len(pdf.pages)):
                page = pdf.pages[p]
                lines = list(filter(None, page.extract_text(layout=True).splitlines()))
                # Strip leading and trailing spaces
                lines = list(map(str.strip, lines))
                # Remove empty lines
                lines = list(filter(None, lines))
                # Remove all lines which are not a member line
                lines = [x for x in lines if 'Einzelnachweise:' not in x]
                lines = [x for x in lines if 'Mitgliedsnr. Name' not in x]
                lines = [x for x in lines if 'Rechnungsnr.:' not in x]
                overall_lines.extend(lines)

        for line in overall_lines:
            line = line.strip()
            if line == '':
                continue
            # Extract mglNo
            pos = line.find(' ')
            mglNo = int(line[:pos])
            line = line[pos+1:]
            line = line.strip()
            # Extract nachname
            pos = line.find(',')
            nachname = line[:pos]
            nachname = nachname.strip()
            line = line[pos+1:]
            line = line.strip()
            # Extract vorname.
            pos = line.find(' VB')
            if pos == -1:
                pos = line.find(' FB')
            if pos == -1:
                pos = line.find(' SB')
            if pos == -1:
                print('PDF Rechnungen parsen nicht möglich. PDF: ' + pdfpath + '  Zeile: ' + line)
                ValueError('PDF Rechnungen parsen nicht möglich. PDF: ' + pdfpath + '  Zeile: ' + line)

            vorname = line[:pos]
            vorname = vorname.strip()
            line = line[pos+1:]
            line = line.strip()
            # Extract mglId
            pos = line.rfind(' ')
            mglId = int(line[pos+1:])
            line = line[:pos]
            line = line.strip()
            # Extract beitrag
            pos = line.rfind(' ')
            beitrag = float(line[pos+1:].replace(',', '.'))
            line = line[:pos]
            line = line.strip()
            # Extract beitragsatz
            beitragsatz = line
            matches = re.findall('[0-9]+.[0-9]+.[0-9]+', beitragsatz)
            datumVon = datetime.datetime.strptime(matches[0], '%d.%m.%y').date()
            datumBis = datetime.datetime.strptime(matches[1], '%d.%m.%y').date()
            member = PdfMember(mglNo, mglId, vorname, nachname, datumVon, datumBis, beitrag)
            l.append(member)

        return l
