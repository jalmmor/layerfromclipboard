import re
from typing import Type

from PyQt5.QtCore import (Qt,QCoreApplication, QLocale)

from PyQt5.QtGui import (QStandardItem, QStandardItemModel)


class CbParseError(Exception):
    pass


class ConvertError(Exception):
    def __init__(self, msg, row, col):
        self.row = row
        self.col = col
        super(ConvertError, self).__init__(msg)


class Field(object):
    FIELD_DATA_TYPES = ('String', 'Integer', 'Double', 'Don\'t import')

    def __init__(self, name, data_type=0):
        self.name = name
        self.data_type = data_type
        self.importField = True
        self.geom = None

    def h_align(self):
        return Qt.AlignLeft if self.data_type in (0, 3) else Qt.AlignRight


class CbDataModel(QStandardItemModel):

    def __init__(self, text='', **options):
        """
            separators='\t', decimal_point='.', header_at_first=True
        """
        super(CbDataModel, self).__init__(None)
        self._lines = text.strip().splitlines()
        self._fields = []
        self._separators = '\t'
        self._decimal_point = '.'
        self._header_at_first = True
        self.parseText(**options)

    def read_options(self, **options):
        self._separators = options.get('separators') or self._separators
        self._decimal_point = options.get('decimal_point') or self._decimal_point
        if 'header_at_first' in options:
            self._header_at_first = options['header_at_first']

    def get_fields(self):
        return self._fields

    def get_field(self, index):
        return self._fields[index]

    def parseText(self, **options):
        self.clear()
        self.read_options(**options)
        if len(self._lines) == 0:
            raise CbParseError(self.tr(u'Clipboard text is empty'))
        if len(self._lines) == 1 and self._header_at_first:
            raise CbParseError(self.tr(u'Data has single line.\nUnmark \'First line has field names\' an try again'))
        pattern = re.compile(self._separators)
        data = [pattern.split(l) for l in self._lines]
        if self._header_at_first:
            header = data.pop(0)
        else:
            header = ["Col " + str(n) for n in range(len(data[0]))]
        self._fields = [Field(name) for name in self.check_field_names(header)]
        numFields = len(self._fields)
        # ensure that the number of data in each row and in the header are the same
        for row in data:
            numDat = len(row)
            if numDat < numFields:
                row.extend([None] * (numFields - len(row)))
            elif numDat > numFields:
                del row[numFields:]
        self.test_field_types(data)

        for c, field in enumerate(self._fields):
            self.setHorizontalHeaderItem(c, QStandardItem(field.name))
            item = QStandardItem(field.data_type)
            item.setEditable(True)
            item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.setItem(0, c, item)
        self.setVerticalHeaderItem(0, QStandardItem("Type:"))

        for numRow, rowData in enumerate(data):
            self.setVerticalHeaderItem(numRow + 1, QStandardItem(str(numRow + 1)))
            for numField, field in enumerate(self._fields):
                fieldValue = rowData[numField]
                item = QStandardItem(fieldValue)
                item.setEditable(False)
                item.setTextAlignment(field.h_align() | Qt.AlignVCenter)
                self.setItem(numRow + 1, numField, item)

    def check_field_names(self, header):
        def get_unique_name(name_list, prefix_name):
            if len(prefix_name) == 0:
                return get_unique_name(name_list, "Col")
            n = 1
            name = prefix_name
            while name in name_list:
                name = "{0}_{1}".format(prefix_name, n)
                n = n + 1
            return name

        if header is None or len(header) == 0: return []
        field_names = []
        for f in header:
            field_names.append(get_unique_name(field_names, f))
        return field_names

    def getFieldCount(self):
        return len(self._fields)


    def test_field_types(self, data):
        loc = QLocale(QLocale.C) if self._decimal_point == '.' else QLocale(QLocale.Spanish)
        for col, field in enumerate(self._fields):
            if all([loc.toInt(row[col])[1] or row[col] is None for row in data]):  # test for integer
                field.data_type = 1
            elif all([loc.toDouble(row[col])[1] for row in data if len(row[col]) > 0]):  # test for double
                field.data_type = 2
            else:
                field.data_type = 0

    def get_converters(self):
        loc = QLocale(QLocale.C) if self._decimal_point == '.' else QLocale(QLocale.Spanish)
        return (
            lambda s: (s, True),
            lambda s: loc.toInt(s) if s else (None,True),
            lambda s: loc.toDouble(s)if s else (None,True)
        )

    def convert_data(self, x_field, y_field):
        converters = self.get_converters()
        attribute_data = []
        selected_fields = {field: index for index, field in enumerate(self._fields) if field.data_type < 3}
        for r in range(1, self.rowCount()):
            row = []
            for field in selected_fields:
                item = self.item(r, selected_fields[field])
                textValue = item.text()
                value, converted = converters[field.data_type](textValue)
                if not converted: raise ConvertError(" ".join((self.tr(u'Can\'t convert to number'), textValue)), r, selected_fields[field])
                row.append(value)

            if x_field and y_field:
                textValue = self.item(r, x_field).text()
                x_coord, converted = converters[2](textValue)  # toDouble
                if not (converted and x_coord):
                    raise ConvertError(" ".join((self.tr(u'Can\'t convert to double coordinate'), 'x', textValue)), r,
                                                     x_field)
                textValue = self.item(r, y_field).text()
                y_coord, converted = converters[2](textValue)  # toDouble
                if not (converted and y_coord):
                    raise ConvertError(" ".join((self.tr(u'Can\'t convert to double coordinate'), 'y', textValue)), r,
                                                     y_field)
                row.append((x_coord, y_coord))
            attribute_data.append(row)
        return attribute_data
