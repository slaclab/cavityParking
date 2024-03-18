from datetime import datetime
from typing import List

from epics import caput
from lcls_tools.common.data_analysis.archiver import Archiver
from lcls_tools.superconducting.sc_linac import Cryomodule
from lcls_tools.superconducting.sc_linac_utils import RF_MODE_CHIRP
from numpy import mean

from park_linac import PARK_MACHINE

ARCHIVER = Archiver("lcls")


def move_steps_park(cm_list: List[str]):
    for cm_name in cm_list:
        cryomodule: Cryomodule = PARK_MACHINE.cryomodules[cm_name]
        for cavity in cryomodule.cavities.values():
            cavity.stepper_tuner.nsteps_cold_pv_obj.put(
                cavity.stepper_tuner.nsteps_park_pv_obj.value, wait=True
            )


def pull_cold_frequencies(start_time: datetime, end_time: datetime, cm_list: List[str]):
    for cm_name in cm_list:
        cryomodule: Cryomodule = PARK_MACHINE.cryomodules[cm_name]
        for cavity in cryomodule.cavities.values():
            pv_list = [cavity.detune_best_pv, cavity.rf_mode_pv, cavity.rf_state_pv]
            data = ARCHIVER.getValuesOverTimeRange(
                pvList=pv_list, startTime=start_time, endTime=end_time
            )
            if (
                len(data.values[cavity.rf_mode_pv]) != 1
                or len(data.values[cavity.rf_state_pv]) != 1
            ):
                print(
                    f"Ignoring CM{cm_name} Cavity {cavity.number} because multiple RF modes or states detected"
                )
                continue

            if (
                data.values[cavity.rf_mode_pv].pop() != RF_MODE_CHIRP
                or data.values[cavity.rf_state_pv].pop() != 1
            ):
                print(
                    f"Ignoring CM{cm_name} Cavity {cavity.number} because cavity was not in Chirp or was off"
                )
                continue

            df_cold = mean(data.values[cavity.detune_best_pv])
            if abs(df_cold) < 3000:
                print(
                    f"Ignoring CM{cm_name} Cavity {cavity.number} because detune {df_cold} suspiciously low"
                )
                continue

            # print(cavity.df_cold_pv, df_cold, 1.3e9 + df_cold)
            caput(cavity.df_cold_pv, df_cold, wait=True)


if __name__ == "__main__":
    exclude = ["H1", "H2"]
    cm_list = [item for item in PARK_MACHINE.cryomodules.keys() if item not in exclude]
    move_steps_park(cm_list)
