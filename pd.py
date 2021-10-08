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
        ('swing', 'Swing'),
        ('unknown', 'Unknown'),
    )
    annotation_rows = (
        ('packet', 'Packet', (0, 1, 2)),
        ('bits', 'Bits', (3,)),
        ('data', 'Data', (5,)),
        ('debug', 'Debug', (4,)),
        ('meaning', 'Meaning', (6, 7, 8, 9, 10, 11)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        #self.timings = {0:[], 1: []}
        self.samplerate = None
        self.edges, self.bits, self.ss_es_bits = [], [], []
        self.timings = {
            0: [],
            1: [],
            'hello': [],
            'bye': []
        }
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
            #self.print("SampleRate: %s" % self.samplerate)

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
        self.debug("RESET THE STATE")

    def polarity(self, ir):
        return True if self.options['polarity'] == 'active-low' and ir == 0 else False

    def debug(self, message):
        if True:
            print("s#%s (p#%s, e#%s): %s" % (self.samplenum, self.packet_count, len(self.edges), message))

    def approximately(self, milliseconds, margin = 0.1):
        seconds = float(milliseconds) / float(1000)
        lower_bound = (seconds * (1 - margin)) * self.samplerate
        upper_bound = (seconds * (1 + margin)) * self.samplerate
        return range(int(lower_bound), int(upper_bound + 1))

    def decode(self):
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        while True:

            # self.ir == 0 | 1 => state?
            # self.samplenum == index of the current edge?
            (self.ir, ) = self.wait({0: self.next_edge})

            self.next_edge = 'l' if self.ir else 'h'

            self.edges.append(self.samplenum)
            self.bits.append([self.samplenum, self.ir])

            if len(self.edges) >= 2:
                #self.debug("sample: #%s, @time: %s, duration: %s, state: %s, samples-since: %s" % (self.samplenum, self.samplenum / self.samplerate, (self.edges[-1] - self.edges[-2]) / self.samplerate, self.ir, (self.edges[-1] - self.edges[-2])))

                self.put(
                    self.samplenum, self.samplenum,
                    0,
                    [
                        4,
                        [
#                            "#%s (%s later)  - %f2 (%s ms later)" % (
                            "%s" % (
                                ((self.samplenum - self.edges[-2]) / self.samplerate) * 1000
                            ),
                            "d"
                        ]
                    ]
                )
            else:
                self.debug("sample: #%s, @time: %s, duration: X, state: %s, samples-since: X" % (self.samplenum, self.samplenum / self.samplerate, self.ir))
#               self.put(
#                   self.samplenum, self.samplenum,
#                   0,
#                   [
#                       4,
#                       [
#                           "#%s (X later)  - %f2 (X ms later)" % (
#                               self.samplenum,
#                               self.samplenum / self.samplerate
#                           ),
#                           "d"
#                       ]
#                   ]
#               )

            """
            - hello
            - bits * N
            - bye
            """


            if len(self.edges) == 1 and self.ir == 1:
                self.debug("WHAT")
                self.next_edge = 'l' if self.ir else 'h'
                self.reset_decoder_state()

            # this should be HEADER
            if len(self.bits) == 3:
                #self.debug("Check for a HEADER")
                #self.debug("bits: %s" % self.debug_bits(self.bits))

                header_polarities = [ b[1] for b in self.bits ]

                # should match polarity
                if header_polarities != [0,1,0]:
                    self.debug("Header doesnt match polarity: %s vs %s" % ([0,1,0], ))
                    self.reset_decoder_state()
                    self.next_edge = 'l' if self.ir else 'h'
                    continue
                else:
                    self.debug("Header polarities match: %s" % header_polarities)


                # should match timing
                long_low_duration = self.bits[-2][0] - self.bits[-3][0]
                if long_low_duration not in self.approximately(4):
                    self.debug("Header long low not in range: %s vs %s" % (long_low_duration, self.approximately(4)))
                    self.reset_decoder_state()
                    continue

                # should match timing
                short_high_duration = self.bits[-1][0] - self.bits[-2][0]
                if short_high_duration not in self.approximately(2):
                    self.debug("Header short high not in range: %s vs %s" % (short_high_duration, self.approximately(4)))
                    self.reset_decoder_state()
                    continue

                self.timings['hello'].append((long_low_duration / self.samplerate, short_high_duration / self.samplerate))

                #self.debug("GOT A HEADER!")
                self.packet_count = self.packet_count + 1
                self.put(self.edges[-3], self.samplenum, 0, [0, ["Hello %s" % self.packet_count, "H"]])

            if len(self.bits) > 3:
                if len(self.packet_data) == 45:
                    if len(self.bits) % 2 == 0:
                        if self.ir != 1:
                            self.debug("stop bit should be high")
                            #self.reset_decoder_state()
                            continue

                        stop_bit_duration = self.edges[-1] - self.edges[-2]
                        if stop_bit_duration in self.approximately(0.141, 0.5):
                            #self.debug("stop bit lasted ~0.18ms (%s)" % str(stop_bit_duration / self.samplerate))
                            self.put(self.edges[2], self.edges[-2], 0, [2, ["Payload: %s bits long" % len(self.packet_data), "P"]])
                            self.put(self.edges[2], self.edges[-2], 0, [5, ["Payload: %s" % ",".join([ str(b) for b in self.packet_data]), "P"]])
                            self.put(self.edges[-2], self.edges[-1], 0, [1, ["Bye", "B"]])

                            self.debug("Expected stop bit and got one")
                            self.timings['bye'].append((stop_bit_duration / self.samplerate, 0))
                            #self.debug(self.timings)

                            print("0: low: %s, high %s (%s)" % (
                                float(sum([x[0] for x in self.timings[0]])) / float(len(self.timings[0])),
                                float(sum([x[1] for x in self.timings[0]])) / float(len(self.timings[0])),
                                len(self.timings[0])
                            ))

                            print("1: low: %s, high %s (%s)" % (
                                float(sum([x[0] for x in self.timings[1]])) / float(len(self.timings[1])),
                                float(sum([x[1] for x in self.timings[1]])) / float(len(self.timings[1])),
                                len(self.timings[1])
                            ))

                            print("hello: low: %s, high %s (%s)" % (
                                float(sum([x[0] for x in self.timings['hello']])) / float(len(self.timings['hello'])),
                                float(sum([x[1] for x in self.timings['hello']])) / float(len(self.timings['hello'])),
                                len(self.timings['hello'])
                            ))

                            print("bye: high: %s (%s)" % (
                                float(sum([x[0] for x in self.timings['bye']])) / float(len(self.timings['bye'])),
                                len(self.timings['bye'])
                            ))

                            self.reset_decoder_state()
                        else:
                            self.debug("stop bit didn't last ~0.18ms (%s)" % str(stop_bit_duration / self.samplerate))

                    # check for stop bit


                if len(self.bits) % 2 == 1:
                    #self.debug("END OF A BIT - Process it")
                    if self.ir != 0:
                        #self.debug("new edges should be low (closing a high)")
                        self.reset_decoder_state()
                        continue

                    bit_low_edge_duration = self.edges[-2] - self.edges[-3]
                    if bit_low_edge_duration not in self.approximately(0.495):
                        self.debug("low edge of bit should always be ~0.5ms (%s) (actual: %s vs expected: %s)" % (bit_low_edge_duration / self.samplerate, bit_low_edge_duration, self.approximately(0.495)))
                        self.reset_decoder_state()
                        continue

                    bit_high_edge_duration = self.edges[-1] - self.edges[-2]
                    if bit_high_edge_duration not in self.approximately(0.495) and bit_high_edge_duration not in self.approximately(0.975):
                        self.reset_decoder_state()
                        self.debug("high edge bit is not 0.5ms or 1ms (%s) (actual: %s vs expected: %s-%s)" % (bit_high_edge_duration / self.samplerate, bit_high_edge_duration, self.approximately(0.495), self.approximately(0.975) ))
                        continue

                    bit_value = None
                    if bit_high_edge_duration in self.approximately(0.495):
                        #self.debug("high edge bit is ~0.5ms")
                        bit_value = 1
                        self.timings[1].append((bit_low_edge_duration / self.samplerate, bit_high_edge_duration / self.samplerate))
                    elif bit_high_edge_duration in self.approximately(0.974):
                        #self.debug("high edge bit is ~1ms")
                        self.timings[0].append((bit_low_edge_duration / self.samplerate, bit_high_edge_duration / self.samplerate))
                        bit_value = 0
                    else:
                        self.debug("high edge bit is not 0.5ms or 1ms (%s)" % bit_high_edge_duration )
                        self.reset_decoder_state()
                        continue

                    self.packet_data.append(bit_value)

                    self.put(self.edges[-3], self.edges[-1], 0, [3, ["Bit %s: %s" % (len(self.packet_data) - 1 , bit_value), "%s" % bit_value]])

                    # UNKNOWNS AT THE START
                    if len(self.packet_data) == 8:
                        self.put(self.edges[-17], self.edges[-1], 0, [11, ["Unknown: %s" % (self.packet_data[0:8]), "U"]])


                    # FAN - bits #8 and #9
                    if len(self.packet_data) == 10:
                        fan_bits = self.packet_data[8:10]
                        fan_int = int("".join([ str(b) for b in fan_bits])[::-1], 2)
                        fan_str = {
                            "0":  "HIGH",
                            "1":  "MED",
                            "2":  "LOW",
                            "3":  "AUTO"
                        }
                        self.put(self.edges[-5], self.edges[-1], 0, [7, ["Fan: %s (%s)" % (fan_str[str(fan_int)], str(fan_int)), "F: %s" % str(fan_int)]])

                    # UNKNOWNS IN THE MIDDLE
                    if len(self.packet_data) == 14:
                        self.put(self.edges[-9], self.edges[-1], 0, [11, ["Unknown: %s" % (self.packet_data[10:14]), "U"]])


                    # MODE - bit #14
                    if len(self.packet_data) == 15:
                        mode_int = self.packet_data[14]
                        if mode_int == 1:
                            mode_str = "COOL"
                        elif mode_int == 0:
                            mode_str = "FAN"
                        else:
                            self.debug("WHAT? INVALID MODE")

                        self.put(self.edges[-3], self.edges[-1], 0, [9, ["Mode: %s (%s)" % (mode_str, mode_int), "M: %s" % mode_int]])

                    # POWER - bit #15
                    if len(self.packet_data) == 16:
                        power_int = self.packet_data[15]
                        if power_int == 1:
                            power_str = "OFF"
                        elif power_int == 0:
                            power_str = "ON"
                        else:
                            self.debug("WHAT? INVALID POWER")

                        self.put(self.edges[-3], self.edges[-1], 0, [8, ["Power: %s (%s)" % (power_str, power_int), "P: %s" % power_int]])


                    # TEMP - bits #16 to #19
                    if len(self.packet_data) == 20:
                        temp_bits = self.packet_data[16:20]
                        temp = int("".join([ str(b) for b in temp_bits])[::-1], 2) + 15
                        self.put(self.edges[-9], self.edges[-1], 0, [6, ["Temperature: %s" % str(temp), "T: %s" % str(temp), "T"]])

                    # SWING - bits #20 to #23
                    if len(self.packet_data) == 24:
                        swing_bits = self.packet_data[20:24]
                        #self.debug("SWING BITS: %s" % swing_bits)
                        swing_int = int("".join([ str(b) for b in swing_bits])[::-1], 2)
                        self.put(self.edges[-9], self.edges[-1], 0, [10, ["Swing: %s" % str(swing_int), "S: %s" % str(swing_int), "S"]])

                    # UNKNOWNS IN THE END
                    if len(self.packet_data) == 45:
                        self.put(self.edges[-43], self.edges[-1], 0, [11, ["Unknown: %s" % (self.packet_data[24:46]), "U"]])
