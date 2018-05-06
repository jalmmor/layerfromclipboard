# -*- coding: utf-8 -*-
"""

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, sys, traceback

from qgis.PyQt import uic
from qgis.PyQt.QtCore import (QVariant, QItemSelectionModel, QItemSelection)
from qgis.PyQt.QtWidgets import (QApplication, QDialog, QStyledItemDelegate, QComboBox, QMessageBox)

from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsField, QgsGeometry, QgsPointXY)

from .cbdatamodel import (CbDataModel, Field, ConvertError)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'layer_from_clipboard_dialog_base.ui'))


class LayerFromClipboardDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(LayerFromClipboardDialog, self).__init__(parent)
        self.setupUi(self)
        self.btPaste.clicked.connect(self.paste_from_clipboard)
        self.btCreate.clicked.connect(self.create_layer)
        self.gbGeom.toggled.connect(self.updateControls)
        self.cb_crs.setCrs(QgsProject.instance().crs())  # .authid()
        self.model = None
        self.tableView.setItemDelegate(FieldTypeDelegate())
    def warning(self,msg):
        QMessageBox.warning(self, self.tr(u'Paste from clipboard'), msg)

    def optionsChanged(self):
        if self.model:
            try:
                self.model.parseText(separators=self.__get_separators(),
                                     decimal_point=',' if self.cb_decimalSep.isChecked() else '.',
                                     header_at_first=self.cb_firstRecord.isChecked()
                                     )

            except Exception as e:
                self.warning( str(e))
        self.updateControls()

    def updateControls(self):
        if not self.model:
            return
        for c in range(self.model.getFieldCount()):
            self.tableView.openPersistentEditor(self.model.index(0, c))
        if self.gbGeom.isChecked():
            self.updateGeomControls()

    def updateGeomControls(self):
        def find_similar_field( fields, test_list):
            test_func = (lambda a, b: a.lower() == b, lambda a, b: a.lower().startswith(t))
            for func in test_func:
                for t in test_list:
                    for i, f in enumerate(fields):
                        if func(f.name, t):
                            return i
            return 0

        fields =self.model.get_fields()
        cbx = self.cbFieldx
        cby = self.cbFieldy
        cbx.clear()
        cby.clear()
        xfield = find_similar_field(fields,('x', 'longitude', 'lon'))
        yfield = find_similar_field(fields,('y', 'latitude', 'lat'))
        for i,f in enumerate(fields):
            cbx.addItem(f.name, i)
            cby.addItem(f.name, i)
        cbx.setCurrentIndex(xfield)
        cby.setCurrentIndex(yfield)

    def __get_separators(self):
        sep = []
        if self.cb_fdTab.isChecked():
            sep.append('\t')
        if self.cb_fdComma.isChecked():
            sep.append(',')
        if self.cb_fdSpace.isChecked():
            sep.append(' ')
        if len(self.le_separator.text()) > 0:
            sep.append(self.le_separator.text())
        return '|'.join(sep)

    def paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        sep = self.__get_separators()
        try:
            self.model = CbDataModel(text,
                                     separators=sep,
                                     decimal_point=',' if self.cb_decimalSep.isChecked() else '.',
                                     header_at_first=self.cb_firstRecord.isChecked()
                                     )
        except Exception as e:
            self.warning( str(e))
        self.tableView.setModel(self.model)
        self.updateControls()

    def createLayerFromData(self, layer_name, data,has_geom):

        fields = self.model.get_fields()
        crs_authid = self.cb_crs.crs().authid() if has_geom else None
        url = "Point?crs=" + crs_authid if crs_authid else "None"
        layer = QgsVectorLayer(url, layer_name, "memory")
        dp = layer.dataProvider()
        field_types = (QVariant.String, QVariant.Int, QVariant.Double)
        attr = [QgsField(field.name, field_types[field.data_type]) for field in self.model.get_fields() if
                field.data_type < 3]
        dp.addAttributes(attr)
        layer.updateFields()
        if has_geom:
            for row in data:
                fet = QgsFeature()
                xy=row[-1]
                point = QgsPointXY(xy[0],xy[1])
                fet.setGeometry(QgsGeometry.fromPointXY(point))
                fet.setAttributes(row[:-1])  # if has geom exlude coordinates data
                dp.addFeatures([fet])
        else:
            for row in data:
                fet = QgsFeature()
                fet.setAttributes(row) # if has geom exlude coordinates data
                dp.addFeatures([fet])
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

    def create_layer(self):
        if self.model:
            layerName = self.ed_layerName.text().strip()
            has_geom = self.gbGeom.isChecked()
            x_field = self.cbFieldx.currentIndex() if has_geom else None
            y_field = self.cbFieldy.currentIndex() if has_geom else None
            if not layerName:
                self.warning(self.tr(u'Layer name is empty'))
                self.ed_layerName.setFocus()
            try:
                data = self.model.convert_data(x_field, y_field)
            except ConvertError as e:
                selection = QItemSelection()
                index = self.model.index(e.row, e.col)
                selection.select(index, index)
                self.tableView.scrollTo(index)
                self.tableView.selectionModel().select(
                    selection, QItemSelectionModel.ClearAndSelect)
                self.warning( str(e))
            except Exception as e:
                T, V, TB = sys.exc_info()
                s = ''.join(traceback.format_exception(T, V, TB))
                self.warning(s)
            else:
                self.createLayerFromData(layerName, data,has_geom)




class FieldTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(FieldTypeDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        if index.row() > 0: return
        editor = QComboBox(parent)
        for c, text in enumerate(Field.FIELD_DATA_TYPES):
            editor.addItem(text, c)
        editor.setAutoFillBackground(True)
        return editor

    def setEditorData(self, editor, index):
        if not editor or not index.model(): return
        field = index.model().get_field(index.column())
        editor.setCurrentIndex(editor.findData(field.data_type))

    def setModelData(self, editor, model, index):
        if not editor: return
        field = index.model().get_field(index.column())
        data_type = editor.itemData(editor.currentIndex())
        field.data_type = data_type
