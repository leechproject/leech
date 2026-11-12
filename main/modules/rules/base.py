from collections import namedtuple

State = namedtuple("State", "active occupied windows fullscreen clients monitors overview layout",
                   defaults=((), False, ""))
Monitor = namedtuple("Monitor", "name x y width height scale focused active windows fullscreen occupied",
                     defaults=(None,))


class NullRules:
    def __init__(self):
        self.state = State(active=1, occupied=set(), windows=0, fullscreen=False, clients=())

    def subscribe(self, callback):
        callback(self.state)

    def start(self):
        pass

    def goto(self, workspace_id):
        pass

    def apply_layer_rules(self):
        pass

    def output_scale(self):
        return None

    def monitors(self):
        return ()
