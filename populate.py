from datetime import datetime
from typing import List

from epics import caput
from lcls_tools.common.data_analysis.archiver import Archiver
from lcls_tools.superconducting.scLinac import ALL_CRYOMODULES, Cryomodule
from lcls_tools.superconducting.scLinacUtils import RF_MODE_CHIRP
from numpy import mean

from park_linac import PARK_CRYOMODULES

ARCHIVER = Archiver("lcls")


def move_steps_park(cm_list: List[str]):
    for cm_name in cm_list:
        cryomodule: Cryomodule = PARK_CRYOMODULES[cm_name]
        for cavity in cryomodule.cavities.values():
            cavity.steppertuner.nsteps_cold_pv.put(cavity.steppertuner.nsteps_park_pv.value,
                                                   wait=True)


def pull_cold_frequencies(start_time: datetime, end_time: datetime, cm_list: List[str]):
    for cm_name in cm_list:
        cryomodule: Cryomodule = PARK_CRYOMODULES[cm_name]
        for cavity in cryomodule.cavities.values():
            pv_list = [cavity.detune_best_PV.pvname, cavity.rfModePV.pvname, cavity.rfStatePV]
            data = ARCHIVER.getValuesOverTimeRange(pvList=pv_list,
                                                   startTime=start_time,
                                                   endTime=end_time)
            if len(data.values[cavity.rfModePV.pvname]) != 1 or len(data.values[cavity.rfStatePV]) != 1:
                print(f"Ignoring CM{cm_name} Cavity {cavity.number} because multiple RF modes or states detected")
                continue
            
            if data.values[cavity.rfModePV.pvname].pop() != RF_MODE_CHIRP or data.values[cavity.rfStatePV].pop() != 1:
                print(f"Ignoring CM{cm_name} Cavity {cavity.number} because cavity was not in Chirp or was off")
                continue
            
            df_cold = mean(data.values[cavity.detune_best_PV.pvname])
            if abs(df_cold) < 3000:
                print(f"Ignoring CM{cm_name} Cavity {cavity.number} because detune {df_cold} suspiciously low")
                continue
            
            # print(cavity.df_cold_pv, df_cold, 1.3e9 + df_cold)
            caput(cavity.df_cold_pv, df_cold, wait=True)


if __name__ == "__main__":
    exclude = ["H1", "H2"]
    cm_list = [item for item in ALL_CRYOMODULES if item not in exclude]
    move_steps_park(cm_list)
