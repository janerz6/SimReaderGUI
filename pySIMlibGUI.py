import json
import sys
import time

from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QObject, QRegExp
from PyQt5.QtGui import QFont, QIntValidator, QRegExpValidator
from PyQt5.QtWidgets import (QWidget, QPushButton,
                             QHBoxLayout, QVBoxLayout, QApplication, QLabel, QMainWindow, QToolButton,
                             QToolBar, QStackedLayout, QProgressBar, QLineEdit, QMessageBox, QInputDialog, QFrame,
                             QScrollArea, QGroupBox, QFormLayout, QAction)

from pySIMlib import pySIMlib


class Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, sim):
        QObject.__init__(self)
        self.sim = sim

    @pyqtSlot()
    def loadMetadata(self):
        try:
            metadata = {"ICCID": self.sim.getICCID(), "LP": self.sim.getLP(), "IMSI": self.sim.getIMSI(),
                        "KC": self.sim.getKC(), "HPLMN": self.sim.getHPLMN(), "SST": self.sim.getSST(),
                        "BCCH": self.sim.getBCCH(), "ACC": self.sim.getACC(), "FPLMN": self.sim.getFPLMN(),
                        "LOCI": self.sim.getLOCI(), "AD": self.sim.getAD(), "Phase": self.sim.getPhase()}
            self.finished.emit(dict(metadata=metadata))
        except Exception as e:
            self.finished.emit(dict(error=True, detail=str(e)))

    @pyqtSlot()
    def loadContacts(self):
        try:
            nums1 = self.sim.getNums(self.sim.FILE_EF_ADN)
            nums2 = self.sim.getNums(self.sim.FILE_EF_FDN)
            nums3 = self.sim.getNums(self.sim.FILE_EF_LND)
            numbers = nums1[0].values() + nums2[0].values() + nums3[0].values()
            self.finished.emit(dict(contacts=numbers, free_slots=nums1[1]))
        except Exception as e:
            self.finished.emit(dict(error=True, detail=str(e)))

    @pyqtSlot()
    def loadSMSs(self):
        try:
            smss = self.sim.getSMSs()
            self.finished.emit(dict(smss=smss))
        except Exception as e:
            self.finished.emit(dict(error=True, detail=str(e)))


class ContactsPanel(QWidget):
    def __init__(self, sim, data):
        QWidget.__init__(self)
        self.contacts_form = QFormLayout()
        self.new_contact_grp = QGroupBox('New contact')
        self.new_name = QLineEdit()
        self.new_number = QLineEdit()
        self.sim = sim
        self.data = data
        self.initGUI()

    def initGUI(self):
        add_new = QPushButton("+ Add new")
        add_new.clicked.connect(self.showAddNewContact)
        self.new_contact_grp.setHidden(True)
        form = QHBoxLayout()
        self.new_name.setPlaceholderText("Name")
        rx = QRegExp("\d{1,13}")
        self.new_number.setPlaceholderText("Number")
        self.new_number.setValidator(QRegExpValidator(rx))
        btnAdd = QPushButton("Add")
        btnAdd.clicked.connect(self.addNewContact)
        btnCancel = QPushButton("Cancel")
        btnCancel.clicked.connect(self.hideAddNewContact)

        form.addWidget(self.new_name)
        form.addWidget(self.new_number)
        form.addWidget(btnAdd)
        form.addWidget(btnCancel)
        self.new_contact_grp.setLayout(form)

        groupbox = QGroupBox('Contacts')
        contacts = self.data["contacts"]
        for idx, contact in enumerate(contacts):
            self.addContactItem(contact[0], contact[1])

        groupbox.setLayout(self.contacts_form)
        scroll = QScrollArea()
        scroll.setWidget(groupbox)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.addWidget(add_new)
        layout.addWidget(self.new_contact_grp)
        layout.addWidget(scroll)
        layout.addStretch()

    def hideAddNewContact(self):
        self.new_contact_grp.setHidden(True)
        self.new_name.setText("")
        self.new_number.setText("")

    def showAddNewContact(self):
        self.new_contact_grp.setHidden(False)

    def addContactItem(self, name, number):
        if len(name) > 0 and len(number) > 0:
            numberField = QLabel(number)
            bold = QFont()
            bold.setBold(True)
            numberField.setFont(bold)
            self.contacts_form.addRow(QLabel(name), numberField)

    def addNewContact(self):
        name = self.new_name.text()
        number = self.new_number.text()
        if len(name) > 0 and len(number) > 0:
            self.addContactItem(name, number)
            self.saveContactToSim(name, number)
            self.new_name.setText("")
            self.new_number.setText("")
            self.new_contact_grp.setHidden(True)

    def saveContactToSim(self, name, number):
        free = self.data["free_slots"]
        slot = free[0]
        self.data["free_slots"].remove(slot)
        sim = self.sim
        recNum, recLen, nameLen = sim.getNumInfo(sim.FILE_EF_ADN)
        sim.setNum(sim.FILE_EF_ADN, slot, recLen, nameLen, name, number)


class SMSPanel(QWidget):
    def __init__(self, data):
        smss = data["smss"]
        QWidget.__init__(self)
        vbox = QVBoxLayout()
        groupbox = QGroupBox('SMS')
        for idx, sms in enumerate(dict(smss).values()):
            # 0 id, 1 date, 2 from, 3 msg
            if len(sms) > 3:
                time_val = sms[1]
                time_parsed = time.strptime(time_val)
                timeF = time.strftime('%Y-%m-%d %H:%M:%S', time_parsed)
                vbox.addLayout(self.generateSMSitem(timeF, sms[2], sms[3]))

                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFrameShadow(QFrame.Sunken)
                vbox.addWidget(line)
        groupbox.setLayout(vbox)
        scroll = QScrollArea()
        scroll.setWidget(groupbox)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addStretch()

    def generateSMSitem(self, time_str, from_str, msg):
        hbox = QHBoxLayout()
        vbox = QVBoxLayout()

        date_label = QLabel()
        date_label.setText(time_str)
        hbox.addWidget(date_label)

        from_label = QLabel()
        from_label.setText(from_str)
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        from_label.setFont(font)
        hbox.addWidget(from_label)
        hbox.addStretch()

        msg_field = QLabel()
        msg_field.setStyleSheet("background: #fff;padding:5px;")
        msg_field.setText(msg)

        vbox.addLayout(hbox)
        vbox.addWidget(msg_field)
        vbox.addStretch()
        return vbox


class MetadataPanel(QWidget):
    def __init__(self, data):
        QWidget.__init__(self)
        metadata = data["metadata"]
        vbox = QVBoxLayout()
        groupbox = QGroupBox('Metadata')
        groupbox.setLayout(vbox)

        for key, value in metadata.items():
            vbox.addLayout(self.generateLabelValueItem(key, value))
        vbox.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(groupbox)

    def generateLabelValueItem(self, text, val_text):
        hbox = QHBoxLayout()
        label = QLabel()
        label.setText(text + ": ")
        value = QLabel()
        value.setText(val_text)
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        value.setFont(font)

        hbox.addWidget(label)
        hbox.addWidget(value)
        hbox.addStretch()

        return hbox


class SimReader(QMainWindow):
    def __init__(self, port="\\.\COM6"):
        QMainWindow.__init__(self)
        self.sim = pySIMlib(False)
        self.backgroundWorker = Worker(self.sim)
        self.data = {}
        self._metaIdx = None
        self._contactsIdx = None
        self._smsIdx = None
        self.window = QWidget()
        self._blankIdx = 1
        self.body_layout = None
        self.stackedLayout = QStackedLayout()
        self.window.setLayout(self.stackedLayout)
        self.setCentralWidget(self.window)
        self.initUI()
        self.port = port
        self.initLib()

    def initLib(self):
        try:
            self.sim.openSession(self.port)
            self.statusBar().showMessage("Successfully connected to serial port.", 2000)
        except Exception as e:
            print(e)
            self.choosePort(self.port)

    def initUI(self):
        self.setGeometry(50, 50, 600, 350)
        self.setWindowTitle('Sim Reader - Beta')

        self.createMenuBar()
        self.stackedLayout.addWidget(self.createPinEnterPanel())
        self.stackedLayout.setCurrentIndex(0)
        self.show()

    @staticmethod
    def silentlyUncheck(checkBtn):
        checkBtn.blockSignals(True)
        checkBtn.setChecked(False)
        checkBtn.blockSignals(False)

    def handleShowMetadata(self):
        self.silentlyUncheck(self.contactsBtn)
        self.silentlyUncheck(self.smsBtn)
        if "metadata" not in self.data.keys():
            self.progressSpeed = 25
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadMetadata, self.prepareMetadataPanel)
        elif self._metaIdx is None:
            self._metaIdx = self.stackedLayout.count()
            self.prepareMetadataPanel(self.data)
        else:
            self.stackedLayout.setCurrentIndex(self._metaIdx)

    def handleShowContacts(self):
        self.silentlyUncheck(self.metaBtn)
        self.silentlyUncheck(self.smsBtn)

        if "contacts" not in self.data.keys():
            self.progressSpeed = 10
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadContacts, self.prepareContactsPanel)
        elif self._contactsIdx is None:
            self.prepareContactsPanel(self.data)
        else:
            self.stackedLayout.setCurrentIndex(self._contactsIdx)

    def handleShowSMS(self):
        self.silentlyUncheck(self.metaBtn)
        self.silentlyUncheck(self.contactsBtn)
        if "smss" not in self.data.keys():
            self.progressSpeed = 1.5
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadSMSs, self.prepareSMSsPanel)
        elif self._smsIdx is None:
            self.prepareSMSsPanel(self.data)
        else:
            self.stackedLayout.setCurrentIndex(self._smsIdx)

    def createMenuBar(self):
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('File')

        exitAction = QAction("Exit", self)
        exitAction.triggered.connect(exit)
        fileMenu.addAction(exitAction)

        toolsMenu = mainMenu.addMenu('Tools')

        self.saveToFileBtn = QAction("Save data to file", self)
        self.saveToFileBtn.triggered.connect(self.saveToFile)
        self.saveToFileBtn.setEnabled(False)
        toolsMenu.addAction(self.saveToFileBtn)

        helpMenu = mainMenu.addMenu('Help')
        about = QAction("About", self)
        about.triggered.connect(self.showAboutDialog)
        helpMenu.addAction(about)

    def showAboutDialog(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("About sim reader")
        msg.setText("Sim reader is a simple tool made by students of the Faculty for computer science in Ljubljana."
                    " It allows inspecting basic data on SIM card.")
        msg.setInformativeText("@copy FRI")
        msg.setStandardButtons(QMessageBox.Ok)

        msg.exec_()

    def saveToFile(self):
        self.prevIndex = self.stackedLayout.currentIndex()
        if "contacts" not in self.data and "smss" not in self.data:
            self.progressSpeed = 1.3
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadContacts, self._processAndLoadAnother)

        elif "contacts" not in self.data:
            self.progressSpeed = 10
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadContacts, self._finishAndSaveToFile)
        elif "smss" not in self.data:
            self.progressSpeed = 1.5
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadSMSs, self._finishAndSaveToFile)
        else:
            self._saveToFile()

    def _processData(self, data):
        if "error" in data:
            self.showException(data["detail"])
            return False
        else:
            for key, value in data.items():
                self.data[key] = value
            return True

    def _processAndLoadAnother(self, data):
        if self._processData(data):
            self.backgroundWorker = Worker(self.sim)
            self.loadData(self.backgroundWorker.loadSMSs, self._finishAndSaveToFile, resetLoader=False)

    def _finishAndSaveToFile(self, data):

        if self._processData(data):
            self.timer.stop()
            self.progress.hide()
            self._saveToFile()

    def _saveToFile(self):
        filename = 'export.json'
        with open(filename, 'w') as outfile:
            print(self.data.keys())
            json.dump(self.data, outfile, ensure_ascii=False)
            self.statusBar().showMessage("Saved data to file %s" % filename, 2000)
            self.stackedLayout.setCurrentIndex(self.prevIndex)

    def createToolbar(self):
        self.formatbar = QToolBar(self)
        self.metaBtn = QToolButton(self)
        self.contactsBtn = QToolButton(self)
        self.smsBtn = QToolButton(self)

        self.metaBtn.setText('Metadata')
        self.metaBtn.toggled.connect(self.handleShowMetadata)
        self.metaBtn.setCheckable(True)
        self.formatbar.addWidget(self.metaBtn)

        self.contactsBtn.setText('Contacts')
        self.contactsBtn.toggled.connect(self.handleShowContacts)
        self.contactsBtn.setCheckable(True)
        self.formatbar.addWidget(self.contactsBtn)

        self.smsBtn.setText('Messages')
        self.smsBtn.toggled.connect(self.handleShowSMS)
        self.smsBtn.setCheckable(True)
        self.formatbar.addWidget(self.smsBtn)

        self.addToolBar(self.formatbar)

    def createPinEnterPanel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        self.pinlabel = QLabel()
        self.pinlabel.setText("Enter PIN number:")

        self.pinBox = QLineEdit()
        self.pinBox.setValidator(QIntValidator())
        self.pinBox.setMaxLength(4)
        self.pinBox.setFont(QFont("Arial", 20))

        submitBtn = QPushButton("Submit", self)
        submitBtn.clicked.connect(self.verifyPin)

        layout.addWidget(self.pinlabel)
        layout.addWidget(self.pinBox)
        layout.addWidget(submitBtn)

        layout.addStretch()
        widget.setLayout(layout)

        return widget

    def choosePort(self, port):
        item, ok = QInputDialog \
            .getItem(self,
                     "Choose serial port",
                     "Serial reader not found on port %s. Please select the correct port bellow:" % port,
                     ["COM1", "COM2", "COM3", "COM4", "COM5", "COM6"], 0, False)

        if ok:
            self.initLib(item)
        else:
            exit(0)

    def verifyPin(self):
        pin = self.pinBox.text()
        ok = self.sim.verPIN(pin)
        if not ok:
            _, triesLeft = self.sim.getPINinfo()
            if triesLeft == 0:
                QMessageBox.warning(self, "Warning", "Pin card locked.")
            else:
                QMessageBox.warning(self, "Warning", "Wrong sim entered")
                self.pinlabel.setText("Enter PIN number (%s tries left):" % triesLeft)
            return False
        print("Pin OK")
        self.statusBar().showMessage("Pin OK", 2000)

        self.createToolbar()
        self.stackedLayout.addWidget(QWidget())
        self.progress = QProgressBar(self)
        self.metaBtn.setChecked(True)

    def loadData(self, loadFunction, finishCallback, resetLoader=True):
        self.stackedLayout.setCurrentIndex(self._blankIdx)
        self.progress.setAlignment(QtCore.Qt.AlignCenter)
        self.progress.setFormat(u'Loading data from SIM card: %p%')
        self.progress.setGeometry(200, 150, 250, 20)
        self.progress.show()

        self.thread = QThread()
        self.backgroundWorker.moveToThread(self.thread)
        self.backgroundWorker.finished.connect(self.thread.quit)
        self.backgroundWorker.finished.connect(finishCallback)
        self.thread.started.connect(loadFunction)
        self.thread.start()

        self.progressVal = 0 if resetLoader else self.progressVal
        self.progress.setValue(self.progressVal)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.updateLoader)
        self.timer.start()

    def killThread(self):
        self.thread.quit()

    def updateLoader(self):
        if self.progressVal < 100:
            self.progressVal += self.progressSpeed
            self.progress.setValue(self.progressVal)

    def showException(self, e):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)

        msg.setText("Error encountered while loading sim data. " +
                    "Please restart sim reader or check if the sim card is not damaged.")
        msg.setInformativeText("The details are as follows:")
        msg.setWindowTitle("Error loading SIM data")
        msg.setDetailedText(e)
        msg.setStandardButtons(QMessageBox.Ok)

        if msg.exec_() == QMessageBox.Ok:
            app.quit()

    def _finishLoading(self, data):
        if "error" in data:
            self.showException(data["detail"])
            return False
        else:
            self.statusBar().showMessage("Data loaded successfully.", 1500)
            for key, value in data.items():
                self.data[key] = value
            self.timer.stop()
            self.progress.hide()
            self.saveToFileBtn.setEnabled(True)
            return True

    def prepareMetadataPanel(self, data):
        if self._finishLoading(data):
            self._metaIdx = self.stackedLayout.count()
            self.stackedLayout.addWidget(MetadataPanel(data))
            self.stackedLayout.setCurrentIndex(self._metaIdx)
        print("loaded metadata")

    def prepareContactsPanel(self, data):
        if self._finishLoading(data):
            self._contactsIdx = self.stackedLayout.count()
            self.stackedLayout.addWidget(ContactsPanel(self.sim, data))
            self.stackedLayout.setCurrentIndex(self._contactsIdx)
        print("loaded contacts")

    def prepareSMSsPanel(self, data):
        if self._finishLoading(data):
            self._smsIdx = self.stackedLayout.count()
            self.stackedLayout.addWidget(SMSPanel(data))
            self.stackedLayout.setCurrentIndex(self._smsIdx)
        print("loaded smss")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    if len(sys.argv) > 1:
        ex = SimReader(port=sys.argv[1])
    else:
        ex = SimReader()
    app.exec_()
