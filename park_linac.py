from typing import Dict

from epics import PV
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.scLinacUtils import (MAX_STEPPER_SPEED, StepperError, TUNE_CONFIG_COLD_VALUE,
                                                     TUNE_CONFIG_OTHER_VALUE)


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


class ParkCavity(Cavity):
    
    def __init__(self, cavityNum, rackObject, ssaClass=SSA,
                 stepperClass=ParkStepper, piezoClass=Piezo):
        super().__init__(cavityNum, rackObject, stepperClass=ParkStepper)
        self._df_cold_pv: PV = None
    
    @property
    def df_cold_pv(self) -> PV:
        if not self._df_cold_pv:
            self._df_cold_pv = PV(self.pvPrefix + "DF_COLD")
        return self._df_cold_pv
    
    def check_abort(self):
        if self.steppertuner.abort_flag:
            raise StepperError(f"Abort requested for CM{self.cryomodule.name} cavity {self.number} stepper tuner")
    
    def move_to_cold_landing(self, count_current: bool):
        
        if self.tune_config_pv.value == TUNE_CONFIG_COLD_VALUE:
            print("Cavity at cold landing")
            print("Turning cavity and SSA off")
            self.turnOff()
            self.ssa.turnOff()
        
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
        
        print("Setting tune config to Other")
        self.tune_config_pv.put(TUNE_CONFIG_OTHER_VALUE)
        
        if not count_current:
            print("Resetting stepper signed count")
            while self.steppertuner.step_signed_pv.value != 0:
                self.steppertuner.reset_signed_pv.put(1, wait=True)
        
        self.check_abort()
        
        df_cold = self.df_cold_pv.value
        if df_cold:
            print(f"Tuning to {df_cold}")
            self.auto_tune(des_detune=df_cold, config_val=TUNE_CONFIG_COLD_VALUE)
        else:
            print("No cold landing frequency recorded, moving npark steps instead")
            self.setup_tuning()
            self.steppertuner.move_to_cold_landing(count_current=count_current)
            self.tune_config_pv.put(TUNE_CONFIG_COLD_VALUE)
            self.df_cold_pv.put(self.detune_best_PV.value)
        
        print("Turning cavity and SSA off")
        self.turnOff()
        self.ssa.turnOff()
        
        # steps_to_cold = caget(self.steppertuner.step_tot_pv.pvname)
        # caput(self.steppertuner.nsteps_park_pv, steps_to_cold)


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
