from typing import Dict

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QCheckBox, QFormLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget
from epics import camonitor, camonitor_clear, caput
from lcls_tools.superconducting.scLinac import ALL_CRYOMODULES
from lcls_tools.superconducting.scLinacUtils import StepperError
from pydm import Display
from pydm.widgets import PyDMLabel

from park_linac import PARK_CRYOMODULES, ParkCavity


class ParkWorker(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, cavity: ParkCavity, label: QLabel, count_current: bool):
        super().__init__()
        self.cavity = cavity
        self.status.connect(label.setText)
        self.status.connect(print)
        self.finished.connect(label.setText)
        self.finished.connect(print)
        self.error.connect(label.setText)
        self.error.connect(print)
        
        self.finished.connect(self.deleteLater)
        self.error.connect(self.deleteLater)
        
        self.count_current = count_current
    
    def run(self) -> None:
        self.status.emit("Moving to cold landing")
        try:
            self.cavity.move_to_cold_landing(count_current=self.count_current)
            self.finished.emit("Cavity at cold landing")
        except StepperError as e:
            self.error.emit(str(e))


class CavityObject(QObject):
    clear_detune_callback_signal: pyqtSignal = pyqtSignal(bool)
    expand_chirp_signal: pyqtSignal = pyqtSignal(bool)
    
    def __init__(self, cm: str, num: int, parent):
        super().__init__(parent=parent)
        self.cm_name = cm
        self.num = num
        self._cavity: ParkCavity = None
        self.label = QLabel("Ready")
        
        readbacks: QFormLayout = QFormLayout()
        
        self.detune_readback: PyDMLabel = PyDMLabel(init_channel=self.cavity.detune_best_PV.pvname)
        self.detune_readback.alarmSensitiveContent = True
        self.detune_readback.showUnits = True
        
        park_steps: PyDMLabel = PyDMLabel(init_channel=self.cavity.steppertuner.nsteps_park_pv.pvname)
        park_steps.alarmSensitiveContent = True
        park_steps.showUnits = True
        
        freq_cold: PyDMLabel = PyDMLabel(init_channel=self.cavity.df_cold_pv.pvname)
        freq_cold.alarmSensitiveContent = True
        freq_cold.showUnits = True
        
        step_readback: PyDMLabel = PyDMLabel(init_channel=self.cavity.steppertuner.step_signed_pv.pvname)
        step_readback.alarmSensitiveContent = True
        step_readback.showUnits = True
        
        config_label = PyDMLabel(init_channel=self.cavity.tune_config_pv)
        config_label.alarmSensitiveContent = True
        config_label.showUnits = True
        
        readbacks.addRow("Live Detune", self.detune_readback)
        readbacks.addRow("Steps to Park", park_steps)
        readbacks.addRow("Cold Landing Detune", freq_cold)
        readbacks.addRow("Live Total Step Count", step_readback)
        readbacks.addRow("Tune Config", config_label)
        
        self.go_button: QPushButton = QPushButton("Move to Cold Landing")
        self.go_button.clicked.connect(self.launch_worker)
        
        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.clicked.connect(self.kill_worker)
        
        self.count_signed_steps: QCheckBox = QCheckBox("Count current steps toward total")
        self.count_signed_steps.setChecked(False)
        
        self.groupbox = QGroupBox(f"Cavity {num}")
        self.vlayout = QVBoxLayout()
        self.vlayout.addWidget(self.count_signed_steps)
        self.vlayout.addWidget(self.go_button)
        self.vlayout.addLayout(readbacks)
        self.vlayout.addWidget(self.label)
        self.vlayout.addWidget(self.abort_button)
        
        self.groupbox.setLayout(self.vlayout)
        
        self.park_worker: ParkWorker = None
        
        self.clear_detune_callback_signal.connect(self.clear_callback)
        self.expand_chirp_signal.connect(self.expand_chirp)
    
    @property
    def cavity(self):
        if not self._cavity:
            self._cavity = PARK_CRYOMODULES[self.cm_name].cavities[self.num]
        return self._cavity
    
    def kill_worker(self):
        print("Aborting stepper move request")
        caput(self.cavity.steppertuner.abort_pv.pvname, 1)
        self.park_worker.error.emit("Aborting")
        self.park_worker.terminate()
    
    def launch_worker(self):
        print("launching worker")
        self.park_worker = ParkWorker(cavity=self.cavity, label=self.label,
                                      count_current=self.count_signed_steps.isChecked())
        self.park_worker.start()
        camonitor(self.cavity.detune_best_PV.pvname, callback=self.chirp_callback)
    
    def clear_callback(self):
        camonitor_clear(self.cavity.detune_best_PV.pvname)
    
    @pyqtSlot(bool)
    def expand_chirp(self):
        self.cavity.set_chirp_range(400000)
        self.clear_detune_callback_signal.emit(True)
    
    def chirp_callback(self, value, **kwargs):
        if abs(value) > 150000:
            self.expand_chirp_signal.emit(True)


class CryomoduleObject(QObject):
    def __init__(self, name: str, parent):
        super().__init__(parent=parent)
        self.cav_objects: Dict[int, CavityObject] = {}
        
        self.go_button: QPushButton = QPushButton("Move to Cold Landing")
        self.go_button.clicked.connect(self.move_cavities_to_cold)
        
        self.page: QWidget = QWidget()
        self.groupbox: QGroupBox = QGroupBox()
        all_cav_layout: QGridLayout = QGridLayout()
        self.groupbox.setLayout(all_cav_layout)
        
        for i in range(1, 9):
            cav_obj = CavityObject(cm=name, num=i, parent=parent)
            self.cav_objects[i] = cav_obj
            all_cav_layout.addWidget(cav_obj.groupbox,
                                     0 if i in range(1, 5) else 1,
                                     (i - 1) % 4)
        
        vlayout: QVBoxLayout = QVBoxLayout()
        vlayout.addWidget(self.go_button)
        vlayout.addWidget(self.groupbox)
        
        self.page.setLayout(vlayout)
    
    @pyqtSlot()
    def move_cavities_to_cold(self):
        for cav_obj in self.cav_objects.values():
            cav_obj.launch_worker()


class ParkGUI(Display):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        
        for cm_name in ALL_CRYOMODULES:
            cm_obj = CryomoduleObject(name=cm_name, parent=self)
            self.ui.tabWidget.addTab(cm_obj.page, cm_name)
    
    def ui_filename(self):
        return "park_gui.ui"