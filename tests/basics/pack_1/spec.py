from snakes.nets import *

net = PetriNet('Net')
s1 = Place('s1', [dot], tBlackToken)
s1.is_OneSafe = True
s2 = Place('s2', [], tBlackToken)
s2.is_OneSafe = False

net.add_place(s1)
net.add_place(s2)

transition = Transition('t', Expression('True'))
net.add_transition(transition)

net.add_input('s1', 't', Variable('dot'))
net.add_output('s2', 't', Variable('dot'))
