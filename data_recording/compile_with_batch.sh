#!/bin/bash
# =============================================================================
# compile_with_batch.sh
#
# Modified copy of Keysight's compile.sh that ALSO builds batch_sweep.
# The only changes from the original are:
#   1. Added "gcc batch_sweep.c ..." line right after the sweep.c line.
#
# Drop this file next to compile.sh in the application folder.
# Run with: ./compile_with_batch.sh
#
# (The original compile.sh is untouched.)
# =============================================================================

chmod +x *.sh *.py
gcc sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o sweep
gcc batch_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o batch_sweep
gcc sweep_tn.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o sweep_tn
gcc sweep_parallel.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o sweep_parallel
gcc display_shared_mem.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -fopenmp -o display_shared_mem
gcc run_sweep_parallel.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o run_sweep_parallel
gcc run_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o run_sweep
gcc run_sweep_log.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o run_sweep_log
gcc setup_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o setup_sweep
gcc EcalSnapShot.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lrt -lm -lpthread -o EcalSnapShot
gcc UserCalOpenShortLoadSweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o  UserCalOpenShortLoadSweep
gcc UserCalUnknownThruSweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o UserCalUnknownThruSweep
gcc UserCalOpenShortLoadOffline.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o  UserCalOpenShortLoadOffline
gcc UserCalUnknownThruOffline.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o UserCalUnknownThruOffline
gcc UserCalOpenShortLoadSegmentedSweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o  UserCalOpenShortLoadSegmentedSweep
gcc UserCalUnknownThruSegmentedSweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o UserCalUnknownThruSegmentedSweep
gcc UserCalIsolationSweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o UserCalIsolationSweep
gcc LOcableCal.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o  LOcableCal
gcc TraceNoise.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o TraceNoise
gcc GetAllMN7021AInfo.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o GetAllMN7021AInfo
gcc GetAllMN7021AInfo_SetTime.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o GetAllMN7021AInfo_SetTime
gcc EthernetToUSB.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o EthernetToUSB
gcc SystemFwUpgrade.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o SystemFwUpgrade
gcc SetSystemIdle.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o SetSystemIdle
gcc RebootSystem.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o RebootSystem
gcc FinalTest.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o FinalTest
gcc DriftCheckFactCal.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o DriftCheckFactCal
gcc SPsweep.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o SPsweep
gcc CalKitSetCreator.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o CalKitSetCreator
gcc CalWithEcal.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o CalWithEcal
gcc InternalCalWithEcal.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o InternalCalWithEcal
gcc PowerOnPhaseCal.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o PowerOnPhaseCal
gcc Prod_LOcableCal.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o  Prod_LOcableCal
gcc DriftCalc.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o DriftCalc
gcc sweep_SPout.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o sweep_SPout
gcc IsoTestSingle.c /usr/local/lib/libMN7021aApp.so -lxml2  /usr/local/lib/libMN7021a.so -lm -lrt -lpthread  -o IsoTestSingle
gcc LicenseQuery.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o LicenseQuery

gcc FinalTest_4unit.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o FinalTest_4unit
gcc DriftCheckFactCal_4unit.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o DriftCheckFactCal_4unit
gcc SPsweep_4unit.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o SPsweep_4unit

gcc USB_CPU_Setup.c /usr/local/lib/libMN7021a.so -lm -o USB_CPU_Setup
gcc AllUnitFirmwareUpgrade.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -o AllUnitFirmwareUpgrade
gcc CalDataCorrection.c /usr/local/lib/libMN7021aApp.so -lxml2  /usr/local/lib/libMN7021a.so -lm -lrt -lpthread  -o CalDataCorrection

gcc NewBoardTest.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o NewBoardTest
gcc FactCal.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o FactCal
gcc EcalCal.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o EcalCal
gcc ADC_Test.c /usr/local/lib/libMN7021a.so -lm -o ADC_Test
gcc Ref_Tune.c /usr/local/lib/libMN7021a.so -lm -o Ref_Tune
gcc Reboot.c /usr/local/lib/libMN7021a.so -lm -o Reboot
gcc Power_Meas_Prod.c /usr/local/lib/libMN7021a.so /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -o Power_Meas_Prod
gcc Ethernet_100MHz_External.c /usr/local/lib/libMN7021a.so -lm -o Ethernet_100MHz_External
gcc Ethernet_LO_External.c /usr/local/lib/libMN7021a.so -lm -o Ethernet_LO_External
gcc Ethernet_100MHz_Internal.c /usr/local/lib/libMN7021a.so -lm -o Ethernet_100MHz_Internal
gcc Ethernet_LO_Internal.c /usr/local/lib/libMN7021a.so -lm -o Ethernet_LO_Internal
gcc Ecal_Set.c /usr/local/lib/libMN7021a.so -lm -o Ecal_Set
gcc External_LO_Ref.c /usr/local/lib/libMN7021a.so -lm -o External_LO_Ref
gcc Ext_Ref_Clk_Control.c /usr/local/lib/libMN7021a.so -lm -o Ext_Ref_Clk_Control
gcc SOLO_SPI_Ethernet.c /usr/local/lib/libMN7021a.so -lm -o SOLO_SPI_Ethernet
gcc GetCalRev.c /usr/local/lib/libMN7021a.so -lm -o GetCalRev
gcc SetMultiUnitTrigger.c /usr/local/lib/libMN7021a.so -lm -o SetMultiUnitTrigger
gcc SetSingleUnitTrigger.c /usr/local/lib/libMN7021a.so -lm -o SetSingleUnitTrigger
gcc SynthCheck.c /usr/local/lib/libMN7021a.so /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -o SynthCheck

gcc ADC_PowTN.c  /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o ADC_PowTN
gcc ADC_Level_Meas.c /usr/local/lib/libMN7021a.so /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -o ADC_Level_Meas
gcc LevelScreenTN.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o LevelScreenTN
gcc LevelScreenTN_0p5dB.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o LevelScreenTN_0p5dB
gcc LevelScreenTN_1dB.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o LevelScreenTN_1dB
gcc BackupFWRecovery.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lm -lrt -lpthread -o BackupFWRecovery
gcc setClearPersistFlag.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o setClearPersistFlag
gcc PersistFlagUnitService.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o PersistFlagUnitService
gcc sweep_thermal_simulator.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o sweep_thermal_simulator
gcc SetSystemPowerOnState.c /usr/local/lib/libMN7021aApp.so -lxml2 -lrt -lm -o SetSystemPowerOnState
gcc RecoveryRoutineSimulator.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o RecoveryRoutineSimulator
echo "Password may be required to compile USB code."
sudo gcc USB_SetupExample.c /usr/local/lib/libMN7021aApp.so -lxml2 /usr/local/lib/libMN7021a.so -lusb-1.0 -lm -lrt -o USB_SetupExample
sudo gcc CheckUSBSwitching.c /usr/local/lib/libMN7021a.so -lusb-1.0 -lm -o CheckUSBSwitching
sudo ldconfig
echo "Compiling C to Python interface"

gcc -c -fPIC -I /usr/include/python3.8/ -l python3.8 Ethernet_readMN7021.c
gcc -shared  Ethernet_readMN7021.o /usr/local/lib/libMN7021a.so -lm -o Ethernet_readMN7021.so

echo "Finished Compiling Code"
echo "Compile complete (with batch_sweep)."
