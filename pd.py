##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2014 Uwe Hermann <uwe@hermann-uwe.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from .lists import *

class SamplerateError(Exception):
    pass

class Decoder(srd.Decoder):
    api_version = 3
    id = 'ir_unknown'
    name = 'IR Unknown'
    longname = 'IR Unknown A/C Remote'
    desc = 'Unknown air-conditioner remote decoder'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['IR']
    channels = (
        {'id': 'ir', 'name': 'IR', 'desc': 'IR data line'},
    )
    options = (
        {'id': 'polarity', 'desc': 'Polarity', 'default': 'active-low',
            'values': ('active-low', 'active-high')},
        {'id': 'protocol', 'desc': 'Protocol type', 'default': 'standard',
            'values': ('standard', 'extended')},
    )
    annotations = (
        ('header', 'Header'),
        ('bye', 'Bye'),
        ('payload', 'Payload'),
        ('bit', 'Bit'),
        ('debug', 'Debug'),
        ('data', 'Data'),
        ('temperature', 'Temperature'),
        ('fan-mode', 'Fan Mode'),
        ('power', 'Power'),
        ('mode', 'Mode'),
    )
    annotation_rows = (
        ('packet', 'Packet', (0, 1, 2)),
        ('bits', 'Bits', (3,)),
        ('data', 'Data', (5,)),
        ('debug', 'Debug', (4,)),
        ('meaning', 'Meaning', (6, 7, 8, 9)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.edges, self.bits, self.ss_es_bits = [], [], []
        self.state = 'IDLE'
        self.packet_data = []
        self.packet_count = 0

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.next_edge = 'l' if self.options['polarity'] == 'active-low' else 'h'

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value
            # One bit: 1.78ms (one half low, one half high).
            self.halfbit = int((self.samplerate * 0.00178) / 2.0)
            self.header_length = int(float(self.samplerate) * 0.004)
            self.bye_length = int(float(self.samplerate) * 0.00018)
            self.margin_length = int(0.00018 * float(self.samplerate))

    def debug_bits(self, bits):
        return [ (b[0], b[0] / self.samplerate, b[1]) for b in bits]

    def edge_type(self):
        distance = self.samplenum - self.edges[-2]
        s, l, margin = self.halfbit, self.halfbit * 2, int(self.halfbit / 2)

        if distance in range(self.header_length - self.margin_length, self.header_length + self.margin_length + 1):
            return 'h'
        elif distance in range(self.bye_length - self.margin_length, self.bye_length + self.margin_length + 1):
            return 'b'
        else:
            return 'u' # Error, invalid edge distance.

    def reset_decoder_state(self):
        self.edges, self.bits, self.ss_es_bits, self.packet_data = [], [], [], []
        self.state = 'IDLE'
        self.start_temp = 0
        self.end_temp = 0
        self.start_fan = 0
        self.end_fan = 0

        self.next_edge = 'l' if self.options['polarity'] == 'active-low' else 'h'

    def polarity(self, ir):
        return True if self.options['polarity'] == 'active-low' and ir == 0 else False

    def debug(self, message):
        if True:
            print(message)

    def approximately(self, milliseconds):
        seconds = float(milliseconds) / float(1000)
        lower_bound = (seconds * 0.9) * self.samplerate
        upper_bound = (seconds * 1.1) * self.samplerate
        return range(int(lower_bound), int(upper_bound + 1))

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')
        while True:

            # self.ir == 0 | 1 => state?
            # self.samplenum == index of the current edge?
            (self.ir, ) = self.wait({0: self.next_edge})

            self.debug("GOT samplenum: %s - %s - %s" % (self.samplenum, self.polarity(self.ir), self.samplenum / self.samplerate))

            self.edges.append(self.samplenum)
            self.bits.append([self.samplenum, self.polarity(self.ir)])

            """
            - hello
            - bits * N
            - bye
            """

            if len(self.edges) == 1:
                if self.polarity(self.ir):
                    self.state = 'NOT IDLE'
                    self.debug('first is active')
                else:
                    self.debug("WHAT? - first edge was False")

                self.next_edge = 'l' if self.ir else 'h'
                continue

            #if len(self.edges) > 1 and self.next_edge == 'h':
            if len(self.edges) > 1:
                self.put(self.samplenum, self.samplenum, 0, [4, ["s: %s - e: %s - %%: %s - b: %s" % (self.samplenum, len(self.edges) - 2, (len(self.edges) - 2) % 2, len(self.packet_data)), "d"]])

                edge_type = self.edge_type()
                if len(self.edges) == 2:
                    self.debug("edge_count: %s" % len(self.edges))
                    if edge_type == 'h':
                        self.debug("hello as expected - %s" % self.packet_count)
                        self.put(self.edges[-2], self.samplenum, 0, [0, ["Hello", "H"]])
                    else:
                        self.debug("expected hello, got %s" % edge_type)
                        self.reset_decoder_state()
                elif len(self.edges) >= 3:
                    if edge_type == 'e':
                        self.debug("ERROR")
                        self.reset_decoder_state()
                    elif edge_type == 'b':
                        self.debug("bye as expected")
                        self.put(self.edges[-2], self.samplenum, 0, [1, ["Bye", "B"]])
                        self.put(self.edges[0], self.samplenum, 0, [2, ["Packet", "P"]])
                        self.put(self.edges[0], self.samplenum, 0, [5, ["Data: %s" % ("".join([str(x) for x in self.packet_data])), "D"]])
                        print('packet data')
                        print(self.packet_data)

                        temp_bits = self.packet_data[16:20]
                        print("temp bits")
                        print(self.packet_data)
                        temp = int("".join([ str(b) for b in temp_bits])[::-1], 2) + 15
                        self.put(self.start_temp, self.end_temp, 0, [6, ["Temperature: %s" % str(temp), "T: %s" % str(temp), "T"]])

                        fan = int("".join([ str(b) for b in self.packet_data[8:10]])[::-1], 2)
                        self.put(self.start_fan, self.end_fan, 0, [7, ["Fan: %s" % str(fan), "F: %s" % str(fan), "F"]])

                        power = int("".join([ str(b) for b in self.packet_data[15:16]])[::-1], 2)
                        self.put(self.start_power, self.end_power, 0, [8, ["Power: %s" % str(power), "P: %s" % str(power), "P"]])

                        mode = int("".join([ str(b) for b in self.packet_data[16:17]])[::-1], 2)
                        mode_str = "Fan" if mode == 1 else "Cool"
                        self.put(self.start_mode, self.end_mode, 0, [9, ["Mode: %s (%s)" % (str(mode_str), mode), "M: %s (%s)" % (str(mode_str), mode), "M"]])

                        self.debug("temp: %s" % temp)

                        self.reset_decoder_state()
                        self.packet_count = self.packet_count + 1
                    # expect bits
                    elif (len(self.edges) - 2) % 2 == 1 and len(self.edges) >= 3:
                        self.debug("looking at bits")
                        self.debug(self.debug_bits(self.bits))
                        #print(self.edges)
                        #if self.bits[-1][1] == False:
                        #    print("last edge is False")

                        distance = self.samplenum - self.edges[-3]
                        self.debug("%s, %s" % (self.edges[-1], self.edges[-2]))
                        high_distance = (self.edges[-2] - self.edges[-3])
                        self.debug("high distance: %s" % high_distance)

                        if low_distance in self.approximately(0.48):
                            self.put(self.edges[-3], self.samplenum, 0, [3, ["Bit: 1", "1"]])
                            self.packet_data.append(1)
                        elif low_distance in self.approximately(0.96):
                            self.put(self.edges[-3], self.samplenum, 0, [3, ["Bit: 0", "0"]])
                            self.packet_data.append(0)
                        else:
                            self.debug("out of range: %s" % low_distance)

                        if len(self.packet_data) == 8:
                            self.start_fan = self.samplenum

                        if len(self.packet_data) == 10:
                            self.end_fan = self.samplenum

                        if len(self.packet_data) == 17:
                            self.start_temp = self.samplenum

                        if len(self.packet_data) == 21:
                            self.end_temp = self.samplenum

                        if len(self.packet_data) == 15:
                            self.start_power = self.edges[-3]
                            self.end_power = self.samplenum

                        if len(self.packet_data) == 16:
                            self.start_mode = self.edges[-3]
                            self.end_mode = self.samplenum

                        self.debug(self.debug_bits(self.bits[-3:]))
                    else:
                        self.debug("got unexpected edge type: %s" % edge_type)
                else:
                    self.debug("why?")

            """
            if self.state == 'IDLE':
                bit = 1
                self.edges.append(self.samplenum)
                self.bits.append([self.samplenum, bit])
                self.next_edge = 'l' if self.ir else 'h'
                self.state = 'NOT IDLE'
                continue

            edge = self.edge_type()
            #print(self.samplenum, self.ir, edge.upper())
            if edge == 'e':
                #print(len(self.edges))
                self.reset_decoder_state() # Reset state machine upon errors.
                continue

            self.edges.append(self.samplenum)
            if bit is not None:
                self.bits.append([self.samplenum, bit])
            """
            self.next_edge = 'l' if self.ir else 'h'
            self.debug("")


