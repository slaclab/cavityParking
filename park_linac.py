from typing import Dict

from lcls_tools.common.pyepics_tools.pyepicsUtils import PV
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.scLinacUtils import (MAX_STEPPER_SPEED, TUNE_CONFIG_COLD_VALUE,
                                                     TUNE_CONFIG_PARKED_VALUE,
                                                     TUNE_CONFIG_RESONANCE_VALUE)

PARK_DETUNE = 10000


class ParkStepper(StepperTuner):
    def __init__(self, cavity):
        super().__init__(cavity)
        self.nsteps_park_pv: str = self.pv_addr("NSTEPS_PARK")
        self._nsteps_park_pv_obj: PV = None
        
        self.nsteps_cold_pv: str = self.pv_addr("NSTEPS_COLD")
        self._nsteps_cold_pv_obj: PV = None
        
        self._step_signed_pv_obj: PV = None
    
    @property
    def nsteps_park_pv_obj(self) -> PV:
        if not self._nsteps_park_pv_obj:
            self._nsteps_park_pv_obj = PV(self.nsteps_park_pv)
        return self._nsteps_park_pv_obj
    
    @property
    def nsteps_cold_pv_obj(self) -> PV:
        if not self._nsteps_cold_pv_obj:
            self._nsteps_cold_pv_obj = PV(self.nsteps_cold_pv)
        return self._nsteps_cold_pv_obj
    
    @property
    def step_signed_pv_obj(self):
        if not self._step_signed_pv_obj:
            self._step_signed_pv_obj = PV(self.step_signed_pv)
        return self._step_signed_pv_obj
    
    def move_to_cold_landing(self, count_current: bool):
        recorded_steps = self.nsteps_cold_pv_obj.get()
        if count_current:
            steps = recorded_steps - self.step_signed_pv_obj.get()
        else:
            steps = recorded_steps
        print(f"Moving {steps} steps")
        self.move(steps, maxSteps=5000000, speed=MAX_STEPPER_SPEED)
    
    def park(self, count_current: bool):
        adjustment = self.step_signed_pv_obj.get() if count_current else 0
        print(f"Moving {self.cavity} tuner 1.8e6 steps")
        self.move(1800000 - adjustment)


class ParkCavity(Cavity):
    
    def __init__(self, cavityNum, rackObject, ssaClass=SSA,
                 stepperClass=ParkStepper, piezoClass=Piezo):
        super().__init__(cavityNum, rackObject, stepperClass=ParkStepper)
        self.df_cold_pv: str = self.pv_addr("DF_COLD")
        self._df_cold_pv_obj: PV = None
    
    @property
    def df_cold_pv_obj(self) -> PV:
        if not self._df_cold_pv_obj:
            self._df_cold_pv_obj = PV(self.df_cold_pv)
        return self._df_cold_pv_obj
    
    def park(self, count_current: bool):
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_PARKED_VALUE:
            return
        
        starting_config = self.tune_config_pv_obj.get()
        
        if not count_current:
            print(f"Resetting {self} stepper signed count")
            self.steppertuner.reset_signed_pv.put(1)
        
        if self.detune_best < PARK_DETUNE:
            self.auto_tune(des_detune=PARK_DETUNE,
                           config_val=TUNE_CONFIG_PARKED_VALUE,
                           tolerance=1000, chirp_range=PARK_DETUNE + 50000)
        
        if starting_config == TUNE_CONFIG_RESONANCE_VALUE:
            print(f"Updating stored steps to park to current step count for {self}")
            self.steppertuner.nsteps_park_pv_obj.put(self.steppertuner.step_tot_pv.get())
        
        print("Turning cavity and SSA off")
        self.turnOff()
        self.ssa.turn_off()
    
    def move_to_cold_landing(self, count_current: bool):
        
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_COLD_VALUE:
            print(f"{self} at cold landing")
            print(f"Turning {self} and SSA off")
            self.turnOff()
            self.ssa.turn_off()
            return
        
        if not count_current:
            print(f"Resetting {self} stepper signed count")
            self.steppertuner.reset_signed_pv.put(0)
        
        df_cold = self.df_cold_pv_obj.get()
        if df_cold:
            chirp_range = abs(df_cold) + 50000
            print(f"Tuning {self} to {df_cold} Hz")
            self.auto_tune(des_detune=df_cold, config_val=TUNE_CONFIG_COLD_VALUE,
                           chirp_range=chirp_range, tolerance=1000)
        else:
            print("No cold landing frequency recorded, moving npark steps instead")
            abs_est_detune = abs(self.steppertuner.steps_cold_landing_pv.get() / self.steps_per_hz)
            self.setup_tuning(chirp_range=abs_est_detune + 50000)
            self.steppertuner.move_to_cold_landing(count_current=count_current)
            self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)
            self.df_cold_pv_obj.put(self.detune_best)
        
        print("Turning cavity and SSA off")
        self.turnOff()
        self.ssa.turnOff()


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
