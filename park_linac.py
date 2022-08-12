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
        print(f"Moving {steps} steps")
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
        curr_detune = caget(self.detune_best_PV.pvname)
        if curr_detune and abs(curr_detune) < 150000:
            self.set_chirp_range(200000)
        else:
            self.set_chirp_range(400000)
        
        print("Setting tune config to Other")
        caput(self.tune_config_pv, TUNE_CONFIG_OTHER_VALUE, wait=True)
        # print("Resetting stepper total count")
        # caput(self.steppertuner.reset_tot_pv.pvname, 1)
        
        df_cold = caget(self.df_cold_pv)
        if df_cold:
            print(f"Tuning to {df_cold}")
            self.auto_tune(des_detune=df_cold, config_val=TUNE_CONFIG_COLD_VALUE)
        else:
            self.setup_tuning()
            self.steppertuner.move_to_cold_landing()
            caput(self.tune_config_pv, TUNE_CONFIG_COLD_VALUE)
        
        # steps_to_cold = caget(self.steppertuner.step_tot_pv.pvname)
        # caput(self.steppertuner.nsteps_park_pv, steps_to_cold)
    
    def set_chirp_range(self, offset: int):
        offset = abs(offset)
        print(f"Setting chirp range for cm{self.cryomodule.name} cavity {self.number} to +/- {offset} Hz")
        caput(self.freq_start_pv, -offset, wait=True)
        caput(self.freq_stop_pv, offset, wait=True)
        print(f"Chirp range set for cm{self.cryomodule.name} cavity {self.number}")


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
