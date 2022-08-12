from typing import Dict

from epics import PV, caput
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.scLinacUtils import (TUNE_CONFIG_COLD_VALUE, TUNE_CONFIG_OTHER_VALUE)


class ParkStepper(StepperTuner):
    def __init__(self, cavity):
        super().__init__(cavity)
        self._nsteps_park_pv: PV = None
    
    @property
    def nsteps_park_pv(self) -> PV:
        if not self._nsteps_park_pv:
            self._nsteps_park_pv = PV(self.pvPrefix + "NSTEPS_PARK")
        return self._nsteps_park_pv
    
    def move_to_cold_landing(self):
        steps = self.nsteps_park_pv.value
        print(f"Moving {steps} steps")
        self.move(steps)


class ParkCavity(Cavity):
    
    def __init__(self, cavityNum, rackObject, ssaClass=SSA,
                 stepperClass=ParkStepper, piezoClass=Piezo):
        super().__init__(cavityNum, rackObject, stepperClass=ParkStepper)
        self._df_cold_pv: PV = None
        chirp_prefix = self.pvPrefix + "CHIRP:"
        
        self.freq_start_pv: str = chirp_prefix + "FREQ_START"
        self.freq_stop_pv: str = chirp_prefix + "FREQ_STOP"
    
    @property
    def df_cold_pv(self) -> PV:
        if not self._df_cold_pv:
            self._df_cold_pv = PV(self.pvPrefix + "DF_COLD")
        return self._df_cold_pv
    
    def move_to_cold_landing(self):
        
        if self.detune_best_PV.severity != 3:
            curr_detune = self.detune_best_PV.value
            if curr_detune and abs(curr_detune) < 150000:
                self.set_chirp_range(200000)
            else:
                self.set_chirp_range(400000)
        
        else:
            self.set_chirp_range(200000)
        
        print("Setting tune config to Other")
        caput(self.tune_config_pv, TUNE_CONFIG_OTHER_VALUE, wait=True)
        print("Resetting stepper total count")
        self.steppertuner.reset_tot_pv.put(1)
        
        df_cold = self.df_cold_pv.value
        if df_cold:
            print(f"Tuning to {df_cold}")
            self.auto_tune(des_detune=df_cold, config_val=TUNE_CONFIG_COLD_VALUE)
        else:
            print("No cold landing frequency recorded, moving npark steps instead")
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
