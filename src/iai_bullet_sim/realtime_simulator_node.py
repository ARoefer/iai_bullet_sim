#!/usr/bin/env python
import rospy
from iai_bullet_sim.basic_simulator_node import BasicSimulatorNode


def gen_fixed_init(t, *args):
    def fixed_init(self, *args):
        t.__init__(self, *args)
        self.timer = None
        self.paused = False
    return fixed_init


def gen_pause(t):
    def pause(self):
        t.pause(self)
        self.paused = True
    return pause


def gen_tick(t):
    def tick(self, timer_event):
        if not self.paused:
            t.tick(self, timer_event)
        elif self.tf_publisher != None:
            with self.lock:
                self.tf_publisher.post_physics_update(self.sim, 0)
    return tick


def gen_run(t):
    def run(self):
        t.run(self)
        if self.timer is None:
            self.timer = rospy.Timer(rospy.Duration(1.0 / self.sim.tick_rate), self.tick)
        self.paused = False
    return run


def gen_stop(t):
    def stop(self):
        self.pause()
        t.stop(self)
    return stop


def gen_is_running(t):
    def is_running(self):
        return not self.paused
    return is_running


def FixedTickSimulator(super_type, *args):
    """Generates and instantiates a subclass of the super class, which ticks at a fixed rate.

    :param super_type: Type to inherit from. Must be a subtype of BasicSimulatorNode.
    :type  super_type: type
    :param args: Arguments to pass to the constructor.
    :rtype: FixedTickSimulator
    """
    if not issubclass(super_type, BasicSimulatorNode):
        raise Exception('Type needs to be a subtype of BasicSimulatorNode. Given type: {}'.format(str(super_type)))

    t = type('FixedTickSimulator',
             (super_type, ),
             {'__init__': gen_fixed_init(super_type),
              'pause'   : gen_pause(super_type),
              'tick'    : gen_tick(super_type),
              'run'     : gen_run(super_type),
              'stop'    : gen_stop(super_type),
              'is_running': gen_is_running(super_type)})
    return t(*args)
