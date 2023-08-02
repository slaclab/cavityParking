from csv import DictWriter

from lcls_tools.superconducting.sc_linac_utils import ALL_CRYOMODULES

from park_linac import PARK_CRYOMODULES

with open('cavity_status.csv', 'w', newline='') as csvfile:
    fieldnames = ['Cryomodule', 'Cavity', 'Tune Config',
                  'Steps to Cold Landing', 'DF Cold', 'HW Mode']
    writer = DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for cm_name in ALL_CRYOMODULES:
        cm_object = PARK_CRYOMODULES[cm_name]
        for cavity_number, cavity in cm_object.cavities.items():
            writer.writerow({'Cryomodule'           : cm_object.name,
                             'Cavity'               : cavity_number,
                             'Tune Config'          : cavity.tune_config_pv_obj.get(as_string=True),
                             'Steps to Cold Landing': cavity.steppertuner.steps_cold_landing_pv_obj.get(),
                             'DF Cold'              : int(cavity.df_cold_pv_obj.get()),
                             'HW Mode'              : cavity.hw_mode_str})
