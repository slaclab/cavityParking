from typing import Dict

from epics import PV
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.scLinacUtils import (MAX_STEPPER_SPEED, StepperAbortError, TUNE_CONFIG_COLD_VALUE,
                                                     TUNE_CONFIG_OTHER_VALUE, TUNE_CONFIG_RESONANCE_VALUE)


class ParkStepper(StepperTuner):
    def __init__(self, cavity):
        super().__init__(cavity)
        self._nsteps_park_pv: PV = None
    
    @property
    def nsteps_park_pv(self) -> PV:
        if not self._nsteps_park_pv:
            self._nsteps_park_pv = PV(self.pvPrefix + "NSTEPS_PARK")
        return self._nsteps_park_pv
    
    def move_to_cold_landing(self, count_current: bool):
        recorded_steps = self.nsteps_park_pv.value
        if count_current:
            steps = recorded_steps - self.step_signed_pv.value
        else:
            steps = recorded_steps
        print(f"Moving {steps} steps")
        self.move(steps, maxSteps=5000000, speed=MAX_STEPPER_SPEED)
    
    def park(self, count_current: bool):
        adjustment = self.step_signed_pv.value if count_current else 0
        print(f"Moving {self.cavity} tuner 1.8e6 steps")
        self.move(1800000 - adjustment)


class ParkCavity(Cavity):
    
    def __init__(self, cavityNum, rackObject, ssaClass=SSA,
                 stepperClass=ParkStepper, piezoClass=Piezo):
        super().__init__(cavityNum, rackObject, stepperClass=ParkStepper)
        self._df_cold_pv: PV = None
        self._park_pv: PV = None
    
    @property
    def park_pv(self) -> PV:
        if not self._park_pv:
            self._park_pv = PV(self.pvPrefix + "PARK")
        return self._park_pv
    
    @property
    def df_cold_pv(self) -> PV:
        if not self._df_cold_pv:
            self._df_cold_pv = PV(self.pvPrefix + "DF_COLD")
        return self._df_cold_pv
    
    def check_abort(self):
        if self.steppertuner.abort_flag:
            raise StepperAbortError(f"Abort requested for CM{self.cryomodule.name} cavity {self.number} stepper tuner")
    
    def park(self, count_current: bool):
        if self.park_pv.value == 1:
            print("Cavity parked")
            print(f"Turning {self} and SSA off")
            self.turnOff()
            self.ssa.turnOff()
            return
        
        self.setup(count_current)
        self.auto_tune(des_detune=10000, config_val=TUNE_CONFIG_OTHER_VALUE)
        self.park_pv.put(1, wait=True)
    
    def move_to_cold_landing(self, count_current: bool):
        
        if self.tune_config_pv.value == TUNE_CONFIG_COLD_VALUE:
            print("Cavity at cold landing")
            print("Turning cavity and SSA off")
            self.turnOff()
            self.ssa.turnOff()
            return
        
        self.setup(count_current)
        
        df_cold = self.df_cold_pv.value
        if df_cold:
            print(f"Tuning {self} to {df_cold} Hz")
            starting_config = self.tune_config_pv.value
            self.auto_tune(des_detune=df_cold, config_val=TUNE_CONFIG_COLD_VALUE)
            if starting_config == TUNE_CONFIG_RESONANCE_VALUE:
                print(f"Updating stored steps to cold landing to current step count for {self}")
                self.steppertuner.nsteps_park_pv.put(self.steppertuner.step_tot_pv.value)
        else:
            print("No cold landing frequency recorded, moving npark steps instead")
            self.setup_tuning()
            self.steppertuner.move_to_cold_landing(count_current=count_current)
            self.tune_config_pv.put(TUNE_CONFIG_COLD_VALUE)
            self.df_cold_pv.put(self.detune_best_PV.value)
        
        print("Turning cavity and SSA off")
        self.turnOff()
        self.ssa.turnOff()
    
    def setup(self, count_current):
        self.check_abort()
        self.setup_tuning()
        self.check_abort()
        
        if self.detune_best_PV.severity != 3:
            curr_detune = self.detune_best_PV.value
            if curr_detune and abs(curr_detune) < 150000:
                self.set_chirp_range(200000)
            else:
                self.set_chirp_range(400000)
        
        else:
            self.set_chirp_range(200000)
        self.check_abort()
        
        print(f"Setting tune config for {self} to Other")
        self.tune_config_pv.put(TUNE_CONFIG_OTHER_VALUE)
        
        if not count_current:
            print(f"Resetting {self} stepper signed count")
            while self.steppertuner.step_signed_pv.value != 0:
                self.steppertuner.reset_signed_pv.put(1, wait=True)
        self.check_abort()


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
