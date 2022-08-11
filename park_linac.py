from typing import Dict

from epics import caget, caput
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.scLinacUtils import (TUNE_CONFIG_COLD_VALUE, TUNE_CONFIG_OTHER_VALUE)


class ParkStepper(StepperTuner):
    def __init__(self, cavity):
        super().__init__(cavity)
        self.nsteps_park_pv: str = self.pvPrefix + "NSTEPS_PARK"
    
    def move_to_cold_landing(self):
        steps = caget(self.nsteps_park_pv)
        self.move(steps)


class ParkCavity(Cavity):
    
    def __init__(self, cavityNum, rackObject, ssaClass=SSA,
                 stepperClass=ParkStepper, piezoClass=Piezo):
        super().__init__(cavityNum, rackObject, stepperClass=ParkStepper)
        self.df_cold_pv: str = self.pvPrefix + "DF_COLD"
        chirp_prefix = self.pvPrefix + "CHIRP:"
        
        self.freq_start_pv: str = chirp_prefix + "FREQ_START"
        self.freq_stop_pv: str = chirp_prefix + "FREQ_STOP"
    
    def move_to_cold_landing(self):
        self.set_chirp_range(200000)
        self.setup_tuning()
        caput(self.tune_config_pv, TUNE_CONFIG_OTHER_VALUE, wait=True)
        self.steppertuner.move_to_cold_landing()
        caput(self.tune_config_pv, TUNE_CONFIG_COLD_VALUE)
        cold_landing_freq = caget(self.detune_best_PV.pvname)
        caput(self.df_cold_pv, cold_landing_freq)
    
    def set_chirp_range(self, offset: int):
        offset = abs(offset)
        print(f"Setting chirp range for cm{self.cryomodule.name} cavity {self.number} to +/- {offset} Hz")
        caput(self.freq_start_pv, -offset, wait=True)
        caput(self.freq_stop_pv, offset, wait=True)
        print(f"Chirp range set for cm{self.cryomodule.name} cavity {self.number}")


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
