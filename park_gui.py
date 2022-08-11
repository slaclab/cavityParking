from typing import Dict

from PyQt5.QtCore import QObject, QThread
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget
from epics import camonitor, camonitor_clear
from lcls_tools.superconducting.scLinac import ALL_CRYOMODULES
from pydm import Display
from pydm.widgets import PyDMLabel
from qtpy.QtCore import Signal, Slot

from park_linac import PARK_CRYOMODULES, ParkCavity


class ParkWorker(QThread):
    status = Signal(str)
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, cavity: ParkCavity, label: QLabel):
        super().__init__()
        self.cavity = cavity
        self.status.connect(label.setText)
        self.finished.connect(label.setText)
        self.error.connect(label.setText)
    
    def run(self) -> None:
        self.status.emit("Moving to cold landing")
        self.cavity.move_to_cold_landing()
        self.finished.emit("Cavity at cold landing")


class CavityObject(QObject):
    clear_detune_callback_signal: Signal = Signal(bool)
    expand_chirp_signal: Signal = Signal(bool)
    
    def __init__(self, cm: str, num: int):
        super().__init__()
        self.cm_name = cm
        self.num = num
        self._cavity: ParkCavity = None
        self.label = QLabel("Ready")
        
        self.detune_readback: PyDMLabel = PyDMLabel(init_channel=self.cavity.detune_best_PV.pvname)
        self.detune_readback.alarmSensitiveContent = True
        self.detune_readback.showUnits = True
        
        self.go_button = QPushButton("Move to Cold Landing")
        self.groupbox = QGroupBox(f"Cavity {num}")
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.go_button)
        vlayout.addWidget(self.detune_readback)
        vlayout.addWidget(self.label)
        self.groupbox.setLayout(vlayout)
        
        self.park_worker: ParkWorker = None
        
        self.go_button.clicked.connect(self.launch_worker)
        self.clear_detune_callback_signal.connect(self.clear_callback)
        self.expand_chirp_signal.connect(self.expand_chirp)
    
    @property
    def cavity(self):
        if not self._cavity:
            self._cavity = PARK_CRYOMODULES[self.cm_name].cavities[self.num]
        return self._cavity
    
    @Slot()
    def launch_worker(self):
        camonitor(self.cavity.detune_best_PV, callback=self.chirp_callback)
        self.park_worker = ParkWorker(cavity=self.cavity, label=self.label)
        self.park_worker.start()
    
    @Slot()
    def clear_callback(self):
        camonitor_clear(self.cavity.detune_best_PV)
    
    @Slot(bool)
    def expand_chirp(self):
        self.cavity.set_chirp_range(400000)
        self.clear_detune_callback_signal.emit(True)
    
    @Slot()
    def chirp_callback(self, value, **kwargs):
        if abs(value) > 150000:
            self.expand_chirp_signal.emit(True)


class CryomoduleObject(QObject):
    def __init__(self, name: str):
        super().__init__()
        self.cav_objects: Dict[int, CavityObject] = {}
        
        self.go_button: QPushButton = QPushButton("Move to Cold Landing")
        self.page: QWidget = QWidget()
        self.groupbox: QGroupBox = QGroupBox()
        all_cav_layout: QGridLayout = QGridLayout()
        self.groupbox.setLayout(all_cav_layout)
        
        for i in range(1, 9):
            cav_obj = CavityObject(cm=name, num=i)
            self.cav_objects[i] = cav_obj
            all_cav_layout.addWidget(cav_obj.groupbox,
                                     0 if i in range(1, 5) else 1,
                                     (i - 1) % 4)
        
        vlayout: QVBoxLayout = QVBoxLayout()
        vlayout.addWidget(self.go_button)
        vlayout.addWidget(self.groupbox)
        
        self.page.setLayout(vlayout)
        self.go_button.clicked.connect(self.move_cavities_to_cold)
    
    @Slot()
    def move_cavities_to_cold(self):
        for cav_obj in self.cav_objects.values():
            cav_obj.launch_worker()


class ParkGUI(Display):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        
        for cm_name in ALL_CRYOMODULES:
            cm_obj = CryomoduleObject(name=cm_name)
            self.ui.tabWidget.addTab(cm_obj.page, cm_name)
    
    def ui_filename(self):
        return "park_gui.ui"
