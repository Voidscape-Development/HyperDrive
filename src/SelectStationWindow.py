from loguru import logger
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.TournamentDataManager import TournamentDataManager


class SelectStationWindow(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle(QApplication.translate("app", "Select a station"))
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.proxyModel = QSortFilterProxyModel()
        self.proxyModel.setFilterKeyColumn(-1)
        self.proxyModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        def filterList(text):
            self.proxyModel.setFilterFixedString(text)

        searchBar = QLineEdit()
        searchBar.setPlaceholderText("Filter...")
        layout.addWidget(searchBar)
        searchBar.textEdited.connect(filterList)

        options = QHBoxLayout()

        layout.layout().addLayout(options)

        self.startggSetSelectionItemList = QTableView()
        self.startggSetSelectionItemList.doubleClicked.connect(lambda x: self.LoadSelectedSet())
        self.startggSetSelectionItemList.installEventFilter(self)
        layout.addWidget(self.startggSetSelectionItemList)
        self.startggSetSelectionItemList.setSortingEnabled(True)
        self.startggSetSelectionItemList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.startggSetSelectionItemList.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.startggSetSelectionItemList.setModel(self.proxyModel)
        self.startggSetSelectionItemList.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.startggSetSelectionItemList.resizeColumnsToContents()

        btOk = QPushButton("OK")
        layout.addWidget(btOk)
        btOk.clicked.connect(lambda x: self.LoadSelectedSet())

        self.resize(1200, 500)

        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        TournamentDataManager.instance.signals.get_stations_finished.connect(self.SetStations)

    def eventFilter(self, obj, event):
        if obj is self.startggSetSelectionItemList and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.LoadSelectedSet()
        return super().eventFilter(obj, event)

    def LoadStations(self):
        self.proxyModel.setSourceModel(QStandardItemModel())
        TournamentDataManager.instance.LoadStations()

    def SetStations(self, stations):
        logger.info("Got stations" + str(len(stations)))
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(
            [
                QApplication.translate("app", "Type"),
                QApplication.translate("app", "Id"),
                QApplication.translate("app", "Stream"),
                QApplication.translate("app", "Identifier"),
            ]
        )

        if stations is not None:
            for s in stations:
                model.appendRow(
                    [
                        QStandardItem(str(s.get("type", ""))),
                        QStandardItem(str(s.get("id", ""))),
                        QStandardItem(str(s.get("stream", ""))),
                        QStandardItem(str(s.get("identifier", ""))),
                    ]
                )

                model.setData(model.index(model.rowCount() - 1, 0), s, Qt.ItemDataRole.UserRole)

        self.proxyModel.setSourceModel(model)
        self.startggSetSelectionItemList.resizeColumnsToContents()
        self.startggSetSelectionItemList.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        QApplication.processEvents()
        self.resize(self.width(), self.height())

    def LoadSelectedSet(self):
        rows = self.startggSetSelectionItemList.selectionModel().selectedRows()
        row = rows[0].row() if rows else 0

        station = (
            self.startggSetSelectionItemList.model().index(row, 0).data(Qt.ItemDataRole.UserRole)
        )

        self.close()

        if station:
            self.parent().signals.StationSelected.emit(station)
