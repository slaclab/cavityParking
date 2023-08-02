from typing import Dict

from lcls_tools.common.pyepics_tools.pyepics_utils import PV
from lcls_tools.superconducting.scLinac import (Cavity, CryoDict, Cryomodule, Piezo, SSA, StepperTuner)
from lcls_tools.superconducting.sc_linac_utils import (CavityHWModeError, HW_MODE_MAINTENANCE_VALUE,
                                                       HW_MODE_ONLINE_VALUE,
                                                       HW_MODE_READY_VALUE, MAX_STEPPER_SPEED,
                                                       TUNE_CONFIG_COLD_VALUE,
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
        self._steps_cold_landing_pv_obj: PV = None
    
    @property
    def steps_cold_landing_pv_obj(self) -> PV:
        if not self._steps_cold_landing_pv_obj:
            self._steps_cold_landing_pv_obj = PV(self.steps_cold_landing_pv)
        return self._steps_cold_landing_pv_obj
    
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
            self.steppertuner.reset_signed_steps()
        
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
    
    def move_to_cold_landing(self, count_current: bool, use_freq=True):
        
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_COLD_VALUE:
            print(f"{self} at cold landing")
            print(f"Turning {self} and SSA off")
            self.turnOff()
            self.ssa.turn_off()
            return
        
        if not count_current:
            print(f"Resetting {self} stepper signed count")
            self.steppertuner.reset_signed_steps()
        
        if use_freq:
            
            if self.hw_mode not in [HW_MODE_MAINTENANCE_VALUE, HW_MODE_ONLINE_VALUE]:
                raise CavityHWModeError(f"{self} not Online or in Maintenance")
            
            df_cold = self.df_cold_pv_obj.get()
            
            if df_cold:
                chirp_range = abs(df_cold) + 50000
                print(f"Tuning {self} to {df_cold} Hz")
                
                def delta_func():
                    return self.detune_best - df_cold
                
                self.setup_tuning(use_sela=False, chirp_range=chirp_range)
                self._auto_tune(delta_hz_func=delta_func, tolerance=1000,
                                step_thresh=1.1)
            else:
                print("No cold landing frequency recorded, moving by steps instead")
                self.check_resonance()
                abs_est_detune = abs(self.steppertuner.steps_cold_landing_pv_obj.get() / self.microsteps_per_hz)
                self.setup_tuning(chirp_range=abs_est_detune + 50000)
                self.steppertuner.move_to_cold_landing(count_current=count_current)
            
            print("Turning cavity and SSA off")
            self.turnOff()
            self.ssa.turn_off()
        
        else:
            if self.hw_mode not in [HW_MODE_MAINTENANCE_VALUE,
                                    HW_MODE_ONLINE_VALUE, HW_MODE_READY_VALUE]:
                raise CavityHWModeError(f"{self} not Online, Maintenance, or Ready")
            
            self.check_resonance()
            self.steppertuner.move_to_cold_landing(count_current=count_current)
        
        self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)
    
    def check_resonance(self):
        if self.tune_config_pv_obj.get() != TUNE_CONFIG_RESONANCE_VALUE:
            raise CavityHWModeError(f"{self} not on resonance, not moving to cold landing by steps")


PARK_CRYOMODULES: Dict[str, Cryomodule] = CryoDict(cavityClass=ParkCavity,
                                                   stepperClass=ParkStepper)
