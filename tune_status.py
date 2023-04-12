from csv import DictWriter

from lcls_tools.superconducting.scLinac import L0B

from park_linac import PARK_CRYOMODULES

with open('cavity_status.csv', 'w', newline='') as csvfile:
    fieldnames = ['Cryomodule', 'Cavity', 'Tune Config',
                  'Steps to Cold Landing', 'DF Cold']
    writer = DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for cm_name in L0B:
        cm_object = PARK_CRYOMODULES[cm_name]
        for cavity_number, cavity in cm_object.cavities.items():
            writer.writerow({'Cryomodule'           : cm_object.name,
                             'Cavity'               : cavity_number,
                             'Tune Config'          : cavity.tune_config_pv.get(as_string=True),
                             'Steps to Cold Landing': cavity.steppertuner.steps_cold_landing_pv.get(),
                             'DF Cold'              : cavity.df_cold_pv.get()})
