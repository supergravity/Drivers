#!/usr/bin/env python
import importlib
import os
import sys
import copy

import numpy as np

from BaseDriver import LabberDriver
from sequence_builtin import CPMG, PulseTrain, Rabi, SpinLocking
from sequence_rb import SingleQubit_RB, TwoQubit_RB
from sequence import SequenceToWaveforms

# dictionary with built-in sequences
SEQUENCES = {'Rabi': Rabi,
             'CP/CPMG': CPMG,
             'Pulse train': PulseTrain,
             '1-QB Randomized Benchmarking': SingleQubit_RB,
             '2-QB Randomized Benchmarking': TwoQubit_RB,
             'Spin-locking' : SpinLocking,
             'Custom': type(None)}


class Driver(LabberDriver):
    """This class implements a multi-qubit pulse generator."""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection."""
        # init variables
        self.sequence = None
        self.sequence_to_waveforms = SequenceToWaveforms()
        self.waveforms = {}
        # always create a sequence at startup
        name = self.getValue('Sequence')
        self.sendValueToOther('Sequence', name)

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation."""
        # only do something here if changing the sequence type
        if quant.name == 'Sequence':
            # create new sequence if sequence type changed
            new_type = SEQUENCES[value]

            if not isinstance(self.sequence, new_type):
                # create a new sequence object
                if value == 'Custom':
                    # for custom python files
                    path = self.getValue('Custom Python file')
                    (path, modName) = os.path.split(path)
                    sys.path.append(path)
                    modName = modName.split('.py')[0]  # strip suffix
                    mod = importlib.import_module(modName)
                    # the custom sequence class has to be named
                    # 'CustomSequence'
                    if not isinstance(self.sequence, mod.CustomSequence):
                        self.sequence = mod.CustomSequence()
                else:
                    # standard built-in sequence
                    self.sequence = new_type()

        elif (quant.name == 'Custom Python file' and
              self.getValue('Sequence') == 'Custom'):
            # for custom python files
            path = self.getValue('Custom Python file')
            (path, modName) = os.path.split(path)
            modName = modName.split('.py')[0]  # strip suffix
            sys.path.append(path)
            mod = importlib.import_module(modName)
            # the custom sequence class has to be named 'CustomSequence'
            if not isinstance(self.sequence, mod.CustomSequence):
                self.sequence = mod.CustomSequence()
        return value

    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation."""
        # ignore if no sequence
        if self.sequence is None:
            return quant.getValue()

        if quant.isVector():
            # traces, check if waveform needs to be re-calculated
            if self.isConfigUpdated():
                # update sequence object with current driver configuation
                config = self.instrCfg.getValuesDict()
                self.sequence.set_parameters(config)
                self.sequence_to_waveforms.set_parameters(config)


                # normal operation, calcluate waveforms
                self.waveforms = self.sequence_to_waveforms.get_waveforms(
                    self.sequence.get_sequence(config))
            # get correct data from waveforms stored in memory
            value = self.getWaveformFromMemory(quant)
        else:
            # for all other cases, do nothing
            value = quant.getValue()
        return value

    def getWaveformFromMemory(self, quant):
        """Return data from already calculated waveforms."""
        # check which data to return
        if quant.name[-1] in ('1', '2', '3', '4', '5', '6', '7', '8', '9'):
            # get name and number of qubit waveform asked for
            name = quant.name[:-1]
            n = int(quant.name[-1]) - 1
            # get correct vector
            if name == 'Trace - I':
                    value = self.waveforms['xy'][n].real
            elif name == 'Trace - Q':
                    value = self.waveforms['xy'][n].imag

        elif quant.name == 'Trace - Readout trig':
            value = self.waveforms['readout_trig']
        elif quant.name == 'Trace - Readout I':
            value = self.waveforms['readout_iq'].real
        elif quant.name == 'Trace - Readout Q':
            value = self.waveforms['readout_iq'].imag

        # return data as dict with sampling information
        dt = 1 / self.sequence_to_waveforms.sample_rate
        value = quant.getTraceDict(value, dt=dt)
        return value


if __name__ == '__main__':
    pass
